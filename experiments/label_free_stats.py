"""Label-free statistics of a labeler cache: verdict mix and abstention against the confidence gate tau.

No ground truth is used, so nothing here measures error.
Run from the repository root:  python -m experiments.label_free_stats --probs data/probs/<model>.jsonl
"""
import argparse
import collections

from nesymon.core import monitor
from nesymon.data import load_all
from nesymon.labeler import ProbCache
from nesymon.pipeline import assemble
from rules.dfas import RULES, applies

RAW = "data/raw/tau-bench/historical_trajectories"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probs", required=True)
    args = ap.parse_args()
    cache = ProbCache(args.probs)
    cached = {k[0] for k in cache.data}
    trajs = [t for t in load_all(RAW) if t.traj_id in cached]
    print("rule,trajs,tau,VIOLATION,COMPLIANT,ABSTAIN,queries_per_traj")
    for rule_id, (dfa, _) in RULES.items():
        if dfa.structured == set(dfa.props):
            continue
        data = []
        for t in trajs:
            if not applies(rule_id, t.domain):
                continue
            try:
                data.append(assemble(t, dfa, cache))
            except KeyError:
                continue
        if not data:
            continue
        for tau in (0.0, 0.6, 0.8, 0.95):
            mix, queries = collections.Counter(), 0
            for tr in data:
                v, calls = monitor(len(tr), lambda t, a: tr[t][0][a], dfa, tau)
                mix[v] += 1
                queries += calls
            n = len(data)
            print(f"{rule_id},{n},{tau},{mix['VIOLATION'] / n:.3f},{mix['COMPLIANT'] / n:.3f},"
                  f"{mix['ABSTAIN'] / n:.3f},{queries / n:.1f}")


if __name__ == "__main__":
    main()
