"""Layer 2: Evon context judge. Returns None on timeout/error so the rule layer still drives the warning.

Evon (gnani/gnani-evon-v3.3-30B-A3B) is published as weights, so EVON_URL points at a self-hosted
OpenAI-compatible server (llama.cpp / vLLM / SGLang), e.g. the Kaggle notebook in evon/.
Quick check: python -m app.evon_judge"""
import asyncio
import json
import re

import httpx

from . import config

PROMPT = """You are a fraud-call analyst for Indian phone calls. The transcript may be Hindi, English or mixed, and may contain speech-recognition errors.
Decide if the CALLER is attempting a scam on the listener.
Return only JSON:
{"risk": 0-100, "scam_type": "digital_arrest|kyc_bank|courier|fake_relative|lottery|none", "reasons": ["short reason", ...], "advice_hi": "one calm sentence in Hindi telling the listener what to do"}
Normal calls (family, doctors, delivery confirmations without payment) must score low.
Transcript:
<<<TRANSCRIPT>>>"""

VALID = {"digital_arrest", "kyc_bank", "courier", "fake_relative", "lottery", "none"}

# Grammar-constrained output (llama.cpp / vLLM honour response_format): without it the quantized model
# sometimes dropped closing quotes and produced invalid JSON (11 of 60 benchmark calls).
SCHEMA = {
    "type": "object",
    "properties": {
        "risk": {"type": "integer", "minimum": 0, "maximum": 100},
        "scam_type": {"type": "string", "enum": sorted(VALID)},
        "reasons": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
        "advice_hi": {"type": "string"},
    },
    "required": ["risk", "scam_type", "reasons", "advice_hi"],
}


def parse(text: str):
    """Pull the first JSON object out of the model output (ignoring any <think> block) and validate it."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        st = d.get("scam_type", "none")
        return {
            "risk": max(0, min(100, int(d.get("risk", 0)))),
            "scam_type": st if st in VALID else "none",
            "reasons": [str(r) for r in d.get("reasons", [])][:5],
            "advice_hi": str(d.get("advice_hi", "")),
        }
    except (ValueError, TypeError, AttributeError):
        return None


async def judge(transcript: str):
    if not config.EVON_URL or not transcript.strip():
        return None
    # Evon's own key only: never send the Gnani key to a self-hosted/tunnelled server
    headers = {"Authorization": f"Bearer {config.EVON_API_KEY}"} if config.EVON_API_KEY else {}
    body = {
        "model": config.EVON_MODEL,
        "temperature": 0,
        "max_tokens": 300,
        # no repetition_penalty: it penalised the repeated '"' tokens JSON needs
        "response_format": {"type": "json_schema", "json_schema": {"name": "verdict", "schema": SCHEMA}},
        "chat_template_kwargs": {"enable_thinking": False},  # model card: thinking off for short, fast answers
        "messages": [{"role": "user", "content": PROMPT.replace("TRANSCRIPT", transcript)}],
    }
    try:
        async with httpx.AsyncClient(timeout=config.EVON_TIMEOUT_S) as c:
            r = await c.post(config.EVON_URL, json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
        text = data["choices"][0]["message"]["content"] if "choices" in data else json.dumps(data)
        return parse(text or "")
    except Exception as e:  # timeout, network, schema: never block the warning
        print(f"[evon] falling back to rules: {e!r}")
        return None


if __name__ == "__main__":
    import time

    for t in ["Main CBI se bol raha hoon, aapke naam pe arrest warrant hai. Camera on rakhiye, aap nigrani mein hain.",
              "Namaste aunty, kal subah gyarah baje aapka checkup hai, reports saath le aaiyega."]:
        t0 = time.time()
        print(asyncio.run(judge(t)), f"({time.time() - t0:.1f}s)")
