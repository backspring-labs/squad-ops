# Workspace-Revision Unification — Gate-1 Spike Conclusion (1.5)

**Concluded:** 2026-08-05 · Gate-1 deliverable of `docs/plans/1-5-0-stabilization-plan.md`
(the item was ROADMAP-slated with no issue and no definition doc; this spike is the
definition, and its conclusion sets the item's 1.5 disposition per the plan's
decision-deadline rule).

## What exists today (verified against code)

**The revision model** — `WorkspaceRevision` (`src/squadops/sandbox/models.py:86`,
SIP-0102 §4.6): content-addressed `revision_id` (content alone; lineage never affects
the id), origins `scaffold_seed | agent_patch | promoted_outputs`, `cut()`
constructor over a `files` mapping. Shipped in 102.1; consumed today only inside the
sandbox floor.

**The acceptance workspace** — assembled by value, with no identity, at three
surfaces:

1. **Dispatch assembly** — `dispatched_flow_executor.py:~1895` (#643): the executor
   resolves the ACCEPTED artifact tree (repair candidates excluded, pf-31 Fix E)
   through `_ACCEPTANCE_WORKSPACE_FILTER` and attaches it to the envelope as
   `inputs["acceptance_workspace_files"]`.
2. **Evaluation reads** — `handlers/cycle/base.py:431` (typed acceptance) and
   `dispatched_flow_executor.py:~2212` (repair acceptance,
   `verify_patched_artifacts`) consume that mapping.
3. **Retest forwarding** — `correction_runner.py:1232` copies the *failed task's*
   `acceptance_workspace_files` into the retest envelope verbatim.

## The defect class the unification addresses

The workspace a verifier observes is an **unnamed moment-in-time assembly**: no
verdict records which workspace state it ran against, and the retest path *forwards*
the original task's assembly while a fresh dispatch would *re-assemble* from
current store state. Two verifiers in one correction round can legitimately see
different trees with nothing in the evidence saying so. Every consumer downstream —
repair targeting (A3), replay (Track C), clean-room verdicts (SIP-0102 step 4) —
currently has to *assume* which tree a verdict meant.

## Conclusion: promote a bounded 1.5 slice; the rest is 1.6

**Slice A — revision provenance (1.5, capacity-bound, one PR): PROMOTED.**
Cut a `WorkspaceRevision` at each of the three surfaces above and stamp
`workspace_revision_id` into what they emit:

- Dispatch assembly cuts a revision (new origin `acceptance_assembly`, an additive
  constant) and rides the id in the envelope beside the files.
- Typed-acceptance evaluation artifacts (`typed_check_evaluation_task_N.json`) and
  repair-acceptance verification records carry the id they evaluated against.
- The retest forward carries the original id — making the forwarded-vs-reassembled
  distinction *visible in evidence* for the first time, without changing it.

Behavior-preserving by construction (identity is computed and recorded; nothing
reads it yet), which is what makes it capacity-bound-safe. **The plan's
no-mixed-provenance constraint is satisfied by scope**: all three surfaces stamp in
the same PR, so after it every acceptance verdict names its tree — there is no
"some verifiers report, some don't" state.

**Slice B — pinned reconstruction (1.6): NOT promoted.** Making retest/repair
*verify against a declared revision* (reconstruct the pinned tree rather than
forward a dict) changes verification behavior and belongs with SIP-0102 steps 3–4
(in-cycle routing + clean-room verdicts), which need exactly this identity
vocabulary — Slice A is their enabler, not their competitor.

## Acceptance criteria for the Slice A issue

1. Every `typed_check_evaluation` and repair-acceptance verification artifact
   produced after the change carries a non-null `workspace_revision_id`.
2. The same assembled tree always yields the same id (content-addressed; test with
   permuted file order), and any content change yields a new id.
3. Retest evidence shows the forwarded id equal to the failed task's id (the
   forwarding path is visible, not silently re-assembled).
4. No behavior change: regression green with zero evaluation-outcome diffs on a
   replayed stored cycle (Track C's slice, or the manual replay pattern).
5. `RevisionOrigin` gains `acceptance_assembly` additively; sandbox parity guards
   untouched.

**Risk note:** the id must be computed from the *exact mapping handed to the
evaluator* (post-filter), not from store state — computing it anywhere upstream
reintroduces the assumption this slice exists to remove.
