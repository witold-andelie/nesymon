"""Statistics of the tau-bench historical trajectories from the tool-call log alone (no labels, no model).

Includes the check that decides the R1 reading: how often two or more write calls fall between
two adjacent user turns. Run from the repository root:  python -m experiments.data_stats
"""
import collections
import statistics as st

from nesymon.data import load_all, structured_trace
from nesymon.inject import INJECTIONS

RAW = "data/raw/tau-bench/historical_trajectories"


def writes_per_user_window(traj):
    """Number of write calls in each stretch between adjacent user turns (stretches without writes omitted)."""
    counts, current = [], 0
    for p in structured_trace(traj):
        if p["user"]:
            if current:
                counts.append(current)
            current = 0
        current += p["write"]
    if current:
        counts.append(current)
    return counts


def main():
    trajs = load_all(RAW)
    groups = collections.defaultdict(list)
    for t in trajs:
        groups[(t.agent, t.domain)].append(t)
    print("agent,domain,tasks,trajs,steps,user_turns,writes_per_traj,trajs_with_write,reward,"
          "write_windows,multi_write_windows,trajs_with_multi_write_window,transfer_trajs")
    for (agent, domain), ts in sorted(groups.items()):
        windows = [writes_per_user_window(t) for t in ts]
        n_windows = sum(len(w) for w in windows)
        n_multi = sum(c >= 2 for w in windows for c in w)
        traces = [structured_trace(t) for t in ts]
        row = (agent, domain, len({t.task_id for t in ts}), len(ts),
               round(st.mean(len(t.steps) for t in ts), 1),
               round(st.mean(sum(p["user"] for p in tr) for tr in traces), 1),
               round(st.mean(sum(p["write"] for p in tr) for tr in traces), 2),
               round(sum(bool(w) for w in windows) / len(ts), 3),
               round(st.mean(t.reward for t in ts), 3),
               n_windows, f"{n_multi} ({n_multi / max(n_windows, 1):.1%})",
               round(sum(any(c >= 2 for c in w) for w in windows) / len(ts), 3),
               round(sum(any(p["transfer"] for p in tr) for tr in traces) / len(ts), 3))
        print(",".join(map(str, row)))
    for name, fn in INJECTIONS.items():
        ok = sum(fn(t) is not None for t in trajs)
        print(f"injection {name}: applicable to {ok}/{len(trajs)} trajectories")


if __name__ == "__main__":
    main()
