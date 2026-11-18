"""B1, the LLM judge, on the evaluation tasks: with and without verdict-level conformal risk control.

B1_judge: violation if P(violation) > 0.5; never abstains, no guarantee.
B1_judge_CRC: abstains when max(p, 1 - p) <= tau, with tau chosen by conformal risk control on the same
verdict-level loss and the same task splits as the monitor (experiments/e1_main.py). This asks whether calibrating
an end-to-end judge would be enough without the automaton.

Run from the repository root:
  python -m experiments.e1_judge --judge data/judge/glm-5.3.jsonl --labels data/labels_eval.csv --out results/real_judge
"""
import argparse
import collections
import csv
import json
import os
import random
import statistics as st

from experiments.e0_pilot import pilot_tasks
from experiments.make_annotation_sheet import RAW
from experiments.run_all import linguistic_rules
from nesymon.core import crc_threshold
from nesymon.data import load_all
from nesymon.evaluate import alpha_floor, split_tasks
from nesymon.labeler import ProbCache
from nesymon.pipeline import assemble, load_labels
from rules.dfas import RULES, applies

GRID = [0.5 + k / 200 for k in range(101)]


def judge_tasks(rule_id, judge, cache, labels, exclude):
    """{(domain, task_id): [(p_violation, true_violation), ...]} in the order build_tasks uses."""
    dfa, _ = RULES[rule_id]
    labelled = {k[0] for k in labels}
    tasks = collections.defaultdict(list)
    for t in load_all(RAW):
        key = (t.domain, t.task_id)
        if t.traj_id not in labelled or not applies(rule_id, t.domain) or key in exclude:
            continue
        p = judge.get((t.traj_id, rule_id))
        if p is None:
            continue
        data = assemble(t, dfa, cache, labels)
        truth = [tuple(tr[a] for a in dfa.props) for _, tr in data]
        tasks[key].append((p, dfa.run(truth) not in dfa.accepting))
    return dict(tasks)


def loss(item, tau, error_type="any"):
    p, violated = item
    if max(p, 1 - p) <= tau:
        return 0.0
    said = p > 0.5
    if said == violated:
        return 0.0
    return float(error_type == "any" or (error_type == "miss") == violated)


def metrics(tasks, tau):
    per = {"joint_error": [], "miss": [], "false_alarm": [], "abstain": []}
    for task in tasks:
        per["joint_error"].append(st.mean(loss(x, tau) for x in task))
        per["miss"].append(st.mean(loss(x, tau, "miss") for x in task))
        per["false_alarm"].append(st.mean(loss(x, tau, "false_alarm") for x in task))
        per["abstain"].append(st.mean(float(max(x[0], 1 - x[0]) <= tau) for x in task))
    return {k: st.mean(v) for k, v in per.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", required=True)
    ap.add_argument("--labels", default="data/labels_eval.csv")
    ap.add_argument("--probs", default="data/probs/mlx-community__Qwen3.5-4B-4bit.jsonl",
                    help="only used to assemble trajectories; the judge does not use it")
    ap.add_argument("--alpha", type=float, default=0.1)
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--out", default="results/real_judge")
    args = ap.parse_args()
    judge, no_verdict = {}, 0
    for r in map(json.loads, open(args.judge)):
        # an answer without a verdict carries no information: P = 0.5 (the calibrated judge abstains on it)
        no_verdict += r["p_violation"] is None
        judge[(r["traj_id"], r["rule"])] = 0.5 if r["p_violation"] is None else r["p_violation"]
    print(f"{len(judge)} judge answers, {no_verdict} without a verdict (set to 0.5)")
    cache, labels = ProbCache(args.probs), load_labels(args.labels)
    os.makedirs(args.out, exist_ok=True)
    rows = []
    for rule_id in linguistic_rules():
        tasks = list(judge_tasks(rule_id, judge, cache, labels, pilot_tasks()).values())
        n_cal = round(0.4 * len(tasks))
        if n_cal < 2 or args.alpha < alpha_floor(n_cal):
            continue
        rng, runs = random.Random(0), collections.defaultdict(list)
        for _ in range(args.reps):
            cal, test = split_tasks(tasks, 0.4, rng)
            runs["B1_judge"].append({"tau": 0.0, **metrics(test, 0.0)})
            tau = crc_threshold(cal, loss, args.alpha, GRID)
            tau = min(tau, 1.0)
            runs["B1_judge_CRC"].append({"tau": tau, **metrics(test, tau)})
        n_traj = sum(map(len, tasks))
        for method, rs in runs.items():
            rows.append({"rule": rule_id, "method": method, "alpha": args.alpha, "tasks": len(tasks),
                         "trajectories": n_traj,
                         **{f"{k}_{s}": round(f([r[k] for r in rs]), 4)
                            for k in ("tau", "joint_error", "miss", "false_alarm", "abstain")
                            for s, f in (("mean", st.mean), ("std", st.pstdev))}})
    if not rows:
        raise SystemExit("not enough judged tasks for calibration yet")
    with open(os.path.join(args.out, "e1_judge.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r["rule"][:3], f'{r["method"]:<13}', "trajs", r["trajectories"], "tau", r["tau_mean"],
              "joint", r["joint_error_mean"], "abstain", r["abstain_mean"])


if __name__ == "__main__":
    main()
