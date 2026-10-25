"""End-to-end test of /check-recording, the way a phone automation app would call it: builds M4A "call
recordings" from benchmark audio and POSTs them as a raw body with the token header.
Run from kavach/ with the server running: python -m eval.recording_check"""
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

from app import config, gnani_stt

HERE = Path(__file__).resolve().parent
RECORDINGS = {
    "scam_call.m4a": ["n6_10", "da1_10", "co5_10"],     # a normal start, then a digital-arrest pitch
    "normal_call.m4a": ["n1_10", "n9_10", "h1_10"],      # doctor, medicine reminder, genuine police check
}


def make_m4a(parts, out: Path):
    exe = gnani_stt.ffmpeg_exe()
    inputs = sum([["-i", str(HERE / "audio" / f"{p}.wav")] for p in parts], [])
    graph = "".join(f"[{i}:a]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[a]"
    subprocess.run([exe, "-loglevel", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[a]",
                    "-c:a", "aac", "-b:a", "48k", str(out)], check=True)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        for name, parts in RECORDINGS.items():
            path = Path(tmp) / name
            make_m4a(parts, path)
            t0 = time.time()
            r = httpx.post("http://127.0.0.1:8000/check-recording", content=path.read_bytes(), timeout=180,
                           headers={"X-Kavach-Token": config.UPLOAD_TOKEN, "X-Filename": name,
                                    "Content-Type": "audio/mp4"})
            d = r.json()
            print(f"{name}: HTTP {r.status_code}, {path.stat().st_size // 1024} KB, {time.time() - t0:.1f}s")
            print(f"  -> {d.get('level')} risk={d.get('risk')} type={d.get('scam_type')} alerted={d.get('alerted')}")
            print(f"  notify: {d.get('notify')!r}")
            print(f"  heard: {d.get('transcript', '')[:160]}...")


if __name__ == "__main__":
    main()
