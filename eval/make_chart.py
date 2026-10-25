"""Results chart for the README / launch post, drawn from eval/results.csv (run `python -m eval.run_eval --audio`
first). Run from kavach/: python -m eval.make_chart   -> eval/results_chart.png

Palette: reference categorical slots 1-3 (blue, orange, aqua), validated all-pairs in light mode with the
dataviz validator. Aqua is below 3:1 on the surface, so every bar carries a direct value label."""
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
SNRS = [("clean", "Clean"), ("20", "20 dB"), ("10", "10 dB"), ("5", "5 dB")]
LAYERS = [("combined", "Kavach (combined)", "#2a78d6"), ("evon", "Evon only", "#eb6834"), ("rules", "Rules only", "#1baf7a")]
SURFACE, INK, INK2, MUTED, GRID, BASE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"


def load():
    rows = list(csv.DictReader(open(HERE / "results.csv", encoding="utf-8")))
    flag = lambda r, k: r[k] == "True"
    recall, false_alarms, n_genuine = {}, {}, None
    for snr, _ in SNRS:
        sub = [r for r in rows if r["snr"] == snr]
        scams, genuine = [r for r in sub if r["label"] == "scam"], [r for r in sub if r["label"] == "normal"]
        n_genuine = len(genuine)
        for key, _, _ in LAYERS:
            recall[key, snr] = 100 * sum(flag(r, key) for r in scams) / len(scams)
            false_alarms.setdefault(key, []).append(sum(flag(r, key) for r in genuine))
    return recall, false_alarms, n_genuine, len(scams)


def main():
    recall, false_alarms, n_genuine, n_scams = load()
    plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 10, "axes.edgecolor": BASE})
    fig = plt.figure(figsize=(10, 5.6), dpi=150, facecolor=SURFACE)
    gs = fig.add_gridspec(1, 2, width_ratios=[2.3, 1], wspace=0.32, left=0.07, right=0.96, top=0.70, bottom=0.17)
    ax1, ax2 = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])

    # left: scams caught at each noise level (bars from zero, 2px surface gap between neighbours)
    width = 0.26
    for i, (key, label, color) in enumerate(LAYERS):
        xs = [j + (i - 1) * width for j in range(len(SNRS))]
        vals = [recall[key, snr] for snr, _ in SNRS]
        bars = ax1.bar(xs, vals, width, color=color, edgecolor=SURFACE, linewidth=2, label=label, zorder=3)
        for b, v in zip(bars, vals):
            ax1.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.0f}", ha="center", va="bottom",
                     fontsize=8.5, color=INK2, zorder=4)
    ax1.set_xticks(range(len(SNRS)), [lab for _, lab in SNRS])
    ax1.set_ylim(0, 112)
    ax1.set_yticks([0, 25, 50, 75, 100])
    ax1.set_title(f"Scams caught (% of {n_scams})", loc="left", fontsize=11.5, weight="bold", color=INK, pad=10)
    ax1.set_xlabel("Background noise  →  louder", color=MUTED)

    # right: false alarms on genuine calls (same at every noise level: show the per-level count)
    counts = {k: v for k, v in false_alarms.items()}
    per_level = {k: max(v) for k, v in counts.items()}
    steady = all(min(v) == max(v) for v in counts.values())
    names = [label for _, label, _ in LAYERS][::-1]
    vals = [per_level[key] for key, _, _ in LAYERS][::-1]
    cols = [color for _, _, color in LAYERS][::-1]
    bars = ax2.barh(names, vals, 0.55, color=cols, edgecolor=SURFACE, linewidth=2, zorder=3)
    for b, v in zip(bars, vals):
        ax2.text(v + 0.06, b.get_y() + b.get_height() / 2, f"{v} of {n_genuine}", va="center", fontsize=9, color=INK2)
    ax2.set_xlim(0, max(vals) + 1.2)
    ax2.set_xticks(range(0, max(vals) + 2))
    ax2.set_title("False alarms on genuine calls", loc="left", fontsize=11.5, weight="bold", color=INK, pad=10)
    ax2.set_xlabel("same at every noise level" if steady else "worst noise level", color=MUTED)
    ax2.tick_params(axis="y", length=0, labelcolor=INK)
    ax2.set_yticks(range(len(names)), [n.replace(" (combined)", "") for n in names])

    for ax in (ax1, ax2):  # recessive chrome: hairline grid, no box
        ax.set_facecolor(SURFACE)
        ax.grid(axis="y" if ax is ax1 else "x", color=GRID, linewidth=0.8, zorder=0)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.spines["left" if ax is ax1 else "bottom"].set_visible(False)
        ax.tick_params(colors=MUTED, labelcolor=INK2)
    ax1.spines["bottom"].set_color(BASE)
    ax2.spines["left"].set_color(BASE)

    fig.text(0.07, 0.93, "Kavach catches scam calls even in heavy background noise", fontsize=16, weight="bold", color=INK)
    fig.text(0.07, 0.875, "Rules alone miss threats with no money ask; Evon alone panics at genuine police calls. "
             "Together: Evon's catch rate, the rules' false-alarm rate.", fontsize=10, color=INK2)
    fig.legend(*ax1.get_legend_handles_labels(), loc="upper left", bbox_to_anchor=(0.062, 0.845), ncol=3,
               frameon=False, fontsize=9.5, handlelength=1.2, labelcolor=INK)
    fig.text(0.07, 0.04, f"{n_scams + n_genuine} synthetic calls (Timbre voices, 8 kHz phone filter, added noise) → Gnani "
             "Prisma → rules + Evon. Synthetic test set written by the author; see README for caveats.",
             fontsize=8, color=MUTED)
    out = HERE / "results_chart.png"
    fig.savefig(out, facecolor=SURFACE)
    print("wrote", out)


if __name__ == "__main__":
    main()
