"""Task-level splitting, calibration and metrics. The task is the exchangeable unit throughout."""
import math
import random
import statistics as st

from .core import ABSTAIN, COMPLIANT, VIOLATION, crc_threshold, loss_cover, loss_verdict, monitor, true_verdict

LOSSES = {
    "cov": lambda dfa: (lambda tr, tau: loss_cover(tr, dfa, tau)),
    "sr": lambda dfa: (lambda tr, tau: loss_cover(tr, dfa, tau, state_relevant=True)),
    "ver": lambda dfa: (lambda tr, tau: loss_verdict(tr, dfa, tau)),
    "miss": lambda dfa: (lambda tr, tau: loss_verdict(tr, dfa, tau, "miss")),
    "false_alarm": lambda dfa: (lambda tr, tau: loss_verdict(tr, dfa, tau, "false_alarm")),
}


def split_tasks(tasks, frac_cal, rng):
    idx = list(range(len(tasks)))
    rng.shuffle(idx)
    n_cal = round(frac_cal * len(tasks))
    return [tasks[i] for i in idx[:n_cal]], [tasks[i] for i in idx[n_cal:]]


def evaluate(tasks, dfa, tau, use_vrg=True):
    """Metrics for one rule at a fixed tau. Rates are averaged within a task first, then over tasks."""
    keys = ("joint_error", "miss", "false_alarm", "abstain", "violation_rate", "calls")
    per_task = {k: [] for k in keys}
    n_definite = n_wrong = 0
    for task in tasks:
        acc = dict.fromkeys(keys, 0.0)
        for tr in task:
            v, calls = monitor(len(tr), lambda t, a: tr[t][0][a], dfa, tau, use_vrg)
            truth = true_verdict(tr, dfa)
            wrong = v != ABSTAIN and v != truth
            acc["joint_error"] += wrong
            acc["miss"] += wrong and truth == VIOLATION
            acc["false_alarm"] += wrong and truth == COMPLIANT
            acc["abstain"] += v == ABSTAIN
            acc["violation_rate"] += truth == VIOLATION
            acc["calls"] += calls
            n_definite += v != ABSTAIN
            n_wrong += wrong
        for k in keys:
            per_task[k].append(acc[k] / len(task))
    out = {k: st.mean(v) for k, v in per_task.items()}
    out["conditional_error"] = n_wrong / n_definite if n_definite else 0.0
    out["tau"] = tau
    return out


def calibrate(cal_tasks, dfa, loss, alpha, grid):
    """loss: a key of LOSSES, or "hard" for the uncalibrated argmax monitor (tau = 0)."""
    if loss == "hard":
        return 0.0
    return crc_threshold(cal_tasks, LOSSES[loss](dfa), alpha, grid)


def calibrate_two_sided(cal_tasks, dfa, alpha_miss, alpha_false_alarm, grid):
    """Separate budgets for missed violations and false alarms.

    Each error type is non-increasing in tau, so the larger of the two thresholds controls both.
    """
    return max(crc_threshold(cal_tasks, LOSSES["miss"](dfa), alpha_miss, grid),
               crc_threshold(cal_tasks, LOSSES["false_alarm"](dfa), alpha_false_alarm, grid))


def run_splits(tasks, dfa, losses, alpha, grid, reps=20, frac_cal=0.4, seed=0):
    """Repeated random task splits. Returns {loss: [metrics dict per split]}."""
    rng = random.Random(seed)
    out = {name: [] for name in losses}
    for _ in range(reps):
        cal, test = split_tasks(tasks, frac_cal, rng)
        for name in losses:
            out[name].append(evaluate(test, dfa, calibrate(cal, dfa, name, alpha, grid)))
    return out


def bootstrap_ci(per_task_values, reps=2000, level=0.95, seed=0):
    """Task-level bootstrap interval for a mean of per-task values."""
    rng, n = random.Random(seed), len(per_task_values)
    means = sorted(st.mean(rng.choices(per_task_values, k=n)) for _ in range(reps))
    lo = means[int((1 - level) / 2 * reps)]
    hi = means[min(reps - 1, int((1 + level) / 2 * reps))]
    return lo, hi


def stratum(rule_tasks, cls):
    """Class-conditional calibration units pooled over rules.

    rule_tasks: list of (dfa, {task_id: [trajectory, ...]}). Returns {task_id: [(trajectory, dfa), ...]}
    keeping only (trajectory, rule) pairs whose true verdict is `cls`; tasks without any are dropped.
    """
    units = {}
    for dfa, tasks in rule_tasks:
        for task_id, trajs in tasks.items():
            keep = [(tr, dfa) for tr in trajs if true_verdict(tr, dfa) == cls]
            if keep:
                units.setdefault(task_id, []).extend(keep)
    return units


def alpha_floor(n):
    """Smallest certifiable risk level with n calibration tasks."""
    return 1 / (n + 1)


def class_conditional_threshold(rule_tasks, cls, alpha, grid):
    """Threshold controlling the error rate among true-`cls` pairs (miss rate for VIOLATION,
    false-alarm rate for COMPLIANT), following class-conditional conformal risk control.

    Only tasks containing a true-`cls` pair can calibrate it, so alpha must be at least 1/(n_cls + 1);
    pass several rules to pool a sparse class across rules of one type.
    """
    units = list(stratum(rule_tasks, cls).values())
    loss = lambda item, tau: loss_verdict(item[0], item[1], tau)
    return crc_threshold(units, loss, alpha, grid)


def summarize(runs):
    """Mean and standard deviation of every metric over splits (tau = inf is reported as 1.0)."""
    keys = runs[0].keys()
    clip = lambda x: 1.0 if math.isinf(x) else x
    return {k: (st.mean(clip(r[k]) for r in runs), st.pstdev(clip(r[k]) for r in runs)) for k in keys}
