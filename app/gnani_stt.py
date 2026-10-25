"""Prisma adapter (REST, docs.gnani.ai/api/STT/speech-to-text).
Accepts WAV/MP3/OGG/FLAC/AAC/M4A, 8-44.1 kHz, up to 60 s per request. The web page sends short WAV chunks;
Telegram voice notes and phone call recordings (M4A, AMR, MP3, OGG; often minutes long) are converted to
16 kHz WAV with ffmpeg (system install, or the free one bundled by the imageio-ffmpeg package), capped at
MAX_AUDIO_S to protect credits.

In testing, single requests for 10-15 s files sometimes returned only the first sentence or two, so WAV
longer than MAX_SEGMENT_S is split at its quietest points and the segments are transcribed separately."""
import asyncio
import io
import os
import shutil
import subprocess
import tempfile
import wave

import httpx
import numpy as np

from . import config

MIN_SEGMENT_S, MAX_SEGMENT_S = 3.0, 7.0
# Gnani allows one active Prisma request per key (HTTP 429 "Only 1 active request is allowed at a time"),
# so every request in the process - live calls, Telegram, recording checks - queues on one gate.
_gate = None
RETRIES_429 = 5


def _prisma_gate() -> asyncio.Semaphore:
    global _gate
    if _gate is None:
        _gate = asyncio.Semaphore(1)
    return _gate


def ffmpeg_exe():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def to_wav(data: bytes) -> bytes:
    """Any audio -> 16 kHz mono WAV, first MAX_AUDIO_S seconds. Short WAV (the live page's chunks) passes through."""
    if data[:4] == b"RIFF":
        return data
    exe = ffmpeg_exe()
    if not exe:
        return data  # Prisma accepts MP3/OGG/M4A as-is, just without splitting
    # Temp files, not pipes, both ways: M4A from phone recorders often keeps its index ("moov") at the end, which
    # ffmpeg can't reach on stdin; and WAV written to stdout gets a bogus length in its header.
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = os.path.join(tmp, "in"), os.path.join(tmp, "out.wav")
        with open(src, "wb") as f:
            f.write(data)
        p = subprocess.run(
            [exe, "-loglevel", "error", "-i", src, "-t", str(config.MAX_AUDIO_S),
             "-ac", "1", "-ar", "16000", "-map_metadata", "-1", dst],
            capture_output=True,
        )
        if p.returncode != 0 or not os.path.exists(dst):
            raise RuntimeError(f"could not decode audio: {p.stderr.decode(errors='replace')[-200:]}")
        with open(dst, "rb") as f:
            return f.read()


def wav_seconds(data: bytes) -> float:
    with wave.open(io.BytesIO(data)) as w:
        return w.getnframes() / w.getframerate()


def split_wav(data: bytes) -> list:
    """Split 16-bit WAV into segments of MIN..MAX_SEGMENT_S, cutting at the quietest 50 ms window."""
    with wave.open(io.BytesIO(data)) as w:
        sr, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        if width != 2:
            return [data]
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1).astype(np.int16)
    if len(x) <= MAX_SEGMENT_S * sr:
        return [data]
    win = sr // 20
    segments, start = [], 0
    while len(x) - start > MAX_SEGMENT_S * sr:
        lo, hi = start + int(MIN_SEGMENT_S * sr), start + int(MAX_SEGMENT_S * sr)
        energy = np.convolve(x[lo:hi].astype(np.float32) ** 2, np.ones(win), mode="valid")
        cut = lo + int(np.argmin(energy)) + win // 2
        segments.append(x[start:cut])
        start = cut
    segments.append(x[start:])
    out = []
    for seg in segments:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(seg.tobytes())
        out.append(buf.getvalue())
    return out


def _filename(data: bytes) -> str:
    return "audio.ogg" if data[:4] == b"OggS" else "audio.mp3" if data[:3] == b"ID3" else "audio.wav"


async def _request(c: httpx.AsyncClient, audio: bytes, language: str) -> str:
    for attempt in range(RETRIES_429 + 1):
        async with _prisma_gate():
            r = await c.post(
                config.PRISMA_URL,
                headers={"X-API-Key-ID": config.GNANI_API_KEY},
                files={"audio_file": (_filename(audio), audio)},
                data={"language_code": language},
            )
        if r.status_code == 429 and attempt < RETRIES_429:  # another client using the same key
            await asyncio.sleep(0.5 * (attempt + 1))
            continue
        if r.status_code != 200:
            raise RuntimeError(f"Prisma {r.status_code}: {r.text[:200]}")
        return r.json().get("transcript", "") or ""


async def transcribe(audio: bytes, language: str = None) -> str:
    if not config.GNANI_API_KEY:
        raise RuntimeError("GNANI_API_KEY not set in .env (create one at app.gnani.ai)")
    audio = to_wav(audio)
    parts = split_wav(audio) if audio[:4] == b"RIFF" else [audio]
    async with httpx.AsyncClient(timeout=30) as c:
        texts = [await _request(c, p, language or config.LANGUAGE) for p in parts]
    return " ".join(t.strip() for t in texts if t.strip())
