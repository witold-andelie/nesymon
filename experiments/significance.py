"""Paired comparison of two calibration methods with a task-level resampling interval.

Each repetition draws a random 40/60 task split, calibrates both methods on the same calibration tasks, resamples the
test tasks with replacement, and evaluates both methods on the same resampled test tasks. The 95 percent interval of
the paired differences covers both split and test-sampling variability. Also reports, per method, the share of
repetitions whose joint error exceeds alpha.

Run from the repository root:
  python -m experiments.significance --probs data/probs/<model>.jsonl --labels data/labels_eval.csv --rule R1
"""
import argparse
import csv
import os
import random
import statistics as st

from experiments.e0_pilot import build_tasks, pilot_tasks
from experiments.e1_main import thresholds
from nesymon.evaluate import evaluate, split_tasks
from nesymon.labeler import ProbCache
from nesymon.pipeline import load_labels
from rules.dfas import RULES


def paired(tasks, dfa, alpha, a, b, reps=400, seed=0):
    rng = random.Random(seed)
    diffs = {"abstain": [], "joint_error": []}
    over = {a: 0, b: 0}
    vals = {a: {"abstain": [], "joint_error": []}, b: {"abstain": [], "joint_error": []}}
    for _ in range(reps):
        cal, test = split_tasks(tasks, 0.4, rng)
        taus = thresholds(cal, dfa, alpha)
        boot = rng.choices(test, k=len(test))
        res = {m: evaluate(boot, dfa, taus[m]) for m in (a, b)}
        for k in diffs:
            diffs[k].append(res[a][k] - res[b][k])
            for m in (a, b):
                vals[m][k].append(res[m][k])
        for m in (a, b):
            over[m] += res[m]["joint_error"] > alpha
    ci = lambda xs: (sorted(xs)[int(0.025 * len(xs))], sorted(xs)[int(0.975 * len(xs)) - 1])
    out = {}
    for k, xs in diffs.items():
        lo, hi = ci(xs)
        out[f"{k}_diff"] = (round(st.mean(xs), 4), round(lo, 4), round(hi, 4))
    for m in (a, b):
        out[f"{m}_joint_error"] = round(st.mean(vals[m]["joint_error"]), 4)
        out[f"{m}_abstain"] = round(st.mean(vals[m]["abstain"]), 4)
        out[f"{m}_share_above_alpha"] = round(over[m] / reps, 3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probs", required=True)
    ap.add_argument("--labels", default="data/labels_eval.csv")
    ap.add_argument("--rules", default="R1,R2,R9")
    ap.add_argument("--a", default="Ours_Ver")
    ap.add_argument("--b", default="B4_per_step_conformal")
    ap.add_argument("--alpha", type=float, default=0.1)
    ap.add_argument("--reps", type=int, default=400)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    cache, labels = ProbCache(args.probs), load_labels(args.labels)
    rows = []
    for prefix in args.rules.split(","):
        rule_id = next(r for r in RULES if r.startswith(prefix + "_"))
        dfa, _ = RULES[rule_id]
        tasks = list(build_tasks(dfa, cache, labels, rule_id, exclude=pilot_tasks()).values())
        res = paired(tasks, dfa, args.alpha, args.a, args.b, args.reps)
        rows.append({"rule": rule_id, "a": args.a, "b": args.b, "alpha": args.alpha, "reps": args.reps, **res})
        print(rule_id, res)
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
