"""Baseline B1: LLM-judge verdicts for every (trajectory, rule) of the annotated selection.

Writes data/judge/<model>.jsonl with one P(violation) per trajectory and rule.
Run from the repository root:  python -m experiments.run_judge --model <mlx model> [--tasks N]
"""
import argparse
import json
import os
import random

from experiments.make_annotation_sheet import RAW
from nesymon.backend_mlx import MLXBackend
from nesymon.baselines import judge_violation_probability
from nesymon.data import load_all
from nesymon.pipeline import render_history
from rules.dfas import RULES, applies


def rule_texts(path="rules/rules.yaml"):
    import yaml
    with open(path) as fh:
        return {r["id"]: r["paraphrase"] for r in yaml.safe_load(fh) if r["id"] in RULES}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    texts = rule_texts()
    trajs = [t for t in load_all(RAW) if t.trial == 0]
    rng = random.Random(args.seed)
    keep = {}
    for domain in ("retail", "airline"):
        ids = sorted({t.task_id for t in trajs if t.domain == domain})
        keep[domain] = set(rng.sample(ids, args.tasks) if args.tasks else ids)
    os.makedirs("data/judge", exist_ok=True)
    out = os.path.join("data/judge", args.model.replace("/", "__") + ".jsonl")
    done = set()
    if os.path.exists(out):
        with open(out) as fh:
            done = {(r["traj_id"], r["rule"]) for r in map(json.loads, fh)}
    backend = MLXBackend(args.model)
    with open(out, "a") as fh:
        for t in trajs:
            if t.task_id not in keep[t.domain]:
                continue
            backend.reset()
            history = render_history(t.steps)
            for rule_id in RULES:
                if applies(rule_id, t.domain) and (t.traj_id, rule_id) not in done:
                    p = judge_violation_probability(history, texts[rule_id], backend)
                    fh.write(json.dumps({"traj_id": t.traj_id, "rule": rule_id, "p_violation": p}) + "\n")
                    fh.flush()
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
