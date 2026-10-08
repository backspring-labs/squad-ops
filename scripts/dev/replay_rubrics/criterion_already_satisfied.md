# Rubric `lesson.criterion_already_satisfied@1`

The one fixed rubric for SIP-0110 Phase 1's proposal target (§0.4, §0.10, §0.12): *a proposed new
acceptance criterion is already satisfied by the accepted application.* Every output is read by it:
every arm of every replay, and every live proposal of the window, approvals and returns alike. It is
named by this id in each experiment manifest (`run_authoring_replay.py --rubric`). A change to it is
a new version and a new manifest.

## What is read

One authored proposal (`change_request.yaml`) at the proposal-writing seam, against the accepted
application it was proposed for, as the proposer's own prompt shows it:
- the interface manifest, verbatim in the envelope;
- the criteria earlier increments froze;
- what the application's frozen code already decides (the stack's frozen conventions).

Only new criteria (`criteria:`) are read. `must_not_break` entries and retirements are not new
criteria.

## For each new criterion

1. State its request: its surface and the input its observable describes.
2. Read what the accepted application answers to that request today, from the three sources above.
   Cite the element that settles it: a manifest line (an entity field, request shape, endpoint,
   error code or client route), a frozen criterion's id, or a frozen convention.
3. The criterion is **already satisfied** when that answer meets its observable, so a test of it
   would pass on the accepted application before the change.

## The verdict, per proposal

| verdict | when |
|---|---|
| **present** | at least one new criterion is already satisfied |
| **absent after assessment** | no new criterion is already satisfied |
| **not applicable** | the proposal adds no new criterion (a `refactor`, or an empty `criteria:`) |
| **unassessed** | no `change_request.yaml` parses from the output, or a criterion cannot be settled from the three sources. The reason is recorded and the evaluator does not guess |

The record keeps, per proposal: the number of new criteria, the ids already satisfied, and for each
criterion the element that settled it.

## Guardrails, read with every verdict (§0.12)

- **The objective:** the proposal's change moves toward the campaign's objective (yes, no, unclear).
- **Scope and meaningful criteria:** at least one new criterion that is not already satisfied, and a
  footprint inside the allowed scope.
- **Other serious defects:** any other return class the proposal would draw (SIP-0109 §9.4),
  named. One that grows under the lesson is a harm signal, whatever this target does.
- **Context cost:** the lesson's injected tokens, as the replay record measures them.
- **No empty win:** the output parses and proposes a change. A `not applicable` or `unassessed`
  output is never counted as an absence.

## How it is applied

- **Blind to the arm:** the evaluator reads each case's outputs with the arm labels removed, in a
  seeded shuffle the record keeps. The key is joined only after every verdict is written.
- **Adjudication:** where a live proposal also has the supervisor's ruling, the ruling is recorded
  beside the verdict. A disagreement is recorded as one, never resolved by preference.
- **The evaluator** is the supervisor, which also drafted the lesson. That is disclosed in every
  readout. Blinding is the control, and the owner may assign another evaluator.
