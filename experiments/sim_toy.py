"""Toy simulation: thresholds, abstention and error of the three calibration losses under one noisy labeler.

Rule R1 with window semantics. Each step is a user turn (confirming or not), a write call or
another step; only confirm on user turns is noisy.
Run from the repository root:  python -m experiments.sim_toy
"""
import random
import statistics as st

from nesymon.core import ABSTAIN, confidence_grid, crc_threshold, loss_cover, loss_verdict, monitor, true_verdict
from rules.dfas import RULES

P_USER, P_CONFIRM, P_WRITE_OPEN, P_WRITE_CLOSED = 0.4, 0.35, 0.5, 0.035


def gen_traj(dfa, rng, T=30, p_conf_err=0.02, p_ambig=0.15):
    traj, q = [], dfa.init
    for _ in range(T):
        u = int(rng.random() < P_USER)
        c = int(u and rng.random() < P_CONFIRM)
        w = int(not u and rng.random() < (P_WRITE_OPEN if q == "ok" else P_WRITE_CLOSED))
        pc = None
        if u:
            r = rng.random()
            if r < p_conf_err:                 # confidently wrong
                p_true_val = 0.05
            elif r < p_conf_err + p_ambig:     # ambiguous
                p_true_val = rng.uniform(0.35, 0.7)
            else:
                p_true_val = rng.uniform(0.75, 1.0)
            pc = p_true_val if c else 1 - p_true_val
        traj.append(({"confirm": pc, "user": float(u), "write": float(w)}, {"confirm": c, "user": u, "write": w}))
        q = dfa.step(q, (c, u, w))
    return traj


def main(seed=0, n_tasks=115, n_trials=4, n_cal=46, alpha=0.1, reps=20):
    rng = random.Random(seed)
    dfa, _ = RULES["R1_write_in_confirmation_window"]
    tasks = [[gen_traj(dfa, rng) for _ in range(n_trials)] for _ in range(n_tasks)]
    grid = confidence_grid()
    methods = {
        "full coverage": lambda tr, tau: loss_cover(tr, dfa, tau),
        "state-relevant coverage": lambda tr, tau: loss_cover(tr, dfa, tau, state_relevant=True),
        "verdict-level CRC": lambda tr, tau: loss_verdict(tr, dfa, tau),
    }
    res = {m: {"tau": [], "abstain": [], "joint": [], "cond": []} for m in methods}
    for _ in range(reps):
        rng.shuffle(tasks)
        cal, test = tasks[:n_cal], tasks[n_cal:]                    # split by task
        for m, lf in methods.items():
            tau = crc_threshold(cal, lf, alpha, grid)
            n_ab = n_wrong = n_tot = 0
            for task in test:
                for tr in task:
                    v, _ = monitor(len(tr), lambda t, a: tr[t][0][a], dfa, tau)
                    n_tot += 1
                    if v == ABSTAIN:
                        n_ab += 1
                    elif v != true_verdict(tr, dfa):
                        n_wrong += 1
            res[m]["tau"].append(min(tau, 1.0))
            res[m]["abstain"].append(n_ab / n_tot)
            res[m]["joint"].append(n_wrong / n_tot)
            res[m]["cond"].append(n_wrong / max(1, n_tot - n_ab))

    trajs = [tr for task in tasks for tr in task]
    hard = sum(monitor(len(tr), lambda t, a: tr[t][0][a], dfa, 0.0)[0] != true_verdict(tr, dfa) for tr in trajs)
    viol = sum(true_verdict(tr, dfa) == "VIOLATION" for tr in trajs)
    print(f"true violation rate: {viol / len(trajs):.3f}")
    print(f"hard-label baseline error: {hard / len(trajs):.3f}")
    for m, r in res.items():
        print(f"{m}: tau={st.mean(r['tau']):.3f}  abstain={st.mean(r['abstain']):.3f}  "
              f"joint error={st.mean(r['joint']):.3f}  conditional error={st.mean(r['cond']):.3f}")
    return res


if __name__ == "__main__":
    main()
