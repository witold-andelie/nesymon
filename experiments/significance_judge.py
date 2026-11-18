"""Paired comparison: the automaton monitor (verdict-level loss) against the LLM judge with the same calibration.

Both are calibrated on the same calibration tasks and scored on the same resampled test tasks in every repetition,
so the 95 percent interval of the paired differences covers split and test-sampling variability.

Run from the repository root:
  python -m experiments.significance_judge --probs data/probs/<model>.jsonl --judge data/judge/glm-5.3.jsonl \
      --labels data/labels_eval.csv --out results/real_judge/significance_vs_4B.csv
"""
import argparse
import csv
import json
import os
import random
import statistics as st

from experiments.e0_pilot import build_tasks, pilot_tasks
from experiments.e1_judge import GRID as JUDGE_GRID
from experiments.e1_judge import judge_tasks, loss, metrics
from experiments.e1_main import GRID
from experiments.run_all import linguistic_rules
from nesymon.core import crc_threshold
from nesymon.evaluate import calibrate, evaluate
from nesymon.labeler import ProbCache
from nesymon.pipeline import load_labels
from rules.dfas import RULES


def paired(mon, jud, dfa, alpha, reps=400, seed=0, frac_cal=0.4):
    rng = random.Random(seed)
    n = len(mon)
    rec = {k: [] for k in ("mon_err", "mon_abs", "jud_err", "jud_abs")}
    for _ in range(reps):
        idx = list(range(n))
        rng.shuffle(idx)
        n_cal = round(frac_cal * n)
        cal, test = idx[:n_cal], idx[n_cal:]
        tau_m = calibrate([mon[i] for i in cal], dfa, "ver", alpha, GRID)
        tau_j = min(crc_threshold([jud[i] for i in cal], loss, alpha, JUDGE_GRID), 1.0)
        boot = rng.choices(test, k=len(test))
        rm = evaluate([mon[i] for i in boot], dfa, tau_m)
        rj = metrics([jud[i] for i in boot], tau_j)
        rec["mon_err"].append(rm["joint_error"]); rec["mon_abs"].append(rm["abstain"])
        rec["jud_err"].append(rj["joint_error"]); rec["jud_abs"].append(rj["abstain"])

    def ci(xs):
        xs = sorted(xs)
        return round(st.mean(xs), 4), round(xs[int(0.025 * len(xs))], 4), round(xs[int(0.975 * len(xs)) - 1], 4)

    d_abs = [a - b for a, b in zip(rec["mon_abs"], rec["jud_abs"])]
    d_err = [a - b for a, b in zip(rec["mon_err"], rec["jud_err"])]
    return {"abstain_diff_monitor_minus_judge": ci(d_abs), "joint_error_diff_monitor_minus_judge": ci(d_err),
            "share_judge_abstains_less": round(sum(d > 0 for d in d_abs) / reps, 3),
            "monitor_joint_error": round(st.mean(rec["mon_err"]), 4), "monitor_abstain": round(st.mean(rec["mon_abs"]), 4),
            "judge_joint_error": round(st.mean(rec["jud_err"]), 4), "judge_abstain": round(st.mean(rec["jud_abs"]), 4),
            "monitor_share_above_alpha": round(sum(e > alpha for e in rec["mon_err"]) / reps, 3),
            "judge_share_above_alpha": round(sum(e > alpha for e in rec["jud_err"]) / reps, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probs", required=True)
    ap.add_argument("--judge", required=True)
    ap.add_argument("--labels", default="data/labels_eval.csv")
    ap.add_argument("--alpha", type=float, default=0.1)
    ap.add_argument("--reps", type=int, default=400)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    judge = {}
    for r in map(json.loads, open(args.judge)):
        judge[(r["traj_id"], r["rule"])] = 0.5 if r["p_violation"] is None else r["p_violation"]
    cache, labels = ProbCache(args.probs), load_labels(args.labels)
    rows = []
    for rule_id in linguistic_rules():
        dfa, _ = RULES[rule_id]
        mon = build_tasks(dfa, cache, labels, rule_id, exclude=pilot_tasks())
        jud = judge_tasks(rule_id, judge, cache, labels, pilot_tasks())
        if list(mon) != list(jud) or any(len(mon[k]) != len(jud[k]) for k in mon):
            raise SystemExit(f"{rule_id}: monitor and judge task lists are not aligned")
        res = paired(list(mon.values()), list(jud.values()), dfa, args.alpha, args.reps)
        rows.append({"rule": rule_id, "alpha": args.alpha, "reps": args.reps, "tasks": len(mon), **res})
        print(rule_id, res, flush=True)
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
