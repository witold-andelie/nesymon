"""Reference semantics for LTLf with past operators, used to cross-check hand-written DFAs.

Formulas are nested tuples:
  ("ap", name) | ("true",) | ("not", f) | ("and", f, g) | ("or", f, g) | ("implies", f, g)
  future: ("X", f) strong next | ("N", f) weak next | ("G", f) | ("F", f) | ("U", f, g)
  past:   ("Y", f) yesterday   | ("O", f) once      | ("H", f) historically | ("S", f, g) since
A trace is a non-empty list of dicts mapping proposition names to 0/1.
"""
from functools import lru_cache


def holds(formula, trace, at_end=False):
    """True iff the trace satisfies the formula at position 0, or at the last position if at_end
    (the convention for pure-past formulas)."""
    n = len(trace)
    if n == 0:
        raise ValueError("LTLf is interpreted over non-empty traces")

    @lru_cache(maxsize=None)
    def ev(f, i):
        op = f[0]
        if op == "true":
            return True
        if op == "ap":
            return bool(trace[i][f[1]])
        if op == "not":
            return not ev(f[1], i)
        if op == "and":
            return ev(f[1], i) and ev(f[2], i)
        if op == "or":
            return ev(f[1], i) or ev(f[2], i)
        if op == "implies":
            return (not ev(f[1], i)) or ev(f[2], i)
        if op == "X":
            return i + 1 < n and ev(f[1], i + 1)
        if op == "N":
            return i + 1 >= n or ev(f[1], i + 1)
        if op == "G":
            return all(ev(f[1], j) for j in range(i, n))
        if op == "F":
            return any(ev(f[1], j) for j in range(i, n))
        if op == "U":
            return any(ev(f[2], j) and all(ev(f[1], k) for k in range(i, j)) for j in range(i, n))
        if op == "Y":
            return i > 0 and ev(f[1], i - 1)
        if op == "O":
            return any(ev(f[1], j) for j in range(0, i + 1))
        if op == "H":
            return all(ev(f[1], j) for j in range(0, i + 1))
        if op == "S":
            return any(ev(f[2], j) and all(ev(f[1], k) for k in range(j + 1, i + 1)) for j in range(0, i + 1))
        raise ValueError(f"unknown operator {op!r}")

    return ev(formula, n - 1 if at_end else 0)
