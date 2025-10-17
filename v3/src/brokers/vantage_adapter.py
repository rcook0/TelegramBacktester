import os
def load_from_env(optional: bool=False):
    cid = os.getenv("VANTAGE_CTRADER_CLIENT_ID")
    sec = os.getenv("VANTAGE_CTRADER_CLIENT_SECRET")
    tok = os.getenv("VANTAGE_CTRADER_ACCESS_TOKEN")
    acc = os.getenv("VANTAGE_CTRADER_ACCOUNT_ID")
    host = (os.getenv("VANTAGE_CTRADER_HOST","LIVE") or "LIVE").upper()
    if not all([cid,sec,tok,acc]):
        if optional: return None
        raise RuntimeError("Missing Vantage cTrader env vars. See .env.example")
    return {"client_id": cid, "client_secret": sec, "access_token": tok, "account_id": int(acc), "host": host}
