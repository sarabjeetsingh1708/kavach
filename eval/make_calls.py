"""Timbre -> audio for every script, phone filter, noise at 4 levels.
Run from kavach/: python -m eval.make_calls [--noise-dir path/to/wavs]
Output: eval/audio/<id>_<snr>.wav  (snr in clean,20,10,5). TTS clips are cached so credits are spent once."""
import argparse
import asyncio
import json
from pathlib import Path

import numpy as np

from app import gnani_tts
from eval.audio_utils import mix_at_snr, phone_filter, read_wav, synthetic_noise, write_wav

HERE = Path(__file__).resolve().parent
SNRS = ["clean", 20, 10, 5]
LANG = {"hi": "hi-IN", "en": "en-IN", "ta": "ta-IN", "bn": "bn-IN"}
NOISE_KINDS = ["tv", "traffic", "chatter", "fan"]
VOICES = ["Avinash", "Shivani"]  # timbre-v3.0 voices speak every supported language


def load_noises(noise_dir):
    if noise_dir:
        clips = []
        for p in sorted(Path(noise_dir).glob("*.wav")):
            x, sr = read_wav(p.read_bytes())
            clips.append(phone_filter(x, sr))
        if clips:
            return clips
    return [synthetic_noise(8000 * 30, 8000, k, seed=i) for i, k in enumerate(NOISE_KINDS)]


async def main(noise_dir=None):
    calls = json.loads((HERE / "scripts" / "calls.json").read_text(encoding="utf-8"))
    noises = load_noises(noise_dir)
    out = HERE / "audio"
    out.mkdir(exist_ok=True)
    for i, call in enumerate(calls):
        pieces = []
        for n, line in enumerate(call["lines"]):
            # caller and listener: alternate a male and a female Timbre voice
            audio = await gnani_tts.synthesize(line, LANG.get(call["lang"], "hi-IN"), VOICES[n % 2])
            if audio is None:
                raise SystemExit("Timbre call failed (see [timbre] log above). Check GNANI_API_KEY in .env.")
            x, sr = read_wav(audio)
            pieces += [phone_filter(x, sr), np.zeros(4000, np.float32)]
        speech = np.concatenate(pieces)
        for snr in SNRS:
            y = speech if snr == "clean" else mix_at_snr(speech, noises[i % len(noises)], snr)
            (out / f"{call['id']}_{snr}.wav").write_bytes(write_wav(y, 8000))
        print(f"[{i + 1}/{len(calls)}] {call['id']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--noise-dir", help="folder of real noise .wav clips (MUSAN / Freesound)")
    asyncio.run(main(ap.parse_args().noise_dir))
