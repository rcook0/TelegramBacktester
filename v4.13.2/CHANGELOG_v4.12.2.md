# Changelog — v4.12.2
- Added deal alignment engine: `src/reconcile/deal_align.py`
- Added runner: `src/runners/ctrader_align_deals.py`
- Persists enriched `deal_aligned` rows (deal_norm + quote/depth context + depth WAP estimate)
- Reconciler now prefers `deal_aligned` fills for WAP before falling back to raw deals/depth/quote mid.
- Added mechanisms document: `docs/MECHANISMS_v4.12.2_deal_alignment.md`
