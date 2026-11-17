"""Write the annotation sheet: one row per (trajectory, step, linguistic proposition) to be judged.

With --tasks N the sampled tasks become the pilot set (saved to data/pilot_tasks.json): proposition
definitions are iterated on them only, and the full sheet leaves them out of the final evaluation.

Trajectories are chosen by a fixed, outcome-independent rule (trial 0 of every agent for each task),
so the choice cannot break exchangeability between calibration and test tasks.
Run from the repository root:  python -m experiments.make_annotation_sheet [--tasks N] [--out PATH]
"""
import argparse
import csv
import json
import os
import random

from nesymon.data import load_all
from nesymon.pipeline import label_sites, load_prop_defs
from rules.dfas import RULES, applies

RAW = "data/raw/tau-bench/historical_trajectories"
PILOT_FILE = "data/pilot_tasks.json"


def reference_actions():
    """{(domain, task_id): reference solution actions} read from the trajectory files."""
    out = {}
    for name in sorted(os.listdir(RAW)):
        if name.endswith(".json"):
            domain = name[:-len(".json")].rsplit("-", 1)[1]
            with open(os.path.join(RAW, name)) as fh:
                for rec in json.load(fh):
                    out[(domain, rec["task_id"])] = rec["info"]["task"]["actions"]
    return out


def props_for(domain):
    props = []
    for rule_id, (dfa, _) in RULES.items():
        if applies(rule_id, domain):
            props += [a for a in dfa.props if a not in dfa.structured and a not in props]
    return props


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=int, default=0, help="number of tasks per domain to sample (0 = all)")
    ap.add_argument("--out", default="data/annotation_sheet.csv")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    defs = load_prop_defs()
    trajs = [t for t in load_all(RAW) if t.trial == 0]
    rng = random.Random(args.seed)
    keep = {}
    for domain in ("retail", "airline"):
        ids = sorted({t.task_id for t in trajs if t.domain == domain})
        keep[domain] = set(rng.sample(ids, args.tasks) if args.tasks else ids)
    if args.tasks:
        with open(PILOT_FILE, "w") as fh:
            json.dump(sorted([d, i] for d in keep for i in keep[d]), fh)
    elif os.path.exists(PILOT_FILE):
        with open(PILOT_FILE) as fh:
            for d, i in json.load(fh):
                keep[d].discard(i)
    rows = 0
    with open(args.out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["task_id", "traj_id", "step", "role", "prop", "value", "note", "text"])
        for t in trajs:
            if t.task_id not in keep[t.domain]:
                continue
            for step, a in label_sites(t, [p for p in props_for(t.domain) if p in defs]):
                s = t.steps[step]
                text = f"{s.tool}({s.args})" if s.tool else s.content.strip()
                w.writerow([f"{t.domain}-{t.task_id}", t.traj_id, step, s.role, a, "", "", text])
                rows += 1
    # Reference solutions help human annotators judge transfers and writes; the labeler never sees them.
    ref_path = args.out.replace(".csv", "_reference_actions.csv")
    with open(ref_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["task_id", "reference_actions"])
        for (domain, task_id), actions in sorted(reference_actions().items()):
            if task_id in keep[domain]:
                w.writerow([f"{domain}-{task_id}", json.dumps(actions)])
    print(f"wrote {rows} judgement rows to {args.out} and reference actions to {ref_path}")


if __name__ == "__main__":
    main()
