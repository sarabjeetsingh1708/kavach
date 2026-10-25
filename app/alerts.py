"""Guardian alerts via the Telegram Bot API (plain HTTP, works without the bot process running).
The guardian is GUARDIAN_CHAT_ID from .env, or whoever sent /guardian to the bot (saved in cache/guardian.json)."""
import json

import httpx

from . import config

LABELS = {
    "digital_arrest": "Digital arrest scam",
    "kyc_bank": "KYC / bank scam",
    "courier": "Courier / customs scam",
    "fake_relative": "Fake relative / emergency scam",
    "lottery": "Lottery / refund scam",
    "none": "Suspicious call",
}
GUARDIAN_FILE = config.CACHE_DIR / "guardian.json"


def guardian_chat_id():
    if config.GUARDIAN_CHAT_ID:
        return config.GUARDIAN_CHAT_ID
    try:
        return json.loads(GUARDIAN_FILE.read_text())["chat_id"]
    except (OSError, ValueError, KeyError):
        return None


def set_guardian(chat_id, name: str):
    GUARDIAN_FILE.write_text(json.dumps({"chat_id": chat_id, "name": name}))


def format_alert(state: dict, note: str = None) -> str:
    reasons = "\n".join(f"• {r}" for r in state["reasons"][:4])
    excerpt = state["transcript"][-300:]
    source = f" ({note})" if note else ""
    action = ("The call has already ended. Call your parent now, before they send any money."
              if note else "Call your parent now.")
    return (f"🚨 Kavach alert{source}: {LABELS.get(state['scam_type'], 'Suspicious call')}\n"
            f"Risk: {state['risk']}/100\n\nWhy:\n{reasons}\n\nTranscript excerpt:\n\"...{excerpt}\"\n\n"
            f"{action} Report fraud on 1930 (national cybercrime helpline).")


async def alert_guardian(state: dict, chat_id=None, note: str = None) -> bool:
    chat_id = chat_id or guardian_chat_id()
    if not (config.TELEGRAM_BOT_TOKEN and chat_id):
        print(f"[alert] Telegram not configured; would send: {state['scam_type']} risk {state['risk']}")
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
                             json={"chat_id": chat_id, "text": format_alert(state, note)})
        if r.status_code != 200:
            print(f"[alert] Telegram {r.status_code}: {r.text[:200]}")
        else:
            print(f"[alert] sent to guardian: {state['scam_type']} risk {state['risk']}")
        return r.status_code == 200
    except Exception as e:
        print(f"[alert] failed: {e!r}")
        return False
