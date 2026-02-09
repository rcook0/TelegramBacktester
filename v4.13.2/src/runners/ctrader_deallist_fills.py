from __future__ import annotations

"""cTrader Open API DealList capture (fills).

Purpose
-------
Capture the authoritative execution layer from cTrader (deals) around a signal's
capture window and persist into `shadow_snapshots`.

Why DealList?
------------
ExecutionEvent streams can be lossy across reconnects. DealList is the broker-side
history of executions (filled / partial / rejected), useful for reconciliation.

Notes
-----
- Deal volumes are "in cents" (0.01 of a unit) per Open API model messages.
- DealListReq/Res supports pagination via `hasMore`.
"""

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from capture.window import parse_iso
from storage.sqlite_store_symbols import SymbolStore
from normalize.ctrader_deals import normalize_deal_payload


try:
    from ctrader_open_api import Client, TcpProtocol, EndPoints, Protobuf
    from ctrader_open_api.messages.OpenApiMessages_pb2 import (
        ProtoOAApplicationAuthReq,
        ProtoOAAccountAuthReq,
        ProtoOASymbolsListReq,
        ProtoOADealListReq,
    )

    CTRADER_OPENAPI_AVAILABLE = True
except Exception:
    CTRADER_OPENAPI_AVAILABLE = False


def _ms(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _iso_from_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat()


@dataclass
class DealListConfig:
    env: str
    client_id: str
    client_secret: str
    access_token: str
    ctid_trader_account_id: int
    from_ms: int
    to_ms: int
    max_rows: int = 5000


def parse_args():
    p = argparse.ArgumentParser(description="cTrader DealList fills capture")
    p.add_argument("--db", required=True)
    p.add_argument("--signal-idem-key", required=True)

    # Window source: either explicit [from, to] OR use stored capture_window snapshot.
    p.add_argument("--from", dest="from_ts", default="", help="ISO start (UTC)")
    p.add_argument("--to", dest="to_ts", default="", help="ISO end (UTC)")
    p.add_argument(
        "--use-capture-window",
        action="store_true",
        help="Use capture_window snapshot stored in DB for this signal-idem-key",
    )
    p.add_argument("--max-rows", type=int, default=5000)

    # Open API
    p.add_argument("--env", choices=["LIVE", "DEMO"], default="LIVE")
    p.add_argument("--client-id", required=True)
    p.add_argument("--client-secret", required=True)
    p.add_argument("--access-token", required=True)
    p.add_argument("--account-id", type=int, required=True, help="ctidTraderAccountId")

    return p.parse_args()


def _load_window_from_db(store: SymbolStore, signal_id: int) -> Optional[Tuple[int, int]]:
    cur = store.conn.cursor()
    cur.execute(
        "SELECT ts, payload FROM shadow_snapshots WHERE signal_id=? AND kind='capture_window' ORDER BY id DESC LIMIT 1",
        (signal_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    payload = json.loads(row[1])
    try:
        start = parse_iso(payload["start"])
        end = parse_iso(payload["end"])
        return _ms(start), _ms(end)
    except Exception:
        return None


def main():
    if not CTRADER_OPENAPI_AVAILABLE:
        raise SystemExit(
            "ctrader-open-api is not installed. Install optional deps: pip install .[ctrader]"
        )

    args = parse_args()
    store = SymbolStore(args.db)

    # Resolve signal id
    cur = store.conn.cursor()
    cur.execute("SELECT id, ts FROM signals WHERE idem_key=?", (args.signal_idem_key,))
    row = cur.fetchone()
    if not row:
        raise SystemExit("No signal found for idem_key. Ingest signals first so it exists in DB.")
    signal_id = int(row[0])
    signal_ts_db = row[1]

    # Determine capture window
    if args.use_capture_window:
        win = _load_window_from_db(store, signal_id)
        if not win:
            raise SystemExit("No capture_window found. Run ctrader_shadow_capture.py first (it writes it).")
        from_ms, to_ms = win
    else:
        if not (args.from_ts and args.to_ts):
            # Default: small window around signal timestamp from DB
            sig = parse_iso(signal_ts_db)
            from_ms = _ms(sig) - 2_000
            to_ms = _ms(sig) + 30_000
        else:
            from_ms = _ms(parse_iso(args.from_ts))
            to_ms = _ms(parse_iso(args.to_ts))

    cfg = DealListConfig(
        env=args.env,
        client_id=args.client_id,
        client_secret=args.client_secret,
        access_token=args.access_token,
        ctid_trader_account_id=int(args.account_id),
        from_ms=int(from_ms),
        to_ms=int(to_ms),
        max_rows=int(args.max_rows),
    )

    # Persist meta
    store.add_shadow_snapshot(
        signal_id,
        "deal_list_meta",
        {
            "from_ms": cfg.from_ms,
            "to_ms": cfg.to_ms,
            "from": _iso_from_ms(cfg.from_ms),
            "to": _iso_from_ms(cfg.to_ms),
            "max_rows": cfg.max_rows,
            "source": "ctrader-openapi",
        },
        ts=_iso_from_ms(cfg.from_ms),
    )
    store.conn.commit()

    # Connect
    env = cfg.env.upper()
    host = EndPoints.PROTOBUF_LIVE_HOST if env == "LIVE" else EndPoints.PROTOBUF_DEMO_HOST
    client = Client(host, EndPoints.PROTOBUF_PORT, TcpProtocol)

    symbols_by_id: Dict[int, Dict[str, Any]] = {}
    paging_from_ms = int(cfg.from_ms)
    paging_to_ms = int(cfg.to_ms)
    total_deals = 0
    pages = 0

    from twisted.internet import reactor

    def send_app_auth():
        req = ProtoOAApplicationAuthReq()
        req.clientId = cfg.client_id
        req.clientSecret = cfg.client_secret
        client.send(req)

    def send_account_auth():
        req = ProtoOAAccountAuthReq()
        req.ctidTraderAccountId = int(cfg.ctid_trader_account_id)
        req.accessToken = cfg.access_token
        client.send(req)

    def request_symbols():
        req = ProtoOASymbolsListReq()
        req.ctidTraderAccountId = int(cfg.ctid_trader_account_id)
        client.send(req)

    def request_deals(from_ms_: int):
        req = ProtoOADealListReq()
        req.ctidTraderAccountId = int(cfg.ctid_trader_account_id)
        req.fromTimestamp = int(from_ms_)
        req.toTimestamp = int(paging_to_ms)
        req.maxRows = int(cfg.max_rows)
        client.send(req)

    def on_error(failure):
        print("OpenAPI error:", failure)
        try:
            reactor.stop()
        except Exception:
            pass

    def _persist_deal(d: Any):
        nonlocal total_deals
        deal_id = int(getattr(d, "dealId", 0))
        symbol_id = int(getattr(d, "symbolId", 0))
        exec_ms = int(getattr(d, "executionTimestamp", 0))
        create_ms = int(getattr(d, "createTimestamp", 0))
        status = getattr(getattr(d, "dealStatus", None), "name", None) or str(getattr(d, "dealStatus", ""))
        side = getattr(getattr(d, "tradeSide", None), "name", None) or str(getattr(d, "tradeSide", ""))
        sym = symbols_by_id.get(symbol_id, {})
        payload = {
            "deal_id": deal_id,
            "order_id": int(getattr(d, "orderId", 0)),
            "position_id": int(getattr(d, "positionId", 0)),
            "symbol_id": symbol_id,
            "symbol": sym.get("name"),
            "digits": sym.get("digits"),
            "pip_position": sym.get("pip_position"),
            "volume_cents": int(getattr(d, "volume", 0)),
            "filled_volume_cents": int(getattr(d, "filledVolume", 0)),
            "volume_units": float(getattr(d, "volume", 0)) / 100.0,
            "filled_volume_units": float(getattr(d, "filledVolume", 0)) / 100.0,
            "create_ts": _iso_from_ms(create_ms) if create_ms else None,
            "execution_ts": _iso_from_ms(exec_ms) if exec_ms else None,
            "execution_price": float(getattr(d, "executionPrice", 0.0)) if getattr(d, "executionPrice", 0.0) else None,
            "trade_side": side,
            "deal_status": status,
            "commission": int(getattr(d, "commission", 0)) if getattr(d, "commission", 0) else 0,
            "money_digits": int(getattr(d, "moneyDigits", 0)) if getattr(d, "moneyDigits", 0) else None,
            "label": getattr(d, "label", "") or "",
            "comment": getattr(d, "comment", "") or "",
            "source": "ctrader-openapi",
        }
        if getattr(d, "closePositionDetail", None):
            cpd = d.closePositionDetail
            payload["close_position_detail"] = {
                "entry_price": float(getattr(cpd, "entryPrice", 0.0)) if getattr(cpd, "entryPrice", 0.0) else None,
                "gross_profit": int(getattr(cpd, "grossProfit", 0)) if getattr(cpd, "grossProfit", 0) else 0,
                "swap": int(getattr(cpd, "swap", 0)) if getattr(cpd, "swap", 0) else 0,
                "commission": int(getattr(cpd, "commission", 0)) if getattr(cpd, "commission", 0) else 0,
                "balance": int(getattr(cpd, "balance", 0)) if getattr(cpd, "balance", 0) else 0,
                "closed_volume_cents": int(getattr(cpd, "closedVolume", 0)) if getattr(cpd, "closedVolume", 0) else 0,
                "quote_to_deposit_conversion_rate": float(getattr(cpd, "quoteToDepositConversionRate", 0.0))
                if getattr(cpd, "quoteToDepositConversionRate", 0.0)
                else None,
                "pnl_conversion_fee": int(getattr(cpd, "pnlConversionFee", 0)) if getattr(cpd, "pnlConversionFee", 0) else 0,
                "money_digits": int(getattr(cpd, "moneyDigits", 0)) if getattr(cpd, "moneyDigits", 0) else None,
            }

        # Persist raw deal (authoritative)
        store.add_shadow_snapshot(signal_id, "deal", payload, ts=payload.get("execution_ts") or _iso_from_ms(cfg.from_ms))

        # Persist normalized view for later attribution & reconciliation
        meta = store.get_symbol_meta("ctrader-openapi", str(cfg.ctid_trader_account_id), symbol_id) or sym or None
        deal_norm = normalize_deal_payload(payload, symbol_meta=meta if isinstance(meta, dict) else None)
        store.add_shadow_snapshot(signal_id, "deal_norm", deal_norm, ts=payload.get("execution_ts") or _iso_from_ms(cfg.from_ms))
        total_deals += 1

    def on_message(_client, message):
        nonlocal paging_from_ms, pages
        try:
            m = Protobuf.extract(message)
            name = m.DESCRIPTOR.name

            if name == "ProtoOAApplicationAuthRes":
                send_account_auth()
                return

            if name == "ProtoOAAccountAuthRes":
                request_symbols()
                return

            if name == "ProtoOASymbolsListRes":
                symbols_by_id.clear()
                for ls in getattr(m, "symbol", []):
                    sym_id = int(getattr(ls, "symbolId", 0))
                    sym_name = getattr(ls, "symbolName", None) or getattr(ls, "name", None)
                    if not sym_id or not sym_name:
                        continue
                    digits = int(getattr(ls, "digits", 5)) if getattr(ls, "digits", None) is not None else None
                    pip_pos = int(getattr(ls, "pipPosition", 4)) if getattr(ls, "pipPosition", None) is not None else None
                    pip_size = None
                    try:
                        if pip_pos is not None:
                            pip_size = 10.0 ** (-int(pip_pos))
                    except Exception:
                        pip_size = None

                    meta = {
                        "symbol_name": sym_name,
                        "digits": digits,
                        "pip_position": pip_pos,
                        "pip_size": pip_size,
                        "lot_size_cents": int(getattr(ls, "lotSize", 0)) if getattr(ls, "lotSize", None) is not None else None,
                        "min_volume_cents": int(getattr(ls, "minVolume", 0)) if getattr(ls, "minVolume", None) is not None else None,
                        "max_volume_cents": int(getattr(ls, "maxVolume", 0)) if getattr(ls, "maxVolume", None) is not None else None,
                        "step_volume_cents": int(getattr(ls, "stepVolume", 0)) if getattr(ls, "stepVolume", None) is not None else None,
                        "measurement_units": getattr(ls, "measurementUnits", None) if getattr(ls, "measurementUnits", None) is not None else None,
                    }
                    symbols_by_id[sym_id] = dict(name=sym_name, **meta)
                    # cache meta in DB (broker=ctrader-openapi, account_id scope = account id)
                    store.upsert_symbol_meta("ctrader-openapi", str(cfg.ctid_trader_account_id), sym_id, sym_name,
                                            digits=digits, pip_position=pip_pos, pip_size=pip_size,
                                            lot_size_cents=meta["lot_size_cents"], min_volume_cents=meta["min_volume_cents"],
                                            max_volume_cents=meta["max_volume_cents"], step_volume_cents=meta["step_volume_cents"],
                                            measurement_units=meta["measurement_units"])
                    # also keep symbol_resolution for convenience (symbol_input == symbol_name)
                    store.upsert_symbol("ctrader-openapi", str(cfg.ctid_trader_account_id), sym_name, sym_name, sym_id,
                                       digits=digits, pip_position=pip_pos, pip_size=pip_size)

                request_deals(paging_from_ms)
                return

            if name == "ProtoOADealListRes":
                pages += 1
                deals = list(getattr(m, "deal", []))

                # Persist deals
                max_exec_ms = paging_from_ms
                for d in deals:
                    _persist_deal(d)
                    max_exec_ms = max(max_exec_ms, int(getattr(d, "executionTimestamp", 0) or 0))
                store.conn.commit()

                has_more = bool(getattr(m, "hasMore", False))
                print(f"DealList page {pages}: {len(deals)} deals (hasMore={has_more})")

                # Paging strategy: move the window forward.
                if has_more and deals and max_exec_ms < paging_to_ms:
                    paging_from_ms = max_exec_ms + 1
                    request_deals(paging_from_ms)
                    return

                # Done
                store.add_shadow_snapshot(
                    signal_id,
                    "deal_list_done",
                    {
                        "pages": pages,
                        "total_deals": total_deals,
                        "final_from_ms": paging_from_ms,
                        "final_to_ms": paging_to_ms,
                    },
                    ts=_iso_from_ms(paging_to_ms),
                )
                store.conn.commit()
                reactor.stop()
                return

            if name == "ProtoOAErrorRes":
                print("OpenAPI ERROR:", getattr(m, "errorCode", ""), getattr(m, "description", ""))
                reactor.stop()
                return

        except Exception as e:
            print("DealList handler error:", type(e).__name__)
            reactor.stop()

    def connected(_client):
        send_app_auth()

    def disconnected(_client, reason):
        print("Disconnected:", reason)
        try:
            reactor.stop()
        except Exception:
            pass

    client.setConnectedCallback(connected)
    client.setDisconnectedCallback(disconnected)
    client.setMessageReceivedCallback(on_message)

    # Minimal: stop if we hang forever
    reactor.callLater(30.0, lambda: reactor.stop())
    client.startService()
    reactor.run()


if __name__ == "__main__":
    main()
