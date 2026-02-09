# src/main.py (v4.3.0-integrated)
import argparse, json, os
from datetime import datetime, timezone
from dotenv import load_dotenv

import pandas as pd

# Core modules expected in your repo:
from .telegram_client import fetch_messages
from .signal_parser import parse_signals_from_messages
from .backtester import Backtester

# Data providers (stubs must exist in your repo as earlier)
from .data_providers.mt5_provider import MT5Provider, MT5_AVAILABLE
from .connectors.csv_provider import CSVConnector

# Spread + Order sim
from .spread_provider import SpreadProvider
# (Order logic is inside backtester via OrderSimulator integration)

# Presets loader
from .presets.loader import load_preset_bundle

def parse_args():
    p = argparse.ArgumentParser(description="Telegram FX Signal Backtester v4.3.0")
    # Core
    p.add_argument("--channel", required=True)
    p.add_argument("--since", required=True)
    p.add_argument("--until", required=True)
    p.add_argument("--data-source", choices=["mt5","csv","ctrader","fix"], default="csv")
    p.add_argument("--timeframe", choices=["M1","M5","M15","H1"], default="M1")

    # Presets + maps
    p.add_argument("--preset", type=str, default=None, help="Broker preset (e.g., vantage, fpmarkets)")
    p.add_argument("--symbol-map", type=str, default="{}")
    p.add_argument("--contract-map", type=str, default="{}")
    p.add_argument("--conv-map", type=str, default="{}")

    # Account + sizing
    p.add_argument("--account-ccy", type=str, default=None)
    p.add_argument("--lot", type=float)
    p.add_argument("--risk-pct", type=float)
    p.add_argument("--deposit", type=float)
    p.add_argument("--leverage", type=int)

    # Exits & fidelity
    p.add_argument("--exit", choices=["first_target","multi_tp","multi_tp_scaled"], default="multi_tp_scaled")
    p.add_argument("--tp-weights", type=str, default="")
    p.add_argument("--time-stop-min", type=int, default=None)
    p.add_argument("--spread-pips", type=float, default=0.0)
    p.add_argument("--slippage-pips", type=float, default=0.0)
    p.add_argument("--commission-per-lot", type=float, default=0.0)

    # Spreads
    p.add_argument("--spreads-dir", type=str, default=None, help="Folder with per-minute spread CSVs (bucket,spread_pips)")
    p.add_argument("--spread-map", type=str, default="{}", help='Per-symbol spreads JSON, e.g. {"XAUUSD":24}')

    # Order-side simulation
    p.add_argument("--order-model", choices=["basic","depth"], default="basic")
    p.add_argument("--slip-model", choices=["fixed","vol","depth"], default="fixed")
    p.add_argument("--be-at-rr", type=float, default=None)
    p.add_argument("--trail", type=str, default="", help='e.g. "type=fixed,pips=20" or "type=atr,win=14,mult=2.0"')
    p.add_argument("--ioc", action="store_true", help="Immediate-or-cancel semantics for entries (no carry)")

    # Live mode (scaffold)
    p.add_argument("--live", choices=["none","paper","live"], default="none")
    p.add_argument("--auto-confirm", action="store_true")
    p.add_argument("--daily-loss-cap-pct", type=float, default=5.0)
    p.add_argument("--max-risk-pct", type=float, default=2.0)
    p.add_argument("--kill-switch", choices=["no","yes"], default="yes")

    # I/O
    p.add_argument("--data-dir", type=str, default=None, help="Folder with <SYMBOL>.csv files (default: src/data)")
    p.add_argument("--export", type=str, default="backtest_results.csv")

    # cTrader
    p.add_argument("--ctrader-client-id")
    p.add_argument("--ctrader-client-secret")
    p.add_argument("--ctrader-access-token")
    p.add_argument("--ctrader-account-id", type=int)
    p.add_argument("--ctrader-host", choices=["LIVE","DEMO"], default="LIVE")

    # FIX
    p.add_argument("--fix-cfg", help="Path to FIX .cfg")
    p.add_argument("--fix-symbols", help="Comma-separated symbols for FIX MD")

    return p.parse_args()

def _parse_trail(s: str):
    if not s:
        return None
    kv = {}
    for part in s.split(","):
        if "=" in part:
            k,v = part.split("=",1); kv[k.strip()] = v.strip()
    kv.setdefault("type","fixed")
    for k in ["pips","win","mult"]:
        if k in kv:
            try:
                kv[k] = float(kv[k]) if k != "win" else int(float(kv[k]))
            except Exception:
                pass
    return kv

def get_data_provider(args):
    if args.data_source == "ctrader":
        from .data_providers.ctrader_provider import CTraderProvider
        required = [args.ctrader_client_id, args.ctrader_client_secret, args.ctrader_access_token, args.ctrader_account_id]
        if not all(required):
            raise RuntimeError("Missing --ctrader-* params (client-id, client-secret, access-token, account-id).")
        return CTraderProvider(client_id=args.ctrader_client_id, client_secret=args.ctrader_client_secret,
                               access_token=args.ctrader_access_token, account_id=args.ctrader_account_id, host=args.ctrader_host)
    if args.data_source == "fix":
        if not args.fix_cfg or not args.fix_symbols:
            raise RuntimeError("--fix-cfg and --fix-symbols are required for FIX market data.")
        from .data_providers.fix_provider import VantageFIXProvider
        syms = [s.strip() for s in args.fix_symbols.split(",") if s.strip()]
        return VantageFIXProvider(cfg_path=args.fix_cfg, symbols=syms)
    if args.data_source == "mt5":
        if not MT5_AVAILABLE:
            raise RuntimeError("MetaTrader5 not available on this platform.")
        return MT5Provider()
    return CSVConnector(data_dir=args.data_dir)

def load_env_defaults(args):
    load_dotenv()
    args.lot = args.lot or float(os.getenv("DEFAULT_LOT", "0.1"))
    args.deposit = args.deposit or float(os.getenv("DEFAULT_DEPOSIT", "1000"))
    args.leverage = args.leverage or int(os.getenv("DEFAULT_LEVERAGE", "500"))
    args.account_ccy = (args.account_ccy or os.getenv("DEFAULT_ACCOUNT_CCY", "USD")).upper()
    return args

def main():
    args = load_env_defaults(parse_args())

    # Presets (7)
    preset_maps = {"symbol_map": {}, "contract_map": {}, "conv_map": {}}
    if args.preset:
        try:
            preset_maps = load_preset_bundle(args.preset)
            print(f"[preset] Loaded '{args.preset}'")
        except Exception as e:
            print(f"[preset] Failed to load '{args.preset}': {e}")

    # Merge precedence: preset < CLI
    symbol_map   = {**preset_maps["symbol_map"],   **json.loads(args.symbol_map)}
    contract_map = {**preset_maps["contract_map"], **json.loads(args.contract_map)}
    conv_map     = {**preset_maps["conv_map"],     **json.loads(args.conv_map)}

    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
    until = datetime.fromisoformat(args.until).replace(tzinfo=timezone.utc)

    tp_weights = None
    if args.tp_weights:
        tw = [float(x) for x in args.tp_weights.split(",") if x.strip()]
        if sum(tw) > 0: tp_weights = tw

    # Spreads
    spread_map = json.loads(args.spread_map)
    from .spread_provider import SpreadProvider
    recorded = SpreadProvider.load_dir(args.spreads_dir) if args.spreads_dir else {}
    spread_provider = SpreadProvider(static_pips=args.spread_pips, per_symbol=spread_map, recorded=recorded)

    print("[1/4] Fetching Telegram messages...")
    msgs = fetch_messages(args.channel, since, until)
    print(f"Fetched {len(msgs)} messages.")

    print("[2/4] Parsing trading signals...")
    signals = parse_signals_from_messages(msgs)
    print(f"Parsed {len(signals)} candidate signals.")

    print("[3/4] Loading market data via", args.data_source.upper())
    provider = get_data_provider(args)

    print("[4/4] Running backtest...")
    bt = Backtester(
        provider=provider,
        default_lot=args.lot,
        deposit=args.deposit,
        leverage=args.leverage,
        account_ccy=args.account_ccy,
        symbol_map=symbol_map,
        contract_map=contract_map,
        conv_map=conv_map,
        exit_rule=args.exit,
        tp_weights=tp_weights,
        risk_pct=args.risk_pct,
        spread_pips=args.spread_pips,
        slippage_pips=args.slippage_pips,
        commission_per_lot=args.commission_per_lot,
        time_stop_min=args.time_stop_min,
        timeframe=args.timeframe,
        spread_provider=spread_provider,
        order_model=args.order_model,
        slip_model=args.slip_model,
        be_at_rr=args.be_at_rr,
        trail_cfg=_parse_trail(args.trail),
        ioc=args.ioc,
    )

    report = bt.run(signals, since, until)

    print("\n=== Performance Summary ===")
    for k, v in report["summary"].items():
        print(f"{k}: {v}")

    print("\nSaving trade log ->", args.export)
    report["trades"].to_csv(args.export, index=False)

if __name__ == "__main__":
    main()
