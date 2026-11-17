import math
import random
from itertools import product

import pytest

from nesymon.core import (ABSTAIN, COMPLIANT, VIOLATION, OnlineMonitor, crc_threshold, loss_cover,
                          loss_verdict, monitor, true_verdict, value_set)
from nesymon.ltlf import holds
from nesymon.monitor_prob import violation_probability
from rules.dfas import PAST_FORM, RULES, response

GRID = [k / 20 for k in range(21)]


def random_traj(dfa, rng, length):
    """Random truth over the rule's alphabet. Each step is a site for at most one linguistic prop,
    as on real traces; that prop is noisy, the others are false by construction (None)."""
    letters, traj = sorted(dfa.alphabet), []
    for _ in range(length):
        bits = rng.choice(letters)
        truth, probs = dict(zip(dfa.props, bits)), {}
        free = [a for i, a in enumerate(dfa.props) if a not in dfa.structured
                and bits[:i] + (1 - bits[i],) + bits[i + 1:] in dfa.alphabet]
        on_site = [a for a in free if truth[a]] or free
        site = rng.choice(on_site) if on_site else None
        for a in dfa.props:
            if a in dfa.structured:
                probs[a] = float(truth[a])
            elif a != site:
                probs[a] = None if truth[a] == 0 else 1.0
            else:
                p_right = rng.choice([0.03, 0.4, 0.55, 0.8, 0.97, 1.0])
                probs[a] = p_right if truth[a] else 1 - p_right
        traj.append((probs, truth))
    return traj


def test_value_sets_are_nested():
    for p in [0.0, 0.1, 0.3, 0.5, 0.62, 0.9, 1.0]:
        prev = set()
        for tau in GRID + [math.inf]:
            cur = value_set(p, tau)
            assert cur and prev <= cur
            prev = cur


@pytest.mark.parametrize("rule_id", sorted(RULES))
def test_dfa_matches_formula(rule_id):
    dfa, formula = RULES[rule_id]
    letters = sorted(dfa.alphabet)
    for length in range(1, 7 if len(letters) <= 3 else 6):
        for word in product(letters, repeat=length):
            trace = [dict(zip(dfa.props, bits)) for bits in word]
            assert (dfa.run(word) in dfa.accepting) == holds(formula, trace), (rule_id, word)
            if rule_id in PAST_FORM:
                assert holds(formula, trace) == holds(PAST_FORM[rule_id], trace, at_end=True)


CONFIRM, OTHER_USER, WRITE, OTHER = (1, 1, 0), (0, 1, 0), (0, 0, 1), (0, 0, 0)


def test_r1_window_semantics():
    dfa, _ = RULES["R1_write_in_confirmation_window"]
    run = lambda word: COMPLIANT if dfa.run(word) in dfa.accepting else VIOLATION
    assert run([CONFIRM, WRITE]) == COMPLIANT
    assert run([CONFIRM, OTHER, WRITE, OTHER, WRITE]) == COMPLIANT         # one confirmation, two writes
    assert run([WRITE]) == VIOLATION                                       # no confirmation at all
    assert run([CONFIRM, OTHER_USER, WRITE]) == VIOLATION                  # another utterance closes the window
    assert run([CONFIRM, WRITE, OTHER_USER, CONFIRM, WRITE]) == COMPLIANT
    assert run([OTHER_USER, OTHER, WRITE]) == VIOLATION
    assert dfa.dead == {"bad"} and dfa.sink == frozenset()
    assert dfa.alphabet == {CONFIRM, OTHER_USER, WRITE, OTHER}
    with pytest.raises(ValueError):                                        # user turn and write at once is not a step type
        OnlineMonitor(dfa, 0.9).step(lambda a: 1.0)


def test_dead_and_sink_are_derived():
    assert RULES["R9_compensation_only_on_request"][0].sink == {"open"}
    assert RULES["R3_no_subjective_recommendation"][0].dead == {"bad"}
    assert response("a", "b")[0].dead == frozenset()


@pytest.mark.parametrize("rule_id", sorted(RULES))
def test_monotone_loss_and_hierarchy(rule_id):
    dfa, _ = RULES[rule_id]
    rng = random.Random(7)
    for _ in range(300):
        traj = random_traj(dfa, rng, rng.randint(1, 15))
        prev = {"any": 1.0, "miss": 1.0, "false_alarm": 1.0}
        for tau in GRID + [math.inf]:
            ver = loss_verdict(traj, dfa, tau)
            sr = loss_cover(traj, dfa, tau, state_relevant=True)
            cov = loss_cover(traj, dfa, tau)
            assert ver <= sr <= cov
            for kind in prev:
                cur = loss_verdict(traj, dfa, tau, kind)
                assert cur <= prev[kind]
                prev[kind] = cur
        assert loss_verdict(traj, dfa, math.inf) == 0.0


@pytest.mark.parametrize("rule_id", sorted(RULES))
def test_vrg_does_not_change_verdicts(rule_id):
    dfa, _ = RULES[rule_id]
    rng = random.Random(11)
    for _ in range(200):
        traj = random_traj(dfa, rng, rng.randint(1, 15))
        label = lambda t, a: traj[t][0][a]
        for tau in (0.0, 0.3, 0.6):
            with_vrg, calls_vrg = monitor(len(traj), label, dfa, tau, use_vrg=True)
            without, calls_all = monitor(len(traj), label, dfa, tau, use_vrg=False)
            assert with_vrg == without and calls_vrg <= calls_all


def test_noise_free_monitor_equals_truth():
    dfa, _ = RULES["R1_write_in_confirmation_window"]
    rng = random.Random(3)
    for _ in range(200):
        traj = [(({a: (None if a == "confirm" and not t["user"] else float(v)) for a, v in t.items()}), t)
                for _, t in random_traj(dfa, rng, 8)]
        assert monitor(len(traj), lambda t, a: traj[t][0][a], dfa, 0.9)[0] == true_verdict(traj, dfa)


def test_online_monitor_reports_early_violation_and_permanent_compliance():
    dfa, _ = RULES["R3_no_subjective_recommendation"]
    m = OnlineMonitor(dfa, 0.5)
    assert m.step(lambda a: 0.05) == "INCONCLUSIVE"
    assert m.step(lambda a: 0.5) == "POSSIBLE_VIOLATION"
    assert m.step(lambda a: 0.02) == "POSSIBLE_VIOLATION" and m.finish() == ABSTAIN
    assert m.step(lambda a: 0.99) == VIOLATION and m.finish() == VIOLATION
    dfa, _ = RULES["R9_compensation_only_on_request"]
    m = OnlineMonitor(dfa, 0.2)
    assert m.step(lambda a: 0.95 if a == "asks_compensation" else None) == COMPLIANT
    assert m.queries() == []


def test_crc_threshold_controls_calibration_risk_and_checks_n():
    dfa, _ = RULES["R1_write_in_confirmation_window"]
    rng = random.Random(5)
    tasks = [[random_traj(dfa, rng, 12) for _ in range(2)] for _ in range(40)]
    loss = lambda tr, tau: loss_verdict(tr, dfa, tau)
    tau = crc_threshold(tasks, loss, 0.1, GRID)
    n = len(tasks)
    risk = sum(sum(loss(tr, tau) for tr in task) / len(task) for task in tasks) / n
    assert n / (n + 1) * risk + 1 / (n + 1) <= 0.1
    with pytest.raises(ValueError):
        crc_threshold(tasks[:5], loss, 0.1, GRID)


def test_probabilistic_monitor_agrees_on_certain_inputs():
    dfa, _ = RULES["R1_write_in_confirmation_window"]
    user = lambda p: {"confirm": p, "user": 1.0, "write": 0.0}
    write = {"confirm": None, "user": 0.0, "write": 1.0}
    assert violation_probability(dfa, [user(1.0), write, write]) == 0.0
    assert violation_probability(dfa, [user(1.0), user(0.0), write]) == 1.0
    assert abs(violation_probability(dfa, [user(0.7), write]) - 0.3) < 1e-9


def test_confidence_grid_and_gate():
    from nesymon.core import confidence_grid
    grid = confidence_grid()
    assert grid[0] == 0.0 and grid[1] == 0.5 and grid[-1] == 1.0 and grid == sorted(grid)
    for p in (0.55, 0.8, 0.97):                       # widened exactly when the top probability is at most tau
        for tau in grid:
            assert (value_set(p, tau) == {0, 1}) == (max(p, 1 - p) <= tau)


def test_class_conditional_threshold_controls_miss_rate():
    from experiments.sim_toy import gen_traj
    from nesymon.core import confidence_grid
    from nesymon.evaluate import alpha_floor, class_conditional_threshold, stratum
    dfa, _ = RULES["R1_write_in_confirmation_window"]
    rng = random.Random(1)
    tasks = {i: [gen_traj(dfa, rng) for _ in range(2)] for i in range(80)}
    units = stratum([(dfa, tasks)], VIOLATION)
    assert 0 < len(units) < 80 and alpha_floor(len(units)) < 0.1
    tau = class_conditional_threshold([(dfa, tasks)], VIOLATION, 0.1, confidence_grid())
    miss = [sum(loss_verdict(tr, d, tau) for tr, d in items) / len(items) for items in units.values()]
    assert sum(miss) / len(miss) <= 0.1
    with pytest.raises(ValueError):
        class_conditional_threshold([(dfa, dict(list(tasks.items())[:8]))], VIOLATION, 0.05, confidence_grid())


def test_evaluate_and_two_sided_calibration():
    from nesymon.evaluate import calibrate, calibrate_two_sided, evaluate, run_splits, summarize
    dfa, _ = RULES["R1_write_in_confirmation_window"]
    rng = random.Random(9)
    tasks = [[random_traj(dfa, rng, 12) for _ in range(2)] for _ in range(60)]
    hard = evaluate(tasks, dfa, 0.0)
    assert hard["abstain"] == 0.0
    assert abs(hard["joint_error"] - hard["miss"] - hard["false_alarm"]) < 1e-12
    tau2 = calibrate_two_sided(tasks, dfa, 0.05, 0.05, GRID)
    assert tau2 >= calibrate(tasks, dfa, "ver", 0.1, GRID)
    res = evaluate(tasks, dfa, tau2)
    assert res["miss"] <= 0.05 and res["false_alarm"] <= 0.05
    runs = run_splits(tasks, dfa, ["hard", "ver"], 0.1, GRID, reps=3)
    assert summarize(runs["ver"])["abstain"][0] >= summarize(runs["hard"])["abstain"][0]


def test_injection_on_synthetic_trajectory():
    from nesymon.data import Step, Trajectory, structured_trace
    from nesymon.inject import drop_confirmation, interrupt_before_write
    steps = [Step("user", "cancel my order"), Step("assistant", "Confirm?"), Step("user", "yes"),
             Step("assistant", "", "cancel_pending_order", "{}"), Step("tool", "ok", "cancel_pending_order")]
    traj = Trajectory("retail", "x", 0, 0, 1.0, steps)
    dropped, log = drop_confirmation(traj)
    assert len(dropped.steps) == 4 and log["removed_step"] == 2
    cut, log = interrupt_before_write(traj)
    assert [p["user"] for p in structured_trace(cut)] == [1, 0, 1, 1, 0, 0] and len(traj.steps) == 5


def test_once_per_order_and_bootstrap():
    from nesymon.data import Step, Trajectory, structured_trace
    from nesymon.evaluate import bootstrap_ci
    call = lambda order: Step("assistant", "", "modify_pending_order_items", '{"order_id": "%s"}' % order)
    result = lambda text: Step("tool", text, "modify_pending_order_items")
    steps = [call("#1"), result("Error: bad item"), call("#1"), result("ok"), call("#2"), result("ok"), call("#1")]
    flags = [p["repeat_once_call"] for p in structured_trace(Trajectory("retail", "x", 0, 0, 1.0, steps))]
    assert flags == [0, 0, 0, 0, 0, 0, 1]
    lo, hi = bootstrap_ci([0.0, 0.5, 1.0, 0.0, 0.5] * 10)
    assert lo < 0.4 < hi


def test_platt_scaling_corrects_a_biased_labeler():
    from nesymon.monitor_prob import fit_platt, platt_scale
    rng = random.Random(1)
    probs, labels = [], []
    for _ in range(2000):                      # true rate 2%, labeler says about 0.25 on negatives
        y = int(rng.random() < 0.02)
        probs.append(min(0.99, max(0.01, (0.8 if y else 0.25) + rng.gauss(0, 0.05))))
        labels.append(y)
    ab = fit_platt(probs, labels)
    scaled = [platt_scale(p, ab) for p in probs]
    assert abs(sum(scaled) / len(scaled) - sum(labels) / len(labels)) < 0.01
    assert platt_scale(0.8, ab) > platt_scale(0.25, ab)
