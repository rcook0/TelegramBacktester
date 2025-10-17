import os
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import PeerChannel

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
PHONE = os.getenv("TELEGRAM_PHONE", None)

def _client():
    if API_ID == 0 or not API_HASH:
        raise RuntimeError("Missing TELEGRAM_API_ID / TELEGRAM_API_HASH in environment")
    client = TelegramClient("telegram", API_ID, API_HASH)
    return client

def fetch_messages(channel_ref: str, since: datetime, until: datetime) -> List[Dict]:
    out = []
    with _client() as client:
        client.connect()
        if PHONE and not client.is_user_authorized():
            client.send_code_request(PHONE)
            raise RuntimeError("First run requires interactive login. Run script standalone to complete login.")
        entity = channel_ref
        if channel_ref.isdigit():
            entity = PeerChannel(int(channel_ref))
        for msg in client.iter_messages(entity, offset_date=until, reverse=True):
            if msg.date < since:
                break
            if msg.message:
                out.append({"id": msg.id, "date": msg.date, "text": msg.message})
    return out
