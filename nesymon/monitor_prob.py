"""Probabilistic comparator (Ours-Prob): forward propagation of a belief over DFA states.

Assumes labeling errors are independent across propositions and steps (tested in E7).
It carries no finite-sample guarantee; only calibration error is reported for it.
"""
import math


def temperature_scale(p, temperature):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return 1 / (1 + math.exp(-math.log(p / (1 - p)) / temperature))


def fit_temperature(probs, labels, grid=None):
    """Temperature minimising binary NLL on held-out (probability, label) pairs."""
    grid = grid or [0.25 * k for k in range(1, 41)]

    def nll(temp):
        total = 0.0
        for p, y in zip(probs, labels):
            q = temperature_scale(p, temp)
            total -= math.log(q if y else 1 - q)
        return total

    return min(grid, key=nll)


def forward(dfa, step_probs):
    """step_probs: one dict per step, prop -> P(true). Yields the belief over states after each step."""
    belief = {dfa.init: 1.0}
    letters = sorted(dfa.alphabet)
    for probs in step_probs:
        nxt = {}
        for bits in letters:
            w = 1.0
            for a, bit in zip(dfa.props, bits):
                p = probs[a] or 0.0          # None marks a proposition that is false by construction
                w *= p if bit else 1 - p
            if w == 0.0:
                continue
            for q, b in belief.items():
                q2 = dfa.delta[(q, bits)]
                nxt[q2] = nxt.get(q2, 0.0) + b * w
        belief = nxt
        yield belief


def violation_probability(dfa, step_probs):
    """P(trace violates the rule) = belief mass outside the accepting states at the end."""
    belief = {dfa.init: 1.0}
    for belief in forward(dfa, step_probs):
        pass
    return sum(b for q, b in belief.items() if q not in dfa.accepting)
