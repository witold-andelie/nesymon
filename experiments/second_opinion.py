"""Compare two pre-annotations of the same sites and flag disagreements for human review.

Writes a review sheet with one row per disagreeing site (both values, plus the turn text from the
annotation sheet) and prints agreement per proposition.
Run from the repository root:
  python -m experiments.second_opinion FIRST_CSV SECOND_CSV SHEET OUT_CSV
"""
import csv
import sys

from experiments.label_quality import cohen_kappa
from nesymon.pipeline import load_labels


def main():
    first_path, second_path, sheet_path, out_path = sys.argv[1:5]
    first, second = load_labels(first_path), load_labels(second_path)
    keys = sorted(set(first) & set(second))
    text = {(r["traj_id"], int(r["step"]), r["prop"]): (r["task_id"], r["text"])
            for r in csv.DictReader(open(sheet_path))}
    print("prop,n,first_positives,second_positives,disagreements,agreement,cohen_kappa")
    for prop in sorted({k[2] for k in keys}) + ["ALL"]:
        ks = [k for k in keys if prop in ("ALL", k[2])]
        pairs = [(first[k], second[k]) for k in ks]
        d = sum(a != b for a, b in pairs)
        print(f"{prop},{len(ks)},{sum(a for a, _ in pairs)},{sum(b for _, b in pairs)},{d},"
              f"{1 - d / len(ks):.3f},{cohen_kappa(pairs):.3f}")
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["task_id", "traj_id", "step", "prop", "first", "second", "value", "note", "text"])
        for k in keys:
            if first[k] != second[k]:
                task_id, t = text[k]
                w.writerow([task_id, k[0], k[1], k[2], first[k], second[k], "", "", t])
    print(f"wrote {sum(first[k] != second[k] for k in keys)} disagreements to {out_path}")


if __name__ == "__main__":
    main()
