# Design review and decision log

Last updated 2026-11-16. "Checked" means verified by code or data in this repository; "search" means
a web search (titles and abstracts only); "author" means a decision or verification supplied by the
project author and not re-verified here.

## 1. Where the design stands

| Topic | Decision | Status |
| --- | --- | --- |
| R1 semantics | Confirmation window: `G(write -> Y(!user S confirm))`. A window opens at a confirming user turn and closes at the next user turn. | Implemented, DFA checked against the formula |
| Listed-versus-executed check | Separate rule `G(write -> matches_listed)`, judged only on write calls | Implemented as R2 |
| Alphabet | Mutually exclusive step types per rule instead of free bit-vectors; impossible letters are never explored | Implemented (`DFA.alphabet`) |
| Threshold | tau is a confidence gate: a judgement is widened exactly when the labeler's top probability is at most tau. Grid on [0.5, 1] in log-odds | Implemented (`confidence_grid`) |
| Relevance filtering (VRG, former M3) | Dropped from the paper; one sentence plus the CAV 2005 citation. Experiment E5 dropped | Done; the code keeps relevance only for the state-relevant loss |
| Risk budgets | One threshold per rule; class-conditional budgets (miss, false alarm) where counts allow; sparse rules pooled by type | Implemented (`class_conditional_threshold`, `stratum`), counts pending labels |
| Rule set | Only rules with a basis in the policy text and natural violations; one verbatim quote per domain | Eight rules in the registry (one selected, four candidates, three structured controls); one response rule kept as a case study |
| Formula form | "G over a past formula" rules also stated in pure-past form (H, read at the last position) | Implemented and tested equivalent (`PAST_FORM`). LTLf2DFA accepts LTLf or pure-past formulas but not a mix (its README, checked 2026-11-16), so the pure-past form is the one to cross-check with it |
| Annotator aids | Reference solution actions are given to human annotators, never to the labeler | Written next to each annotation sheet |
| Shift detection (E6) | Label-free indicators only (labeler confidence, abstention rate); stated to detect input shift only | Implemented in `analyses.cross_domain` |
| Uncertainty reporting | Task-level bootstrap intervals | Implemented (`bootstrap_ci`), used in the pilot script |
| Pilot hygiene | Proposition definitions are iterated on pilot tasks only; pilot tasks are excluded from the final evaluation | Implemented (`data/pilot_tasks.json`) |
| Label release | Publish the human-checked proposition labels as a dataset | Planned contribution |

## 2. Evidence gathered so far

### 2.1 The check that settles R1 (checked, no labels needed)

Share of "write windows" (stretches between adjacent user turns that contain a write) holding two or
more write calls, from `experiments/data_stats.py` over all 1,980 trajectories:

| Agent | Domain | Write windows | With two or more writes | Trajectories affected |
| --- | --- | --- | --- | --- |
| gpt-4o | airline | 184 | 39 (21.2%) | 17.5% |
| gpt-4o | retail | 567 | 75 (13.2%) | 16.1% |
| sonnet-35-new | airline | 346 | 92 (26.6%) | 22.5% |
| sonnet-35-new | retail | 1,175 | 143 (12.2%) | 15.0% |

Multi-write windows are common, so the "one confirmation per write" reading would create false
violations in 15 to 22 percent of trajectories. Window semantics is required, not merely preferable.

### 2.2 Natural violations of the fully structured rules (checked, exact, all trajectories)

| Rule | Violating trajectories | Tasks with a violation | Calibration tasks at 40% | Miss-rate alpha floor |
| --- | --- | --- | --- | --- |
| R6 no basic-economy flight change (airline) | 16 of 600 | 6 of 50 | 2 | 0.333 |
| R7 authenticate before info tools (retail) | 34 of 1,380 | 9 of 115 | 4 | 0.200 |
| R8 once per order (retail) | 5 of 1,380 | 3 of 115 | 1 | 0.500 |

R7 uses the wide reading (product tools included, as the policy sentence on what may be provided
"once the user has been authenticated" names product information); the narrow reading gives 6
trajectories. None of the three can carry its own miss budget; they are structured controls. Not
added, because they never occur: several tool calls in one message, a tool call after a transfer.

Other structural counts: transfers occur in 104 of 1,380 retail and 179 of 600 airline trajectories
(the trigger of R4); `send_certificate` is called in 30 of 600 airline trajectories (a trigger of R9).
The count table for the linguistic rules comes from `experiments/rule_counts.py` once pilot labels
exist.

### 2.3 Annotation load (checked)

Trial 0 of both agents per task. Pilot: 10 tasks per domain, 835 judgements (confirm 278,
subjective_recommendation 238, asks_compensation 138, offers_compensation 118, matches_listed 55,
transfer_justified 8). Remaining 145 tasks: 5,431 judgements. The pilot sample holds only 8 transfer
calls, too few to assess agreement on `transfer_justified`; add transfer-containing trajectories to
the pilot if that proposition is to be tested properly.

### 2.4 Toy simulation under window semantics (checked)

`experiments/sim_toy.py`, alpha = 0.1, 115 tasks x 4 trajectories, 20 splits, violation rate 0.372.
Generator parameters were re-chosen for the new rule, so numbers are not comparable with the guide's
table, which the previous version of the code reproduced exactly (0.213 / 0.95 / 0.61 / 0.273 /
0.080 / 0.108) before the rule changed.

| Method | tau | Abstention | Joint error | Conditional error |
| --- | --- | --- | --- | --- |
| Hard labels | 0 | 0 | 0.117 | 0.117 |
| Full coverage | 0.953 | 0.772 | 0.000 | 0.000 |
| State-relevant coverage | 0.953 | 0.772 | 0.000 | 0.000 |
| Verdict-level | 0.573 | 0.107 | 0.061 | 0.067 |

The direction is unchanged: coverage calibration abstains on most trajectories, verdict-level
calibration on about a tenth. Fewer noisy judgements per trajectory (only user turns are judged) make
every method abstain less than in the guide's version.

### 2.5 Simulated sweeps with fresh draws (checked)

`experiments/sim_sweeps.py`, output in `results/sim_sweeps.csv`: fresh calibration and test tasks in
each of 100 repetitions, so the mean joint error estimates the quantity the theorem bounds. Toy data
with hand-set noise; it shows mechanisms, not real-data numbers. Hard-label error is about 0.114,
of which 0.094 false alarms and 0.020 misses.

| alpha | Verdict-level joint error | Conditional error | Abstention | Two-sided abstention | Coverage abstention |
| --- | --- | --- | --- | --- | --- |
| 0.05 | 0.020 | 0.025 | 0.43 | 0.79 | 0.78 |
| 0.075 | 0.047 | 0.054 | 0.16 | 0.57 | 0.78 |
| 0.10 | 0.071 | 0.077 | 0.09 | 0.36 | 0.78 |
| 0.15 | 0.109 | 0.110 | 0.01 | 0.12 | 0.78 |
| 0.20 | 0.115 | 0.115 | 0.00 | 0.06 | 0.66 |
| 0.30 | 0.116 | 0.116 | 0.00 | 0.00 | 0.17 |

- The joint error stays below alpha at every level (standard errors 0.002 to 0.003).
- From alpha = 0.15 upward the hard-label error is already below alpha, calibration returns tau = 0
  and the method adds nothing. The method is only meaningful for alpha below the hard-label error.
- In this setting the conditional error stays below alpha as well, because abstention is low. The
  earlier rule version showed it exceeding alpha; the paper should present it as unguaranteed either way.
- Splitting the budget evenly between misses and false alarms (joint version) raises abstention by
  11 to 41 points at alpha <= 0.15.

Regime sweep at alpha = 0.10, by per-judgement confident-error rate:

| Confident-error rate | Hard-label error | Verdict-level abstention | Coverage abstention |
| --- | --- | --- | --- |
| 0 | 0.088 | 0.05 | 0.18 |
| 0.01 | 0.100 | 0.07 | 0.73 |
| 0.02 | 0.113 | 0.09 | 0.78 |
| 0.05 | 0.153 | 0.27 | 0.79 |
| 0.10 | 0.212 | 0.78 | 0.79 |

Coverage calibration collapses at a 1 percent confident-error rate. Verdict-level calibration degrades
gradually up to 5 percent and collapses to the coverage level at 10 percent.

### 2.6 Labeler throughput (checked)

4-bit MLX models on the 16 GB Apple-silicon machine, measured on four pilot trajectories while a
CPU job was also running:

| Model | Seconds per judgement | New tokens encoded per second | Prompt tokens served from cache |
| --- | --- | --- | --- |
| Qwen2.5-1.5B-Instruct | 0.31 | 389 | 89% |
| Qwen2.5-7B-Instruct | 1.57 | 90 | 88% |

Over the whole pilot (835 judgements, longer conversations, nothing else running) the 7B model
averaged 3.05 s per judgement with 84 percent of prompt tokens served from cache: 42 minutes for the
pilot, and about 4.6 hours projected for the remaining 5,431.

The prompt prefix differs from the guide's template: it grows append-only (the turn number moved into
the question) so that the KV cache can be reused, and tool calls are rendered with their arguments so
that write-step propositions can be judged.

### 2.7 Label-free pilot with the 7B labeler (checked; no ground truth, so nothing here is an error rate)

Source: `experiments/label_free_stats.py` and `experiments/rule_counts.py --probs`, 40 pilot
trajectories (20 tasks), revised definitions.

| Rule | Hard-label violations | Tasks with a hard-label violation | Abstention at tau = 0.8 | Abstention at tau = 0.95 |
| --- | --- | --- | --- | --- |
| R1 confirmation window | 4 of 40 | 4 of 20 | 0% | 5% |
| R2 matches listed | 4 of 40 | 4 of 20 | 5% | 15% |
| R3 subjective recommendation | 14 of 40 | 11 of 20 | 7.5% | 20% |
| R4 transfer justified | 0 of 40 | 0 of 20 | 0% | 5% |
| R9 compensation on request (airline) | 3 of 20 | 2 of 10 | 5% | 5% |

Per-proposition confidence of the labeler:

| Proposition | Judgements | Yes | Top probability <= 0.8 | Top probability <= 0.95 |
| --- | --- | --- | --- | --- |
| confirm | 278 | 103 | 7 | 30 |
| subjective_recommendation | 238 | 22 | 7 | 17 |
| asks_compensation | 138 | 6 | 1 | 6 |
| offers_compensation | 118 | 7 | 1 | 2 |
| matches_listed | 55 | 48 | 5 | 13 |
| transfer_justified | 8 | 8 | 0 | 2 |

What this suggests, pending human labels:

- The labeler is confident on most judgements (89 to 98 percent of them above 0.95, except
  matches_listed at 76 percent), so abstention stays low even at a strict gate. Whether that
  confidence is deserved is exactly what the pilot labels must show.
- R3 fires in 11 of 20 tasks according to the labeler. Either subjective recommendations are common,
  or the labeler over-detects them; this rule is the first place to look at disagreements.
- confirm is answered Yes on 103 of 278 user turns, which looks high for the stricter definition and
  should be checked the same way.
- R4 has only 8 transfer calls in the pilot and the labeler accepts all of them; the pilot cannot
  test this proposition without more transfer-containing trajectories.
- If the labeler's counts are roughly right, R1, R2 and R9 would have about 20 percent of tasks with a
  violation, which over 145 evaluation tasks gives around a dozen calibration tasks in the violation
  class and a miss-rate floor near 0.08. Per-rule miss budgets would then be marginal and pooling by
  rule type the realistic option.

### 2.8 Pilot labels and the E0 gate (checked against the adjudicated human labels)

Labels: `data/labels.csv`, 835 judgements on 40 trajectories of the 20 pilot tasks, two annotators,
33 disagreements adjudicated by a third party plus one agreed label corrected (provenance in
`data/label_adjudication_history.csv` and `data/label_adjudication_notes.md`).

| Proposition | Judgements | Positives | Annotator disagreements | Cohen kappa |
| --- | --- | --- | --- | --- |
| confirm | 278 | 39 | 18 | 0.76 |
| subjective_recommendation | 238 | 3 | 5 | 0.54 |
| asks_compensation | 138 | 7 | 0 | 1.00 |
| offers_compensation | 118 | 5 | 2 | 0.74 |
| matches_listed | 55 | 49 | 7 | 0.00 |
| transfer_justified | 8 | 4 | 1 | 0.75 |

Overall kappa is 0.84. Two propositions fall below the 0.6 bar: subjective_recommendation (very few
positives) and matches_listed, where kappa is zero despite 87 percent raw agreement because one
annotator used a single value throughout. Both need the tightened definitions and a second agreement
check; the adjudication notes already fix the interpretation rules.

Natural violations on the pilot (human labels): R1 in 7 of 20 tasks (9 of 40 trajectories), R4 in 3
tasks, R3 in 3, R2 in 2, R9 in 1 of 10 airline tasks. Scaled to the 145 evaluation tasks at a 40
percent split, only R1 (about 20 calibration tasks with a violation, floor near 0.05) can carry its
own miss budget; R2, R3, R4 and R9 need pooling by rule type or a joint budget only.

E0 with the 7B labeler under version 1 of the definitions (`experiments/e0_pilot.py`):

| Rule | Violation rate | Hard-label error (95% task bootstrap) | Errors surviving tau = 0.8 | Gate |
| --- | --- | --- | --- | --- |
| R1 confirmation window | 0.225 | 0.125 (0.025-0.250) | 0.125 | too noisy |
| R2 matches listed | 0.050 | 0.050 (0.000-0.125) | 0.025 | continue |
| R3 subjective recommendation | 0.075 | 0.275 (0.125-0.425) | 0.225 | too noisy |
| R4 transfer justified | 0.100 | 0.100 (0.000-0.225) | 0.100 | continue (8 transfer calls only) |
| R9 compensation on request | 0.100 | 0.050 (0.000-0.150) | 0.000 | continue |

Labeler against human labels, per proposition (`experiments/label_quality.py`):

| Proposition | TP | FP | FN | TN | Accuracy | Wrong with confidence above 0.95 |
| --- | --- | --- | --- | --- | --- | --- |
| confirm | 38 | 65 | 1 | 174 | 0.76 | 54 of 278 (19%) |
| subjective_recommendation | 3 | 19 | 0 | 216 | 0.92 | 11 of 238 (5%) |
| matches_listed | 44 | 4 | 5 | 2 | 0.84 | 3 of 55 (5%) |
| offers_compensation | 4 | 3 | 1 | 110 | 0.97 | 2 of 118 |
| asks_compensation | 5 | 1 | 2 | 130 | 0.98 | 2 of 138 |
| transfer_justified | 4 | 4 | 0 | 0 | 0.50 | 3 of 8 |

Reading: the labeler almost never misses a positive but says Yes far too often, and does so with high
confidence. For confirm the confident-error rate per judgement is about 19 percent, far beyond the 5
to 10 percent at which the simulation shows verdict-level calibration collapsing; no threshold can
rescue that. The false positives have a clear shape: closing thank-you turns after the action was
already carried out, turns where the user chooses an option or supplies a parameter, and for
subjective_recommendation, option lists filtered by the user's own criterion. These are definition
and prompt problems rather than capacity problems, so version 2 of `props/definitions.yaml` states the
adjudicated interpretation rules explicitly. The version 1 outputs are kept in
`results/pilot_probs_7B_definitions_v1.jsonl` for comparison.

### 2.9 Labeler model choice (checked on Hugging Face, 2026-11-16)

The first runs used Qwen2.5-7B-Instruct (released September 2024), chosen from memory without
checking what was current; that was a mistake for a paper submitted in 2026 or later. Qwen3.8 has no
small model: its open checkpoints are a 27B dense model (about 18 GB at 4 bits, too large for a 16 GB
machine), Flash-Next and a 2.4T flagship. The newest Qwen family with small models is Qwen3.5
(February to March 2026): 0.8B, 2B, 4B and 9B, all with 4-bit MLX builds. The labeler ladder for E3 is
therefore Qwen3.5 at 2B / 4B / 9B, with 9B as the main labeler; Qwen2.5-7B is kept only as an
older-generation reference point.

**Decision (author, 2026-11-16): the main labeler is Qwen3.5-4B (4 bits), the size ladder is Qwen3.5-2B / 4B.**
On a labelled pilot sample (`diag2`, logits only), Qwen3.5-4B, Qwen3-4B-Instruct-2507 and Gemma 4 e4b all reach AUC
0.83-1.00 per proposition, comparable to Qwen2.5-7B, while Qwen3.5-9B with reasoning off is near chance on four of
six propositions and runs out of memory with reasoning on. Qwen3.5-4B labels at 2.3 s per judgement with prefix
caching (79 percent of prompt tokens reused), about 4 hours for all 330 trajectories. The Qwen2.5 weights were
deleted; `results/pilot_probs_7B_definitions_v1.jsonl` is kept as the source of section 2.8.

Earlier measurement: Qwen3.5-9B (4 bits) runs on the 16 GB machine at 4.5 s per judgement with reasoning switched off in
the chat template, so the pilot takes about an hour and the remaining 5,431 judgements about 7 hours.

### 2.10 Blind pre-annotation of the pilot by a frontier model (checked)

Claude (the assistant maintaining this repository, not one of the evaluated labelers) judged all 835
pilot sites from the trajectories and the version 2 definitions, without access to the label values.
Output: `results/pilot_preannotation_blind.csv`; comparison: `experiments/compare_annotations.py`.

| Proposition | Sites compared | Label positives | Changed by the human labels | Agreement | Cohen kappa |
| --- | --- | --- | --- | --- | --- |
| confirm | 260 | 36 | 4 | 0.985 | 0.94 |
| subjective_recommendation | 232 | 2 | 1 | 0.996 | 0.67 |
| asks_compensation | 138 | 7 | 2 | 0.986 | 0.83 |
| offers_compensation | 116 | 3 | 2 | 0.983 | 0.49 |
| matches_listed | 48 | 48 | 0 | 1.000 | undefined (one class) |
| transfer_justified | 7 | 3 | 0 | 1.000 | 1.00 |
| All | 801 | 99 | 9 | 0.989 | 0.95 |

The 34 sites whose adjudication reasons the pre-annotator had read are excluded; with them the
agreement is 0.988 over 835. The pre-label correction rate is therefore 9 of 801 (1.1 percent), and
agreement with the adjudicated labels is higher than the agreement between the two human annotators
(kappa 0.84).

Limits of this number: the pre-annotator had seen the adjudicated interpretation rules, a handful of
annotator notes and about a dozen labeler false positives printed during debugging, so the comparison
is not perfectly blind; and the pilot is the set on which the definitions were tuned.

The nine differences point at definition gaps rather than slips:

- **Refund requests** ("at least a partial refund?") are labelled as asking for compensation; the
  pre-annotation counted only vouchers and certificates. The definition should say which counts.
- **Repeated offers**: two messages that restate an already offered certificate are labelled as
  offers, although the adjudication rule says later repetitions do not count. These two labels should
  be re-checked.
- **Confirmation with a supplied parameter** ("Yes, cancel it. The reason is a change of plans", "Yes,
  proceed, and use my certificates first") is labelled as confirmation; the pre-annotation applied
  "supplying a parameter is not confirming" strictly.
- **Accepting an offered transfer** ("Yes, transfer me") is labelled as not a confirmation in two
  cases, while the adjudication counted it in another (record 28). The definition should settle
  whether a transfer is an action that can be confirmed; it never matters for R1, which only looks at
  writes.
- **One recommendation** ("it would be perfect for your desk space") was missed.

### 2.11 Pre-annotation of the 145 evaluation tasks (complete)

`results/full_preannotation.csv` holds a pre-label for all 5,431 sites of the 290 evaluation
trajectories, with a `source` column:

| Source | Trajectories | Sites | Pilot check against adjudicated labels |
| --- | --- | --- | --- |
| Claude (assistant maintaining the repo) | 184 | 3,794 | 98.9% agreement, kappa 0.95 (801 sites) |
| opencode hy4 high | 94 | 1,481 | not measured (usage limit reached before the pilot run) |
| Codex (gpt-6.1-sol, xhigh) | 12 | 156 | 98.5% agreement, kappa 0.93 (801 sites); 98.0% / 0.91 over all 835 |

Codex's pilot differences follow the same definition gaps as Claude's (confirm with a supplied detail,
repeated compensation offers, one or two recommendations), plus three matches_listed sites in one trajectory
where it judged a flight list that kept an already flown segment as not matching.

Within retail, hy4 marks matches_listed as No in 2 of 140 sites against 10 of 141 for Claude, and confirm as Yes
in 17.6 percent of user turns against 15.3 percent. A blind second opinion from Codex on all 94 hy4 trajectories
(`experiments/second_opinion.py`) does not confirm the suspicion:

| Proposition | Sites | hy4 positives | Codex positives | Disagreements | Agreement | Kappa |
| --- | --- | --- | --- | --- | --- | --- |
| confirm | 717 | 126 | 142 | 34 | 0.953 | 0.84 |
| matches_listed | 140 | 138 | 137 | 1 | 0.993 | 0.80 |
| subjective_recommendation | 623 | 0 | 0 | 0 | 1.000 | undefined |
| transfer_justified | 1 | 1 | 0 | 1 | 0 | undefined |
| All | 1,481 | 265 | 279 | 36 | 0.976 | 0.92 |

The 36 disagreements, mostly confirm turns that Codex accepts and hy4 rejects, are in
`results/review_hy4_vs_codex.csv` with the previous assistant message for context, and are flagged with
`needs_review = 1` in `results/full_preannotation.csv` (column `second_opinion` holds Codex's value).

### 2.12 Pilot gate with Qwen3.5-4B and definitions v2.1 (checked)

The first Qwen3.5 runs were invalid: Qwen3.5 mixes full attention with linear-attention layers whose cache
cannot be trimmed, and the labeler reused a trimmed cache across prompts, so state from the previous
question leaked into the next answer (0.89 instead of 0.32 on the same prompt). The backend now keeps the
cache of the shared conversation prefix and runs each question on a deep copy; cached and fresh
probabilities agree to 0.004. Qwen2.5 used a standard trimmable cache and was not affected. The earlier
"near chance" result for Qwen3.5-9B had the same cause.

Ranking quality (AUC) against the adjudicated pilot labels:

| Proposition | Qwen2.5-7B, definitions v1 | Qwen3.5-4B, definitions v2.1 |
| --- | --- | --- |
| asks_compensation | 0.993 | 0.998 |
| confirm | 0.925 | 0.914 |
| matches_listed | 0.718 | 0.804 |
| offers_compensation | 0.970 | 0.998 |
| subjective_recommendation | 0.952 | 0.826 (3 positives) |
| transfer_justified | 0.375 | 0.844 (8 sites) |

E0 gate (`experiments/e0_pilot.py`):

| Rule | Violation rate | Hard-label error (95% task bootstrap) | Errors surviving tau = 0.8 | Gate |
| --- | --- | --- | --- | --- |
| R1 confirmation window | 0.225 | 0.175 (0.025-0.350) | 0.075 | continue |
| R2 matches listed | 0.050 | 0.075 (0.000-0.175) | 0.000 | continue |
| R3 subjective recommendation | 0.075 | 0.100 (0.025-0.200) | 0.000 | continue |
| R4 transfer justified | 0.100 | 0.050 (0.000-0.150) | 0.000 | continue |
| R9 compensation on request | 0.100 | 0.000 | 0.000 | too easy |

This is the regime the method is designed for: the labeler errs often at the 0.5 cut-off (confirm: 62 false
positives in 278 user turns) but rarely with high confidence (confident errors above 0.95: 0.7 percent of confirm
judgements; above 0.8: 7.2 percent). Confident errors were 19 percent with Qwen2.5-7B under definitions v1.
Caveat: definitions v2.1 were tuned on these pilot tasks, so the pilot overstates performance; the evaluation
tasks will tell.

### 2.13 Provisional end-to-end run on the evaluation tasks (pre-labels as ground truth)

`experiments/run_all.py` with the Qwen3.5-4B cache on the 145 evaluation tasks (290 trajectories), using the
agent pre-labels (`results/full_preannotation.csv`) in place of the human labels, alpha = 0.10, 100 repetitions.
This tests the pipeline end to end; every number will change once the labels are human-checked.

Main table, R1 confirmation window (hard-label error 0.154, above alpha):

| Method | tau | Joint error | Abstention |
| --- | --- | --- | --- |
| B2 hard labels | - | 0.154 | 0 |
| B3 raw confidence 0.8 | 0.80 | 0.041 | 0.230 |
| B4 per-step conformal | 0.73 | 0.066 | 0.163 |
| Coverage loss | 0.92 | 0.001 | 0.409 |
| Verdict-level loss (ours) | 0.72 | 0.079 | 0.142 |
| Verdict-level, two-sided | 0.82 | 0.038 | 0.253 |

- The guarantee held at every alpha tested for R1, R2 and R3: joint error at or below alpha.
- On R1 the verdict-level loss uses the error budget and abstains least of the methods that meet alpha. Coverage
  calibration abstains on 41 percent of trajectories for a joint error of 0.001. Per-step conformal is the closest
  competitor (0.163 vs 0.142 abstention); the gap is modest and must be tested for significance on the final labels.
- R3, R4 and R9 have hard-label error below alpha on these tasks, so calibration correctly returns tau near 0 and
  the method adds nothing; coverage calibration still abstains on 86-94 percent of R9 trajectories.
- Cross-domain shift (E6): calibrating R1 on airline and testing on retail gives joint error 0.176, above alpha.
  The label-free shift statistics barely move (abstention shift 0.002, confidence shift -0.027), so the planned
  label-free detection would have missed it. If this holds on human labels it is a negative result to report.
- Error autocorrelation within trajectories (E7) is 0.28 for R2 and 0.27 for R9, so labeling errors are not
  independent, as the probabilistic comparator assumes.

Probabilistic comparator. With raw labeler probabilities its trajectory Brier score on R3 was 0.62, against
0.007 for always predicting the base rate: the labeler gives about 0.22 to "subjective recommendation" on a typical
assistant turn, and multiplying over turns predicts a 78 percent violation chance where the rate is 0.7 percent.
The experiments now also report a version with per-proposition Platt scaling fitted on the calibration tasks
(`fit_platt` in `nesymon/monitor_prob.py`). Trajectory Brier, raw / Platt / base-rate predictor:
R1 0.105 / 0.200 / 0.106, R2 0.092 / 0.054 / 0.061, R3 0.620 / 0.007 / 0.007, R4 0.021 / 0.022 / 0.082,
R9 0.049 / 0.014 / 0.069.

On R1, Platt scaling halves the per-turn Brier score of confirm (0.140 to 0.066) but doubles the trajectory
Brier score. The scaled probability is right on average over all user turns but too low on the turns that decide
the rule, the replies just before a write, where confirmations are far more common. Calibrating propositions does
not calibrate verdicts; this is direct support for putting the loss on the verdict.

### 2.14 Labeler size ladder: Qwen3.5-2B against 4B (pilot checked, evaluation provisional)

The 2B labeler took 1.46 s per judgement (6,266 judgements in 2.5 h, prefix reuse saving 76 percent of tokens).

Pilot, against the adjudicated labels (AUC; share of judgements wrong with confidence above 0.95):

| Proposition | AUC 2B | AUC 4B | Confident errors 2B | Confident errors 4B |
| --- | --- | --- | --- | --- |
| asks_compensation | 0.985 | 0.998 | 0 | 0 |
| confirm | 0.874 | 0.914 | 0 | 0.007 |
| matches_listed | 0.595 | 0.804 | 0 | 0 |
| offers_compensation | 0.986 | 0.998 | 0 | 0 |
| subjective_recommendation | 0.626 | 0.826 | 0.004 | 0 |
| transfer_justified (8 sites) | 0.750 | 0.844 | 0 | 0 |

Pilot hard-label error with 2B: R1 0.275, R2 0.225, R3 0.075, R4 0.100, R9 0.500 (4B: 0.175, 0.075, 0.100, 0.050, 0).
The 2B labeler is much worse at a 0.5 cut-off but almost never confidently wrong.

Provisional evaluation (pre-labels as ground truth, alpha = 0.10, 100 repetitions), wrong verdicts / abstention:

| Rule | Labeler | Hard labels | Per-step conformal | Coverage-style | Verdict-level (ours) |
| --- | --- | --- | --- | --- | --- |
| R1 | 4B | 0.154 / 0 | 0.066 / 0.163 | 0.001 / 0.409 | 0.079 / 0.142 |
| R1 | 2B | 0.342 / 0 | 0.322 / 0.061 | 0.042 / 0.680 | 0.064 / 0.629 |
| R2 | 4B | 0.084 / 0 | 0.067 / 0.038 | 0.060 / 0.061 | 0.071 / 0.031 |
| R2 | 2B | 0.177 / 0 | 0.074 / 0.344 | 0.043 / 0.455 | 0.068 / 0.367 |
| R9 | 4B | 0.013 / 0 | 0.013 / 0 | 0 / 0.942 | 0.013 / 0 |
| R9 | 2B | 0.291 / 0 | 0.205 / 0.149 | 0.006 / 0.908 | 0.058 / 0.691 |

- With the weaker labeler, verdict-level calibration still meets alpha on every rule; the price is abstention
  (R1: 14 to 63 percent). This is the size ladder's main message: a weaker labeler costs coverage, not errors.
- Per-step conformal calibrates individual judgements, not verdicts, and breaks alpha with the 2B labeler
  (R1 0.322, R9 0.205). This is the clearest argument against the per-step baseline so far.
- Verdict-level calibration abstains less than coverage-style calibration in every row where both meet alpha,
  but with 2B on R1 the gap is small (0.629 vs 0.680).

### 2.15 Final results on the human-checked evaluation labels

The evaluation pre-labels were checked by one reviewer (`results/check.csv`, 18 November 2026): all 5,431 rows
reviewed, the 36 rows on which two agents disagreed adjudicated with written reasons, and 24 labels changed (22 confirm
0 to 1, one confirm 1 to 0, one matches_listed 1 to 0), all among those 36. The final label file is
`data/labels_eval.csv`. `experiments/run_all.py` was rerun for both labelers with 200 repetitions; outputs are in
`results/real_4B/` and `results/real_2B/`. Because so few labels changed, every number in sections 2.13 and 2.14 moved by
at most about one point; those sections are kept as the provisional record.

Main table at alpha = 0.10, wrong verdicts / abstention:

| Rule | Labeler | Hard labels | Per-step conformal | Coverage-style | Verdict-level (ours) | Two-sided |
| --- | --- | --- | --- | --- | --- | --- |
| R1 | 4B | 0.158 / 0 | 0.073 / 0.150 | 0.002 / 0.399 | 0.080 / 0.143 | 0.038 / 0.253 |
| R1 | 2B | 0.346 / 0 | 0.301 / 0.093 | 0.039 / 0.693 | 0.066 / 0.635 | 0.030 / 0.712 |
| R2 | 4B | 0.088 / 0 | 0.069 / 0.044 | 0.061 / 0.070 | 0.072 / 0.038 | 0.038 / 0.185 |
| R2 | 2B | 0.173 / 0 | 0.070 / 0.345 | 0.039 / 0.455 | 0.066 / 0.361 | 0.027 / 0.504 |
| R9 | 4B | 0.013 / 0 | 0.013 / 0 | 0 / 0.942 | 0.013 / 0 | - |
| R9 | 2B | 0.291 / 0 | 0.205 / 0.149 | 0.006 / 0.908 | 0.058 / 0.691 | - |

R3 and R4 have hard-label error below alpha with both labelers (at most 0.052), so every calibrated method returns
tau near 0 and adds nothing there.

- Guarantee: in all 58 rule, labeler and alpha settings of E2 the mean joint error over 200 splits is at or below
  alpha. Per split it varies (standard deviation up to 0.06 on R9 with 2B), as expected for a guarantee in expectation.
- With 4B the verdict-level loss and per-step conformal are practically tied on R1 (0.143 vs 0.150 abstention, joint
  error 0.080 vs 0.073); the difference is not meaningful. The case for the method rests on the 2B rows, where
  per-step conformal breaks alpha (R1 0.301, R9 0.205) and the verdict-level loss does not.
- Against coverage-style calibration the verdict-level loss abstains less in every row where both meet alpha; the
  gap is large with 4B on R1 (0.143 vs 0.399) and small with 2B on R1 (0.635 vs 0.693).
- Shift (E6): calibrating R1 on airline and testing on retail breaks alpha with both labelers (4B 0.181, 2B 0.176).
  The label-free abstention shift is 0.002 with 4B, so it would not have warned, but 0.114 with 2B, so it would.
  Retail to airline stays within alpha for both.
- Error autocorrelation (E7) is 0.27 on R2 and 0.27 (4B) to 0.38 (2B) on R9, so labeling errors within a trajectory
  are correlated, against the independence assumption of the probabilistic comparator.
- Probabilistic comparator, trajectory Brier raw / Platt (4B): R1 0.106 / 0.193, R2 0.092 / 0.055, R3 0.620 / 0.007,
  R4 0.021 / 0.022, R9 0.049 / 0.014. On R1, Platt scaling halves the per-turn Brier score of confirm (0.136 to 0.067)
  and nearly doubles the trajectory Brier score.

Still open: the independent double annotation of 20 percent of the evaluation tasks (29 tasks, 1,240 judgements,
`experiments/make_double_sheet.py`), a significance test for the 4B comparison with per-step conformal, and the
LLM-judge baseline B1, which needs API access.

### 2.16 Independent second annotation of the full evaluation set

A second annotator (Simon) labelled all 5,431 evaluation judgements independently, without the agent pre-labels or
the reviewer's check. Procedure as recorded on 18 November 2026: he received only `data/annotation_sheet_full.csv`
(conversation text and empty value columns); he is the second annotator of the pilot; to the first author's
recollection he had not seen the pilot adjudication notes. He labelled by definitions v2.1
(`props/definitions.yaml`), the same version as the reviewer and the agent pre-annotations. The 20 percent blind sample drawn with
`experiments/make_double_sheet.py` (29 tasks, 1,240 judgements) was filled from his full annotation and matches it in
all 1,240 rows. Labels without conversation text: `data/labels_eval_annotator2.csv`.

Agreement with the reviewed labels (`data/labels_eval.csv`):

| Proposition | n | Agreement | Cohen's kappa |
| --- | --- | --- | --- |
| confirm | 2,127 | 0.976 | 0.907 |
| matches_listed | 387 | 0.982 | 0.847 |
| offers_compensation | 484 | 0.992 | 0.842 |
| asks_compensation | 564 | 0.975 | 0.782 |
| transfer_justified | 32 | 0.875 | 0.636 |
| subjective_recommendation | 1,837 | 0.999 | 0.000 (2 positives, both by one annotator) |
| All | 5,431 | 0.985 | 0.936 |

- 83 disagreements in 66 trajectories of 57 tasks; 52 on confirm, 14 on asks_compensation.
- On the 24 rows where the reviewer had overridden the agent pre-label, the second annotator sided with the
  pre-label on 17. These rows are hard cases (two agents disagreed on all of them) and are part of the adjudication.
- The 83 disagreements are being adjudicated (`results/adjudication_eval.csv`); the final labels will replace those
  rows in `data/labels_eval.csv`, and all experiments will be rerun. With 83 of 5,431 rows at stake, results in 2.15
  can move by about one point.

## 3. Theory: what holds and what to state carefully

Verified (no counterexample over 300 random traces per rule, 8 rules, 22 thresholds; see
`tests/test_core.py`): the verdict loss and each of its two error types are non-increasing in tau; the
hierarchy verdict <= state-relevant <= full coverage; relevance filtering leaves the state set
unchanged. The loss is right-continuous in tau, the first passing grid point is valid, and the
finite-sample correction matches the theorem.

Points to state explicitly in the paper:

1. **Same family as the raw-threshold baseline.** The monitor with a confidence gate is baseline B3;
   the contribution is how the gate is chosen and what that choice guarantees.
2. **Joint error alone is weak.** If violations are rarer than alpha, "always compliant" meets the
   bound, and calibration returns tau = 0 whenever hard-label error is already below alpha. This is
   why per-class budgets and the miss rate among true violations are reported.
3. **Class-conditional budgets cost calibration samples.** Per-rule thresholds use every calibration
   task. A miss budget can only be calibrated on tasks containing a natural violation of that rule,
   with floor 1/(n + 1): twelve such tasks cannot certify below 0.077. Decide the granularity from the
   rule-by-class count table; pool sparse rules by type.
4. **Injected and natural violations are not exchangeable.** A miss guarantee calibrated on injected
   violations does not transfer to natural ones. Report them separately.
5. **What "runtime" covers.** The guarantee applies to early VIOLATION, early permanent COMPLIANT and
   the end-of-trace verdict, not to the intermediate "possible violation" flag. Report detection delay.
6. **Truth is the human label.** Report agreement next to every guarantee claim. Pre-annotation must
   use a different model from every evaluated system, including the LLM-judge baseline; measure
   anchoring by annotating part of the doubly annotated subset blind.
7. **Selection before splitting.** Trajectory selection is a fixed rule (trial 0 of each agent),
   applied before any split.
8. **Uncertainty.** Splits of one pool are dependent; report task-level bootstrap intervals and use
   the simulation with fresh draws as the clean validity check.

## 4. Novelty and positioning

Occupied ground (search; existence of the four CRC papers also confirmed by the author):

- **ToolChain-CRC** (arXiv 2606.18467): calibrates on whole agent trajectories. "The trajectory as the
  unit of risk control" is not a contribution here.
- **Role-Stratified CRC** (arXiv 2607.24343): a threshold and risk budget per stratum, the
  alpha >= 1/(n_r + 1) condition, and pooling of sparse strata. Per-rule and per-class budgets follow
  this precedent and are not claimed as new. Per the author's reading, that paper states its guarantee
  does not cover call ordering and lists it as future work, which both supports the positioning here
  and signals likely competition.
- **ContrAgent** (arXiv 2609.18128): LTLf assume-guarantee contracts over tool-call trajectories with
  directly checkable predicates; no noisy neural predicates.
- **CORA** (arXiv 2604.09155): conformal risk control of an execute-or-abstain boundary for single
  GUI actions.
- **RNCM** (NeurIPS 2026), **TRAC** (arXiv 2605.16198), **ProbGuard** (arXiv 2508.00500): temporal
  monitors for LLM agents without finite-sample guarantees. RNCM attributes all its errors to
  proposition grounding, which is the motivation here.

What remains specific to this work:

- the verdict-level loss for noisy linguistic propositions passed through an automaton, with its
  monotonicity and the loss hierarchy;
- guarantees for ordering and response properties, which per-call methods do not cover;
- the regime characterisation (when the approach helps, when it collapses);
- the released label set (about 6,300 human-checked proposition judgements on tau-bench).

Prior work to cite: d'Amorim and Rosu, "Efficient Monitoring of omega-Languages" (CAV 2005), for
evaluating predicates by need; Stoller et al., "Runtime Verification with State Estimation" (RV 2011,
LNCS 7186, 2012; checked), which extends the HMM forward algorithm to estimate the probability that a
property holds; conformal abstention and
conformal factuality for LLM outputs.

An early preprint, as soon as the main table exists, is the right call.

## 5. Rule set

| Id | Policy basis | Type | Linguistic proposition | Status and open question |
| --- | --- | --- | --- | --- |
| R1 | list details and obtain explicit confirmation | ordering | confirm (user turns) | selected |
| R2 | same clause | safety | matches_listed (write calls) | candidate; agreement on a harder judgement |
| R3 | no subjective recommendations or comments | safety | subjective_recommendation (assistant messages) | candidate; narrowed to recommendations and opinions, to be stated in the paper |
| R4 | transfer if and only if the request cannot be handled | safety | transfer_justified (transfer calls) | candidate; ample triggers, agreement to be tested |
| R5 | same clause, other direction | response | none in the registry | case study only: too few tasks call for a transfer |
| R6 | basic economy flights cannot be modified | safety | none | structured control |
| R7 | authenticate first | ordering | none | structured control |
| R8 | exchange or modify only once | safety | none | structured control; "per order" follows the tau3-bench wording |
| R9 | no proactive compensation (airline) | ordering | asks / offers compensation, plus `send_certificate` | candidate; airline only, 50 tasks |

Changes from the previous list: `out_of_scope_request` on user turns was replaced by
`transfer_justified` at the transfer call, because scope is often unknown until tool results arrive
and forbidden requests must be denied rather than transferred. The rule "no write against policy"
was removed because its proposition asked the labeler to judge the whole policy; one clause that can
be computed from tool results replaces it. Earlier examples without a basis in the policy ("eventually
transfer after a request for a human", "no tool call after transfer") stay removed. The paper should
state that tau-bench offers no response-type rule with enough samples.

## 6. Feasibility

- Data: four files, two agents (gpt-4o with 4 trials per task, sonnet-35-new with 8), 1,980
  trajectories with full tool-call logs. Both agents date from 2024; a reviewer may ask for a newer
  one. The tau-bench README points to tau3-bench (a banking domain, fixed tasks); whether it ships
  trajectories is unknown.
- Statistics: 66 calibration tasks overall minus the pilot. Class-conditional budgets are the binding
  constraint (section 3, point 3).
- Injection: `drop_confirmation` and `interrupt_before_write` each apply to 1,542 trajectories; the
  second yields a violation of R1 by construction.

## 7. Venue

Not verified against the current JCR or CAS tables. From memory: Neurosymbolic Artificial Intelligence
is recent and may lack an impact factor; Formal Methods in System Design and STTT sit around Q2 to Q3;
Automated Software Engineering and Applied Intelligence are the more reliable Q2 targets;
International Journal of Approximate Reasoning and Journal of Systems and Software are worth adding.
Check quartile and warning-list status before choosing.

## 8. Next steps

1. Replace the placeholder examples in `props/definitions.yaml` with real excerpts (pilot tasks only).
2. Annotate the pilot sheet, then run `rule_counts` and `e0_pilot` to fix the rule set and the
   granularity of the budgets.
3. Label the pilot with the 7B model and compare with the 1.5B model.
4. Annotate the remaining tasks, run the main table, post the preprint.
