"""Compare a pre-annotation with the adjudicated labels: agreement, kappa and the rows that differ.

The pre-annotation file has the columns task_id, traj_id, step, prop, value. Rows listed in the
adjudication history can be excluded with --exclude-history (for example when the pre-annotator
had seen the adjudication reasons for them).
Run from the repository root:
  python -m experiments.compare_annotations --pre results/pilot_preannotation_blind.csv --exclude-history
"""
import argparse
import collections
import csv

from experiments.label_quality import cohen_kappa
from nesymon.pipeline import load_labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pre", required=True)
    ap.add_argument("--labels", default="data/labels.csv")
    ap.add_argument("--history", default="data/label_adjudication_history.csv")
    ap.add_argument("--exclude-history", action="store_true")
    args = ap.parse_args()
    labels, pre = load_labels(args.labels), load_labels(args.pre)
    keys = [k for k in pre if k in labels]
    if args.exclude_history:
        with open(args.history, newline="") as fh:
            seen = {(r["traj_id"], int(r["step"]), r["prop"]) for r in csv.DictReader(fh)}
        keys = [k for k in keys if k not in seen]
    print("prop,n,label_positives,pre_positives,changed_by_humans,agreement,cohen_kappa")
    for prop in sorted({k[2] for k in keys}) + ["ALL"]:
        ks = [k for k in keys if prop in ("ALL", k[2])]
        pairs = [(pre[k], labels[k]) for k in ks]
        changed = sum(a != b for a, b in pairs)
        print(f"{prop},{len(ks)},{sum(b for _, b in pairs)},{sum(a for a, _ in pairs)},{changed},"
              f"{1 - changed / len(ks):.3f},{cohen_kappa(pairs):.3f}")
    print("rows that differ:")
    for k in sorted(k for k in keys if pre[k] != labels[k]):
        print(f"  {k[0]} step {k[1]} {k[2]}: pre={pre[k]} label={labels[k]}")


if __name__ == "__main__":
    main()
