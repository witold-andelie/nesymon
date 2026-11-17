"""Turn per-batch exception JSON files into a pre-annotation CSV aligned with an annotation sheet.

Each JSON file maps traj_id -> {"C"|"S"|"A"|"O": [yes steps], "M0": [no steps], "T": {step: 0|1}}.
Sites of trajectories absent from every JSON file are left out of the output and counted.
Run from the repository root:
  python -m experiments.assemble_preannotation SHEET OUT_CSV JSON_DIR [JSON_DIR ...]
"""
import csv
import glob
import json
import os
import sys

SHORT = {"confirm": "C", "subjective_recommendation": "S", "asks_compensation": "A", "offers_compensation": "O"}


def load_judgements(dirs):
    judged, source = {}, {}
    for d in dirs:
        for path in sorted(glob.glob(os.path.join(d, "*.json"))):
            for tid, j in json.load(open(path)).items():
                if tid in judged:
                    raise ValueError(f"{tid} judged twice ({source[tid]} and {path})")
                judged[tid], source[tid] = j, path
    return judged, source


def value(j, prop, step):
    if prop in SHORT:
        return int(step in j.get(SHORT[prop], []))
    if prop == "matches_listed":
        return int(step not in j.get("M0", []))
    if prop == "transfer_justified":
        t = j.get("T", {})
        if str(step) not in t:
            raise KeyError(f"no transfer_justified value for step {step}")
        return int(t[str(step)])
    raise KeyError(prop)


def main():
    sheet, out, dirs = sys.argv[1], sys.argv[2], sys.argv[3:]
    judged, source = load_judgements(dirs)
    rows, missing, written = list(csv.DictReader(open(sheet))), set(), 0
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["task_id", "traj_id", "step", "prop", "value", "source"])
        for r in rows:
            j = judged.get(r["traj_id"])
            if j is None:
                missing.add(r["traj_id"])
                continue
            w.writerow([r["task_id"], r["traj_id"], r["step"], r["prop"],
                        value(j, r["prop"], int(r["step"])), os.path.basename(os.path.dirname(source[r["traj_id"]]))])
            written += 1
    print(f"wrote {written} rows to {out}; {len(missing)} trajectories not yet judged")


if __name__ == "__main__":
    main()
