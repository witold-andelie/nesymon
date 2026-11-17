"""Rule x class count table: how many tasks contain a natural violation (or a compliant run) of each rule.

Decides how fine the stratified risk budgets can be: a class with n calibration tasks cannot be
certified below alpha = 1/(n + 1). Only natural violations are counted; injected ones are not
exchangeable with them. Sources, in order of trust:
  labels  - human labels (data/labels.csv), once they exist
  exact   - fully structured rules, read off the tool-call log over all trajectories
  labeler - hard labels of a labeler cache (--probs); a rough, noisy estimate on the cached tasks only
Run from the repository root:  python -m experiments.rule_counts [--probs data/probs/<model>.jsonl]
"""
import argparse
import collections
import os

from nesymon.core import VIOLATION, monitor, true_verdict
from nesymon.data import load_all
from nesymon.evaluate import alpha_floor
from nesymon.labeler import ProbCache
from nesymon.pipeline import assemble, load_labels
from rules.dfas import RULE_TYPE, RULES, applies

RAW = "data/raw/tau-bench/historical_trajectories"
FRAC_CAL = 0.4


def verdicts(trajs, rule_id, cache, labels):
    """{(domain, task_id): [is_violation, ...]} and the source used."""
    dfa, _ = RULES[rule_id]
    structured = dfa.structured == set(dfa.props)
    source = "exact" if structured else ("labels" if labels else "labeler")
    out = collections.defaultdict(list)
    if source == "labeler" and cache is None:
        return out, source
    known = None if structured else {k[0] for k in (labels if source == "labels" else cache.data)}
    for t in trajs:
        if not applies(rule_id, t.domain) or (known is not None and t.traj_id not in known):
            continue
        try:
            data = assemble(t, dfa, cache, labels if source == "labels" else None)
        except KeyError:
            continue
        if source == "labeler":
            v = monitor(len(data), lambda i, a: data[i][0][a], dfa, 0.0)[0]
        else:
            v = true_verdict(data, dfa)
        out[(t.domain, t.task_id)].append(v == VIOLATION)
    return out, source


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probs", default="")
    ap.add_argument("--labels", default="data/labels.csv")
    args = ap.parse_args()
    cache = ProbCache(args.probs) if args.probs else None
    labels = load_labels(args.labels) if os.path.exists(args.labels) else None
    trajs = load_all(RAW)
    print("rule,type,source,tasks,trajs,violating_trajs,tasks_with_violation,tasks_with_compliant,"
          "cal_tasks_violation,miss_alpha_floor,cal_tasks_compliant,false_alarm_alpha_floor")
    for rule_id in RULES:
        per_task, source = verdicts(trajs, rule_id, cache, labels)
        if not per_task:
            print(f"{rule_id},{RULE_TYPE[rule_id]},none,0 (needs labels or --probs)")
            continue
        n_viol = sum(any(v) for v in per_task.values())
        n_comp = sum(not all(v) for v in per_task.values())
        cal_v, cal_c = round(FRAC_CAL * n_viol), round(FRAC_CAL * n_comp)
        print(f"{rule_id},{RULE_TYPE[rule_id]},{source},{len(per_task)},{sum(map(len, per_task.values()))},"
              f"{sum(map(sum, per_task.values()))},{n_viol},{n_comp},"
              f"{cal_v},{alpha_floor(cal_v):.3f},{cal_c},{alpha_floor(cal_c):.3f}")


if __name__ == "__main__":
    main()
