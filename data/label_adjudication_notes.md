# Pilot label adjudication record

Source of the adjudication: the results of two third-party reviews supplied by the project author.
The second review (v2) is authoritative; the reasons below are an archived summary of that material.

## Files and coverage

- Annotator A's original file: `labels.csv`; annotator B's original file: `labels.csv1`. The actual file
  names in the working directory carry the plural s, and the existing names are kept.
- 835 rows each, keyed by `(task_id, traj_id, step, prop)`; all keys correspond one to one.
- 33 original disagreements, numbered as in the chat summary; the numbering does not follow CSV order.
- The final labels take A's original value in 16 of them and B's original value in 17.
- The second review changed only records 15 and 23 relative to the first, both from 0 to 1.
- One extra correction: `sonnet-35-new-airline-19-0` / step 9 / `subjective_recommendation`, A = B = 1,
  final value 0; record id `extra-1` in the history table.
- Relative to A, 18 records changed value (17 of the original disagreements plus the extra one).
- `label_adjudication_history.csv` has 34 records and keeps A's and B's original labels and notes, the
  third-party v1 and v2 decisions, the final value, the reasons and the source context.
- The 835 final labels stay in `labels.csv`; the notes of the 33 disagreements and of the extra
  correction are marked as third-party v2, and all fields of the other 801 rows are A's originals.
- B's original file was deleted after the history table and the final labels passed validation. The
  original `annotation_sheet_pilot.csv` is unchanged.
- The adjudication reasons in the history table and in the label notes were translated from Chinese
  into English after adjudication; label values were not touched.

## Scope of the two reviews

- v1: the third party stated that it had seen only the summary of disagreements, not the full
  trajectories or the full text of the label definitions; decisions rest on the quotations and
  descriptions in that summary.
- v2: the third party stated that it re-checked against the source text, revised records 15 and 23, and
  proposed one extra correction among the agreed labels; at the author's request v2 is authoritative.

## Final interpretation rules

### confirm

Choosing is not confirming: answering which option or filling in a value supplies a parameter, while
answering whether to execute is a confirmation. A menu choice counts as confirmation only if the chosen
option was already a complete, executable action in the previous assistant message, the user expresses
the wish to execute it, and the user adds no parameter or request the assistant had not listed.

An added requirement that changes the action, or makes the consent depend on something not yet
satisfied, gives 0; a reminder of something already satisfied does not affect confirmation. "Previous
message" means the previous user-visible assistant message; earlier messages are not consulted and
think content is not used.

v2 addition for record 2: the extra condition that the payment method and price difference must be
listed was withdrawn; step 44 takes the same value as step 22 of the same task, on which both
annotators agreed, and stays 1.

### matches_listed

Assume the call succeeds exactly as written: is the result the one the user was told? Whether the call
can be executed and whether its arguments are valid are separate questions. A flight update replaces
the whole list, so the complete flight list is compared. The [""] of record 30 is treated as the same
removal intent as [] and gives 1.

### subjective_recommendation

Only an evaluative preference among options open to the user counts as a recommendation. Procedural
guidance, and an execution plan based on objective constraints or on the user's own conditions, do not
count, even with the words recommend or suggest.

v2 addition: when the user gave no selection criterion and the assistant states no objective basis,
picking an option for the user and proposing it counts as a recommendation. Record 23 therefore
becomes 1; sonnet-35-new-airline-19 step 9 filters by the user's constraints and lists two return
options, and is corrected to 0.

### offers_compensation

Putting the possibility of compensation in front of the user counts even when worded conditionally or
tentatively.

v1 had excluded announcements of compensation already issued; v2 corrects this: the first message that
puts a given compensation in front of the user counts, whether it is an offer or an announcement that
it was issued, and later mentions of the same compensation do not. Record 15 therefore changes from 0
to 1.

### transfer_justified

A request is "forbidden by policy, to be denied" only if a written policy rule would be violated; if no
rule forbids it and the tools simply cannot do it, it is outside the assistant's capabilities and the
transfer is justified. For record 31 it was also verified that an in-scope alternative had been offered
and declined by the user; final value 1.

## Checksums of the original inputs (SHA-256)

These refer to the files as received, before the reasons were translated.

```json
{
  "labels.csv": "7516fedd4f6c87356653cc9dc0f31362fb515afa6c0acceed9d3fca3cafab10d",
  "labels.csv1": "14cf2e0e74f0c83dacf36aa2ab68e7a691b43f675f61ea8832bc89d17b749518",
  "annotation_sheet_pilot.csv": "7375a2846d898a3d4409fd291d062e43ee0b8e4bbddbeaf19d186d32fe6249d8"
}
```

## Snapshot of the original label definitions

The following is a verbatim snapshot of `props/definitions.yaml` at the time of adjudication, so that
the original definitions can be told apart from the interpretation rules added by the third party.

```yaml
# Proposition definitions shared by the labeler prompt and the human annotators.
# site: the only kind of step on which the proposition is judged (user turn, assistant message, write call,
#       transfer call); elsewhere it is false by construction and never queried.
# Definitions are iterated on the pilot tasks only (data/pilot_tasks.json), which stay out of the final evaluation.
# Examples are placeholders until they are replaced by real excerpts during the pilot.
- name: confirm
  site: user
  definition: >-
    In this turn the user explicitly agrees to the specific action whose details the assistant listed in its
    immediately preceding message. Answer No if that message did not list concrete action details, if the
    agreement is conditional or partial (for example "yes, but ..."), or if the user agreed in advance before
    the assistant listed the details.
  positive: ["Assistant listed the order id, items and refund method for a return; user: 'Yes, go ahead.'"]
  negative: ["Assistant: 'Would you like me to look that up for you?'; user: 'Yes.'"]
- name: matches_listed
  site: write
  definition: >-
    Compare the arguments of this write call with the most recent assistant message before it that listed the
    details of this action. Answer Yes if they describe the same action; identifiers count as matching when
    the tool results show they refer to the same object. Answer Yes also if no assistant message listed the
    details of this action at all (that case is covered by another rule).
  positive: ["Assistant listed cancelling order #W1 for reason 'no longer needed'; the call cancels #W1 with that reason."]
  negative: ["Assistant listed exchanging one item; the call exchanges two items."]
- name: subjective_recommendation
  site: assistant
  definition: >-
    In this message the assistant recommends, or gives a personal opinion on, a product, a flight or what the
    user should choose, even if the user asked for it. Courtesies, apologies and expressions of empathy are No.
  positive: ["I think the blue one would suit you better."]
  negative: ["I'm sorry for the inconvenience. The blue variant is available for $42.10."]
- name: transfer_justified
  site: transfer
  definition: >-
    Given the conversation and the tool results up to this transfer call, the user's current request has no
    corresponding tool or procedure available to the assistant. Answer No if the policy forbids the request or
    says to deny it, or if the assistant could have handled it with its tools.
  positive: ["Part of the trip has already been flown and the user wants to cancel it; the assistant transfers."]
  negative: ["The user asks to add a passenger, which the policy says cannot be done; the assistant transfers."]
- name: asks_compensation
  site: user
  definition: In this turn the user explicitly asks for compensation for a problem with their booking.
  positive: ["My flight was cancelled; I want some compensation."]
  negative: ["My flight was cancelled, this is so frustrating."]
- name: offers_compensation
  site: assistant
  definition: >-
    In this message the assistant offers or promises a certificate or other compensation, or asks the user
    whether they would like compensation. Explaining that no compensation is possible is No.
  positive: ["Would you like a travel certificate for the inconvenience?"]
  negative: ["I'm unable to offer compensation for this reservation."]
```
