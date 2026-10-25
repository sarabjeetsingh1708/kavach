import asyncio

import numpy as np
from fastapi.testclient import TestClient

from app import evon_judge, rules
from app.main import app
from app.pipeline import CallSession
from eval.audio_utils import mix_at_snr, phone_filter
from eval.run_eval import wer


def test_digital_arrest_scores_high():
    r = rules.score("Main CBI se bol raha hoon, aapke naam pe arrest warrant hai, kisi ko mat batana")
    assert r["score"] >= 70 and r["scam_type"] == "digital_arrest"


def test_devanagari_prisma_output():
    # real Prisma transcript of a Timbre-generated scam line
    r = rules.score("मेन सी बी आई से बोल रहा हूँ, आपके नाम पे अरेस्ट वारंट है, यह बाट किसी को मत बताना, अभी पैसे ट्रांसफ़र कीजिए।")
    assert r["score"] >= 70 and r["scam_type"] == "digital_arrest"
    assert rules.score("नमस्ते आंटी, कल सुबह ग्यारह बजे आपका चेकअप है")["score"] < 40


def test_normal_call_scores_low():
    assert rules.score("Namaste aunty, kal subah gyarah baje aapka checkup hai")["score"] < 40


def test_single_flag_is_capped():
    assert rules.score("aapka parcel kal aayega")["score"] <= rules.SINGLE_FLAG_CAP


def test_evon_parse():
    out = evon_judge.parse('Sure: {"risk": 150, "scam_type": "weird", "reasons": ["otp"], "advice_hi": "kaat do"}')
    assert out == {"risk": 100, "scam_type": "none", "reasons": ["otp"], "advice_hi": "kaat do"}
    assert evon_judge.parse("no json here") is None


def test_session_is_monotonic_and_alerts_once():
    async def run():
        s = CallSession(use_evon=False, send_alerts=False)
        a = await s.add_text("KYC expire ho gaya, account band ho jayega")
        b = await s.add_text("OTP bata dijiye")
        c = await s.add_text("theek hai")
        return a, b, c
    a, b, c = asyncio.run(run())
    assert a["risk"] <= b["risk"] <= c["risk"]
    assert b["fire_alert"] and not c["fire_alert"] and c["level"] == "danger"


def test_api_and_websocket():
    client = TestClient(app)
    assert client.get("/health").json()["ok"]
    assert client.post("/analyze-text", json={"text": "Lottery jeeti hai, processing fee bhejiye"}).json()["level"] == "danger"
    with client.websocket_connect("/ws/listen") as ws:
        ws.send_json({"text": "Papa mera accident ho gaya, naya number hai"})
        ws.send_json({"text": "jaldi se paise bhej do"})
        ws.receive_json()
        assert ws.receive_json()["level"] == "danger"


def test_warning_language_follows_the_call():
    from app import gnani_tts
    assert gnani_tts.detect_language("मैं सीबीआई से बोल रहा हूँ") == "hi-IN"
    assert gnani_tts.detect_language("நான் சிபிஐ ஆஃபிசர் பேசுறேன்") == "ta-IN"
    assert gnani_tts.detect_language("আমি ব্যাঙ্ক থেকে বলছি") == "bn-IN"
    assert gnani_tts.detect_language("Main CBI se bol raha hoon") == "hi-IN"   # romanized: default language
    for lang, lines in gnani_tts.WARNINGS.items():                             # every language covers every case
        assert set(lines) == set(gnani_tts.WARNINGS["hi-IN"]), lang

    async def run():
        s = CallSession(use_evon=False, send_alerts=False)
        return await s.add_text("நான் சிபிஐ ஆஃபிசர் பேசுறேன். உங்களுக்கு அரெஸ்ட் வாரண்ட் வந்திருக்கு. யாருக்கும் சொல்லாதீங்க. பணம் ட்ரான்ஸ்பர் பண்ணுங்க.")
    st = asyncio.run(run())
    assert st["level"] == "danger" and st["language"] == "ta-IN"
    assert "அழைப்பைத் துண்டியுங்கள்" in st["warning_text"] and "lang=ta-IN" in st["warning_audio"]


def test_check_recording_requires_token(monkeypatch):
    from app import config
    client = TestClient(app)
    monkeypatch.setattr(config, "UPLOAD_TOKEN", "")
    assert client.post("/check-recording", content=b"x" * 2000).status_code == 503   # disabled until configured
    monkeypatch.setattr(config, "UPLOAD_TOKEN", "s3cret")
    assert client.post("/check-recording", content=b"x" * 2000).status_code == 403
    assert client.post("/check-recording", content=b"x" * 2000, headers={"X-Kavach-Token": "wrong"}).status_code == 403
    assert client.post("/check-recording", content=b"x", headers={"X-Kavach-Token": "s3cret"}).status_code == 400


def test_to_wav_converts_and_caps(monkeypatch, tmp_path):
    import subprocess
    from app import config, gnani_stt
    exe = gnani_stt.ffmpeg_exe()
    # 8 s of tone as AAC/M4A, the format most phone call recorders use (index at the end of the file)
    out = tmp_path / "call.m4a"
    subprocess.run([exe, "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=8",
                    "-c:a", "aac", str(out)], check=True)
    m4a = out.read_bytes()
    monkeypatch.setattr(config, "MAX_AUDIO_S", 5)
    wav = gnani_stt.to_wav(m4a)
    assert wav[:4] == b"RIFF" and 4.9 < gnani_stt.wav_seconds(wav) <= 5.01


def test_combine_layers_veto_each_other():
    from app.pipeline import combine
    assert combine(100, None) == 100          # no Evon answer: rules decide alone
    assert combine(61, 95) == 95              # both suspicious: Evon's context confirms the alarm
    assert combine(26, 95) < 70               # Evon panics at a genuine police call: capped to caution
    assert combine(100, 10) < 70              # rules fooled by "we never ask for OTP": capped to caution
    assert combine(10, 5) == 10


def test_audio_utils_and_wer():
    x = np.sin(np.linspace(0, 2000, 16000)).astype(np.float32)
    y = phone_filter(x, 16000)
    assert len(y) == 8000 and np.abs(y).max() <= 1
    assert mix_at_snr(y, np.random.randn(100).astype(np.float32), 5).shape == y.shape
    assert wer("a b c", "a x c") == 1 / 3
