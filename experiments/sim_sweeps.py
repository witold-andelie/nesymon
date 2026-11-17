"""Simulated E2 (guarantee vs alpha) and E8 (regime vs confident-error rate) with fresh draws per repetition.

Fresh calibration and test tasks are drawn every repetition, so the mean joint error estimates the
quantity the CRC theorem bounds. Run from the repository root:  python -m experiments.sim_sweeps
"""
import csv
import os
import random
import statistics as st

from experiments.sim_toy import gen_traj
from nesymon.core import confidence_grid
from nesymon.evaluate import calibrate, calibrate_two_sided, evaluate
from rules.dfas import RULES

GRID = confidence_grid()
FIELDS = ("sweep", "method", "alpha", "p_conf_err", "reps", "tau", "joint_error", "joint_error_se",
          "conditional_error", "miss", "false_alarm", "abstain", "violation_rate")


def run(dfa, method, alpha, p_conf_err, reps, rng, n_cal=46, n_test=69, n_trials=4):
    rows = []
    for _ in range(reps):
        draw = lambda n: [[gen_traj(dfa, rng, p_conf_err=p_conf_err) for _ in range(n_trials)] for _ in range(n)]
        cal, test = draw(n_cal), draw(n_test)
        if method == "two_sided":
            tau = calibrate_two_sided(cal, dfa, alpha / 2, alpha / 2, GRID)
        else:
            tau = calibrate(cal, dfa, method, alpha, GRID)
        rows.append(evaluate(test, dfa, tau))
    mean = lambda k: st.mean(min(r[k], 1.0) for r in rows)
    return {"method": method, "alpha": alpha, "p_conf_err": p_conf_err, "reps": reps, "tau": round(mean("tau"), 3),
            "joint_error": round(mean("joint_error"), 4),
            "joint_error_se": round(st.pstdev(r["joint_error"] for r in rows) / len(rows) ** 0.5, 4),
            "conditional_error": round(mean("conditional_error"), 4), "miss": round(mean("miss"), 4),
            "false_alarm": round(mean("false_alarm"), 4), "abstain": round(mean("abstain"), 4),
            "violation_rate": round(mean("violation_rate"), 4)}


def main(reps=100, seed=1, out="results/sim_sweeps.csv"):
    rng = random.Random(seed)
    dfa, _ = RULES["R1_write_in_confirmation_window"]
    rows = []
    for alpha in (0.05, 0.075, 0.1, 0.15, 0.2, 0.3):
        for method in ("hard", "ver", "two_sided", "cov"):
            rows.append({"sweep": "E2_alpha", **run(dfa, method, alpha, 0.02, reps, rng)})
    for e in (0.0, 0.01, 0.02, 0.05, 0.10):
        for method in ("hard", "ver", "cov"):
            rows.append({"sweep": "E8_regime", **run(dfa, method, 0.1, e, reps, rng)})
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(",".join(str(r[k]) for k in FIELDS))


if __name__ == "__main__":
    main()
