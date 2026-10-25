"""Benchmark: detection (rules / Evon / combined), time-to-warning and Prisma WER at each noise level.
Run from kavach/:
  python -m eval.run_eval --text     # transcripts only, no API calls (rules, + Evon if EVON_URL set)
  python -m eval.run_eval --audio    # full pipeline on eval/audio/*.wav via Prisma (run make_calls first)
Writes eval/results.csv and prints a markdown table for the README."""
import argparse
import asyncio
import csv
import json
import re
from pathlib import Path

from app import config, evon_judge, gnani_stt, rules
from app.pipeline import combine

HERE = Path(__file__).resolve().parent
SNRS = ["clean", "20", "10", "5"]


def wer(ref: str, hyp: str) -> float:
    r, h = re.findall(r"\w+", ref.lower()), re.findall(r"\w+", hyp.lower())
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)] / max(1, len(r))


async def detect(lines, use_evon: bool):
    """Feed lines one by one like a live call. Returns rule/evon/combined flags and lines-to-warning."""
    text, rule_risk, first_line = "", 0, None
    for n, line in enumerate(lines, 1):
        text = f"{text} {line}".strip()
        rule_risk = max(rule_risk, rules.score(text)["score"])
        if rule_risk >= config.ALERT_THRESHOLD and first_line is None:
            first_line = n
    evon_risk = None
    if use_evon:
        res = await evon_judge.judge(text)
        evon_risk = res["risk"] if res else None
    combined = combine(rule_risk, evon_risk)
    return {"rules": rule_risk >= config.ALERT_THRESHOLD,
            "evon": None if evon_risk is None else evon_risk >= config.ALERT_THRESHOLD,
            "combined": combined >= config.ALERT_THRESHOLD,
            "lines_to_warning": first_line, "rule_risk": rule_risk, "evon_risk": evon_risk}


def metrics(rows, key):
    rows = [r for r in rows if r[key] is not None]
    tp = sum(r[key] and r["label"] == "scam" for r in rows)
    fp = sum(r[key] and r["label"] == "normal" for r in rows)
    fn = sum((not r[key]) and r["label"] == "scam" for r in rows)
    normals = sum(r["label"] == "normal" for r in rows)
    if not rows:
        return None
    return {"precision": tp / max(1, tp + fp), "recall": tp / max(1, tp + fn), "false_alarm": fp / max(1, normals)}


async def main(mode: str):
    calls = json.loads((HERE / "scripts" / "calls.json").read_text(encoding="utf-8"))
    use_evon = bool(config.EVON_URL)
    rows = []
    levels = ["text"] if mode == "text" else SNRS
    for snr in levels:
        for c in calls:
            ref = " ".join(c["lines"])
            if mode == "text":
                lines, w = c["lines"], None
            else:
                path = HERE / "audio" / f"{c['id']}_{snr}.wav"
                lang = {"en": "en-IN", "ta": "ta-IN", "bn": "bn-IN"}.get(c["lang"], "hi-IN")
                cache = HERE / "audio" / f"{c['id']}_{snr}.{lang}.txt"  # each file is transcribed once
                if cache.exists():
                    hyp = cache.read_text(encoding="utf-8")
                else:
                    try:
                        hyp = await gnani_stt.transcribe(path.read_bytes(), lang)
                        cache.write_text(hyp, encoding="utf-8")
                    except Exception as e:
                        print(f"[prisma] {c['id']} {snr}: {e}")
                        hyp = ""
                # scripts are romanized but Prisma writes Hindi/Tamil/Bengali in native script,
                # so WER is only comparable on the English calls
                lines, w = [hyp], (wer(ref, hyp) if c["lang"] == "en" else None)
            d = await detect(lines, use_evon)
            rows.append({"id": c["id"], "label": c["label"], "type": c["type"], "lang": c["lang"], "snr": snr,
                         "wer": w, **d})
    with open(HERE / "results.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)

    print(f"\n{len(calls)} synthetic calls ({sum(c['label'] == 'scam' for c in calls)} scam). Threshold {config.ALERT_THRESHOLD}.\n")
    print("| Noise | Layer | Precision | Recall | False alarms | Prisma WER (English calls) |")
    print("|---|---|---|---|---|---|")
    for snr in levels:
        sub = [r for r in rows if r["snr"] == snr]
        ws = [r["wer"] for r in sub if r["wer"] is not None]
        wer_s = f"{sum(ws) / len(ws):.0%}" if ws else "n/a"
        for key in ["rules", "evon", "combined"]:
            m = metrics(sub, key)
            if m:
                print(f"| {snr} | {key} | {m['precision']:.0%} | {m['recall']:.0%} | {m['false_alarm']:.0%} | {wer_s} |")
    lt = [r["lines_to_warning"] for r in rows if r["label"] == "scam" and r["lines_to_warning"]]
    if mode == "text" and lt:
        print(f"\nRule layer warns after {sum(lt) / len(lt):.1f} sentences on average (scam calls).")
    misses = [r["id"] for r in rows if r["label"] == "scam" and not r["combined"]]
    false_alarms = [r["id"] for r in rows if r["label"] == "normal" and r["combined"]]
    print(f"Missed scams: {misses}\nFalse alarms: {false_alarms}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--text", action="store_true")
    g.add_argument("--audio", action="store_true")
    a = ap.parse_args()
    asyncio.run(main("audio" if a.audio else "text"))
