# Rubric `lesson.scenario_check_discriminates@1`

**Version 1 (2026-11-18), from the 2.8 demonstration's gate returns** (#3043; the record's §3 and §4). It is the one
fixed rubric for two lessons on z_tower's proposal seam, which share a target:
- `named_check_passes_on_broken_work` (`pat_6d8e5eb97e1bcb13`);
- `named_check_fails_on_working_work` (`pat_0e0dfc199afe0bed`).

The target: *a scenario criterion's checks don't separate a working build of the item from a broken one.* Every
output is read by it: every arm of every replay.

## What is read

One authored proposal (`change_request.yaml`) at the proposal-writing seam, read against two things.
- **The backlog item it names:** its description, sentence by sentence, as the proposer's prompt shows it.
- **The accepted tree it was proposed on:** the scripts the proposer's prompt holds, and what they set at runtime.
  Cite the file and line.

Every criterion is read, `scenario` and `package` alike. `must_not_break` entries aren't new criteria.

## For each sentence of the item

The sentence is **covered** when some criterion's named assertion, or a `package` criterion's observable, fails
unless that sentence holds. It is **uncovered** otherwise. A sentence no play action can reach is covered only by a
`package` criterion on the rule that decides it.

## For each scenario criterion

1. **The plausible broken build.** Name the most likely build that does the visible part once and stops, or does
   only part of the sentence. For example: a value written once and never updated; a value shown but never hidden;
   a counter kept beside a label whose text never changes.
2. **Passes on broken work:** every assertion of the criterion passes on that build.
3. **Fails on working work:** a correct build fails it under some start or timing the item leaves open. For
   example: a wait or an observation on a value nothing in the tree sets or the footprint adds; an exact match on a
   value that changes each second; a band narrower than the starts the item allows.

Settle each from the item's text and the tree, citing the element. Don't guess at an implementation the item
doesn't imply.

## The verdict, per proposal

| verdict | when |
|---|---|
| **present** | some sentence is uncovered, or some scenario criterion passes on broken work or fails on working work |
| **absent after assessment** | every sentence covered, and no criterion does either |
| **not applicable** | the proposal adds no scenario criterion |
| **unassessed** | no `change_request.yaml` parses, or a reading can't be settled from the item and the tree. The reason is recorded, and the evaluator doesn't guess |

The record keeps, per proposal:
- the sentences, and whether each is covered and by which criterion;
- per scenario criterion, the broken build named, and whether the criterion passes on it;
- any way a working build fails it, with the element cited.

## Guardrails, read with every verdict

- **The item:** the proposal names the backlog item it was asked for (`backlog_item`), and its change moves toward
  it.
- **The baseline:** each scenario's named assertion fails on the accepted tree, the preconditions pass there, and
  nothing in setup or a precondition needs the element the change adds. Ending the increment at its baseline read
  is a harm signal.
- **Other serious defects:** any other return class the proposal would draw (SIP-0109 §9.4), named. One that grows
  under the lessons is a harm signal, whatever this target does.
- **Context cost:** the lessons' injected tokens, as the replay record measures them.

## Who reads it

**The evaluator** is not the lessons' drafter: a fresh reader handed the outputs blind to arm, the item, this
rubric and the tree. The key joins only after the verdicts are written, as in `criterion_already_satisfied@2`.
