"""Voice the digital-arrest warning in every female timbre-v3.0 voice, to pick TIMBRE_VOICE by ear.
Run from kavach/: python -m eval.voice_samples   -> listen at http://localhost:8000/voices"""
import asyncio

from app import config, gnani_tts

VOICES = ["Shivani", "Lakshmi", "Kalpana", "Chetana", "Vasudha", "Riyaa", "Tarika"]
OUT = config.ROOT / "web" / "voices"
BEFORE = "Yeh call fraud lag rahi hai. Police kabhi phone pe paise nahi maangti. Call kaat dijiye."


async def main():
    OUT.mkdir(exist_ok=True)
    text = gnani_tts.warning_text("digital_arrest")
    jobs = [(v, text) for v in VOICES] + [("before-romanized-Shivani", BEFORE)]
    for name, t in jobs:
        audio = await gnani_tts.synthesize(t, "hi-IN", name.split("-")[-1])
        if audio:
            (OUT / f"{name}.wav").write_bytes(audio)
        print(name, "ok" if audio else "FAILED")


if __name__ == "__main__":
    asyncio.run(main())
