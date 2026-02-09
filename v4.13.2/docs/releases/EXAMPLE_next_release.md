# Example: creating the next release stub

```bash
pip install pyyaml
python tools/release_new.py 4.12.5 "P&L attribution (pips + base CCY)"   --roadmap-line "trade_links -> pnl_ccy attribution"   --next "v4.12.6 — reconciliation v3"
python tools/docs_build.py
```
