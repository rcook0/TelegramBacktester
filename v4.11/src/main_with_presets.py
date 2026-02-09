import argparse, json, os
from datetime import datetime, timezone

from src.presets.loader import load_preset_bundle

def parse_args():
    p = argparse.ArgumentParser(description="Backtester (v4.3.0 presets example)")
    p.add_argument("--channel", required=True)
    p.add_argument("--since", required=True)
    p.add_argument("--until", required=True)
    p.add_argument("--data-source", choices=["mt5","csv","ctrader","fix"], default="csv")
    p.add_argument("--timeframe", choices=["M1","M5","M15","H1"], default="M1")

    # presets + maps
    p.add_argument("--preset", type=str, default=None)
    p.add_argument("--symbol-map", type=str, default="{}")
    p.add_argument("--contract-map", type=str, default="{}")
    p.add_argument("--conv-map", type=str, default="{}")

    p.add_argument("--lot", type=float, default=0.1)
    p.add_argument("--deposit", type=float, default=1000.0)
    p.add_argument("--leverage", type=int, default=500)
    p.add_argument("--export", type=str, default="out.csv")
    return p.parse_args()

def main():
    args = parse_args()
    preset_maps = {"symbol_map": {}, "contract_map": {}, "conv_map": {}}
    if args.preset:
        preset_maps = load_preset_bundle(args.preset)
        print(f"[preset] loaded: {args.preset}")

    # precedence: preset < CLI (CLI wins)
    symbol_map   = {**preset_maps["symbol_map"],   **json.loads(args.symbol_map)}
    contract_map = {**preset_maps["contract_map"], **json.loads(args.contract_map)}
    conv_map     = {**preset_maps["conv_map"],     **json.loads(args.conv_map)}
    print("[preset] merged maps:", {"symbol_map": len(symbol_map), "contract_map": len(contract_map), "conv_map": len(conv_map)})
    print("[demo] this is a reference main; wire this logic into your real src.main.")
    # here you would call your Backtester with these merged maps

if __name__ == "__main__":
    main()
