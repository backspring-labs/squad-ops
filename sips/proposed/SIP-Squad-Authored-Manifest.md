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

## 5a. Amendments from the 1.5 boundary (2026-08-07)

Recorded at the 1.5 cut boundary, after the stabilization line landed machinery this
draft predates. Three recommendations for design review plus an updated foundation
inventory.

### Recommendation on Q1 — single author, multi-reviewer (not co-authoring)

The proposer-merge pattern (SIP-0093) works for *task lists* because merging them is
deterministic set arithmetic. A manifest is one coherent interface: two agents
co-authoring entities and routes produce collisions that are **semantic, not
positional** — the `proposed_plan_tasks.yaml` filename-collision class, relocated into
the type system, with no deterministic merge to save it. Recommended Phase-1 shape:

- **Dev authors**, at the `development.design_plan` stage — the manifest is an
  architecture artifact (entities, API surface, view surface) and that stage already
  authors the technical design; it is the best-informed placement (today's author-mode
  emission sits with the lead at plan-authoring/review, the *least*-informed moment).
  Strategy's frame constrains scope from above.
- **QA reviews for verifiability** — every view declares its anchors, every endpoint a
  probe-able status contract. QA signs the surface it will later be held to testing.
- **Governance gates** (schema → winnability → HITL review), unchanged from §3.

Collaboration through *review*, not co-authoring. The multi-role dice question (Q1's
other branch) can be revisited with evidence if single-author quality disappoints —
the reverse migration (merging co-authored fragments) has no such fallback.

### The chaos-containment frame (supporting §3, for the design review's risk row)

Authoring the manifest does not make the *system* generative — it confines generation
to **one authoring window with a hard exit**. Three bounds, in order:

1. **Blueprint grammar in** — the author can only declare what the expander can expand
   (the Stack Blueprint's closed vocabulary; unknown surface is rejected, not
   improvised).
2. **Deterministic gates + free re-roll** — schema and winnability failures die at a
   framing re-roll (system rejection, the #522 free-re-roll class), never at
   implementation.
3. **Freeze at approval** — the instant the HITL gate approves, the manifest
   hash-freezes and the contract derives; everything downstream runs on exactly the
   rails the 1.4/1.5 arcs hardened. Post-freeze determinism is identical to seeded
   mode by construction (§3.5's claim, stated as the containment property it is).

### Recommendation on Q5 — seeded mode stays, permanently

Comparability requires frozen hashes: the golden benchmark works *because* the manifest
is byte-stable across cycles. Authored mode should bank its own baseline series;
seeded mode remains the permanent measurement rig and regression referent, not a
transitional configuration. (Replacing it would trade the ability to attribute a
regression to machinery vs authoring — the exact attribution discipline the odd-minor
convention exists to protect.)

### Foundation inventory update (what 1.5 banked for this SIP)

- **The enforcement chain is now fully manifest-rooted and *declared*.** Scaffold
  expansion, fill slots, `fill_slot_signature` (#730 D1), testid surfaces (#659), the
  criteria index (98.3), and the typed-check governance registry (#730) all derive
  mechanically from the manifest — an authored manifest propagates into the entire
  verification stack with **zero new plumbing**.
- **SIP-0099's validation net is live** and is deliberately the manifest's only net —
  the seam the winnability gate (§3.3) extends rather than invents.
- **Workspace-revision provenance (#734)** means every acceptance verdict in an
  authored-mode experiment names the tree it measured — authored-vs-seeded evidence
  stays attributable.
- **Replay (SIP-0101) + stranded-cycle detection (#481)** make authored-mode FAY
  windows cheap to interrupt and crash-tolerant — relevant because §4's window is the
  most compute-expensive measurement the project has scheduled.

## 5b. Deep review against main (`df29d45c`, 2026-08-07) — corrections and answers

Premise-verification pass at the 1.5 cut boundary; every claim below checked against
code, the v9 contract / v4 manifest pair, and the live pipeline.

### Correction 1 — the contract is NOT derived today, and that under-scopes this SIP

The Motivation's "SIP-0098 derives 14 criteria from it mechanically" and §3.5's
"contract derivation … operate[s] identically" overstate current mechanics: **contract
v9 is a hand-authored artifact** (ingested as `art_4f368ea08799`), *bound* to the
manifest by hash — no `derive_contract(manifest)` exists anywhere in the pipeline.
Consequence: squad-authoring the manifest alone leaves the contract as the remaining
hand-wired seed, and bind mode without a contract is just author mode. The SIP must
scope this explicitly. **Recommendation: add mechanical contract derivation to scope**,
split by derivability (verified against the v9/v4 pair):

- **Fully derivable:** the interface layer — `endpoint_defined` per fill slot from
  `api.endpoints`, `field_present` from `entities`, `import_present`/`module_imports`
  from the skeleton; `fill_slot_signature`'s surface already derives (#730 D1 proved
  the pattern end-to-end).
- **Largely derivable:** probe skeletons — the manifest declares per-endpoint semantic
  error codes (`errors: [validation_error]`, 4/5 endpoints in v4) and `success_status`
  (1/5 in v4 — see Correction 2); method/path/status expectations derive; probe
  *payloads* and `json_has` fields carry product intent → derive the shape, author the
  values in the same authoring stage.
- **Authored residue:** suite/coverage expectations — stays with the authoring stage,
  not derivation.

The alternative (squad authors *both* artifacts freehand) doubles the chaos surface to
hand-write what is mostly mechanical — rejected.

### Correction 2 — schema tightening the derivation needs

`success_status` is optional and sparsely used (1/5 endpoints in v4); derivation and
the winnability gate both want it required-per-endpoint. Cheap schema change, and the
scaffold already emits the declared status (pf-40's whole arc), so the field is
load-bearing today in all but name.

### Correction 3 — "every entry cites its PRD derivation" is coarser in the schema

The citation discipline exists but at *decision* granularity, not per-entry:
`source_prd` plus `decisions[].warrant` (section-cited, e.g. "§5.4 validation — …").
Per-entry citation fields do not exist. **Recommendation: keep decision-granularity**
(per-entry citations would bloat authoring for little gate value) and reword §3.2's
schema-gate bullet to match.

### Correction 4 — the HITL manifest gate needs zero new machinery (good news)

§3.4 reads as if a new gate mechanism is needed. It isn't: `task_flow_policy.gates`
entries key on `after_task_types`, and the mid-run gate wait already pauses/resumes on
recorded decisions — the same seam `progress_plan_review` uses. The manifest review
gate is a policy entry naming the authoring task type, plus CRP defaults. Similarly
§3.2's schema gate is **partially built**: `InterfaceManifest.lint()` already rejects
the parses-but-unexpandable class (no endpoints, undeclared request shapes,
route-without-view, unknown stack) at the SIP-0099 net.

### Q2 answered — winnability depth for Phase 1

Deterministic closed-surface proofs only, all buildable from existing seams:
`lint()` (exists) · expander dry-run (`expand()` succeeds and `fill_slot_paths()` is
non-empty — pure and cheap) · derived-contract dry-run (once Correction 1's derivation
lands: every derived check passes `CHECK_SPECS` validation, #671 module-existence holds
against the implied skeleton, and no check is dead-on-arrival per
`is_check_applicable`) · testid coverage (every route declares ≥ 1 testid — the schema
field exists) · status completeness (per Correction 2). **Deferred:** semantic PRD
coverage — the `decisions[].warrant` discipline plus the HITL gate carry that judgment
in Phase 1; a mechanical coverage proof is not a Phase-1 blocker.

### Q3 answered — evaluation referent

Functional outcome gates the window (unchanged). Add a **deterministic manifest-diff
against the reference as a non-gating diagnostic**: the manifest is a typed, canonical
surface, so the diff is cheap and mechanical — but it stays out of the gate and out of
squad inputs (contamination discipline intact). Design-diff *grading* by a model is not
needed; the structural diff already answers "how far from the human design did the
squad land."

### Q4 answered — the re-roll budget already exists

`manifest_max_attempts` is live today (`PlanAuthoringService`, default 2,
profile-configurable — the validated profiles run 4): the in-stage authoring retry
budget, with corrective feedback per attempt. `framing_max_rerolls` governs
whole-framing re-rolls after gate rejections. **Keep both, at their existing seams** —
the authoring stage inherits `manifest_max_attempts` as its revision budget; gate
rejections spend `framing_max_rerolls`. Nothing to invent; the SIP should name the
two seams so design review doesn't reinvent them.

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
