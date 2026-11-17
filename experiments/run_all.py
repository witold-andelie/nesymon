"""Run every real-data experiment for one labeler cache and write tables and figures.

E1 main table, E2 guarantee against alpha, E4 difficulty by trajectory length, E6 cross-domain shift,
E7 error autocorrelation, E8 regime under injected confident errors. Pilot tasks are excluded unless
--include-pilot is given (useful only for a dry run, since the definitions were tuned on them).

Run from the repository root:
  python -m experiments.run_all --probs data/probs/<model>.jsonl --labels data/labels.csv --out results/real
"""
import argparse
import csv
import math
import os

from experiments.analyses import (alpha_sweep, cross_domain, difficulty_buckets, error_autocorrelation,
                                  regime_sweep)
from experiments.e0_pilot import build_tasks, pilot_tasks
from experiments.e1_main import METRICS, brier_of_prob_monitor, main_table
from nesymon.evaluate import alpha_floor, calibrate
from nesymon.labeler import ProbCache
from nesymon.pipeline import load_labels
from rules.dfas import RULES, applies

ALPHAS = (0.05, 0.075, 0.1, 0.15, 0.2, 0.3)
FRAC_CAL = 0.4


def write_csv(path, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def linguistic_rules():
    return [r for r, (dfa, _) in RULES.items() if dfa.structured != set(dfa.props)]


def figures(out, e2_rows, e8_rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(os.path.join(out, "figures"), exist_ok=True)
    for rule in sorted({r["rule"] for r in e2_rows}):
        rows = sorted((r for r in e2_rows if r["rule"] == rule), key=lambda r: r["alpha"])
        a = [r["alpha"] for r in rows]
        fig, ax = plt.subplots(figsize=(4, 3.2))
        ax.plot([0, max(a)], [0, max(a)], color="#999999", lw=1, ls="--", label="alpha")
        ax.plot(a, [r["joint_error"] for r in rows], marker="o", label="joint error (guaranteed)")
        ax.plot(a, [r["conditional_error"] for r in rows], marker="s", label="conditional error")
        ax.plot(a, [r["abstain"] for r in rows], marker="^", label="abstention")
        ax.set_xlabel("alpha")
        ax.set_title(rule, fontsize=8)
        ax.legend(fontsize=6)
        fig.tight_layout()
        fig.savefig(os.path.join(out, "figures", f"e2_{rule}.png"), dpi=150)
        plt.close(fig)
    for rule in sorted({r["rule"] for r in e8_rows}):
        rows = sorted((r for r in e8_rows if r["rule"] == rule), key=lambda r: r["rate"])
        x = [r["rate"] for r in rows]
        fig, ax = plt.subplots(figsize=(4, 3.2))
        ax.plot(x, [r["hard_error"] for r in rows], marker="o", label="hard-label error")
        ax.plot(x, [r["joint_error"] for r in rows], marker="s", label="verdict-level joint error")
        ax.plot(x, [r["abstain"] for r in rows], marker="^", label="abstention")
        ax.set_xlabel("injected confident-error rate")
        ax.set_title(rule, fontsize=8)
        ax.legend(fontsize=6)
        fig.tight_layout()
        fig.savefig(os.path.join(out, "figures", f"e8_{rule}.png"), dpi=150)
        plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probs", required=True)
    ap.add_argument("--labels", default="data/labels.csv")
    ap.add_argument("--out", default="results/real")
    ap.add_argument("--alpha", type=float, default=0.1)
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--include-pilot", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    cache, labels = ProbCache(args.probs), load_labels(args.labels)
    exclude = frozenset() if args.include_pilot else pilot_tasks()

    e1, e2, e4, e6, e7, e8, sizes = [], [], [], [], [], [], []
    for rule_id in linguistic_rules():
        dfa, _ = RULES[rule_id]
        by_task = build_tasks(dfa, cache, labels, rule_id, exclude=exclude)
        tasks = list(by_task.values())
        n_cal = round(FRAC_CAL * len(tasks))
        sizes.append({"rule": rule_id, "tasks": len(tasks), "trajectories": sum(map(len, tasks)),
                      "calibration_tasks": n_cal, "alpha_floor": round(alpha_floor(n_cal), 4)})
        if n_cal < 2:
            continue
        usable = [a for a in ALPHAS if a >= alpha_floor(n_cal)]
        if args.alpha >= alpha_floor(n_cal):
            for method, res in main_table(tasks, dfa, args.alpha, reps=min(args.reps, 50)).items():
                e1.append({"rule": rule_id, "method": method, "alpha": args.alpha,
                           **{f"{k}_{s}": round(v, 4) for k in METRICS for s, v in zip(("mean", "std"), res[k])}})
            raw, scaled = brier_of_prob_monitor(tasks, dfa)
            e1.append({"rule": rule_id, "method": "Ours_Prob_raw", "alpha": args.alpha, "brier_mean": round(raw, 4)})
            e1.append({"rule": rule_id, "method": "Ours_Prob_platt", "alpha": args.alpha,
                       "brier_mean": round(scaled, 4)})
            e8 += [{"rule": rule_id, **{k: round(v, 4) for k, v in r.items()}}
                   for r in regime_sweep(tasks, dfa, alpha=args.alpha, reps=max(10, args.reps // 4))]
        if usable:
            e2 += [{"rule": rule_id, **{k: round(min(v, 1.0), 4) for k, v in r.items()}}
                   for r in alpha_sweep(tasks, dfa, alphas=usable, reps=args.reps)]
        all_tasks = [tr for task in tasks for tr in task]
        tau = calibrate(tasks, dfa, "ver", max(args.alpha, alpha_floor(len(tasks))), [x / 100 for x in range(50, 101)])
        e4 += [{"rule": rule_id, "tau": tau, **r} for r in difficulty_buckets(tasks, dfa, tau)]
        e7.append({"rule": rule_id, "error_autocorrelation": round(error_autocorrelation(tasks, dfa), 4),
                   "judged_trajectories": len(all_tasks)})
        if applies(rule_id, "retail") and applies(rule_id, "airline"):
            by_domain = {d: [t for (dom, _), t in by_task.items() if dom == d] for d in ("retail", "airline")}
            for src, dst in (("retail", "airline"), ("airline", "retail")):
                if len(by_domain[src]) >= 10 and by_domain[dst] and args.alpha >= alpha_floor(len(by_domain[src])):
                    r = cross_domain(by_domain[src], by_domain[dst], dfa, alpha=args.alpha)
                    e6.append({"rule": rule_id, "calibrate_on": src, "test_on": dst,
                               **{k: (round(v, 4) if isinstance(v, float) and not math.isinf(v) else v)
                                  for k, v in r.items()}})

    for name, rows in (("sizes", sizes), ("e1_main", e1), ("e2_alpha", e2), ("e4_length", e4),
                       ("e6_shift", e6), ("e7_autocorrelation", e7), ("e8_regime", e8)):
        write_csv(os.path.join(args.out, f"{name}.csv"), rows)
    figures(args.out, e2, e8)
    print(f"wrote results to {args.out}: " + ", ".join(f"{n}={len(r)}" for n, r in
          (("rules", sizes), ("e1", e1), ("e2", e2), ("e4", e4), ("e6", e6), ("e7", e7), ("e8", e8))))


if __name__ == "__main__":
    main()
