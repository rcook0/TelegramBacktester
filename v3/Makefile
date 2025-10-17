# ---- Parameterized tasks (no secrets stored) ----
# usage: make ctrader-top SYMS="EURUSD,XAUUSD" OUT="data/spreads" CT_ID=... CT_SECRET=... CT_TOKEN=... CT_ACC=123 CT_HOST=LIVE
ctrader-top:
	python -m tools.record_ctrader_spreads --symbols $(SYMS) --mode top --out $(OUT) \
	  --ctrader-client-id $(CT_ID) --ctrader-client-secret $(CT_SECRET) \
	  --ctrader-access-token $(CT_TOKEN) --ctrader-account-id $(CT_ACC) --ctrader-host $(CT_HOST)

ctrader-weighted:
	python -m tools.record_ctrader_spreads --symbols $(SYMS) --mode weighted --out $(OUT) \
	  --ctrader-client-id $(CT_ID) --ctrader-client-secret $(CT_SECRET) \
	  --ctrader-access-token $(CT_TOKEN) --ctrader-account-id $(CT_ACC) --ctrader-host $(CT_HOST)

fix-capture:
	python -m tools.record_fix_md --cfg $(CFG) --symbols $(SYMS) --out $(OUT) --flush-sec 5 --rotate-mb 256

fix-build:
	python -m tools.build_candles --ticks $(TICKDIR) --symbol $(SYM) --timeframe $(TF) --out $(OUT)

backtest-csv:
	python -m src.main --channel "$(CHAN)" --since "$(SINCE)" --until "$(UNTIL)" \
	  --data-source csv --timeframe $(TF) --lot $(LOT) --deposit $(DEP) --leverage $(LEV) \
	  --export $(OUT)
