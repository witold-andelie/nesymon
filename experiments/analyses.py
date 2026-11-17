"""Analyses E2, E6 and E8 as functions over assembled tasks (lists of trajectories per task).

Each function works on any rule's tasks, real or simulated. On real data, build the tasks with
`experiments.e0_pilot.build_tasks` once labels and a probability cache exist.
"""
import random
import statistics as st

from nesymon.core import confidence_grid
from nesymon.evaluate import calibrate, evaluate, split_tasks

GRID = confidence_grid()


def _mean(rows, key):
    return st.mean(min(r[key], 1.0) for r in rows)


def alpha_sweep(tasks, dfa, alphas=(0.05, 0.075, 0.1, 0.15, 0.2, 0.3), loss="ver", reps=200, seed=0):
    """E2: joint and conditional error against alpha over repeated task splits."""
    rng, out = random.Random(seed), []
    for alpha in alphas:
        rows = []
        for _ in range(reps):
            cal, test = split_tasks(tasks, 0.4, rng)
            rows.append(evaluate(test, dfa, calibrate(cal, dfa, loss, alpha, GRID)))
        out.append({"alpha": alpha, **{k: _mean(rows, k) for k in
                                       ("joint_error", "conditional_error", "miss", "false_alarm", "abstain", "tau")}})
    return out


def cross_domain(cal_tasks, test_tasks, dfa, alpha=0.1, loss="ver"):
    """E6: calibrate on one domain, test on another.

    The two shift indicators need no labels. They reveal a change in the input distribution only;
    a change in how often the labeler is confidently wrong at equal confidence stays invisible.
    """
    tau = calibrate(cal_tasks, dfa, loss, alpha, GRID)
    source, target = evaluate(cal_tasks, dfa, tau), evaluate(test_tasks, dfa, tau)
    return {"tau": tau, "target_joint_error": target["joint_error"], "target_abstain": target["abstain"],
            "abstain_shift": target["abstain"] - source["abstain"],
            "confidence_shift": mean_confidence(test_tasks, dfa) - mean_confidence(cal_tasks, dfa)}


def mean_confidence(tasks, dfa):
    """Label-free statistic: mean max(p, 1 - p) over queried linguistic judgements."""
    vals = [max(p, 1 - p) for task in tasks for tr in task for probs, _ in tr
            for a, p in probs.items() if p is not None and a not in dfa.structured]
    return st.mean(vals) if vals else 1.0


def inject_confident_errors(tasks, dfa, rate, rng, confidence=0.95):
    """E8: replace a fraction of linguistic judgements by confident wrong ones (truth is untouched)."""
    out = []
    for task in tasks:
        new_task = []
        for tr in task:
            new_tr = []
            for probs, truth in tr:
                probs = dict(probs)
                for a, p in probs.items():
                    if p is not None and a not in dfa.structured and rng.random() < rate:
                        probs[a] = 1 - confidence if truth[a] else confidence
                new_tr.append((probs, truth))
            new_task.append(new_tr)
        out.append(new_task)
    return out


def regime_sweep(tasks, dfa, rates=(0.0, 0.01, 0.02, 0.05, 0.10), alpha=0.1, reps=50, seed=0):
    """E8: abstention and error of the verdict-level method as confident errors are injected."""
    rng, out = random.Random(seed), []
    for rate in rates:
        rows, hard = [], []
        for _ in range(reps):
            noisy = inject_confident_errors(tasks, dfa, rate, rng)
            cal, test = split_tasks(noisy, 0.4, rng)
            rows.append(evaluate(test, dfa, calibrate(cal, dfa, "ver", alpha, GRID)))
            hard.append(evaluate(test, dfa, 0.0))
        out.append({"rate": rate, "hard_error": _mean(hard, "joint_error"),
                    "joint_error": _mean(rows, "joint_error"), "abstain": _mean(rows, "abstain")})
    return out


def difficulty_buckets(tasks, dfa, tau, edges=(15, 25, 35)):
    """E4: hard-label error, calibrated error and abstention by trajectory length."""
    from nesymon.core import ABSTAIN, monitor, true_verdict
    buckets = {}
    for task in tasks:
        for tr in task:
            key = sum(len(tr) > e for e in edges)
            b = buckets.setdefault(key, {"n": 0, "hard_error": 0, "error": 0, "abstain": 0})
            truth = true_verdict(tr, dfa)
            label = lambda t, a: tr[t][0][a]
            v = monitor(len(tr), label, dfa, tau)[0]
            b["n"] += 1
            b["hard_error"] += monitor(len(tr), label, dfa, 0.0)[0] != truth
            b["error"] += v not in (ABSTAIN, truth)
            b["abstain"] += v == ABSTAIN
    names = [f"<={edges[0]}"] + [f"{a + 1}-{b}" for a, b in zip(edges, edges[1:])] + [f">{edges[-1]}"]
    return [{"length": names[k], "n": b["n"], **{m: b[m] / b["n"] for m in ("hard_error", "error", "abstain")}}
            for k, b in sorted(buckets.items())]


def error_autocorrelation(tasks, dfa):
    """E7: correlation between hard-label errors at consecutive judgements of the same proposition.

    A value near zero supports the independence assumption of the probabilistic comparator.
    """
    pairs = []
    for task in tasks:
        for tr in task:
            for a in dfa.props:
                if a in dfa.structured:
                    continue
                errs = [int((p >= 0.5) != bool(truth[a])) for probs, truth in tr
                        if (p := probs[a]) is not None]
                pairs.extend(zip(errs, errs[1:]))
    if len(pairs) < 2:
        return 0.0
    xs, ys = zip(*pairs)
    mx, my = st.mean(xs), st.mean(ys)
    sx, sy = st.pstdev(xs), st.pstdev(ys)
    if sx == 0 or sy == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in pairs) / (len(pairs) * sx * sy)
