"""Phone-call simulation helpers: 8 kHz band-limited audio and noise mixing at a target SNR (numpy only)."""
import io
import wave

import numpy as np


def read_wav(data: bytes):
    with wave.open(io.BytesIO(data)) as w:
        sr, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    x = np.frombuffer(raw, dtype={1: np.int8, 2: np.int16, 4: np.int32}[width]).astype(np.float32)
    x /= float(2 ** (8 * width - 1))
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


def write_wav(x: np.ndarray, sr: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


def resample(x: np.ndarray, sr: int, target: int) -> np.ndarray:
    if sr == target:
        return x
    n = int(len(x) * target / sr)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def phone_filter(x: np.ndarray, sr: int, target_sr: int = 8000) -> np.ndarray:
    """Downsample to 8 kHz, band-pass 300-3400 Hz (FFT mask), light compression."""
    y = resample(x, sr, target_sr)
    spec = np.fft.rfft(y)
    f = np.fft.rfftfreq(len(y), 1 / target_sr)
    spec[(f < 300) | (f > 3400)] = 0
    y = np.fft.irfft(spec, n=len(y))
    y = np.tanh(2.0 * y) / np.tanh(2.0)  # soft compression
    return (0.9 * y / (np.abs(y).max() + 1e-9)).astype(np.float32)


def synthetic_noise(n: int, sr: int, kind: str, seed: int = 0) -> np.ndarray:
    """Stand-in noise when no real clips (MUSAN/Freesound) are provided."""
    rng = np.random.default_rng(seed)
    white = rng.standard_normal(n).astype(np.float32)
    if kind == "fan":  # brown-ish hum
        y = np.cumsum(white)
        y -= np.convolve(y, np.ones(400) / 400, mode="same")
    elif kind == "traffic":  # low rumble with swells
        y = np.convolve(white, np.ones(40) / 40, mode="same") * (1 + 0.6 * np.sin(np.arange(n) / sr * 0.7))
    else:  # "chatter"/"tv": amplitude-modulated band noise, speech-like rhythm
        env = np.abs(np.convolve(rng.standard_normal(n), np.ones(sr // 8) / (sr // 8), mode="same"))
        y = np.convolve(white, np.ones(3) / 3, mode="same") * (env / (env.max() + 1e-9))
    return (y / (np.abs(y).max() + 1e-9)).astype(np.float32)


def mix_at_snr(speech: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    if len(noise) < len(speech):
        noise = np.tile(noise, int(np.ceil(len(speech) / len(noise))))
    noise = noise[: len(speech)]
    ps, pn = np.mean(speech ** 2), np.mean(noise ** 2) + 1e-12
    y = speech + noise * np.sqrt(ps / (pn * 10 ** (snr_db / 10)))
    return (y / max(1.0, np.abs(y).max())).astype(np.float32)
