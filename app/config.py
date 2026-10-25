import os
import sys
from pathlib import Path

# Logs contain Devanagari/Tamil/Bengali; the Windows console default (cp1252) would crash on print().
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"
CACHE_DIR.mkdir(exist_ok=True)

GNANI_API_KEY = os.getenv("GNANI_API_KEY", "")
# Endpoints from docs.gnani.ai (API quick start). Both authenticate with the X-API-Key-ID header.
PRISMA_URL = os.getenv("PRISMA_URL") or "https://api.vachana.ai/stt/v3"
TIMBRE_URL = os.getenv("TIMBRE_URL") or "https://api.vachana.ai/api/v1/tts/inference"
TIMBRE_MODEL = os.getenv("TIMBRE_MODEL") or "timbre-v3.0"  # v3.0 voices speak all 10 Indian languages
TIMBRE_VOICE = os.getenv("TIMBRE_VOICE") or "Shivani"
EVON_URL = os.getenv("EVON_URL", "")
EVON_MODEL = os.getenv("EVON_MODEL", "evon")
EVON_API_KEY = os.getenv("EVON_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GUARDIAN_CHAT_ID = os.getenv("GUARDIAN_CHAT_ID", "")
LANGUAGE = os.getenv("LANGUAGE", "hi-IN")
ALERT_THRESHOLD = int(os.getenv("ALERT_THRESHOLD", "70"))
CAUTION_THRESHOLD = int(os.getenv("CAUTION_THRESHOLD", "40"))
EVON_INTERVAL_S = float(os.getenv("EVON_INTERVAL_S", "10"))
# Call recordings: only the first MAX_AUDIO_S seconds are transcribed (scams show their hand early; saves credits)
MAX_AUDIO_S = int(os.getenv("MAX_AUDIO_S", "300"))
# Shared secret the phone's automation app sends to /check-recording (see docs/auto-check-recordings.md)
UPLOAD_TOKEN = os.getenv("KAVACH_UPLOAD_TOKEN", "")
EVON_TIMEOUT_S = float(os.getenv("EVON_TIMEOUT_S", "20"))  # runs in the background in live mode
