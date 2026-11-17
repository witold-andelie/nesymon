"""E0 pilot gate: hard-label error and verdict-changing confident error per rule.

Needs data/labels.csv (human labels) and a probability cache for one labeler model.
Run from the repository root:  python -m experiments.e0_pilot --probs data/probs/<model>.jsonl
"""
import argparse
import collections
import json
import os

from nesymon.core import loss_verdict
from nesymon.data import load_all
from nesymon.evaluate import bootstrap_ci, evaluate
from nesymon.labeler import ProbCache
from nesymon.pipeline import assemble, load_labels
from rules.dfas import RULES, applies

RAW = "data/raw/tau-bench/historical_trajectories"
CONFIDENT_TAU = 0.8      # a judgement is widened only if min(p, 1 - p) >= 1 - tau, so surviving errors had confidence > 0.8


PILOT_FILE = "data/pilot_tasks.json"


def pilot_tasks():
    """Tasks used to iterate on proposition definitions; they never enter the final evaluation."""
    if not os.path.exists(PILOT_FILE):
        return set()
    with open(PILOT_FILE) as fh:
        return {tuple(x) for x in json.load(fh)}


def build_tasks(dfa, cache, labels, rule_id, exclude=frozenset(), only=None):
    """{(domain, task_id): [assembled trajectory, ...]} over labelled trajectories of applicable domains."""
    labelled = {k[0] for k in labels}
    tasks = collections.defaultdict(list)
    for t in load_all(RAW):
        key = (t.domain, t.task_id)
        if t.traj_id not in labelled or not applies(rule_id, t.domain) or key in exclude:
            continue
        if only is not None and key not in only:
            continue
        try:
            data = assemble(t, dfa, cache, labels)
        except KeyError:          # missing probability or label: skip this trajectory
            continue
        tasks[key].append(data)
    return dict(tasks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probs", required=True)
    ap.add_argument("--labels", default="data/labels.csv")
    ap.add_argument("--alpha", type=float, default=0.1)
    args = ap.parse_args()
    if not (os.path.exists(args.labels) and os.path.exists(args.probs)):
        raise SystemExit("E0 needs human labels and a labeler cache; neither step has been run yet.")
    cache, labels = ProbCache(args.probs), load_labels(args.labels)
    print("rule,tasks,trajs,violation_rate,hard_error,hard_error_ci95,confident_error,decision")
    for rule_id, (dfa, _) in RULES.items():
        if dfa.structured == set(dfa.props):
            continue
        tasks = list(build_tasks(dfa, cache, labels, rule_id).values())
        if not tasks:
            continue
        hard = evaluate(tasks, dfa, 0.0)
        lo, hi = bootstrap_ci([sum(loss_verdict(tr, dfa, 0.0) for tr in task) / len(task) for task in tasks])
        trajs = [tr for task in tasks for tr in task]
        confident = sum(loss_verdict(tr, dfa, CONFIDENT_TAU) for tr in trajs) / len(trajs)
        if hard["joint_error"] < 0.03:
            decision = "too easy: harder rules or a smaller labeler"
        elif confident > args.alpha:
            decision = "too noisy: stronger labeler or tighter definitions"
        else:
            decision = "continue"
        print(f"{rule_id},{len(tasks)},{len(trajs)},{hard['violation_rate']:.3f},"
              f"{hard['joint_error']:.3f},{lo:.3f}-{hi:.3f},{confident:.3f},{decision}")


if __name__ == "__main__":
    main()
