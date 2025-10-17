# (same as previous main; full content retained)
import argparse, json, os
from datetime import datetime, timezone
from dotenv import load_dotenv
import pandas as pd
from .telegram_client import fetch_messages
from .signal_parser import parse_signals_from_messages
from .backtester import Backtester
from .data_providers.mt5_provider import MT5Provider, MT5_AVAILABLE
from .data_providers.cache_provider import CachedProvider
def parse_args():
    p = argparse.ArgumentParser(description="Telegram FX Signal Backtester")
    p.add_argument("--channel", required=True); p.add_argument("--since", required=True); p.add_argument("--until", required=True)
    p.add_argument("--data-source", choices=["mt5","csv"], default="csv"); p.add_argument("--timeframe", choices=["M1","M5","M15","H1"], default="M1")
    p.add_argument("--account-ccy", type=str, default=None)
    p.add_argument("--lot", type=float); p.add_argument("--risk-pct", type=float); p.add_argument("--deposit", type=float); p.add_argument("--leverage", type=int)
    p.add_argument("--exit", choices=["first_target","multi_tp","multi_tp_scaled"], default="multi_tp_scaled")
    p.add_argument("--tp-weights", type=str, default=""); p.add_argument("--time-stop-min", type=int, default=None)
    p.add_argument("--spread-pips", type=float, default=None); p.add_argument("--spread-map", type=str, default="{}")
    p.add_argument("--slippage-pips", type=float, default=0.0); p.add_argument("--commission-per-lot", type=float, default=0.0)
    p.add_argument("--symbol-map", type=str, default="{}"); p.add_argument("--contract-map", type=str, default="{}"); p.add_argument("--conv-map", type=str, default="{}")
    p.add_argument("--export", type=str, default="backtest_results.csv"); p.add_argument("--cache", action="store_true"); p.add_argument("--cache-dir", type=str, default=".cache")
    return p.parse_args()
def load_env_defaults(args):
    load_dotenv(); args.lot = args.lot or float(os.getenv("DEFAULT_LOT", "0.1"))
    args.deposit = args.deposit or float(os.getenv("DEFAULT_DEPOSIT", "1000"))
    args.leverage = args.leverage or int(os.getenv("DEFAULT_LEVERAGE", "500"))
    args.account_ccy = args.account_ccy or os.getenv("DEFAULT_ACCOUNT_CCY", "USD"); return args
def get_data_provider(source: str, cache: bool, cache_dir: str):
    if source == "mt5":
        if not MT5_AVAILABLE: raise RuntimeError("MetaTrader5 package not available on this platform. Use --data-source csv.")
        base = MT5Provider()
    else:
        class CSVProvider:
            def candles(self, symbol, start, end, timeframe="M1"):
                import os; import pandas as pd
                path_mid = os.path.join(os.path.dirname(__file__), "..", "data", f"{symbol}.csv")
                if not os.path.exists(path_mid): raise FileNotFoundError(f"CSV not found: {path_mid}")
                df = pd.read_csv(path_mid, parse_dates=["time"]).sort_values("time")
                df = df[(df["time"] >= pd.Timestamp(start)) & (df["time"] <= pd.Timestamp(end))].reset_index(drop=True)
                return df
        base = CSVProvider()
    return CachedProvider(base, cache_dir) if cache else base
def main():
    args = parse_args(); args = load_env_defaults(args)
    symbol_map = json.loads(args.symbol_map); contract_map = json.loads(args.contract_map)
    spread_map = json.loads(args.spread_map); conv_map = json.loads(args.conv_map)
    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc); until = datetime.fromisoformat(args.until).replace(tzinfo=timezone.utc)
    tp_weights = None
    if args.tp_weights: tp_weights = [float(x) for x in args.tp_weights.split(",") if x.strip()]; 
    if tp_weights and sum(tp_weights) <= 0: tp_weights = None
    print("[1/5] Fetching Telegram messages..."); msgs = fetch_messages(args.channel, since, until); print(f"Fetched {len(msgs)} messages.")
    print("[2/5] Parsing trading signals..."); signals = parse_signals_from_messages(msgs); print(f"Parsed {len(signals)} candidate signals.")
    print("[3/5] Loading market data via", args.data_source.upper()); provider = get_data_provider(args.data_source, args.cache, args.cache_dir)
    print("[4/5] Running backtest...")
    bt = Backtester(provider=provider, default_lot=args.lot, deposit=args.deposit, leverage=args.leverage, account_ccy=args.account_ccy,
                    symbol_map=symbol_map, contract_map=contract_map, conv_map=conv_map, exit_rule=args.exit, tp_weights=tp_weights,
                    risk_pct=args.risk_pct, spread_pips=args.spread_pips, spread_map=spread_map, slippage_pips=args.slippage_pips,
                    commission_per_lot=args.commission_per_lot, time_stop_min=args.time_stop_min, timeframe=args.timeframe)
    report = bt.run(signals, since, until); print("\\n=== Performance Summary ===")
    for k,v in report["summary"].items(): print(f"{k}: {v}")
    print("\\nSaving trade log ->", args.export); report["trades"].to_csv(args.export, index=False)
if __name__ == "__main__": main()
