# Verdict-Level Risk Control for Neurosymbolic Runtime Monitoring of LLM Agents

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)
![MLX 0.32](https://img.shields.io/badge/MLX-0.32-black.svg)
![Status](https://img.shields.io/badge/paper-in%20preparation-lightgrey.svg)

Code, labels and result files for the paper **"Verdict-Level Risk Control for Neurosymbolic Runtime Monitoring of
LLM Agents"** (Wentao Ma, Czech University of Life Sciences Prague; manuscript in preparation). Every number below is
produced by a script in this repository. Results marked *provisional* use agent pre-labels in place of human labels
and will change once the human check of the evaluation labels is complete.

## Overview

LLM agents that act for users, such as cancelling an order or changing a flight, are given written policies:
*"before taking any action that updates the database, list the action details and obtain explicit user confirmation"*.
A promising way to check such rules splits the job in two. A language model reads each turn and answers simple
questions ("did the user explicitly confirm the listed action here?"), and a temporal-logic automaton combines the
answers into a verdict. When the language model misreads a turn, the verdict can be wrong without any sign of it.

This project makes the monitor say how often its verdicts are wrong, and abstain instead of guessing:

- each rule is an **LTLf formula** (linear temporal logic on finite traces) compiled to a small automaton over
  mutually exclusive step types;
- structured propositions (a write call, a transfer, a successful authentication) come from the tool-call log;
  linguistic propositions get a **probability from a local LLM**, asked only on the turns where they can hold;
- a judgement whose top probability is at most a **confidence gate tau** keeps both values open, and the monitor
  tracks every automaton state consistent with the judgements, returning *violation*, *compliance* or *abstain*;
- tau is chosen by **conformal risk control on a verdict-level loss** (1 exactly when the monitor commits to a wrong
  verdict), which is monotone in tau, so the expected rate of confident wrong verdicts on a new task is at most alpha.

<p align="center"><img src="docs/figures/overview.png" width="860" alt="Overview: the tool-call log gives exact values, the LLM labeler gives probabilities that the confidence gate turns into value sets, the rule automaton tracks every consistent state, and conformal risk control on calibration tasks picks the gate"></p>

## Main contributions

1. **A verdict-level loss for set-based monitors**, with a proof that it is monotone in the confidence gate, so
   conformal risk control bounds the rate of confident wrong verdicts at a level alpha chosen by the user. The loss
   hierarchy verdict <= state-relevant <= full coverage shows the usual coverage-style calibration as a more
   conservative special case.
2. **Per-rule and per-error-class budgets** (missed violations vs false alarms), with tasks as the exchangeable unit
   and the finite-sample floor alpha >= 1/(n+1) reported for every rule.
3. **Policy rules grounded verbatim in tau-bench**: eight rules with per-domain policy quotes, automata over
   mutually exclusive step types, and a confirmation-window semantics G(write -> Y(not user S confirm)) under which a
   write does not consume the confirmation.
4. **A labelled benchmark**: proposition-level human labels on public agent trajectories with versioned definitions
   and an adjudication record (835 pilot judgements now; about 6,000 when the evaluation labels are checked).
5. **Negative and limiting results reported as such**: the method helps only when the hard-label error exceeds
   alpha and confident labeling errors are rare, and calibrating propositions does not calibrate verdicts.

## Key results

| Question | Finding | Status | Where |
|---|---|---|---|
| Do the automata implement the formulas? | Every automaton agrees with a reference LTLf semantics on all traces of up to five or six steps. | checked | `tests/test_core.py` |
| Does the guarantee hold? (simulation) | The rate of confident wrong verdicts stays below alpha at every level tested (100 fresh calibration/test draws per level). | checked | `experiments/sim_sweeps.py` |
| When does the method help? (simulation) | At alpha = 0.10, coverage-style calibration abstains on 73 % of trajectories once 1 % of judgements are confidently wrong; verdict-level calibration abstains on 7-27 % up to a 5 % rate and collapses at 10 %. | checked | `experiments/sim_sweeps.py` |
| Can humans agree on the propositions? | Two annotators on 835 pilot judgements: Cohen's kappa 0.84; disagreements adjudicated with written reasons. | checked | `data/labels.csv` |
| Can AI agents pre-annotate? | Agreement with the adjudicated pilot labels 98.9 % and 98.5 % for two agents; a cross-check of a third agent's share left 36 disagreements for humans. | checked | `experiments/compare_annotations.py` |
| Is a small local labeler good enough? (pilot) | Qwen3.5-4B: fewer than 1 % of confirm judgements are wrong with confidence above 0.95; four of five rules with linguistic propositions pass the go/no-go gate. Definitions were tuned on the pilot, so this is optimistic. | checked | `experiments/e0_pilot.py` |
| Labeler size | Qwen3.5-2B ranks worse than 4B on every proposition (pilot AUC 0.60-0.99 vs 0.80-1.00) but is rarely confidently wrong. On R1 at alpha = 0.10, verdict-level calibration keeps wrong verdicts at 6.4 % with 2B, at the cost of 63 % abstention (4B: 7.9 % and 14 %). A weaker labeler costs abstention, not errors. | pilot checked, R1 provisional | `experiments/label_quality.py`, `experiments/run_all.py` |
| Is per-step calibration enough? | No: it calibrates judgements, not verdicts. With the 2B labeler at alpha = 0.10, per-step conformal is wrong on 32 % of R1 and 20 % of R9 trajectories; verdict-level calibration stays at 6.4 % and 5.8 %. | provisional | `experiments/run_all.py` |
| Main comparison, R1 confirmation window | Hard labels are wrong on 15.4 % of trajectories. At alpha = 0.10, verdict-level calibration: 7.9 % wrong, 14.2 % abstention; per-step conformal 6.6 % / 16.3 %; coverage-style 0.1 % / 40.9 %. | provisional | `experiments/run_all.py` |
| Does calibrating propositions calibrate verdicts? | No. On R1, Platt scaling halves the per-turn Brier score of confirm (0.140 to 0.066) but doubles the trajectory Brier score of the probabilistic monitor (0.105 to 0.200). | provisional | `experiments/e1_main.py` |
| Does the guarantee survive a domain shift? | Calibrating R1 on airline and testing on retail gives 17.6 % wrong verdicts at alpha = 0.10, and the label-free shift statistics barely move. | provisional | `experiments/analyses.py` |

<p align="center">
<img src="docs/figures/simulation.png" width="860" alt="Simulation: wrong-verdict rate against alpha for four methods, and abstention and wrong-verdict rate against the rate of confidently wrong judgements"><br>
<em>Simulation with fresh draws: (a) rate of confident wrong verdicts against the target alpha; (b, c) abstention and wrong verdicts at alpha = 0.10 as confident labeling errors become more common.</em>
</p>

## Installation

```bash
git clone https://github.com/witold-andelie/nesymon.git
cd nesymon
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" mlx-lm        # numpy, pandas, matplotlib, pyyaml; pytest; MLX for the local labeler
python -m pytest -q
```

Python 3.11 was used throughout. The local labeler runs with MLX (mlx-lm 0.32.2) and needs Apple silicon; all other
steps run on any CPU. All numbers here were produced on an Apple M1 with 16 GB of memory.

## Data

The raw trajectories are not in the repository.

| Data set | Source | Licence | Used in |
|---|---|---|---|
| tau-bench historical trajectories: 1,980 conversations, retail (115 tasks) and airline (50 tasks), gpt-4o (4 trials per task) and sonnet-35-new (8 trials) | `git clone --depth 1 https://github.com/sierra-research/tau-bench.git data/raw/tau-bench` | MIT | everything |
| tau-bench policy documents (rule quotes) | same repository | MIT | `rules/rules.yaml` |
| Pilot labels: 835 judgements on 20 pilot tasks | this repository, `data/labels.csv` | Apache 2.0 | `e0_pilot`, `label_quality` |
| Evaluation pre-labels: 5,431 judgements on 145 tasks (290 trajectories) | this repository, `results/full_preannotation.csv` | Apache 2.0 | provisional results |

Pilot tasks are used only to tune the proposition definitions and are excluded from every evaluation. Annotation
sheets and labeler probability caches are generated locally (`data/README.md`) and are not stored here, because the
sheets repeat the conversation text.

## Reproducing the results

Run every command from the repository root.

| Result | Script | Command | Hardware (measured time) |
|---|---|---|---|
| Simulated guarantee and regime sweep, figure above | `sim_sweeps`, `readme_figures` | `python -m experiments.sim_sweeps`, `python -m experiments.readme_figures` | CPU |
| Toy comparison of the three calibration losses | `sim_toy` | `python -m experiments.sim_toy` | CPU |
| Data statistics, natural violations per rule and alpha floors | `data_stats`, `rule_counts` | `python -m experiments.data_stats`, `python -m experiments.rule_counts` | CPU |
| Annotation sheets (pilot, then evaluation) | `make_annotation_sheet` | `python -m experiments.make_annotation_sheet --tasks 10`, then without `--tasks` | CPU |
| Labeler probabilities | `run_labeler` | `python -m experiments.run_labeler --model mlx-community/Qwen3.5-4B-4bit` | M1, 16 GB (all 6,266 judgements: 4B 2.7 s each, about 4.7 h; 2B 1.46 s each, about 2.5 h) |
| Pilot gate and label quality | `e0_pilot`, `label_quality` | `python -m experiments.e0_pilot --probs <cache>`, `python -m experiments.label_quality --probs <cache>` | CPU (seconds) |
| All real-data experiments (E1, E2, E4, E6, E7, E8) | `run_all` | `python -m experiments.run_all --probs <cache> --labels <labels>` | CPU (about 8 min with `--reps 100`) |

`<cache>` is `data/probs/<model>.jsonl`, written by `run_labeler`. The labeler cache is append-only and keyed by
trajectory, step and proposition, so an interrupted run resumes where it stopped.

## Verification

- **Automata against formulas.** Each automaton is compared with a reference LTLf semantics with past operators on
  every trace up to the tested length, and each rule's pure-past form with its future form (`tests/test_core.py`).
- **Properties of the method.** Nested value sets, monotonicity of the verdict loss in tau, the loss hierarchy, the
  calibration threshold and its alpha floor, and the class-conditional budgets are unit-tested; a simulated pipeline checks the main table end to end (`tests/test_pipeline.py`).
- **Labeler cache.** Probabilities computed with the shared-prefix cache were compared with fresh model calls
  (largest difference 0.004). This check found that hybrid-attention models (Qwen3.5) cannot reuse a trimmed cache;
  all affected runs were deleted and recomputed.
- **Labels.** Human pilot labels were double-annotated and adjudicated; AI pre-annotations were scored against them on
  the held-out pilot before use, and one agent's share was cross-checked by another (`results/review_hy4_vs_codex.csv`).
- **Statistics.** Results are averaged over repeated random task splits; intervals are task-level bootstrap intervals.

## Limitations

All trajectories come from one benchmark with simulated users and two agents, in two customer-service domains. The
guarantee is marginal over exchangeable tasks: it does not hold under a shift between calibration and use, and the
provisional cross-domain result suggests that label-free statistics may not detect such a shift. Some rules have few
tasks (R9: 40 evaluation tasks, alpha floor 0.059 with a 40 % calibration split), and three of the five rules with
linguistic propositions have a hard-label error already below alpha = 0.10, where the method adds nothing. The
proposition definitions were tuned on the pilot tasks, and the evaluation labels are not yet human-checked.

## Repository structure

```
nesymon/            the method
  core.py           automata over step types, value sets, online set monitor, losses, conformal risk control
  ltlf.py           reference LTLf semantics with past operators
  evaluate.py       task splits, pooled / two-sided / class-conditional calibration, metrics, bootstrap
  baselines.py      hard-label, raw-threshold, per-step conformal and LLM-judge baselines
  monitor_prob.py   probabilistic comparator (forward algorithm, temperature and Platt scaling)
  labeler.py        labeler prompt, yes/no probability, probability cache
  backend_mlx.py    MLX backend that reuses the shared conversation prefix
  data.py           tau-bench loader, structured propositions, label sites
  pipeline.py       labeling driver and assembly of monitor inputs
  inject.py         programmatic violation injection
rules/              rule registry with policy quotes (rules.yaml) and automaton templates (dfas.py)
props/              proposition definitions shared by the labeler prompt and the annotators
experiments/        simulations, data statistics, annotation, labeling, pilot gate, real-data experiments
data/               pilot labels, adjudication record, agent pre-annotations (no raw data)
results/            pre-annotation files, review sheet, simulation output
docs/
  theory.md         definitions, lemmas and proofs
  design_review.md  decision log: every design choice with its evidence and caveats
  framework/        OPM diagram of the project (DOT source and renderings)
  figures/          figures shown in this README
tests/              unit and property tests
```

Pre-annotation was done by AI agents working from `data/preannotation/INSTRUCTIONS.md` in separate folders that did
not contain the human labels; their raw outputs are kept separately per agent in `data/preannotation/`.

## Citation

The paper is in preparation; until it is published, please cite the repository as:

```bibtex
@unpublished{ma2026verdict,
  author = {Ma, Wentao},
  title  = {Verdict-Level Risk Control for Neurosymbolic Runtime Monitoring of {LLM} Agents},
  note   = {Manuscript in preparation; code at https://github.com/witold-andelie/nesymon},
  year   = {2026}
}
```

## License

The code and the labels are released under the Apache License 2.0 (`LICENSE`). The tau-bench trajectories and policy
documents are not redistributed here and remain under their MIT licence.

## Acknowledgements

The author thanks Professor Vojtěch Merunka (Faculty of Economics and Management, Czech University of Life Sciences
Prague) for his guidance on the Object-Process Methodology (OPM) framework. Trajectories and policies come from
tau-bench (Yao et al., 2024).
