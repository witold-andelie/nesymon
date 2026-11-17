from nesymon.core import monitor, true_verdict
from nesymon.data import Step, Trajectory
from nesymon.labeler import ProbCache, yes_no_probability
from nesymon.pipeline import assemble, label_sites, label_trajectory, load_labels, load_prop_defs
from rules.dfas import RULES


class FakeBackend:
    """Says Yes with high confidence when the last user turn contains 'yes'."""
    def answer_logits(self, prefix, suffix):
        last = prefix.strip().splitlines()[-1].lower()
        return (4.0, 0.0) if "yes" in last else (0.0, 4.0)


def make_traj():
    steps = [Step("user", "please cancel order 1"), Step("assistant", "Cancel order 1, correct?"),
             Step("user", "yes"), Step("assistant", "", "cancel_pending_order", '{"order_id": "1"}'),
             Step("tool", "done", "cancel_pending_order"), Step("user", "thanks, also order 2"),
             Step("assistant", "", "cancel_pending_order", '{"order_id": "2"}')]
    return Trajectory("retail", "fake", 3, 0, 1.0, steps)


def test_label_assemble_monitor_roundtrip(tmp_path):
    traj, defs = make_traj(), load_prop_defs()
    dfa, _ = RULES["R1_write_in_confirmation_window"]
    assert label_sites(traj, dfa.props) == [(0, "confirm"), (2, "confirm"), (5, "confirm")]
    assert label_sites(traj, ["matches_listed"]) == [(3, "matches_listed"), (6, "matches_listed")]
    cache = ProbCache(str(tmp_path / "fake.jsonl"))
    assert label_trajectory(traj, {"confirm": defs["confirm"]}, FakeBackend(), cache) == 3
    assert label_trajectory(traj, {"confirm": defs["confirm"]}, FakeBackend(), cache) == 0
    assert ProbCache(str(tmp_path / "fake.jsonl")).get(traj.traj_id, 2, "confirm") == yes_no_probability(4.0, 0.0)

    sheet = tmp_path / "labels.csv"
    sheet.write_text("task_id,traj_id,step,prop,value,note\n"
                     f"retail-3,{traj.traj_id},0,confirm,0,\nretail-3,{traj.traj_id},2,confirm,1,\n"
                     f"retail-3,{traj.traj_id},5,confirm,0,\n")
    data = assemble(traj, dfa, cache, load_labels(str(sheet)))
    assert data[3][0] == {"confirm": None, "user": 0.0, "write": 1.0}
    assert true_verdict(data, dfa) == "VIOLATION"                       # the second write follows a non-confirming turn
    verdict, calls = monitor(len(data), lambda t, a: data[t][0][a], dfa, 0.1)
    assert verdict == "VIOLATION" and calls == 3


def test_main_table_on_simulated_tasks():
    import random
    from experiments.e1_main import brier_of_prob_monitor, main_table
    from experiments.sim_toy import gen_traj
    dfa, _ = RULES["R1_write_in_confirmation_window"]
    rng = random.Random(2)
    tasks = [[gen_traj(dfa, rng, T=15) for _ in range(2)] for _ in range(50)]
    table = main_table(tasks, dfa, alpha=0.1, reps=3)
    assert table["B2_hard"]["abstain"][0] == 0.0
    assert table["Ours_Cov"]["tau"][0] >= table["Ours_SR"]["tau"][0] >= table["Ours_Ver"]["tau"][0]
    assert table["Ours_Ver_two_sided"]["tau"][0] >= table["Ours_Ver"]["tau"][0]
    raw, scaled = brier_of_prob_monitor(tasks, dfa, reps=2)
    assert 0.0 <= raw <= 1.0 and 0.0 <= scaled <= 1.0


def test_analyses_on_simulated_tasks():
    import random
    from experiments.analyses import alpha_sweep, cross_domain, regime_sweep
    from experiments.sim_toy import gen_traj
    dfa, _ = RULES["R1_write_in_confirmation_window"]
    rng = random.Random(4)
    tasks = [[gen_traj(dfa, rng, T=15) for _ in range(2)] for _ in range(60)]
    sweep = alpha_sweep(tasks, dfa, alphas=(0.05, 0.2), reps=5)
    assert sweep[0]["abstain"] >= sweep[1]["abstain"] and sweep[0]["tau"] >= sweep[1]["tau"]
    regime = regime_sweep(tasks, dfa, rates=(0.0, 0.1), reps=3)
    assert regime[1]["hard_error"] > regime[0]["hard_error"]
    shift = cross_domain(tasks[:30], tasks[30:], dfa)
    assert 0.0 <= shift["target_joint_error"] <= 1.0


def test_judge_baseline_and_extra_analyses():
    import random
    from experiments.analyses import difficulty_buckets, error_autocorrelation
    from experiments.run_judge import rule_texts
    from experiments.sim_toy import gen_traj
    from nesymon.baselines import judge_violation_probability
    from nesymon.pipeline import render_history

    class Judge:
        def answer_logits(self, prefix, suffix):
            assert "Rule:" in suffix and "Conversation:" in prefix
            return (1.0, 3.0)

    texts = rule_texts()
    assert set(texts) == set(RULES)
    p = judge_violation_probability(render_history(make_traj().steps), texts["R1_write_in_confirmation_window"], Judge())
    assert 0.0 < p < 0.5
    dfa, _ = RULES["R1_write_in_confirmation_window"]
    rng = random.Random(6)
    tasks = [[gen_traj(dfa, rng, T=rng.choice([10, 30, 40])) for _ in range(2)] for _ in range(40)]
    rows = difficulty_buckets(tasks, dfa, 0.7)
    assert sum(r["n"] for r in rows) == 80 and all(r["error"] <= r["hard_error"] for r in rows)
    assert abs(error_autocorrelation(tasks, dfa)) < 0.3
