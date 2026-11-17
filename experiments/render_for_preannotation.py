"""Compact rendering of trajectories with their label sites, in batches, for LLM pre-annotation.

Run from the repository root:
  python -m experiments.render_for_preannotation OUT_DIR PER_BATCH [SHEET]
"""

import csv, sys, collections
from nesymon.data import load_all, TRANSFER_TOOL

out_dir, per_batch = sys.argv[1], int(sys.argv[2])
sheet = sys.argv[3] if len(sys.argv) > 3 else "data/annotation_sheet_full.csv"
sites = collections.defaultdict(lambda: collections.defaultdict(list))
for r in csv.DictReader(open(sheet)):
    sites[r["traj_id"]][int(r["step"])].append(r["prop"])
SHORT = {"confirm": "C", "subjective_recommendation": "S", "asks_compensation": "A",
         "offers_compensation": "O", "matches_listed": "M", "transfer_justified": "T"}
trajs = {t.traj_id: t for t in load_all("data/raw/tau-bench/historical_trajectories")}
def clip(text, head, tail):
    text = " ".join(text.split())
    if len(text) <= head + tail + 20:
        return text
    return text[:head] + " [...] " + (text[-tail:] if tail else "")
order = sorted(sites, key=lambda tid: (trajs[tid].domain, trajs[tid].task_id, trajs[tid].agent))
total, batch, n = 0, [], 0
for tid in order:
    t = trajs[tid]
    full = any(s.tool == TRANSFER_TOOL for s in t.steps)
    lines = [f"### {tid}"]
    for i, s in enumerate(t.steps):
        tag = "{" + "".join(SHORT[p] for p in sites[tid].get(i, [])) + "}" if i in sites[tid] else ""
        if s.role == "assistant" and s.tool:
            if s.tool == "think":
                continue
            body = f"CALL {s.tool}({clip(s.args, 700, 0) if 'M' in tag or 'T' in tag else clip(s.args, 160, 0)})"
        elif s.role == "tool":
            if s.tool == "think":
                continue
            body = "RESULT " + clip(s.content, 420 if full else 110, 0)
        elif s.role == "user":
            body = "U: " + clip(s.content, 500, 150)
        else:
            body = "A: " + clip(s.content, 650, 350)
        lines.append(f"[{i}]{tag} {body}")
    batch.append("\n".join(lines))
    if len(batch) == per_batch:
        text = "\n".join(batch) + "\n"; total += len(text)
        open(f"{out_dir}/batch_{n:03d}.txt", "w").write(text); batch, n = [], n + 1
if batch:
    text = "\n".join(batch) + "\n"; total += len(text)
    open(f"{out_dir}/batch_{n:03d}.txt", "w").write(text); n += 1
print(len(order), "trajectories,", n, "batches,", total, "characters")
