from __future__ import annotations
import argparse, json
from storage.sqlite_store_symbols import SymbolStore
from capture.window import parse_iso, CaptureWindow

def parse_args():
    p = argparse.ArgumentParser(description="cTrader shadow capture (quotes/depth)")
    p.add_argument("--db", required=True)
    p.add_argument("--signal-idem-key", required=True)
    p.add_argument("--symbols", required=True, help="Comma-separated symbols (canonical or broker names)")
    p.add_argument("--duration-sec", type=float, default=20.0)

    # Capture window alignment (v4.11.4)
    p.add_argument("--signal-ts", default="", help="ISO timestamp of signal; if provided, capture window recorded")
    p.add_argument("--pre-ms", type=int, default=2000)
    p.add_argument("--post-ms", type=int, default=30000)

    # Capture mode
    p.add_argument("--mode", choices=["openapi","poll"], default="openapi")

    # Open API (real)
    p.add_argument("--env", choices=["LIVE","DEMO"], default="LIVE")
    p.add_argument("--client-id")
    p.add_argument("--client-secret")
    p.add_argument("--access-token")
    p.add_argument("--account-id", type=int, help="ctidTraderAccountId")
    p.add_argument("--capture-depth", action="store_true")

    # v4.11.10 hardening
    p.add_argument("--flush-interval-sec", type=float, default=0.2)
    p.add_argument("--max-depth-hz-per-symbol", type=float, default=5.0)
    p.add_argument("--drop-depth-under-pressure", action="store_true")
    p.add_argument("--no-reconnect", action="store_true")
    p.add_argument("--reconnect-backoff-sec", type=float, default=2.0)
    p.add_argument("--max-reconnect-backoff-sec", type=float, default=30.0)


    # Symbol normalization (v4.11.5)
    p.add_argument("--symbol-map-json", default="{}", help="JSON map alias->brokerSymbolName")

    # Poll scaffold (legacy)
    p.add_argument("--base-url", default="")
    p.add_argument("--access-token-poll", default="")
    p.add_argument("--poll-interval-sec", type=float, default=0.5)

    return p.parse_args()

def main():
    args = parse_args()
    store = SymbolStore(args.db)

    cur = store.conn.cursor()
    cur.execute("SELECT id, ts, payload FROM signals WHERE idem_key=?", (args.signal_idem_key,))
    row = cur.fetchone()
    if not row:
        raise SystemExit("No signal found for idem_key. Ingest signals first so it exists in DB.")
    signal_id = int(row[0])
    signal_ts_db = row[1]

    # Determine capture window if signal-ts provided (else use db ts)
    sig_ts = args.signal_ts or signal_ts_db
    cw = CaptureWindow(pre_ms=args.pre_ms, post_ms=args.post_ms)
    start, end = cw.start_end(parse_iso(sig_ts))

    # Persist capture-window meta snapshot
    store.add_shadow_snapshot(signal_id, "capture_window", dict(
        signal_ts=sig_ts,
        pre_ms=args.pre_ms,
        post_ms=args.post_ms,
        start=start.isoformat(),
        end=end.isoformat(),
    ), ts=sig_ts)

    symbols_in = [s.strip() for s in args.symbols.split(",") if s.strip()]
    alias_map = json.loads(args.symbol_map_json) if args.symbol_map_json else {}

    def on_quote(q: dict):
        store.add_shadow_snapshot(signal_id, "quote", q, ts=q.get("ts"))
        print("quote", q.get("symbol"), q.get("bid"), q.get("ask"), "spr(pips)", q.get("spread_pips"))

        # Cache symbol resolution when fields present
        if q.get("symbol_id") is not None:
            store.upsert_symbol(
                broker=str(q.get("source","ctrader-openapi")),
                account_id=str(args.account_id) if args.account_id else None,
                symbol_input=_reverse_alias(alias_map, q.get("symbol", q.get("symbol"))),
                symbol_name=q.get("symbol", ""),
                symbol_id=int(q.get("symbol_id")),
                digits=int(q.get("digits")) if q.get("digits") is not None else None,
                pip_position=int(q.get("pip_position")) if q.get("pip_position") is not None else None,
                pip_size=float(q.get("pip_size")) if q.get("pip_size") is not None else None,
            )

    def on_depth(d: dict):
        store.add_shadow_snapshot(signal_id, "depth", d, ts=d.get("ts"))
        print("depth", d.get("symbol"), len(d.get("bids", [])), len(d.get("asks", [])))

    if args.mode == "openapi":
        from capture.ctrader_openapi_capture import CTraderOpenApiCapture, OpenApiCaptureConfig
        cfg = OpenApiCaptureConfig(
            env=args.env,
            client_id=args.client_id or "",
            client_secret=args.client_secret or "",
            access_token=args.access_token or "",
            ctid_trader_account_id=int(args.account_id or 0),
            symbols=[alias_map.get(s, s) for s in symbols_in],
            subscribe_depth=bool(args.capture_depth),
            symbol_alias_map=alias_map,
            flush_interval_sec=float(args.flush_interval_sec),
            max_depth_hz_per_symbol=float(args.max_depth_hz_per_symbol),
            drop_depth_under_pressure=bool(args.drop_depth_under_pressure),
            reconnect=not bool(args.no_reconnect),
            reconnect_backoff_sec=float(args.reconnect_backoff_sec),
            max_reconnect_backoff_sec=float(args.max_reconnect_backoff_sec),
        )
        if not (cfg.client_id and cfg.client_secret and cfg.access_token and cfg.ctid_trader_account_id):
            raise SystemExit("Missing Open API credentials. Provide --client-id --client-secret --access-token --account-id.")
        cap = CTraderOpenApiCapture(cfg)
        cap.start(on_quote=on_quote, on_depth=on_depth if args.capture_depth else None, stop_after_sec=args.duration_sec)
        return

    # legacy polling scaffold
    from capture.ctrader_capture import CTraderCapture, CTraderCaptureConfig
    cap = CTraderCapture(CTraderCaptureConfig(
        host=args.env, access_token=args.access_token_poll, symbols=[alias_map.get(s, s) for s in symbols_in],
        poll_interval_sec=args.poll_interval_sec, base_url=args.base_url
    ))
    cap.run_poll_loop(on_quote=on_quote, on_depth=on_depth if args.capture_depth else None, stop_after_sec=args.duration_sec)

def _reverse_alias(alias_map: dict, broker_symbol: str) -> str:
    # Best-effort: map broker symbol back to one of the inputs
    for k,v in alias_map.items():
        if v == broker_symbol:
            return k
    return broker_symbol

if __name__ == "__main__":
    main()
