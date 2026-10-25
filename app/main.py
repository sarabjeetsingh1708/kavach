"""FastAPI app. Run: uvicorn app.main:app --reload  (from the kavach/ folder)"""
import json
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import alerts, config, gnani_tts
from .pipeline import CallSession

WEB = Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(_app):
    await gnani_tts.warm_cache()
    bot = None
    if config.TELEGRAM_BOT_TOKEN and config.RUN_BOT:  # run the Mode B bot in the same process: one command starts everything
        from .telegram_bot import build
        bot = build()
        await bot.initialize()
        await bot.start()
        await bot.updater.start_polling()
    yield
    if bot:
        await bot.updater.stop()
        await bot.stop()
        await bot.shutdown()


app = FastAPI(title="Kavach", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"ok": True, "gnani_key": bool(config.GNANI_API_KEY), "timbre_model": config.TIMBRE_MODEL,
            "evon": bool(config.EVON_URL), "telegram_bot": bool(config.TELEGRAM_BOT_TOKEN),
            "guardian": bool(alerts.guardian_chat_id())}


@app.get("/warning/{scam_type}")
async def warning(scam_type: str, lang: str = "hi-IN"):
    lang = lang if lang in gnani_tts.SUPPORTED else "hi-IN"
    audio = await gnani_tts.synthesize(gnani_tts.warning_text(scam_type, lang), lang)
    if audio is None:
        return Response(status_code=204)  # web page falls back to browser speech
    return Response(audio, media_type="audio/wav")


class TextIn(BaseModel):
    text: str


@app.post("/analyze-text")
async def analyze_text(body: TextIn):
    """Key-less path: analyze a transcript directly (demo and tests)."""
    return await CallSession(send_alerts=False).add_text(body.text, final=True)


@app.post("/analyze-file")
async def analyze_file(file: UploadFile = File(...)):
    """Mode B over HTTP: a whole recording through the same pipeline."""
    return await CallSession().add_audio(await file.read(), final=True)


NOTIFY_HI = {
    "danger": "⚠ कवच: पिछली कॉल फ्रॉड लग रही थी। किसी को पैसे या OTP मत दीजिए। परिवार को बता दिया गया है।",
    "caution": "कवच: पिछली कॉल में कुछ संदिग्ध बातें थीं। पैसे भेजने से पहले परिवार से पूछ लीजिए।",
}


@app.post("/check-recording")
async def check_recording(request: Request):
    """Auto-check a finished call recording from the parent's phone (sent by a free automation app such as
    MacroDroid; see docs/auto-check-recordings.md). Accepts multipart `file` or a raw audio body.
    Auth: X-Kavach-Token header (or `token` query/form field) must match KAVACH_UPLOAD_TOKEN.
    On danger, the guardian gets a Telegram alert. `notify` is a short Hindi line for the phone to show."""
    if not config.UPLOAD_TOKEN:
        raise HTTPException(503, "Set KAVACH_UPLOAD_TOKEN in .env to enable recording checks")
    form = await request.form() if request.headers.get("content-type", "").startswith("multipart/") else None
    token = request.headers.get("x-kavach-token") or request.query_params.get("token") or (form or {}).get("token") or ""
    if not secrets.compare_digest(str(token), config.UPLOAD_TOKEN):
        raise HTTPException(403, "bad token")
    if form is not None and form.get("file") is not None:
        audio, name = await form["file"].read(), form["file"].filename
    else:
        audio, name = await request.body(), request.headers.get("x-filename") or request.query_params.get("name")
    if len(audio) < 1000:
        raise HTTPException(400, "no audio received")
    print(f"[recording] {name or 'unnamed'}: {len(audio) // 1024} KB")

    session = CallSession(send_alerts=False)
    try:
        st = await session.add_audio(audio, final=True)
    except Exception as e:
        print(f"[recording] failed: {e}")
        raise HTTPException(502, f"could not analyse recording: {e}")
    alerted = False
    if st["level"] == "danger":
        alerted = await alerts.alert_guardian(st, note=f"recorded call{f' ({name})' if name else ''}")
    print(f"[recording] verdict {st['level']} risk={st['risk']} type={st['scam_type']} alerted={alerted}")
    return {"level": st["level"], "risk": st["risk"], "scam_type": st["scam_type"], "reasons": st["reasons"],
            "notify": NOTIFY_HI.get(st["level"], ""), "alerted": alerted, "transcript": st["transcript"]}


@app.websocket("/ws/listen")
async def ws_listen(ws: WebSocket):
    """Mode A. Binary frames = self-contained audio chunks; text frames {"text": "..."} = transcript lines
    (typed demo without Prisma). Each frame gets the full call state back. Nothing is stored."""
    await ws.accept()
    session = CallSession(language=ws.query_params.get("lang"))  # the language picked in the app
    while True:
        msg = await ws.receive()
        if msg["type"] == "websocket.disconnect":
            break
        try:
            if msg.get("bytes"):
                st = await session.add_audio(msg["bytes"])
            elif msg.get("text"):
                st = await session.add_text(json.loads(msg["text"]).get("text", ""))
            else:
                continue
        except Exception as e:
            st = {**session.state(), "fire_alert": False, "error": str(e)}
        await ws.send_json(st)


@app.get("/")
async def index():
    return FileResponse(WEB / "index.html")


@app.get("/voices")
async def voices_page():
    """Voice picker: listen to every Timbre voice (generate with python -m eval.voice_samples)."""
    return FileResponse(WEB / "voices.html")


app.mount("/voices", StaticFiles(directory=WEB / "voices", check_dir=False), name="voices")
app.mount("/icons", StaticFiles(directory=WEB / "icons", check_dir=False), name="icons")


@app.get("/manifest.webmanifest")
async def manifest():
    return FileResponse(WEB / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
async def service_worker():
    # served from the root so its scope covers the whole app
    return FileResponse(WEB / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})
