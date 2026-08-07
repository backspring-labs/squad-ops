# 1.6.0 Authorship Plan — Author the Design, Prove It Was Won

**Established:** 2026-08-07 · **Opens:** now (v1.5.0 tagged 2026-08-06; SIP-0103 accepted
2026-08-07). Successor to the 1.5 line's discipline (`docs/plans/1-5-0-stabilization-plan.md`):
one PR per issue with `Closes`, premise re-verified against code at build time, targeted
verification per fix, live validation before merge for behavior-changing work, bump only
after a green confirmation shakedown. Sequencing, not dates — **substance gates the cut.**

Roadmap position: `docs/plans/post-1-4-roadmap-reconciliation.md` (the 1.6 row, unchanged)
and `docs/plans/post-1-5-roadmap-reconciliation.md` (1.7/1.8 rows, plus the design
intention this release owns).

## Character

An **even minor**: a feature release led by headline SIPs, which gate the version.
Hardening rides along freely.

One coherent claim: **the squad authors the interface design from the PRD, and the
release proves it was won rather than asserted.**

Two headlines, one per lane, per the dual-lane precedent set by 1.4:

| Lane | Headline | SIP |
|---|---|---|
| **M** (executor / handlers / framing surfaces) | **Squad-Authored Manifest** | **SIP-0103**, accepted 2026-08-07 with §5a/§5b/§5c in force |
| **S** (test-runner / build-check / agent-image / deploy-infra) | **Generalized Build Capability** | `SIP-Stack-Blueprint-Contract` — **deliberately still proposed**; promoted *mid-release* (see Track S) |

### The two protections this release needs

1.5's protective device was "feature-free, defined behaviorally." A feature release needs
different guards. Two, both testable:

> **Guard 1 — authored mode is a mode of manifest *provenance*, not a second pipeline.**
> Post-approval, an authored manifest enters `plan_artifact_refs` exactly as a seeded one
> does; expander, contract derivation, bind-mode plan validation, and every 1.4/1.5
> enforcement surface operate identically. **Verification at cut:** no execution path
> branches on authoring mode below the framing workload — pinned by an architecture test,
> the `test_plan_gate_seams.py` precedent.

> **Guard 2 — the measurement cannot be tuned by the thing it measures.** The authored-mode
> FAY window is pre-registered (N, PRD, deploy hash, scoring discipline) before the first
> roll, unfiltered, on a frozen deploy. The hand-authored reference manifest is excluded
> from squad inputs (contamination discipline). **Verification at cut:** the pre-registration
> record is committed before roll 1, and the window's rolls are enumerated in it.

Seeded mode remains permanently (§5a) as the control configuration and the
replay/regression referent — not a legacy path to be retired.

### Work classes (release-claim protection, carried from 1.5)

- **Release-defining** — without it, 1.6 has not delivered its claim. Exits the slate only
  by delivery, proof it was already satisfied, invalid premise, or an **owner-ratified
  scope change** that updates the release claim and the ROADMAP language.
- **Enabling** — required only because a release-defining item depends on it.
- **Capacity-bound** — may land while the release is open; **cannot delay the cut**.
  Unfinished capacity items roll to the 1.7 pool with a milestone update.

| Class | Contents |
|---|---|
| Release-defining | M1–M5 (SIP-0103's phases) · S1–S3 (Generalized Build minimum) · the authored-mode FAY window · **B1** (the memory baseline — see "Owed to 1.8") |
| Enabling | M0 (contract derivation proof) · SIP-0093 completion (#762, #194 — the authoring pattern SIP-0103 extends) · SIP-0102 steps 3–4 (clean-room verdicts; #376) |
| Capacity-bound | #668 (both halves) · #761 (A4.1) · #598 structural half · SIP-0092 M3 · #733 Slice B · SIP-0091 · SIP-0090 Phase 2 · SIP-0102 steps 5–7 · agent-comms delivery guarantees · ops riders |

**Scope warning, recorded at plan time.** The ROADMAP's 1.6 row lists five riders
(SIP-0091, SIP-0090 P2, SIP-0102 steps 3–7, SIP-0093 completion, agent-comms) alongside
two headlines. That is more than one release has held before. This plan classifies only
the two riders that *serve the headline claim* as enabling and pushes the rest to
capacity — SIP-0091 and SIP-0090 Phase 2 in particular are platform work unrelated to
authorship, and carrying them as commitments would let the release be held hostage by
work that does not prove the claim. **Removing them from the release-defining set is a
scope reading, not a scope change**; if the owner wants either as a commitment, that is
an owner-ratified scope change with a ROADMAP language update.

---

## Track M — Squad-Authored Manifest (SIP-0103)

### M0. Mechanical contract derivation, proven against the known-good pair *(enabling — do this first)*

§5b Correction 1 is the reason this track cannot start with authoring: **contract v9 is a
hand-authored artifact bound to the manifest by hash — no `derive_contract(manifest)`
exists anywhere in the pipeline.** Squad-authoring the manifest alone would leave the
contract as the remaining hand-wired seed, and bind mode without a derived contract is
just author mode wearing a costume.

Build derivation *before* any authored manifest exists, and prove it against the pair the
1.4 arc already validated:

> **M0 exit criterion (deterministic, and the shape of the whole track's risk posture):**
> `derive_contract(manifest v4 art_8becd104e9fc)` reproduces contract v9
> (`art_4f368ea08799`) — byte-equivalent, or with every diff named and justified as an
> improvement in a committed record. A diff that cannot be explained is a derivation
> defect, not a contract improvement.

This is *rails before mechanism* applied a third time (SIP-0101 Slice 1, SIP-0096's inert
Phase 1 core). If derivation cannot reproduce a contract a human wrote for a manifest a
human wrote, we learn it against a fixed target instead of inside authoring chaos.

Scope split by verified derivability (§5b):

| Layer | Disposition |
|---|---|
| Interface — `endpoint_defined` per fill slot from `api.endpoints`, `field_present` from `entities`, `import_present`/`module_imports` from the skeleton | **fully derivable** (`fill_slot_signature`'s surface already derives — #730 D1 proved the pattern end-to-end) |
| Probe skeletons — method/path/status from declared `errors` + `success_status` | **largely derivable**; probe *payloads* and `json_has` values carry product intent → derive the shape, author the values in the same authoring stage |
| Suite/coverage expectations | **authored residue** — stays with the authoring stage |

Rider: **`success_status` becomes required-per-endpoint** (§5b Correction 2 — optional and
1/5-used in v4, but the scaffold already emits the declared status, so it is load-bearing
today in all but name). Manifest schema change ⇒ **manifest v5**; the version bump is
expected here and nowhere else in the track.

### M1. Authoring stage

A manifest-authoring task family opens the framing workload in authored mode. Inputs:
the PRD and the Stack Blueprint's closed vocabulary. Output: `interface_manifest.yaml`.

**The enumerated input contract is normative (§5c.1)** — the PRD, the blueprint's closed
vocabulary, in-cycle rejection context (#669), **and nothing else**. The reference manifest
is excluded. A declared extension point marks where cross-cycle memory recalls plug in
later, *with provenance*. Undeclared inputs are contamination by definition; declared ones
are capability.

Decomposition (single merger-authored vs multi-role proposers) is §6's open question 1,
resolved at the Gate-1 design review — informed by §5a's recommendation: **single author at
design time, multi-reviewer**, because a design is a coherence artifact and merging two
independently-authored designs produces neither author's coherence.

Budget seams already exist and are **not** reinvented (§5b Q4): the authoring stage
inherits `manifest_max_attempts` as its in-stage revision budget; gate rejections spend
`framing_max_rerolls`.

### M2. Schema gate (deterministic) — partially built

`InterfaceManifest.lint()` already rejects the parses-but-unexpandable class (no endpoints,
undeclared request shapes, route-without-view, unknown stack) at the SIP-0099 net. M2 is
the delta: required sections present, and the **decision-granularity** citation discipline
(`source_prd` + `decisions[].warrant`) — *not* per-entry citation, which §5b Correction 3
rules would bloat authoring for little gate value.

Two schema extensions land here:
- **`decisions[]` gains an `unresolved: true` form** (§5c.10) — the author surfaces a design
  question it declines to resolve rather than silently defaulting; any unresolved-critical
  entry lands in the HITL gate note as a question.
- **Every judgment call the schema cannot express mechanically must land in `decisions[]`
  with a PRD warrant** (§5c.4) — pagination, authz boundaries, idempotency, caching. Judgment
  becomes explicit, reviewable at the gate, and auditable later.

### M3. Winnability gate (deterministic — the new validator family)

The authored manifest must be provably winnable before anything downstream spends on it.
Phase-1 depth is **deterministic closed-surface proofs only** (§5b Q2), each buildable from
an existing seam:

| Proof | Seam |
|---|---|
| `lint()` passes | exists (SIP-0099) |
| expander dry-run — `expand()` succeeds, `fill_slot_paths()` non-empty, paths under scaffold roots | exists, pure and cheap (the pf-26 wrong-root class, one level up) |
| derived-contract dry-run — every derived check passes `CHECK_SPECS` validation, #671 module-existence holds against the implied skeleton, no check dead-on-arrival per `is_check_applicable` | **depends on M0** |
| testid coverage — every route declares ≥ 1 testid | schema field exists |
| status completeness — per-endpoint `success_status` | M0's rider |

Deferred: semantic PRD coverage. The `decisions[].warrant` discipline plus the HITL gate
carry that judgment in Phase 1; a mechanical coverage proof is not a Phase-1 blocker.

### M4. Manifest review gate (HITL) — zero new machinery

§5b Correction 4: `task_flow_policy.gates` entries key on `after_task_types`, and the mid-run
gate wait already pauses and resumes on recorded decisions — the same seam
`progress_plan_review` uses. The manifest gate is **a policy entry naming the authoring task
type, plus CRP defaults.**

Iterative review, not binary (§5c.6): `RETURNED_FOR_REVISION` is a live third state (#466),
and rejection-context injection (#669) already threads reviewer notes into the next attempt.
Revision returns the manifest **with the prior artifact and the reviewer's notes as authoring
context — revise, don't re-roll** (the fay-6 new-dice lesson), spending `manifest_max_attempts`.
**Partial approval is deliberately not introduced**: approval stays whole-artifact because
the contract derives from the whole.

### M5. Provenance + freeze

A `provenance` block on the manifest itself (§5c.5 — the #734 pattern one level up): authored
vs seeded mode, authoring task and cycle, attempt count, and any operator edit's own record.
Immutability is already mechanical — the gate approves *bytes*, `content_hash` freezes them,
and an operator edit is a **new manifest version with a new hash**, never an in-place
mutation. Replay, regression, and memory read provenance from the artifact rather than from
cycle-history archaeology.

**Manifest evolution stays out** (§5c.8). The freeze is what makes verdicts attributable:
every check, probe, and repair measures against one hash, and a mid-cycle moving target is
the #494 stale-binding class systemically. The named trigger for revisiting: a measured rate
of A4 `plan_defect` terminations whose root cause names an authoring-unknowable constraint.

---

## Track S — Generalized Build Capability

The S headline's SIP prescribes its own sequencing, and it does **not** start with acceptance.

### S1. Consolidate the five per-stack facts — no SIP required

Today "a stack" is an identifier indexing four module-level dicts plus one function with the
answer written inline. One of them — `fill_slot_paths` — hardcodes the FastAPI slot map behind
a guard that only checks whether the stack is *registered*, so a second stack would silently
inherit `backend/routes.py` as a fill slot and nothing would object.

Consolidate into one object carrying **today's fields**. Pure refactor, exact test:
`expand()` output byte-identical, contract `content_hash` and `interface_manifest_hash`
unmoved, both emission gates 6/6, regression unchanged. This removes the silent-omission
failure mode immediately and prejudges nothing.

### S2. Stack #2 — **the release's largest open decision**

Which second stack is **not decided by this plan**. It is a Gate-1 owner decision, and it
gates everything after it in this track. The selection criterion that matters: stack #2 must
differ from `fullstack_fastapi_react` along the axes the blueprint SIP names as
FastAPI-shaped assumptions, or it will not reveal the mismatches the whole exercise exists
to find — one analysable language per stack, a Python-style import boundary between tests
and app, test ownership as directory prefixes, slots derivable from declared entities and
routes.

### S3. Promote the Stack Blueprint SIP, schema written against two stacks

Its acceptance gate is literally the existence of a second real stack, because "generalising
from one instance produces the FastAPI contract with generic field names — which is worse
than no contract, because it looks authoritative and the second stack will quietly bend
itself to fit rather than reveal the mismatch." Promotion is therefore a **mid-release
milestone**, and the schema is reconciled across both stack vocabularies.

Riding here (ROADMAP's 1.6 S scope): the **QA-decomposition anchor's structural derivation** —
tasks declare produce-vs-verify and `expected_artifacts` derive from the blueprint's ownership
map, making the shk-1 dual-claim class *inexpressible* rather than merely rejected.

### S4 *(capacity)*. Migrate typed checks off hardcoded `.py`

Onto the blueprint's declared source language. This is where #668's `.jsx` territory and
#598's packaging criterion become expressible; both stay capacity-bound.

---

## Owed to 1.8 — the one intention this release owns

**B1. Record the pre-memory rejection-class recurrence baseline.** *(Release-defining, and
the only item here whose omission is permanent.)*

Cross-Cycle Memory's entire value claim is that recurrence of the same mistake falls. That
needs a baseline captured from the authored-mode window, **before memory exists**. Once memory
is live the baseline is unrecoverable and the claim becomes unmeasurable.

Concretely: durable per-cycle counts of rejection classes — plan-validation rejections and the
new manifest-gate rejection taxonomy — emitted as a first-class output of the authored-mode
window, read by nothing in 1.6. Cheap while building authored mode; impossible afterward.

Full rationale: `docs/plans/post-1-5-roadmap-reconciliation.md`, "Design intentions carried
forward," intention 5.

---

## Gates

**Gate 1 — design commitments and enabling proofs.** SIP-0103 §6's open questions resolved
(authoring decomposition first among them); the stack-#2 decision (S2); M0's derivation proof
banked; S1's consolidation merged. *Exit:* no release-defining work starts against an
unresolved design question.

**Gate 2 — the authoring loop closes.** M1–M4 land; an authored manifest passes schema and
winnability gates, reaches the HITL gate, and — post-approval — runs the existing pipeline
end to end with no mode branch below framing (Guard 1's architecture test green).

**Gate 3 — integration.** M5 provenance; S3 promotion with the two-stack schema; B1 emitting;
enabling riders (SIP-0093 completion, SIP-0102 steps 3–4) landed. Deploy window with
loaded-module verification, per the 1.5 precedent.

**Cut gate.**
1. **Core-claim gate:** M0–M5 and S1–S3 complete; B1 emitting. Removal of any item requires an
   owner-ratified scope change.
2. **Capacity roll:** unfinished capacity items → 1.7 pool with a milestone update.
3. **Full regression green**, and both guards verified (the no-branch architecture test; the
   committed pre-registration record).
4. **The measurement:** authored-mode FAY window — pre-registered N, unfiltered, frozen deploy.
   **Gate: FAY repeatably > 0 in authored-manifest mode**, banked as the authored-mode baseline
   that 1.8's memory and campaign work measure against.
5. **Confirmation shakedown** on the fully integrated line, green, per the 1.4/1.5 cadence.

### Non-gating diagnostics for the window (§5c.7)

FAY stays the gate — functional truth. Recorded alongside, non-gating: structural manifest
diff against the human reference (§5b Q3 — cheap and mechanical on a typed canonical surface,
and it stays out of both the gate and squad inputs), revision/attempt counts, the gate-rejection
reason taxonomy, and manifest size/surface counts. **"Maintainability" and "elegance" metrics
are declined** — no deterministic representation exists, and an LLM-graded elegance score is
exactly the evidence-quality laundering A6 forbids.

Design-quality heuristics may enter only as **advisory-lane checks with their own identity**
(the `plan_prose_contract_divergence` pattern — visible, non-gating, never laundering into
blocking), promotable only with a deterministic representation. Phase 1's design-quality
authority is the HITL gate plus measurement, stated as such (§5c.2).

---

## Risks

| Risk | Why it is real here | Containment |
|---|---|---|
| **Derivation can't reproduce v9** | The pair was authored by hand and may encode judgment no deriver can see | M0 runs first, against a fixed target; every diff named or it's a defect |
| **Authored chaos swamps the window** | An authored manifest can fail in ways a seeded one never could | Blueprint grammar + deterministic gates bound the space; free re-roll and hash-freeze at approval bound the blast radius (§5a) |
| **Stack #2 chosen for convenience** | A near-twin of FastAPI would validate nothing | S2's selection criterion is stated above and is a Gate-1 owner decision |
| **Authored mode forks the pipeline** | The easy implementation is a second path | Guard 1's architecture test |
| **Rider creep** | Five riders were listed against two headlines | Work classes; only claim-serving riders are enabling |
| **Measurement drift** | A window tuned mid-flight proves nothing | Guard 2's pre-registration, committed before roll 1 |

## Rollback seams

One PR per issue keeps every behavior-changing item independently revertible by image swap.
The manifest **v5** schema change (M0's `success_status` rider) is the one versioned boundary:
additive-and-required-forward means old manifests must be migrated or rejected explicitly, not
silently accepted — decide which at Gate 1 and record it. Authored mode itself is
config-selected, so its rollback is a profile change, not a code revert.

## Evidence matrix

Instantiated at Gate 1 and maintained per landed item, per the 1.5 precedent (`Item · behavior
class · primary risk · required proof · live validation · replay/golden artifact · cut status`).
Every release-defining item has a filled row before the cut; every behavior-stricter item's row
names the ruling that authorizes it.
