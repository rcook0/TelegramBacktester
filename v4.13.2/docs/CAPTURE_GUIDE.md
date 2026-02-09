# Capturing assistant step notes (release discipline)

Goal: preserve the dense “why/mechanism/unlocks/caveats” info each step forward, without the docs turning into a mess.

## Rules
1) **Every shipped version gets a release note**: `docs/releases/vX.Y.Z.md`
2) Release notes carry BOTH:
   - operator path (commands + artifacts)
   - assistant notes (why/mechanism/unlocks/caveats)
3) Any deep dive goes into `docs/MECHANISMS_*.md` and is linked from the release note.
4) The feature registry stays *short*: `docs/FEATURE_TREE.yaml` only stores pointers + short structured notes.

## Workflow (2 minutes per version)
1) Create the stub + register the release:
   ```bash
   python tools/release_new.py 4.12.5 "P&L attribution (pips + base CCY)" --roadmap-line "trade_links -> pnl_ccy" --next "v4.12.6 — reconciliation v3"
   ```
2) Fill in the release note sections (5–15 bullet points is normal as complexity grows).
3) Regenerate manuals:
   ```bash
   python tools/docs_build.py
   ```

## Optional: use flags to pre-seed notes
Example:
```bash
python tools/release_new.py 4.12.5 "P&L attribution (pips + base CCY)" \
  --roadmap-line "trade_links -> pnl_ccy attribution" \
  --changed "Add pip-value conversion (symbol contract sizing)" \
  --changed "Add account-ccy conversion map (USD/EUR/GBP)" \
  --mechanism "Compute pnl_pips from linkage entry/exit WAP, apply pip_size" \
  --mechanism "Convert to pnl_ccy using pip_value_per_lot * qty_lots (and FX conversion if needed)" \
  --run "python -m src.runners.pnl_attrib --db ./journal/trader.db --signal-idem-key <KEY> --overwrite" \
  --snapshots "trade_link,pnl_attrib" \
  --tables "trade_links" \
  --why "You can’t reconcile or dashboard without money P&L." \
  --unlocks "dash reports, gating thresholds, live mode scoring"
```

## Why this scales
- Release notes keep the narrative coherent as features multiply.
- The manuals stay navigable (generated, structured).
- You don’t lose the “assistant commentary” that actually explains the system.
