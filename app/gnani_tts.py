"""Timbre adapter + cached warning clips. Warnings are pre-written: short, calm and tested.

Written in native script on purpose: Timbre picks its voice profile from the script, and romanized Hindi
("Yeh call fraud lag rahi hai") came out flat and English-accented. <pauses> (timbre-v3.0 audio tag) gives
each sentence room to land; tags are stripped for on-screen text.

The warning is spoken in the language chosen in the app; without a choice (Telegram, recordings) it is detected
from the script Prisma writes the transcript in (Devanagari / Tamil / Bengali), else LANGUAGE. Tamil and Bengali
lines were written for this project and should be checked by a native speaker."""
import hashlib
import re

import httpx

from . import config

WARNINGS = {
    "hi-IN": {
        "digital_arrest": "सावधान! यह कॉल फ्रॉड लग रही है। <pauses> पुलिस कभी फ़ोन पर पैसे नहीं माँगती। <pauses> कॉल काट दीजिए।",
        "kyc_bank": "सावधान! यह कॉल फ्रॉड लग रही है। <pauses> बैंक कभी फ़ोन पर OTP या PIN नहीं माँगता। <pauses> कॉल काट दीजिए।",
        "courier": "सावधान! यह कॉल फ्रॉड लग रही है। <pauses> पार्सल के नाम पर पैसे माँगना धोखा है। <pauses> कॉल काट दीजिए।",
        "fake_relative": "रुकिए! अभी पैसे मत भेजिए। <pauses> पहले अपने घरवालों को खुद फ़ोन करके पूछ लीजिए।",
        "lottery": "सावधान! यह कॉल फ्रॉड लग रही है। <pauses> इनाम पाने के लिए कभी पैसे नहीं देने पड़ते। <pauses> कॉल काट दीजिए।",
        "none": "सावधान! यह कॉल फ्रॉड लग रही है। <pauses> किसी को OTP या पैसे मत दीजिए। <pauses> कॉल काट दीजिए।",
        "caution": "ध्यान रखिए। <pauses> किसी को भी OTP या पैसे मत दीजिए।",
    },
    "ta-IN": {
        "digital_arrest": "கவனம்! இது மோசடி அழைப்பு போல் தெரிகிறது. <pauses> காவல்துறை ஒருபோதும் தொலைபேசியில் பணம் கேட்காது. <pauses> அழைப்பைத் துண்டியுங்கள்.",
        "kyc_bank": "கவனம்! இது மோசடி அழைப்பு போல் தெரிகிறது. <pauses> வங்கி ஒருபோதும் தொலைபேசியில் OTP அல்லது PIN கேட்காது. <pauses> அழைப்பைத் துண்டியுங்கள்.",
        "courier": "கவனம்! இது மோசடி அழைப்பு போல் தெரிகிறது. <pauses> பார்சல் பெயரில் பணம் கேட்பது மோசடி. <pauses> அழைப்பைத் துண்டியுங்கள்.",
        "fake_relative": "நில்லுங்கள்! இப்போது பணம் அனுப்ப வேண்டாம். <pauses> முதலில் உங்கள் குடும்பத்தினரை நேரடியாக அழைத்துக் கேளுங்கள்.",
        "lottery": "கவனம்! இது மோசடி அழைப்பு போல் தெரிகிறது. <pauses> பரிசு பெற ஒருபோதும் பணம் கட்ட வேண்டியதில்லை. <pauses> அழைப்பைத் துண்டியுங்கள்.",
        "none": "கவனம்! இது மோசடி அழைப்பு போல் தெரிகிறது. <pauses> யாரிடமும் OTP அல்லது பணம் கொடுக்காதீர்கள். <pauses> அழைப்பைத் துண்டியுங்கள்.",
        "caution": "கவனமாக இருங்கள். <pauses> யாரிடமும் OTP அல்லது பணம் கொடுக்காதீர்கள்.",
    },
    "bn-IN": {
        "digital_arrest": "সাবধান! এই কলটি প্রতারণা বলে মনে হচ্ছে। <pauses> পুলিশ কখনও ফোনে টাকা চায় না। <pauses> কলটি কেটে দিন।",
        "kyc_bank": "সাবধান! এই কলটি প্রতারণা বলে মনে হচ্ছে। <pauses> ব্যাংক কখনও ফোনে OTP বা PIN চায় না। <pauses> কলটি কেটে দিন।",
        "courier": "সাবধান! এই কলটি প্রতারণা বলে মনে হচ্ছে। <pauses> পার্সেলের নামে টাকা চাওয়া প্রতারণা। <pauses> কলটি কেটে দিন।",
        "fake_relative": "থামুন! এখনই টাকা পাঠাবেন না। <pauses> আগে নিজে পরিবারের লোককে ফোন করে জিজ্ঞেস করুন।",
        "lottery": "সাবধান! এই কলটি প্রতারণা বলে মনে হচ্ছে। <pauses> পুরস্কার পেতে কখনও টাকা দিতে হয় না। <pauses> কলটি কেটে দিন।",
        "none": "সাবধান! এই কলটি প্রতারণা বলে মনে হচ্ছে। <pauses> কাউকে OTP বা টাকা দেবেন না। <pauses> কলটি কেটে দিন।",
        "caution": "সাবধান থাকুন। <pauses> কাউকে OTP বা টাকা দেবেন না।",
    },
    "en-IN": {
        "digital_arrest": "Careful! This call looks like a scam. <pauses> The police never ask for money over the phone. <pauses> Please hang up.",
        "kyc_bank": "Careful! This call looks like a scam. <pauses> Your bank will never ask for an OTP or PIN on a call. <pauses> Please hang up.",
        "courier": "Careful! This call looks like a scam. <pauses> Asking for money over a parcel is a trick. <pauses> Please hang up.",
        "fake_relative": "Wait! Don't send any money yet. <pauses> First call your family member yourself and check.",
        "lottery": "Careful! This call looks like a scam. <pauses> You never have to pay to receive a prize. <pauses> Please hang up.",
        "none": "Careful! This call looks like a scam. <pauses> Don't share an OTP or send money to anyone. <pauses> Please hang up.",
        "caution": "Be careful. <pauses> Don't share an OTP or send money to anyone.",
    },
}
SUPPORTED = tuple(WARNINGS)  # languages the app offers: screen text, listening and warnings
WARNINGS_HI = WARNINGS["hi-IN"]
CAUTION_HI = WARNINGS_HI["caution"]

# Unicode blocks of the scripts Prisma writes each language in
_SCRIPTS = {"hi-IN": ("ऀ", "ॿ"), "ta-IN": ("஀", "௿"), "bn-IN": ("ঀ", "৿")}


def detect_language(transcript: str) -> str:
    """The language whose script dominates the transcript; LANGUAGE (or Hindi) when there is none."""
    counts = {lang: sum(lo <= ch <= hi for ch in transcript) for lang, (lo, hi) in _SCRIPTS.items()}
    lang, n = max(counts.items(), key=lambda kv: kv[1])
    if n >= 5:
        return lang
    return config.LANGUAGE if config.LANGUAGE in WARNINGS else "hi-IN"


def warning_text(scam_type: str, lang: str = "hi-IN") -> str:
    lines = WARNINGS.get(lang, WARNINGS_HI)
    return lines.get(scam_type, lines["none"])


def warning_for(level: str, scam_type: str, lang: str = "hi-IN") -> str:
    """Tagged text to speak for a level ("" when safe)."""
    if level == "danger":
        return warning_text(scam_type, lang)
    if level == "caution":
        return warning_text("caution", lang)
    return ""


def plain(text: str) -> str:
    """Text without audio tags, for the screen, Telegram and the browser-voice fallback."""
    return re.sub(r"\s*<[^>]+>\s*", " ", text).strip()


def _cache_path(text: str, language: str, voice: str):
    key = hashlib.sha1(f"{config.TIMBRE_MODEL}|{voice}|{language}|{text}".encode()).hexdigest()[:16]
    return config.CACHE_DIR / f"tts_{key}.wav"


async def synthesize(text: str, language: str = None, voice: str = None):
    """16 kHz mono WAV bytes (cached on disk), or None if Timbre is unavailable
    (the web page then uses browser speech). API: docs.gnani.ai/api/TTS/tts-inference"""
    language, voice = language or config.LANGUAGE, voice or config.TIMBRE_VOICE
    path = _cache_path(text, language, voice)
    if path.exists():
        return path.read_bytes()
    if not config.GNANI_API_KEY:
        return None
    body = {
        "text": text, "voice": voice, "model": config.TIMBRE_MODEL, "language": language, "speed": 0.95,
        "audio_config": {"sample_rate": 16000, "num_channels": 1, "sample_width": 2,
                         "encoding": "linear_pcm", "container": "wav"},
    }
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(config.TIMBRE_URL, headers={"X-API-Key-ID": config.GNANI_API_KEY}, json=body)
        if r.status_code != 200 or not r.content.startswith(b"RIFF"):
            raise RuntimeError(f"{r.status_code}: {r.text[:200]}")
        path.write_bytes(r.content)
        return r.content
    except Exception as e:
        print(f"[timbre] unavailable: {e}")
        return None


async def warm_cache():
    """Pre-generate every warning in every language so it plays instantly during a call."""
    for lang, lines in WARNINGS.items():
        for t in lines.values():
            await synthesize(t, lang)
