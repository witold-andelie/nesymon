"""Fill the probability cache for one labeler model and report throughput.

Run from the repository root:
  python -m experiments.run_labeler --model mlx-community/Qwen3.5-4B-4bit --tasks 2
Labels trial 0 of every agent for the sampled tasks (the same selection as the annotation sheet).
"""
import argparse
import os
import random
import time

from experiments.make_annotation_sheet import RAW, props_for
from nesymon.backend_mlx import MLXBackend
from nesymon.data import load_all
from nesymon.labeler import ProbCache
from nesymon.pipeline import label_trajectory, load_prop_defs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", type=int, default=0, help="tasks per domain (0 = all)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    defs = load_prop_defs()
    trajs = [t for t in load_all(RAW) if t.trial == 0]
    rng = random.Random(args.seed)
    keep = {}
    for domain in ("retail", "airline"):
        ids = sorted({t.task_id for t in trajs if t.domain == domain})
        keep[domain] = set(rng.sample(ids, args.tasks) if args.tasks else ids)
    trajs = [t for t in trajs if t.task_id in keep[t.domain]]

    os.makedirs("data/probs", exist_ok=True)
    cache = ProbCache(os.path.join("data/probs", args.model.replace("/", "__") + ".jsonl"))
    backend = MLXBackend(args.model)
    start, calls = time.time(), 0
    for i, t in enumerate(trajs, 1):
        backend.reset()
        calls += label_trajectory(t, {a: defs[a] for a in props_for(t.domain)}, backend, cache)
        print(f"[{i}/{len(trajs)}] {t.traj_id}: {calls} calls, {time.time() - start:.0f}s", flush=True)
    dt = time.time() - start
    if calls:
        print(f"calls={calls} seconds={dt:.1f} sec_per_call={dt / calls:.2f} "
              f"encoded_tokens={backend.encoded_tokens} prompt_tokens={backend.prompt_tokens} "
              f"cache_saving={1 - backend.encoded_tokens / backend.prompt_tokens:.2%} "
              f"tokens_per_sec={backend.encoded_tokens / dt:.0f}")


if __name__ == "__main__":
    main()
