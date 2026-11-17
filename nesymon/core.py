"""Set-based LTLf runtime monitoring under noisy neural predicates.

Pieces: a DFA with derived dead/sink states, state-dependent proposition
relevance (VRG), conformal value sets, an online set-propagating monitor,
three calibration losses, and conformal risk control (CRC) over a threshold.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import product

VIOLATION = "VIOLATION"
COMPLIANT = "COMPLIANT"
ABSTAIN = "ABSTAIN"
POSSIBLE_VIOLATION = "POSSIBLE_VIOLATION"   # running status: some but not all tracked states are dead
INCONCLUSIVE = "INCONCLUSIVE"               # running status: the prefix alone cannot decide


@dataclass
class DFA:
    """DFA over bit-tuples of `props`, complete on `alphabet`.

    `alphabet` lists the letters that can occur (mutually exclusive step types); by default
    every bit-tuple. Letters outside it are impossible by construction and are never explored.

    `structured` props are read from the tool-call log and are noise-free;
    all other props are linguistic and come from the labeler.
    `dead` (no accepting state reachable) and `sink` (no rejecting state
    reachable) are derived, never written by hand.
    """
    props: tuple
    delta: dict                      # (state, bits) -> state
    init: str
    accepting: frozenset
    structured: frozenset = frozenset()
    alphabet: frozenset = None
    states: frozenset = field(init=False)
    dead: frozenset = field(init=False)
    sink: frozenset = field(init=False)

    def __post_init__(self):
        self.props = tuple(self.props)
        self.accepting = frozenset(self.accepting)
        self.structured = frozenset(self.structured)
        self.states = frozenset(q for q, _ in self.delta) | frozenset(self.delta.values())
        if self.alphabet is None:
            self.alphabet = frozenset(product((0, 1), repeat=len(self.props)))
        self.alphabet = frozenset(self.alphabet)
        letters = sorted(self.alphabet)
        missing = [(q, b) for q in self.states for b in letters if (q, b) not in self.delta]
        if missing:
            raise ValueError(f"incomplete transition function, e.g. {missing[0]}")
        self._succ = {q: {self.delta[(q, b)] for b in letters} for q in self.states}
        self.dead = self.states - self._can_reach(self.accepting)
        self.sink = self.states - self._can_reach(self.states - self.accepting)
        self._relevant = {}

    def _can_reach(self, targets):
        reach = set(targets)
        changed = True
        while changed:
            changed = False
            for q in self.states - reach:
                if self._succ[q] & reach:
                    reach.add(q)
                    changed = True
        return frozenset(reach)

    def step(self, q, bits):
        return self.delta[(q, bits)]

    def run(self, bit_seq, q=None):
        q = self.init if q is None else q
        for bits in bit_seq:
            q = self.delta[(q, bits)]
        return q

    def relevant(self, q):
        """Props whose single flip can change the transition out of q."""
        if q not in self._relevant:
            out = []
            for i, a in enumerate(self.props):
                for bits in self.alphabet:
                    flipped = bits[:i] + (1 - bits[i],) + bits[i + 1:]
                    if flipped in self.alphabet and self.delta[(q, bits)] != self.delta[(q, flipped)]:
                        out.append(a)
                        break
            self._relevant[q] = tuple(out)
        return self._relevant[q]


def relevant_props(dfa, states):
    rel = set()
    for q in states:
        rel.update(dfa.relevant(q))
    return [a for a in dfa.props if a in rel]


def value_set(p_true, tau):
    """Conformal value set {v : 1 - p(v) <= tau}; nested in tau.

    An empty set falls back to the argmax, which is the first value to enter
    as tau grows, so nesting is preserved. Both values are present exactly when
    min(p, 1 - p) >= 1 - tau, so every tau below 0.5 behaves like the hard-label monitor.
    """
    C = {v for v, pv in ((1, p_true), (0, 1 - p_true)) if 1 - pv <= tau}
    return C or {int(p_true >= 0.5)}


def confidence_grid(n=40, top=0.999):
    """Thresholds on [0.5, 1], evenly spaced in log-odds, plus 0 (hard labels) and 1 (always widen).

    A value set is {0, 1} exactly when the labeler's top probability is at most tau, so tau is a
    confidence gate and nothing below 0.5 differs from the hard-label monitor. Logit-derived
    probabilities crowd near 1, hence the log-odds spacing.
    """
    hi = math.log(top / (1 - top))
    return [0.0] + [1 / (1 + math.exp(-hi * k / (n - 1))) for k in range(n)] + [1.0]


def prop_set(dfa, a, p_true, tau):
    """Value set of one proposition.

    p_true=None marks a proposition that is false by construction at this step (wrong turn role);
    structured props are never widened.
    """
    if p_true is None:
        return {0}
    if a in dfa.structured:
        return {int(p_true >= 0.5)}
    return value_set(p_true, tau)


class OnlineMonitor:
    """Tracks the set S_t of DFA states consistent with the value sets so far."""

    def __init__(self, dfa, tau, use_vrg=True):
        self.dfa, self.tau, self.use_vrg = dfa, tau, use_vrg
        self.S = frozenset({dfa.init})
        self.calls = 0            # labeler queries on linguistic props
        self.final = None         # VIOLATION / COMPLIANT once irrevocable

    def queries(self):
        """Props that must be observed at the next step."""
        if self.final is not None:
            return []
        return relevant_props(self.dfa, self.S) if self.use_vrg else list(self.dfa.props)

    def step(self, label):
        """Advance one step. `label(a)` returns P(a holds now); called only for queried props."""
        if self.final is not None:
            return self.final
        dfa, asked, sets = self.dfa, set(self.queries()), []
        for a in dfa.props:
            if a in asked:
                p = label(a)
                if p is not None and a not in dfa.structured:
                    self.calls += 1
                sets.append(prop_set(dfa, a, p, self.tau))
            else:
                sets.append({0, 1})          # irrelevant in every tracked state: S_t unchanged
        letters = [bits for bits in product(*sets) if bits in dfa.alphabet]
        if not letters:
            raise ValueError(f"observation outside the alphabet of the rule: {sets}")
        self.S = frozenset(dfa.delta[(q, bits)] for q in self.S for bits in letters)
        return self.status()

    def status(self):
        if self.final is None:
            if self.S <= self.dfa.dead:
                self.final = VIOLATION
            elif self.S <= self.dfa.sink:
                self.final = COMPLIANT
        if self.final is not None:
            return self.final
        return POSSIBLE_VIOLATION if self.S & self.dfa.dead else INCONCLUSIVE

    def finish(self):
        """End-of-trace verdict."""
        if self.final is not None:
            return self.final
        if self.S <= self.dfa.accepting:
            return COMPLIANT
        if not (self.S & self.dfa.accepting):
            return VIOLATION
        return ABSTAIN


def monitor(n_steps, label, dfa, tau, use_vrg=True):
    """Run the set monitor over a whole trace. `label(t, a)` returns P(a holds at step t).

    Returns (verdict, number of labeler queries).
    """
    m = OnlineMonitor(dfa, tau, use_vrg)
    for t in range(n_steps):
        if m.step(lambda a: label(t, a)) in (VIOLATION, COMPLIANT):
            break
    return m.finish(), m.calls


# A trajectory is a list of (probs, truth) pairs, one per step:
# probs[a] = labeler probability, truth[a] = ground-truth bit.

def true_verdict(traj, dfa):
    q = dfa.run(tuple(truth[a] for a in dfa.props) for _, truth in traj)
    return COMPLIANT if q in dfa.accepting else VIOLATION


def loss_verdict(traj, dfa, tau, error_type="any"):
    """1 if the monitor commits to a verdict and it is wrong.

    error_type: "any", "miss" (says COMPLIANT on a true violation) or
    "false_alarm" (says VIOLATION on a compliant trace). Each is
    non-increasing in tau, so each can be calibrated separately.
    """
    v, _ = monitor(len(traj), lambda t, a: traj[t][0][a], dfa, tau)
    truth = true_verdict(traj, dfa)
    if v == ABSTAIN or v == truth:
        return 0.0
    if error_type == "miss":
        return float(truth == VIOLATION)
    if error_type == "false_alarm":
        return float(truth == COMPLIANT)
    return 1.0


def loss_cover(traj, dfa, tau, state_relevant=False):
    """1 if some (step, prop) truth falls outside its value set.

    With state_relevant=True only props relevant in the true DFA state count.
    """
    q = dfa.init
    for probs, truth in traj:
        props = dfa.relevant(q) if state_relevant else dfa.props
        for a in props:
            if truth[a] not in prop_set(dfa, a, probs[a], tau):
                return 1.0
        q = dfa.step(q, tuple(truth[a] for a in dfa.props))
    return 0.0


def task_risk(tasks, loss_fn, tau):
    """Mean over tasks of the within-task mean loss."""
    return sum(sum(loss_fn(tr, tau) for tr in task) / len(task) for task in tasks) / len(tasks)


def crc_threshold(cal_tasks, loss_fn, alpha, grid):
    """Conformal risk control over tasks (the exchangeable unit).

    Returns the smallest tau in `grid` (then inf) with
    n/(n+1) * R_hat(tau) + 1/(n+1) <= alpha. Requires a loss in [0, 1] that is
    non-increasing in tau and zero at tau = inf.
    """
    n = len(cal_tasks)
    if 1 / (n + 1) > alpha:
        raise ValueError(f"too few calibration tasks: n={n} needs alpha >= {1 / (n + 1):.3f}")
    grid = sorted(grid)
    ok = lambda tau: n / (n + 1) * task_risk(cal_tasks, loss_fn, tau) + 1 / (n + 1) <= alpha
    lo, hi = 0, len(grid)                 # bisection is valid because the risk is non-increasing
    while lo < hi:
        mid = (lo + hi) // 2
        if ok(grid[mid]):
            hi = mid
        else:
            lo = mid + 1
    return grid[lo] if lo < len(grid) else math.inf
