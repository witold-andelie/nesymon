"""Annotator agreement and labeler accuracy per proposition on the labelled tasks.

Agreement uses the two original annotations recorded in data/label_adjudication_history.csv
(rows absent from it were labelled identically by both annotators).
Run from the repository root:  python -m experiments.label_quality --probs data/probs/<model>.jsonl
"""
import argparse
import collections
import csv
import os

from nesymon.labeler import ProbCache
from nesymon.pipeline import load_labels


def cohen_kappa(pairs):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    pa, pb = sum(a for a, _ in pairs) / n, sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def agreement(labels, history_path):
    """{prop: (n, disagreements, kappa)} between the two original annotators."""
    original = {}
    if os.path.exists(history_path):
        with open(history_path, newline="") as fh:
            for r in csv.DictReader(fh):
                original[(r["traj_id"], int(r["step"]), r["prop"])] = (int(r["a_value"]), int(r["b_value"]))
    pairs = collections.defaultdict(list)
    for key, value in labels.items():
        pairs[key[2]].append(original.get(key, (value, value)))
    return {p: (len(v), sum(a != b for a, b in v), cohen_kappa(v)) for p, v in pairs.items()}


def labeler_confusion(labels, cache):
    """{prop: counts} comparing the labeler's hard labels with the human labels."""
    out = collections.defaultdict(collections.Counter)
    for key, y in labels.items():
        p = cache.get(*key)
        if p is None:
            continue
        guess = int(p >= 0.5)
        out[key[2]][("TP" if y else "FP") if guess else ("FN" if y else "TN")] += 1
        if guess != y:
            out[key[2]]["wrong_above_0.8"] += max(p, 1 - p) > 0.8
            out[key[2]]["wrong_above_0.95"] += max(p, 1 - p) > 0.95
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probs", default="")
    ap.add_argument("--labels", default="data/labels.csv")
    ap.add_argument("--history", default="data/label_adjudication_history.csv")
    args = ap.parse_args()
    labels = load_labels(args.labels)
    print("prop,n,positives,annotator_disagreements,cohen_kappa")
    positives = collections.Counter(k[2] for k, v in labels.items() if v)
    for prop, (n, d, kappa) in sorted(agreement(labels, args.history).items()):
        print(f"{prop},{n},{positives[prop]},{d},{kappa:.3f}")
    if args.probs:
        print("prop,TP,FP,FN,TN,accuracy,confident_error_rate_0.8,confident_error_rate_0.95")
        for prop, c in sorted(labeler_confusion(labels, ProbCache(args.probs)).items()):
            n = c["TP"] + c["FP"] + c["FN"] + c["TN"]
            print(f"{prop},{c['TP']},{c['FP']},{c['FN']},{c['TN']},{(c['TP'] + c['TN']) / n:.3f},"
                  f"{c['wrong_above_0.8'] / n:.3f},{c['wrong_above_0.95'] / n:.3f}")


if __name__ == "__main__":
    main()
