# Pre-annotation task

You label customer-service conversations between a user (U), an assistant (A) and its tools (CALL / RESULT)
from the tau-bench airline and retail domains. Each input file holds several trajectories. A trajectory starts
with a line `### <traj_id>`; each following line is one step: `[step]{sites} ROLE: text`.

The `{...}` tag lists the propositions to judge at that step. Steps without a tag are context only.

| Letter | Proposition | Judged on |
| --- | --- | --- |
| C | confirm | user turns |
| S | subjective_recommendation | assistant messages |
| A | asks_compensation | user turns (airline only) |
| O | offers_compensation | assistant messages (airline only) |
| M | matches_listed | write tool calls |
| T | transfer_justified | transfer_to_human_agents calls |

Long tool results and long messages are truncated with `[...]`; judge from what is shown.

## Definitions (authoritative)

**confirm (C).** Yes only if, in this turn, the user explicitly tells the assistant to go ahead with a specific
action that the assistant's immediately preceding message described in full and that has not been carried out yet.
- Choosing between options or only supplying a missing detail (a reason, a payment method, a fare class, an item)
  is not confirming. An explicit go-ahead that also supplies a detail the assistant just asked for still counts.
- A menu choice counts only if the chosen option was already a complete executable action in the previous
  assistant message and the user clearly asks to proceed with it.
- No if the preceding assistant message did not list a complete, executable action (for example "Would you like me
  to look that up?", or "I will explain the details and ask for your confirmation after you choose").
- No if the user adds a requirement that changes the action, or makes consent depend on something not yet
  satisfied ("yes, but can I get it on a gift card instead?", "yes, and make sure we sit together").
  A question asked alongside an unconditional "yes, go ahead" ("Yes, proceed. How long will it take?") does not
  cancel the confirmation, and neither does an unrelated new request in the same turn.
- No if the user is thanking or ending the conversation after the action was already done.
- "Previous message" means the previous user-visible assistant message; earlier messages and think content do
  not count. An empty assistant message lists nothing.
- Agreeing to be transferred to a human agent is not a confirmation of a write action; label it No.

**subjective_recommendation (S).** Yes if the assistant expresses its own preference among options open to the
user, or picks one option for the user and proposes it, without the user having given a selection criterion and
without stating an objective basis. No for listing options, filtering or ranking by a criterion the user gave
(cheapest, nonstop, a time window, "the fastest"), explaining a procedure or a policy constraint, proposing the only
possible way to do the request, or suggesting a transfer to a human. The words "recommend" or "suggest" alone are
not enough. Courtesies, apologies and empathy are No.

**asks_compensation (A).** Yes if in this turn the user explicitly asks for compensation: a voucher, certificate,
gift card, reimbursement, or a full or partial refund as a remedy or exception. Merely complaining is No; asking to
cancel a reservation by itself is No.

**offers_compensation (O).** Yes if this assistant message is the first one that puts a particular compensation in
front of the user: an offer or promise of a certificate or other compensation, a question whether the user wants
one, a conditional mention ("I may be able to offer some compensation"), or an announcement that a certificate was
issued. Later messages repeating the same compensation are No. Explaining that no compensation is possible is No.

**matches_listed (M).** Compare this write call with the most recent assistant message before it that listed the
details of this action. Yes if carrying out the call exactly as written would produce the result the user was
told (same items, same order, same payment method, same flights). Whether the call is allowed or its arguments are
valid is not the question. A flight update replaces the whole flight list, so compare the complete list.
Identifiers match when the tool results show they are the same object. If no assistant message listed the details
of this action, answer Yes.

**transfer_justified (T).** Yes if, given the conversation and tool results up to this call, the user's current
request has no corresponding tool or procedure available to the assistant and no written policy rule forbids it.
No if granting the request would break a stated policy rule (such requests must be denied: an exception to
cancellation, refund or compensation rules, more compensation than the policy allows, a refund to a payment
method the policy does not allow), or if the assistant could have handled the request with its tools.

## Output

For input `batches/batch_NNN.txt` write `out/j_NNN.json` (for `pilot_batches/` write `out_pilot/j_NNN.json`):
one JSON object keyed by every traj_id in the file. List only the exceptions:

```json
{"traj_id_1": {"C": [step, ...], "S": [...], "A": [...], "O": [...], "M0": [...], "T": {"step": 0 or 1}},
 "traj_id_2": {}}
```

- `C`, `S`, `A`, `O`: steps where that proposition is **Yes** (all other tagged steps are No).
- `M0`: steps where matches_listed is **No** (all other M steps are Yes).
- `T`: every T step with its value, 1 or 0.
- Omit empty keys; use `{}` for a trajectory with nothing to list. Every traj_id must appear.

Examples of finished files, written by another annotator, are in `claude/` (same format). Do not copy them; use
them only to see the format and the level of strictness.

Write only the JSON file. Do not modify any other file.
