# SIP: Squad-Authored Manifest

## Status
Draft (proposed)

**Author:** Jason Ladd
**Created:** 2026-08-03
**Targets:** v1.6 (Lane M headline — the Authorship release, per
`docs/plans/post-1-4-roadmap-reconciliation.md`)
**Builds on:** SIP-0099 (Contract-First Build Scaffolding — the expander this feeds),
SIP-0098 (Verification Contracts — derived from the manifest, so authoring the manifest
authors the ground truth the contract expands from), SIP-0093 (Multi-Role Plan
Authoring — the authoring-task family this extends), the #494/#496 bind-mode gate, and
the plan-validation family (#658/#671/#673 — the authoring-time closed-surface-proof
precedent this SIP lifts one level up).
**This IS the 1.4 cut gate's deferred condition.** Recorded at the cut: seeded-manifest
FAY 6/6 demonstrates that *given* a PRD and a fully specified interface manifest, the
squad delivers a working app. What remained unmeasured — by the original gate's own
correct reasoning — is whether the squad can *author* that manifest from the PRD.

---

## 1. Summary

Move the authorship rung up the ladder: from **filling a given design** (1.4,
seeded-manifest bind mode) to **authoring the design from the PRD**, under the same
gate discipline that made 1.4's number honest.

A new manifest-authoring stage in the framing workload produces
`interface_manifest.yaml` from the PRD alone. It passes a **schema gate**
(parses, structurally complete), a **winnability gate** (the manifest it authored can
actually be won: the expander accepts it, the derived verification contract is
satisfiable by construction, fill slots enumerate, testids cover the promised views),
and a **manifest review gate** (human, HITL — the operator approves the *design* before
implementation spends budget on it). Downstream, the existing pipeline consumes the
authored manifest exactly as it consumes a seeded one — bind mode, expander, contract
derivation, and enforcement machinery all unchanged.

Exit is measured, not asserted: an authored-mode FAY window, pre-registered N, gate
**FAY repeatably > 0 in authored-manifest mode**, banked as the authored-mode baseline
(the referent v1.8's memory and campaign work measure against).

## 2. Motivation

1.4's cut-gate supersession was honest about what it measured: the squad implements,
verifies, and delivers against a *hand-authored* manifest (the Phase-0.5 reference
instance, authored from prd.md alone under the contamination discipline). The manifest
is the single remaining hand-wired seed in the golden path — the design intelligence is
still human. Until the squad authors it, SquadOps demonstrates *implementation*
capability, not *engineering* capability.

The 1.4 arc also produced the exact toolkit this rung needs: the manifest is a schema'd,
versioned, closed surface (SIP-0098 derives 14 criteria from it mechanically); the
plan-validation family proved that authoring-time closed-surface proofs (#671's
module-existence, #673's dual-claim net) reject doomed authoring *before* budget burns;
and the FAY methodology gives the measurement shape.

## 3. Design sketch (normative surface for review; implementation design is Lane M's)

1. **Authoring stage.** A manifest-authoring task (or task family) opens the framing
   workload when the cycle runs in authored mode: inputs are the PRD and the stack's
   scaffold surface (the Stack Blueprint's closed vocabulary — what roots, slots, and
   conventions exist to design *with*); output is `interface_manifest.yaml`. Role
   assignment and single- vs multi-role decomposition follow the SIP-0093 authoring
   pattern (proposers + merger) — exact shape is design-review input, informed by the
   Phase-0.5 spike rider ("merger authors manifest cold").
2. **Schema gate (deterministic).** `InterfaceManifest.from_yaml` parses; required
   sections present; every entry cites its PRD derivation per the reference instance's
   discipline. Failures re-roll with rejection context (#669 machinery, already live).
3. **Winnability gate (deterministic — the new validator family).** The authored
   manifest must be provably winnable before anything downstream spends on it:
   - the expander accepts it and the skeleton it implies is expressible (fill slots
     enumerate, paths live under scaffold roots — the pf-26 wrong-root class, one level
     up);
   - the derived verification contract is satisfiable by construction (no
     contradictory-by-construction checks — the #671 class, authored rather than
     inherited);
   - interface self-consistency: endpoints/params/testids the manifest promises are
     mutually coherent and cover the PRD's promised surface (the #565 `{id}`/`{run_id}`
     naming-prior class becomes an authoring-time check instead of a live-roll loss).
4. **Manifest review gate (HITL).** A named gate between manifest acceptance and
   implementation: the operator approves the authored design the way
   `progress_plan_review` approves the plan. Design is cheap to reject here and
   expensive to reject later — this is the budget argument that justifies a second
   human gate in the cycle.
5. **Downstream unchanged.** Post-approval, the authored manifest enters
   `plan_artifact_refs` exactly as a seeded one does; expander, contract derivation,
   bind-mode plan validation, and all 1.4 enforcement machinery operate identically.
   Authored mode is a *mode of manifest provenance*, not a second pipeline.

## 4. Measurement (the gate)

- Authored-mode FAY window: pre-registered N, unfiltered, frozen deploy, same PRD and
  scoring discipline as the 1.4 windows. Release gate: **FAY repeatably > 0**; the
  window's number is banked as the authored-mode baseline.
- The hand-authored reference manifest is **excluded from squad inputs** in authored
  mode (contamination discipline). Whether it serves as an evaluation referent
  (design-diff grading) or only functional outcome counts is an open question (§6).

## 5. Non-goals

- A second stack (Generalized Build, the 1.6 S-lane headline, is a sibling — this SIP
  authors against one blueprint's closed vocabulary).
- Objective→PRD authoring (the rung above; separate future direction) and prototype/
  desirability gates.
- Any change to seeded-manifest mode — it remains the control configuration and the
  replay/regression referent.
- Manifest *revision* mid-implementation (drift between authored manifest and built app
  is caught by the existing contract machinery; in-cycle manifest renegotiation is
  explicitly out).

## 6. Open questions for design review

1. Authoring decomposition: single merger-authored manifest (spike-rider shape) vs the
   full #657-style proposer set — does design authoring benefit from multi-role dice
   the way plan authoring did, or is a single strong author + review gate the right
   Phase-1 shape?
2. Winnability depth: which self-consistency proofs are Phase 1 (closed-surface,
   deterministic) vs deferred (semantic coverage of the PRD — harder than path/schema
   proofs)?
3. Evaluation referent: functional-outcome-only, or design-diff against the reference
   manifest as a *non-gating* diagnostic?
4. Re-roll budget: does manifest authoring share `framing_max_rerolls` or carry its own
   revision budget?
5. Does authored mode enter the golden benchmark as a second measured configuration
   permanently, or does it *replace* seeded mode as the canonical measurement once its
   baseline is banked?
