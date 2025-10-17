import os
def load_from_env(optional: bool=False):
    cid = os.getenv("FPMARKETS_CTRADER_CLIENT_ID")
    sec = os.getenv("FPMARKETS_CTRADER_CLIENT_SECRET")
    tok = os.getenv("FPMARKETS_CTRADER_ACCESS_TOKEN")
    acc = os.getenv("FPMARKETS_CTRADER_ACCOUNT_ID")
    host = (os.getenv("FPMARKETS_CTRADER_HOST","LIVE") or "LIVE").upper()
    if not all([cid,sec,tok,acc]):
        if optional: return None
        raise RuntimeError("Missing FP Markets cTrader env vars. See .env.example")
    return {"client_id": cid, "client_secret": sec, "access_token": tok, "account_id": int(acc), "host": host}
