"""Figures shown in the README: simulated guarantee and regime sweep (from results/sim_sweeps.csv).

Run from the repository root:  python -m experiments.readme_figures
The overview diagram is rendered separately:  dot -Tpng -Gdpi=150 docs/figures/overview.dot -o docs/figures/overview.png
"""
import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SRC, OUT = "results/sim_sweeps.csv", "docs/figures/simulation.png"
# Fixed categorical order (validated default palette, slots 1-4); text stays in neutral ink.
STYLE = {
    "ver": ("Verdict-level (ours)", "#2a78d6", "o"),
    "two_sided": ("Verdict-level, two-sided", "#eb6834", "s"),
    "cov": ("Coverage-style", "#1baf7a", "^"),
    "hard": ("Hard labels", "#eda100", "D"),
}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def series(rows, sweep, method, x, y):
    pts = sorted((float(r[x]), float(r[y])) for r in rows if r["sweep"] == sweep and r["method"] == method)
    return [p[0] for p in pts], [p[1] for p in pts]


def style_axes(ax, title, xlabel, ylabel):
    ax.set_title(title, fontsize=9, color=INK, loc="left")
    ax.set_xlabel(xlabel, fontsize=8, color=MUTED)
    ax.set_ylabel(ylabel, fontsize=8, color=MUTED)
    ax.tick_params(labelsize=7, colors=MUTED, length=0)
    ax.grid(color=GRID, lw=0.6)
    for s in ax.spines.values():
        s.set_visible(False)


def main():
    rows = list(csv.DictReader(open(SRC)))
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.2))
    ax = axes[0]
    ax.plot([0, 0.3], [0, 0.3], color=MUTED, lw=1, ls="--")
    ax.text(0.205, 0.22, "error = alpha", fontsize=7, color=MUTED, rotation=33)
    for m in ("ver", "two_sided", "cov", "hard"):
        label, color, marker = STYLE[m]
        ax.plot(*series(rows, "E2_alpha", m, "alpha", "joint_error"), color=color, lw=2, marker=marker, ms=5,
                label=label)
    style_axes(ax, "(a) Wrong verdicts stay below alpha", "target alpha", "rate of confident wrong verdicts")
    for i, (key, ylabel, title) in enumerate((("abstain", "abstention rate", "(b) Abstention at alpha = 0.10"),
                                              ("joint_error", "rate of confident wrong verdicts",
                                               "(c) Wrong verdicts at alpha = 0.10"))):
        ax = axes[i + 1]
        for m in ("ver", "cov", "hard"):
            if key == "abstain" and m == "hard":
                continue
            label, color, marker = STYLE[m]
            ax.plot(*series(rows, "E8_regime", m, "p_conf_err", key), color=color, lw=2, marker=marker, ms=5,
                    label=label)
        if key == "joint_error":
            ax.axhline(0.1, color=MUTED, lw=1, ls="--")
        style_axes(ax, title, "rate of confidently wrong judgements", ylabel)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=8, frameon=False, labelcolor=INK)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fig.savefig(OUT, dpi=160, facecolor="#fcfcfb")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
