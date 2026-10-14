# Rubric `lesson.criterion_already_satisfied@3`

**Version 3 (2026-10-13), from the 2.2 window's independent adjudication (#2208; PR #2207).** It states which reading
decides when the prompt's sources are silent or contradict the delivered code, and how the meaningful-criteria guardrail
reads then (§ "When the sources are silent, or the code contradicts them"). The window scored by that reading already,
so @3 writes down the rule @2 left unstated. Like every version, it is used only by an experiment whose manifest names
it, never retroactively.

**Version 2 (2026-10-09), from the owner's review.** It adds the case-level objective check, the completeness rule
and the rubric's calibration, and it separates the evaluator from the lesson's drafter. Version 1 scored the lesson's
first development check (`var/replays/lesson-check-criterion-already-satisfied-r1`).

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

## Before any output: the case's objective

For each case, before its arms generate, read its accepted application (the three sources above) against the
campaign's objective. Record, citing the elements that settle it, whether the objective still holds legitimate
authorized work. The record is made blind to every output. A case whose objective is already wholly satisfied is
`objective already satisfied`: it leaves the primary comparison, and it is never scored as a mistake or a win, because
a proposal cannot say an objective is met (the rails refuse `nothing_to_build`).

## For each new criterion

1. State its request: its surface and the input its observable describes.
2. Read what the accepted application answers to that request today, from the three sources above.
   Cite the element that settles it: a manifest line (an entity field, request shape, endpoint,
   error code or client route), a frozen criterion's id, or a frozen convention.
3. The criterion is **already satisfied** when that answer meets its observable, so a test of it
   would pass on the accepted application before the change.

## When the sources are silent, or the code contradicts them (@3)

**The delivered application decides.** The verdict is about the accepted application, and the application is the
code it was accepted with (its stored tree), so where the three sources above don't settle a request, the code does.
- **Silent sources.** When the manifest, the frozen criteria and the frozen conventions say nothing about the
  request, read the delivered code and cite the file and line that answers it. Cases from the 2.2 window:
  - whether leaving a run matches a name by case, where the uniqueness decision names only duplicate joins;
  - whether a view shows the server's error message text;
  - how internal whitespace in a name is handled.

  Each is settled by the code (`present` or `absent after assessment`). It is `unassessed` only when the code doesn't
  settle it either, for example when the behaviour depends on input the stored tree cannot show.
- **A contradiction.** When a source declares a behaviour the code does not implement, the code decides, and the
  contradiction is recorded beside the verdict as a manifest defect. The case from the window: a manifest declaring
  lexical datetime sorting for the runs list whose `GET /runs` returned insertion order (#2202). A new sort criterion
  there is **not** already satisfied: a test of it fails on the accepted application.
- **The record** names, per criterion, which settled it: a source or the code. A reader can then recompute the case by
  the sources alone (the window's "reading B"). That reading is reported beside the verdict, never in its place.

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
  footprint inside the allowed scope. "Already satisfied" is read as the verdict reads it (@3): by the delivered
  code where the sources are silent or contradict it. So a criterion a manifest declares but the code does not
  implement is meaningful work, and the manifest defect is recorded.
- **Other serious defects:** any other return class the proposal would draw (SIP-0109 §9.4),
  named. One that grows under the lesson is a harm signal, whatever this target does.
- **Context cost:** the lesson's injected tokens, as the replay record measures them.
- **No empty win:** the output parses and proposes a change. A `not applicable` or `unassessed`
  output is never counted as an absence.

## Completeness

- A case is **complete** when every planned output in both arms parses and has a verdict (`present`, `absent after
  assessment` or `not applicable`). One `unassessed` output makes the case **partly assessed**: it is reported by arm
  and reason, and leaves the paired comparison.
- A case's **complete removal** of the target needs every memory-arm output valid, applicable, `absent after
  assessment`, and within the guardrails. No output marked `present` is not enough.

## How it is applied

- **Blind to the arm:** the evaluator reads each case's outputs with the arm labels removed, in a
  seeded shuffle the record keeps. The key is joined only after every verdict is written.
- **Adjudication:** where a live proposal also has the supervisor's ruling, the ruling is recorded
  beside the verdict. A disagreement is recorded as one, never resolved by preference.
- **The evaluator** is named in the experiment manifest. **Preferred: a separate blinded evaluator** that did not draft
  the lesson. If the supervisor evaluates, it drafted the lesson, which every readout discloses, and **every apparent
  win, every worsening and every ambiguous verdict is adjudicated independently** by an evaluator that did not draft
  it.
- **Calibration, before the window's scoring:** the evaluator scores known examples first: the clean historical case's
  returned criteria as `present`, and accepted criteria that the accepted application did not already satisfy as
  `absent after assessment`. Their verdicts are recorded. They are never counted as held-out evidence.
