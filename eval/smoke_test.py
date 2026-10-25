"""One real round trip: Timbre speaks a scam line -> Prisma transcribes it -> Kavach scores it.
Run from kavach/: python -m eval.smoke_test"""
import asyncio

from app import config, gnani_stt, gnani_tts
from app.pipeline import CallSession

LINE = "Main CBI se bol raha hoon. Aapke naam pe arrest warrant hai. Yeh baat kisi ko mat batana, abhi paise transfer kijiye."


async def main():
    print("key loaded:", bool(config.GNANI_API_KEY), "| length", len(config.GNANI_API_KEY))
    audio = await gnani_tts.synthesize(LINE, "hi-IN", "Avinash")
    if not audio:
        raise SystemExit("Timbre failed (see log above)")
    print(f"Timbre OK: {len(audio)} bytes of WAV")
    text = await gnani_stt.transcribe(audio, "hi-IN")
    print("Prisma transcript:", text)
    st = await CallSession(use_evon=False, send_alerts=False).add_text(text, final=True)
    print(f"Kavach: {st['level']} risk={st['risk']} type={st['scam_type']} reasons={st['reasons']}")
    warn = await gnani_tts.synthesize(st["warning_text"] or gnani_tts.CAUTION_HI)
    print("Warning clip:", f"{len(warn)} bytes" if warn else "failed")


if __name__ == "__main__":
    asyncio.run(main())
