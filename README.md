# nesymon

**Verdict-level risk control for neurosymbolic runtime monitoring of LLM agents.**

LLM agents that act for users (cancelling orders, changing flights) are given written policies such as
*"before taking any action that updates the database, list the action details and obtain explicit user
confirmation"*. `nesymon` checks whether an agent followed such rules over a whole conversation, and bounds how often
its verdicts are wrong: when it is not sure enough, it abstains instead of guessing.

> Status: research code, work in progress (November 2026). The method, theory, simulations, labeling pipeline and a
> human-labelled pilot are complete; the human check of the evaluation labels and the full experiments are next.

## The problem

A promising way to monitor agents splits the job in two. A language model reads each turn and answers simple
questions ("did the user explicitly confirm the listed action here?"), and a formal rule checker combines those
answers into a verdict. When the language model misreads a turn, the verdict can silently be wrong. `nesymon` asks:
can such a monitor guarantee, on new conversations, that the rate of confident wrong verdicts stays below a level the
user chooses?

## Method

1. **Rules as automata.** Each policy rule is written in linear temporal logic on finite traces (LTLf) and compiled to
   a small deterministic automaton over mutually exclusive step types. Every hand-written automaton is checked
   against a reference LTLf semantics on all traces of up to five or six steps.
2. **Propositions.** Structured propositions (a write call, a transfer, a successful authentication) are read from the
   tool-call log. Linguistic propositions (the user confirmed, the assistant gave a subjective recommendation) get a
   probability from a local language model, asked only on the turns where the proposition can hold.
3. **Set-based monitoring.** A judgement whose top probability is at most a confidence gate `tau` keeps both values
   open. The monitor tracks every automaton state consistent with the judgements and returns *violation*,
   *compliance* or *abstain*.
4. **Verdict-level risk control.** `tau` is chosen on calibration tasks by conformal risk control, using a loss that is
   1 exactly when the monitor commits to a wrong verdict. This loss is monotone in `tau`, so the expected rate of
   confident wrong verdicts on a new task is at most `alpha`. Per-rule and per-error-class variants (missed violations
   vs false alarms) are included; coverage-style calibration is a more conservative special case.

Definitions, lemmas and proofs are in [`docs/theory.md`](docs/theory.md).

## Data and labels

- **Trajectories:** 1,980 public agent conversations from [tau-bench](https://github.com/sierra-research/tau-bench)
  (retail and airline customer service, MIT licence), from two agents with 4 and 8 trials per task. Not included here;
  see *Setup*.
- **Rules:** eight rules in [`rules/rules.yaml`](rules/rules.yaml), each quoting the tau-bench policy text verbatim
  (confirmation window, write matches the listed action, no subjective recommendation, transfer only when justified,
  authentication first, one modification per order, no flight change on basic economy, compensation only on request).
- **Proposition definitions:** [`props/definitions.yaml`](props/definitions.yaml) (version 2.1), shared by the
  labeler prompt and the human annotators.
- **Pilot labels:** [`data/labels.csv`](data/labels.csv), 835 judgements on 20 pilot tasks, two annotators (Cohen's
  kappa 0.84), disagreements adjudicated; the record is in
  [`data/label_adjudication_history.csv`](data/label_adjudication_history.csv) and
  [`data/label_adjudication_notes.md`](data/label_adjudication_notes.md). Pilot tasks are used only to tune the
  definitions and are excluded from evaluation.
- **Evaluation pre-labels:** [`results/full_preannotation.csv`](results/full_preannotation.csv), 5,431 judgements on
  290 trajectories of 145 tasks, pre-labelled by AI agents for human checking (agreement with the adjudicated pilot
  labels: 98.9% and 98.5% for the two annotating agents that were calibrated; a third agent's share was cross-checked
  and its 36 disagreements are in [`results/review_hy4_vs_codex.csv`](results/review_hy4_vs_codex.csv)). These are not
  yet human-checked ground truth.

## Results so far

- **Theory checked by tests.** Monotonicity of the verdict loss, the loss hierarchy, and every automaton against its
  formula (`pytest`).
- **Simulation** (`experiments/sim_sweeps.py`, fresh draws): the joint error stays below `alpha` at every level
  tested. At alpha = 0.10, coverage-style calibration abstains on 73% of trajectories once 1% of judgements are
  confidently wrong, while verdict-level calibration abstains on 7-27% up to a 5% confident-error rate and collapses
  to the coverage level at 10%.
- **Pilot gate** (Qwen3.5-4B labeler, definitions v2.1): fewer than 1% of `confirm` judgements are wrong with
  confidence above 0.95, and four of the five rules with linguistic propositions pass the go/no-go check. The
  definitions were tuned on the pilot, so these numbers are optimistic.

The full record of decisions, evidence and caveats is in [`docs/design_review.md`](docs/design_review.md).

## Repository layout

| Path | Content |
| --- | --- |
| `nesymon/core.py` | Automata over step types, value sets, online set monitor, losses, conformal risk control |
| `nesymon/ltlf.py` | Reference LTLf semantics with past operators |
| `nesymon/evaluate.py` | Task splits, pooled / two-sided / class-conditional calibration, metrics, bootstrap |
| `nesymon/baselines.py` | Hard-label, raw-threshold, per-step conformal and LLM-judge baselines |
| `nesymon/monitor_prob.py` | Probabilistic comparator (forward algorithm) |
| `nesymon/labeler.py`, `nesymon/backend_mlx.py` | Labeler prompt, probability cache, MLX backend with prefix reuse |
| `nesymon/data.py`, `nesymon/pipeline.py` | tau-bench loader, structured propositions, label sites, input assembly |
| `nesymon/inject.py` | Programmatic violation injection |
| `rules/` | Rule registry and automaton templates |
| `props/` | Proposition definitions |
| `experiments/` | Simulations, data statistics, annotation sheets, labeling, pilot gate, all real-data experiments |
| `data/` | Pilot labels and adjudication record; agent pre-annotation outputs in `data/preannotation/` |
| `results/` | Pre-annotation files, review sheet, simulation output |
| `docs/` | Theory, design review and decision log, project framework diagram |
| `tests/` | Unit and property tests |

## Setup

Requires Python 3.11. The local labeler uses [MLX](https://github.com/ml-explore/mlx) and needs Apple silicon; the rest
runs anywhere.

```bash
git clone git@github.com:witold-andelie/nesymon.git && cd nesymon
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" mlx-lm
git clone --depth 1 https://github.com/sierra-research/tau-bench.git data/raw/tau-bench
python -m pytest -q
```

## Reproducing

```bash
python -m experiments.sim_toy                     # three calibration losses on one simulated labeler
python -m experiments.sim_sweeps                  # guarantee against alpha and regime sweep (simulation)
python -m experiments.data_stats                  # statistics of the tau-bench trajectories
python -m experiments.rule_counts                 # natural violations per rule and class, with alpha floors
python -m experiments.make_annotation_sheet --tasks 10   # pilot sheet (writes data/pilot_tasks.json)
python -m experiments.make_annotation_sheet              # evaluation sheet, pilot tasks excluded
python -m experiments.run_labeler --model mlx-community/Qwen3.5-4B-4bit   # labeler probabilities (about 4 h on an M1)
python -m experiments.e0_pilot --probs data/probs/mlx-community__Qwen3.5-4B-4bit.jsonl
python -m experiments.run_all  --probs data/probs/mlx-community__Qwen3.5-4B-4bit.jsonl --labels <checked labels>
```

Annotation sheets and labeler caches are generated locally and are not stored in the repository.

## Roadmap

- Human check of the 5,431 evaluation pre-labels and a 20% double-annotation sample.
- Full experiments: main comparison, guarantee against `alpha`, labeler size ladder (Qwen3.5-2B / 4B), length
  buckets, retail-to-airline shift, error autocorrelation, regime under injected errors.
- Preprint and public release of the human-checked labels.

## Acknowledgements

Trajectories and policies come from tau-bench (Yao et al., 2024, MIT licence). Pre-annotation used Claude, Codex and
a third model through opencode; their outputs are kept separately in `data/preannotation/` and marked by source.

## License

Apache License 2.0, see [LICENSE](LICENSE).
