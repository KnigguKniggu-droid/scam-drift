"""Lead chart: scam recall vs false alarms on real legitimate texts, per model.

Reads results/real_ham_fix_probe.json (numbers only from that file).
Writes figures/lead_chart.png.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "results" / "real_ham_fix_probe.json"
OUT = ROOT / "figures" / "lead_chart.png"

MODELS = [
    ("word_2012", "2012 filter", "#9aa5b1"),
    ("word_naive_fix", "Retrained on modern scams", "#d9822b"),
    ("word_fix_real_ham", "+ real legit texts", "#2b6cb0"),
]
METRICS = [
    ("late_2022_24_recall", "2022-24 scams caught\n(higher is better)"),
    ("fa_india_heldout_brands", "False alarms: real India legit texts\n(held-out brands, lower is better)"),
    ("fa_moz_pt", "False alarms: real Mozambique legit texts\n(lower is better)"),
]


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=150)
    width = 0.26
    for i, (key, label, color) in enumerate(MODELS):
        rates = [data[key][m]["rate"] for m, _ in METRICS]
        xs = [j + (i - 1) * width for j in range(len(METRICS))]
        bars = ax.bar(xs, rates, width, label=label, color=color)
        for b, r in zip(bars, rates):
            ax.text(b.get_x() + b.get_width() / 2, r + 0.015, f"{r:.3f}",
                    ha="center", va="bottom", fontsize=8)
    ax.set_xticks(range(len(METRICS)))
    ax.set_xticklabels([t for _, t in METRICS], fontsize=9)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("Rate")
    ax.set_title("Catching modern scams costs false alarms on real legitimate texts")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=9, loc="upper right", ncol=3)
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
