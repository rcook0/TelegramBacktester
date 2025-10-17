import argparse
import json
import os
from datetime import datetime, timezone
import pandas as pd
from dotenv import load_dotenv

from .telegram_client import fetch_messages
from .signal_parser import parse_signals_from_messages
from .backtester import Backtester
from .data_providers.mt5_provider import MT5Provider, MT5_AVAILABLE
from .data_providers.cache_provider import CachedProvider

def parse_args():
    p = argparse.ArgumentParser(description="Telegram FX Signal Backtester")
    p.add_argument("--channel", required=True, help="Telegram channel name or ID")
    p.add_argument("--since", required=True, help="UTC start date YYYY-MM-DD")
    p.add_argument("--until", required=True, help="UTC end date YYYY-MM-DD")
    p.add_argument("--data-source", choices=["mt5","csv"], default="csv")
    p.add_argument("--timeframe", choices=["M1","M5","M15","H1"], default="M1")
    p.add_argument("--lot", type=float, help="Fixed lot size per trade (e.g., 0.1)")
    p.add_argument("--risk-pct", type=float, help="Risk percent per trade (e.g., 1.0 means 1% of equity)")
    p.add_argument("--deposit", type=float, help="Account deposit/balance baseline")
    p.add_argument("--leverage", type=int, help="Account leverage (e.g., 500)")
    p.add_argument("--exit", choices=["first_target","multi_tp","multi_tp_scaled"], default="multi_tp_scaled",
                   help="Exit rule for targets")
    p.add_argument("--tp-weights", type=str, default="",
                   help='Comma-separated weights for scaled exits, e.g. "0.5,0.3,0.2"')
    p.add_argument("--time-stop-min", type=int, default=None, help="Optional time-based exit in minutes")
    p.add_argument("--spread-pips", type=float, default=0.0, help="Assumed total spread in pips")
    p.add_argument("--slippage-pips", type=float, default=0.0, help="Entry slippage in pips (one-way)")
    p.add_argument("--commission-per-lot", type=float, default=0.0, help="Commission per 1.0 lot in account ccy")
    p.add_argument("--symbol-map", type=str, default="{}",
                   help='JSON mapping of signal symbols to broker symbols, e.g. {"GOLD":"XAUUSD"}')
    p.add_argument("--export", type=str, default="backtest_results.csv", help="CSV path for trade-by-trade results")
    p.add_argument("--cache", action="store_true", help="Enable on-disk candle cache")
    p.add_argument("--cache-dir", type=str, default=".cache", help="Cache directory")
    return p.parse_args()

def load_env_defaults(args):
    load_dotenv()
    args.lot = args.lot or float(os.getenv("DEFAULT_LOT", "0.1"))
    args.deposit = args.deposit or float(os.getenv("DEFAULT_DEPOSIT", "1000"))
    args.leverage = args.leverage or int(os.getenv("DEFAULT_LEVERAGE", "500"))
    return args

def get_data_provider(source: str, cache: bool, cache_dir: str):
    if source == "mt5":
        if not MT5_AVAILABLE:
            raise RuntimeError("MetaTrader5 package not available on this platform. Use --data-source csv.")
        base = MT5Provider()
    else:
        class CSVProvider:
            def candles(self, symbol, start, end, timeframe="M1"):
                path = os.path.join(os.path.dirname(__file__), "..", "data", f"{symbol}.csv")
                if not os.path.exists(path):
                    raise FileNotFoundError(f"CSV not found: {path}")
                df = pd.read_csv(path, parse_dates=["time"])
                df = df[(df["time"] >= pd.Timestamp(start)) & (df["time"] <= pd.Timestamp(end))]
                df = df.sort_values("time").reset_index(drop=True)
                return df
        base = CSVProvider()
    if cache:
        return CachedProvider(base, cache_dir)
    return base

def main():
    args = parse_args()
    args = load_env_defaults(args)
    symbol_map = json.loads(args.symbol_map)

    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
    until = datetime.fromisoformat(args.until).replace(tzinfo=timezone.utc)

    tp_weights = None
    if args.tp_weights:
        tp_weights = [float(x) for x in args.tp_weights.split(",") if x.strip()]
        if sum(tp_weights) <= 0:
            tp_weights = None

    print("[1/5] Fetching Telegram messages...")
    msgs = fetch_messages(args.channel, since, until)
    print(f"Fetched {len(msgs)} messages.")

    print("[2/5] Parsing trading signals...")
    signals = parse_signals_from_messages(msgs)
    print(f"Parsed {len(signals)} candidate signals.")

    print("[3/5] Loading market data via", args.data_source.upper())
    provider = get_data_provider(args.data_source, args.cache, args.cache_dir)

    print("[4/5] Running backtest...")
    bt = Backtester(provider=provider,
                    default_lot=args.lot,
                    deposit=args.deposit,
                    leverage=args.leverage,
                    symbol_map=symbol_map,
                    exit_rule=args.exit,
                    tp_weights=tp_weights,
                    risk_pct=args.risk_pct,
                    spread_pips=args.spread_pips,
                    slippage_pips=args.slippage_pips,
                    commission_per_lot=args.commission_per_lot,
                    time_stop_min=args.time_stop_min,
                    timeframe=args.timeframe)
    report = bt.run(signals, since, until)

    print("\n=== Performance Summary ===")
    for k,v in report["summary"].items():
        print(f"{k}: {v}")

    print("\nSaving trade log ->", args.export)
    report["trades"].to_csv(args.export, index=False)

if __name__ == "__main__":
    main()
