"""E1 main table: every method on every rule with a linguistic proposition, over repeated task splits.

Needs data/labels.csv and a probability cache.
Run from the repository root:  python -m experiments.e1_main --probs data/probs/<model>.jsonl
"""
import argparse
import csv
import os
import random
import statistics as st

from experiments.e0_pilot import build_tasks, pilot_tasks
from nesymon.baselines import per_step_conformal_tau
from nesymon.core import confidence_grid
from nesymon.evaluate import calibrate, calibrate_two_sided, evaluate, split_tasks
from nesymon.labeler import ProbCache
from nesymon.monitor_prob import violation_probability
from nesymon.pipeline import load_labels
from rules.dfas import RULES

GRID = confidence_grid()
METRICS = ("tau", "joint_error", "miss", "false_alarm", "conditional_error", "abstain", "calls")


def thresholds(cal, dfa, alpha):
    """Threshold of every set-based method for one calibration split.

    All of them are the same monitor with a confidence gate tau; they differ only in how tau is chosen.
    """
    methods = {
        "B2_hard": lambda: 0.0,
        "B3_raw_conf_0.8": lambda: 0.8,
        "B4_per_step_conformal": lambda: per_step_conformal_tau([tr for task in cal for tr in task], dfa, alpha),
        "Ours_Cov": lambda: calibrate(cal, dfa, "cov", alpha, GRID),
        "Ours_SR": lambda: calibrate(cal, dfa, "sr", alpha, GRID),
        "Ours_Ver": lambda: calibrate(cal, dfa, "ver", alpha, GRID),
        "Ours_Ver_two_sided": lambda: calibrate_two_sided(cal, dfa, alpha / 2, alpha / 2, GRID),
    }
    out = {}
    for name, fn in methods.items():
        try:
            out[name] = fn()
        except ValueError:        # too few calibration tasks for this risk level: method not certifiable
            continue
    return out


def brier_of_prob_monitor(tasks, dfa):
    """Ours-Prob: Brier score of the violation probability (role-gated props count as certainly false)."""
    errs = []
    for task in tasks:
        for tr in task:
            steps = [probs for probs, _ in tr]
            truth = [tuple(t[a] for a in dfa.props) for _, t in tr]
            y = float(dfa.run(truth) not in dfa.accepting)
            errs.append((violation_probability(dfa, steps) - y) ** 2)
    return st.mean(errs)


def main_table(tasks, dfa, alpha, reps=20, frac_cal=0.4, seed=0):
    """Returns {method: {metric: (mean, std)}} over repeated task splits for one rule."""
    rng = random.Random(seed)
    runs = {}
    for _ in range(reps):
        cal, test = split_tasks(tasks, frac_cal, rng)
        for method, tau in thresholds(cal, dfa, alpha).items():
            runs.setdefault(method, []).append(evaluate(test, dfa, tau))
    return {m: {k: (st.mean(min(r[k], 1.0) for r in rs), st.pstdev(min(r[k], 1.0) for r in rs)) for k in METRICS}
            for m, rs in runs.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probs", required=True)
    ap.add_argument("--labels", default="data/labels.csv")
    ap.add_argument("--alpha", type=float, default=0.1)
    ap.add_argument("--reps", type=int, default=20)
    ap.add_argument("--out", default="results/e1_main.csv")
    args = ap.parse_args()
    if not (os.path.exists(args.labels) and os.path.exists(args.probs)):
        raise SystemExit("E1 needs human labels and a labeler cache; neither step has been run yet.")
    cache, labels = ProbCache(args.probs), load_labels(args.labels)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["rule", "method", "tasks"] + [f"{k}_{s}" for k in METRICS for s in ("mean", "std")])
        for rule_id, (dfa, _) in RULES.items():
            if dfa.structured == set(dfa.props):
                continue
            tasks = list(build_tasks(dfa, cache, labels, rule_id, exclude=pilot_tasks()).values())
            if len(tasks) < 25:
                print(f"{rule_id}: only {len(tasks)} labelled tasks, skipped")
                continue
            for method, res in main_table(tasks, dfa, args.alpha, args.reps).items():
                w.writerow([rule_id, method, len(tasks)] + [round(x, 4) for k in METRICS for x in res[k]])
            w.writerow([rule_id, "Ours_Prob_brier", len(tasks), round(brier_of_prob_monitor(tasks, dfa), 4)])
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
