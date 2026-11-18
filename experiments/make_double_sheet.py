"""Blind double-annotation sheet: a 20 percent sample of evaluation tasks, stratified by domain.

The sheet is cut from the evaluation annotation sheet, with the value and note columns empty and no
pre-labels, so the second annotator works independently. Agreement with the final labels is then
measured with experiments/compare_annotations.py.

Run from the repository root:
  python -m experiments.make_double_sheet                    # writes the sheet and data/double_annotation_tasks.json
  python -m experiments.compare_annotations --pre <filled sheet> --labels data/labels_eval.csv --history /dev/null
"""
import argparse
import csv
import json
import random

SHEET, REFS = "data/annotation_sheet_full.csv", "data/annotation_sheet_full_reference_actions.csv"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frac", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default="data/annotation_sheet_double.csv")
    ap.add_argument("--tasks-out", default="data/double_annotation_tasks.json")
    args = ap.parse_args()
    rows = list(csv.DictReader(open(SHEET, newline="")))
    rng = random.Random(args.seed)
    chosen = []
    for domain in ("retail", "airline"):
        tasks = sorted({r["task_id"] for r in rows if r["task_id"].startswith(domain)},
                       key=lambda t: int(t.split("-")[1]))
        chosen += sorted(rng.sample(tasks, round(args.frac * len(tasks))), key=lambda t: int(t.split("-")[1]))
    keep = set(chosen)
    sample = [dict(r, value="", note="") for r in rows if r["task_id"] in keep]
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(sample)
    refs = [r for r in csv.DictReader(open(REFS, newline="")) if r["task_id"] in keep]
    with open(args.out.replace(".csv", "_reference_actions.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["task_id", "reference_actions"])
        w.writeheader()
        w.writerows(refs)
    json.dump({"seed": args.seed, "frac": args.frac, "tasks": chosen}, open(args.tasks_out, "w"), indent=1)
    n_judged = sum(1 for r in sample if r["prop"])
    print(f"{len(chosen)} tasks, {len({r['traj_id'] for r in sample})} trajectories, {n_judged} judgements "
          f"-> {args.out}")


if __name__ == "__main__":
    main()
