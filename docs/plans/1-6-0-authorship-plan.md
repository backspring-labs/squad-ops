# 1.6.0 Authorship Plan — Author the Design, Prove It Was Won

**Established:** 2026-08-07 · **Opens:** now (v1.5.0 tagged 2026-08-06; SIP-0103 accepted
2026-08-07). Successor to the 1.5 line's discipline (`docs/plans/1-5-0-stabilization-plan.md`):
one PR per issue with `Closes`, premise re-verified against code at build time, targeted
verification per fix, live validation before merge for behavior-changing work, bump only
after a green confirmation shakedown. Sequencing, not dates — **substance gates the cut.**

Roadmap position: `docs/plans/post-1-4-roadmap-reconciliation.md` (the 1.6 row, unchanged)
and `docs/plans/post-1-5-roadmap-reconciliation.md` (1.7/1.8 rows, plus the design
intention this release owns).

**Revised 2026-08-07** after an owner review round (twelve points). They are folded in
where they act rather than appended as a list, because an appendix gets skimmed and a
gate criterion does not. What they changed, for traceability: M0 gained a divergence
taxonomy; M2 gained the unresolved-decision lifecycle; M5 gained a structured revision
reason; Guard 1 gained an **equivalence** half; S3 gained the exit criterion it was
missing; B1 gained time-to-resolution; and three sections are new — **the authoring
failure taxonomy**, **generalization debt after 1.6**, and **blueprint vocabulary
governance**. The review's sharpest finding was that S1 and M0 had proof strategies and
S3 had only a subjective one; the second sharpest was that three separate asks (revision
reason, memory baseline, window attribution) are one artifact used three ways.

**Revised again 2026-08-07 — M0's premise was wrong.** A pre-build verification pass
measured the actual artifacts and found that the contract deriver already exists and that
contract v9 is its exact output for manifest v4. **This plan therefore contradicts accepted
SIP-0103 §5b Correction 1 on measured evidence**; the SIP stands as the accepted design
commitment and the correction lives here. Consequences: M0 collapses from "build a deriver"
to a guard plus wiring; Track M gains an explicit **gates-before-author** build order; and
the `success_status` rider is upgraded from a schema-tidiness argument to a live latent
defect with a reproduction.

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
> enforcement surface operate identically.
>
> **Verification at cut, in two halves — structure and output:**
>
> - **1a, no fork:** no execution path branches on authoring mode below the framing
>   workload — pinned by an architecture test, the `test_plan_gate_seams.py` precedent.
> - **1b, equivalence:** feed the **reference manifest** through authored mode's
>   post-approval path; the expansion, the derived contract, and every verification
>   artifact must be **byte-identical** to seeded mode's. Same input, same output,
>   different provenance.
>
> 1a alone is not sufficient and the distinction matters: a structural test proves nothing
> *branches*, not that the transformation is the same. 1b is what isolates a provenance
> change from a transformation defect, and it is cheap — the golden/replay machinery from
> 1.5 already does exactly this comparison.

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
| Release-defining | M1–M6 (SIP-0103's phases + the failure taxonomy) · S1–S3 + S5 (Generalized Build minimum + blueprint governance) · the authored-mode FAY window · **B1** (the memory baseline — see "Owed to 1.8") |
| Enabling | M0a/M0b (equivalence guard + derive-at-seed; the derivation *proof* is already banked) · SIP-0093 completion (#194 — the authoring pattern SIP-0103 extends; **#762 moved to the queue front**, where its preflight block starts paying immediately rather than waiting on the rest of 93's completion) · SIP-0102 steps 3–4 (clean-room verdicts; #376) |
| Queue front (pre-work) | #762 · #766 · #770 — see "Queue front" above; cheap, not claim-proving, but they tax every roll |
| Capacity-bound | #668 (both halves) · #772 (rides M0's schema change) · #761 (A4.1) · #598 structural half · SIP-0092 M3 · #733 Slice B · SIP-0091 · SIP-0090 Phase 2 · SIP-0102 steps 5–7 · agent-comms delivery guarantees · ops riders |

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

## Queue front — pre-work hygiene *(ahead of M0a; owner-ruled 2026-08-07)*

Three small fixes land **before** the headline tracks open. They are not release-defining and
they do not prove the claim; they are here because 1.6's output is measured in **cycle rolls**,
and each of these taxes every roll the release will run.

| Item | What it costs per roll today | Why now rather than later |
|---|---|---|
| **#762** — bind mode with no `plan_authoring_contributors` is a guaranteed plan rejection | a wasted launch; **cost three rolls at shk-6** before diagnosis | 1.6 runs authoring experiments, gate probes, and an **unfiltered** FAY window, where a roll lost to misconfiguration is expensive in a way it is not during development |
| **#766** — LangFuse prompt linkage is inert under the filesystem asset provider, and logs a vendor `ERROR` per agent per cycle | triage noise on every cycle; prompt→generation linkage silently absent from every trace | 1.6 is a release spent reading traces and triaging authoring failures — this degrades the instrument we will lean on hardest |
| **#770** — `update_sip_status.py` fails opaquely on drafts without frontmatter | a blocked promotion at the worst moment | 1.6 promotes the Stack Blueprint SIP **mid-release** (S3), so this bites again inside this line |

**This is deliberately not a 1.5.1 patch line.** The population since the v1.5.0 cut is five
items (these three, plus #761 already homed to 1.6 as A4.1, plus #772), none urgent, three of
them papercuts — below the bar the 1.4 patch lines set at 5–7 real fixes each, and not worth a
deploy window, shakedown, bump, tag, and ledger close. 1.6 also opens with **pure offline work**
(M0a is a fixture test; M0b is seed-time wiring), so a freshly-verified deployed baseline buys
nothing yet. Same fixes, same order of arrival, none of the release overhead.

**Trigger that would change this ruling:** the population reaching five or six *real defects*
while 1.6's first deploy window is still far out, or any one of them turning live-breaking.

---

## Track M — Squad-Authored Manifest (SIP-0103)

### Build order — **gates before author**

The M-numbers below are section identities, not a sequence. The build order is:

> **queue front (#762, #766, #770) → M0a → M0b → M3 → M2 → M6 → M1 → M4 → M5**

M0's collapse (below) made the original M1-first ordering wrong. The reasoning, which is
the same rails-before-mechanism rule this repo has now applied three times (SIP-0101
Slice 1, SIP-0096's inert core, and M0a here):

- **The gates are deterministic and testable against hand-made adversarial manifests
  today**, with no authoring stage, no LLM, and no deploy. The `success_status` defaults
  trap documented under M0 is a designed-failure probe that can be written this week.
- **M1 is the only piece whose output is a lottery.** Landing it last means it arrives
  against gates already proven to reject the classes we know about — so a failed authored
  manifest is attributable to the author rather than ambiguous between author and
  unproven gate.
- Ordering M1 first inverts that: every early gate defect would surface *as* an authoring
  failure, and the window's attribution (M6) would inherit the confusion.

M4 (the HITL gate) follows M1 because there is nothing to review until something is
authored; M5 (provenance) is last because it stamps a pipeline whose shape is settled by
then.

### M0. Contract derivation — **premise corrected 2026-08-07; the proof is already banked**

> **PREMISE CORRECTION — this plan contradicts accepted SIP-0103 §5b Correction 1, on
> measured evidence.** The SIP states: *"contract v9 is a hand-authored artifact … no
> `derive_contract(manifest)` exists anywhere in the pipeline."* **Both halves are false.**
> The SIP stays as accepted (it is a design commitment on main, not a living document);
> the correction lives here, where the work is planned.

The deriver exists and always did: `squadops.capabilities.scaffold_contract.emit_contract_dict()`,
shipped as SIP-0098 phase 98.2 — *"the criteria are derived deterministically from the same
interface manifest the skeleton is expanded from, so verification is a fixed property of the
scaffold rather than a per-roll LLM lottery."*

Run against the artifacts themselves on 2026-08-07:

```
emit_contract_dict(InterfaceManifest.from_yaml(art_8becd104e9fc))  ==  yaml(art_4f368ea08799)
→ True   (exact dict equality; all six sections identical; 4 fill_files, 5 probes)
```

**Contract v9 is a pinned emission of manifest v4, not a hand-authored artifact.** M0's
exit criterion as originally written — reproduce v9 from v4, byte-equivalent or every diff
classified — is therefore **met with zero diffs, before any work started.**

#### What is actually missing: wiring, not intelligence

Bind mode loads the pinned contract from `contract_ref` *by design* — `handlers/cycle/base.py`
states it outright: *"bind mode loads the pinned contract from `contract_ref` instead of
regenerating it, so a criterion added to the expander would not appear until a re-seed."*
That is correct for seeded mode and **impossible for authored mode**, where no pinned
artifact exists yet because the manifest was only just written.

M0 therefore collapses to two small, deterministic pieces:

- **M0a — pin the equivalence as a standing guard.** A test over committed fixtures asserting
  `emit_contract_dict(v4) == v9`. This converts a one-off measurement into an invariant, so
  the deriver can never silently drift away from the contract the 1.4 evidence was measured
  against. Cheap, and the entire track now rests on it.
- **M0b — derive-at-seed.** When a cycle supplies a manifest and no `contract_ref`, derive
  the contract at seed time and pin it, so authored mode gets the same frozen-by-hash
  guarantee seeded mode has. No LLM, no new intelligence, fully testable offline.

The divergence taxonomy below is **retained deliberately**, not deleted as spent. It now
governs M0b (an authored manifest's derived contract vs what the scaffold actually emits)
and any future change to the deriver — the classes are what keep "we changed the contract"
from becoming an unexamined act.

**Every accepted divergence is classified, not merely justified.** "Justified" degrades
into a rubber stamp under schedule pressure; a required class does not. The taxonomy —
and note that v9 is the *incumbent*, not automatically the gold standard:

| Class | Meaning | Consequence |
|---|---|---|
| `normalization` | same semantics, different serialization (ordering, whitespace, defaulted field made explicit) | accept; pin the normal form so it never drifts again |
| `ambiguity_removal` | v9 left something implicit that derivation must make explicit | accept; record the resolution as the new reference |
| `derivation_defect` | the deriver is wrong | **fix the deriver** — never the record |
| `reference_defect` | the pinned reference is wrong and a deriver change found it | accept the new form **and** see below |
| `underivable` | the reference encodes intent the manifest cannot express | the manifest schema gap is named; the check moves to authored residue |

**The `reference_defect` class carries a retrospective obligation.** The 1.4 FAY window
(6/6, five consecutive) was measured *against v9*. A defect there is not merely a contract
note — it qualifies a published number, and the plan must record the qualification in the
same PR rather than absorbing it silently. This is unlikely and cheap to state; discovering
it later without a stated policy is neither.

Scope split by verified derivability (§5b):

| Layer | Disposition |
|---|---|
| Interface — `endpoint_defined` per fill slot from `api.endpoints`, `field_present` from `entities`, `import_present`/`module_imports` from the skeleton | **fully derivable** (`fill_slot_signature`'s surface already derives — #730 D1 proved the pattern end-to-end) |
| Probe skeletons — method/path/status from declared `errors` + `success_status` | **largely derivable**; probe *payloads* and `json_has` values carry product intent → derive the shape, author the values in the same authoring stage |
| Suite/coverage expectations | **authored residue** — stays with the authoring stage |

Rider: **`success_status` becomes required-per-endpoint** (§5b Correction 2). Manifest schema
change ⇒ **manifest v5**; the version bump is expected here and nowhere else in the track.

**The empirical case is stronger than the SIP's, and it is a live latent defect.** Measured
2026-08-07: `success_status` is declared on **1 of 5** endpoints in v4. Where it is absent,
two components default *differently*:

- the deriver asserts a status — `ep.success_status or 201` for POST-to-collection
  (`scaffold_contract.py:267`), `or 200` for child routes (line 327);
- the scaffold omits `status_code=` from the route decorator entirely when it is undeclared
  (`scaffold.py:901`), so **FastAPI's own default (200) applies.**

For a POST-to-collection with no declared status, the contract asserts **201** against a
scaffold that emits **200** — an unwinnable contract, authored innocently. Today this is
masked *only* because the single endpoint reaching that branch (`POST /runs`) happens to
declare 201 explicitly. Nothing enforces that coincidence.

Two consequences:

1. This is the **first designed-failure probe for the M3 winnability gate**, and it is
   available immediately — a hand-made manifest omitting `success_status` on a POST-to-
   collection must be rejected as unwinnable before it ever reaches implementation.
2. It is a defect in seeded mode too, not only an authored-mode hazard: any future
   hand-authored manifest hits it. **Filed as #772** (2026-08-07), homed to 1.6 with the
   preferred resolution recorded as *fix by deletion*: making `success_status` required
   makes both defaults unreachable, so the underlying REST-semantics question — is the
   deriver presumptuous, or the scaffold under-specified? — is dissolved rather than
   answered. If the required-field change ever leaves scope, #772 says explicitly that the
   question comes back live and needs an owner ruling.

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

#### The lifecycle of an unresolved decision *(otherwise it propagates silently)*

Three rules, so an unresolved entry can never become an implementation surprise:

1. **Preserved, never consumed.** An unresolved entry stays in the manifest as part of the
   design record and its provenance. Approval does **not** silently drop it.
2. **Approval does not resolve it.** The operator approving a manifest approves the design
   *including its stated open questions*; resolution is a separate act that produces a new
   manifest version with a new hash (M5's immutability rule). Nothing may read "approved"
   as "all questions answered."
3. **Derivation may not depend on one.** If a derived check would depend on an unresolved
   decision, that is a **winnability failure (M3), not an approval question** — the gate
   rejects before a human ever sees it.

Rule 3 is the load-bearing one: it keeps the invariant in deterministic machinery rather
than in reviewer discipline, which is the difference between a rule and a hope.

#### The judgment ratchet *(the surface must shrink, not grow)*

§5c.4 defines *what* may be judgment — anything the schema cannot express mechanically.
What it does not do is create any pressure for that set to get smaller, so an
implementation can satisfy every deterministic gate while quietly relocating more and
more engineering reasoning into `decisions[]`.

The ratchet: **`decisions[] entries are counted by class in the window diagnostics, and a
recurring judgment class is a schema-gap signal**, not a standing accommodation. A class
that appears in most authored manifests is a candidate for promotion to a mechanical
field — adjudicated by the blueprint governance rule below, since promotion is a
blueprint-version change rather than silent drift.

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

**Provenance records *why* it changed, not only where it came from.** Attempt count alone
says a manifest took three tries; it does not say whether those tries were a schema failure,
a winnability rejection, reviewer feedback, or the author's own refinement — and every
downstream consumer (replay comparison, the window's attribution, 1.8's memory) wants
exactly that distinction. Each revision therefore carries a **structured reason drawn from
the shared authoring failure taxonomy below** — one vocabulary, not a free-text field that
each reader parses differently.

**Manifest evolution stays out** (§5c.8). The freeze is what makes verdicts attributable:
every check, probe, and repair measures against one hash, and a mid-cycle moving target is
the #494 stale-binding class systemically. The named trigger for revisiting: a measured rate
of A4 `plan_defect` terminations whose root cause names an authoring-unknowable constraint.

### M6. The authoring failure taxonomy — **one artifact, three consumers**

Three separate needs in this plan turn out to be the same record, and building it three
times would recreate exactly the taxonomy-reconciliation problem the 1.8 reconciliation
exists to prevent (intention 2 — one failure-class vocabulary, not parallel ones):

| Consumer | Needs |
|---|---|
| M5 provenance | why each revision happened |
| B1 baseline | rejection classes and their recurrence, per cycle |
| the FAY window | which subsystem a failure is attributable to |

**Build it once, in M6, before the window opens.** Without it, the window's output
collapses into a single "manifest rejected" bucket, and a bucket cannot tell us whether
authored mode is limited by the *author*, the *schema*, the *blueprint*, or the *deriver* —
which is the entire question the release exists to answer.

The taxonomy keys off the vocabulary that already exists — `failure_ownership` (#730's
registry attrs), locus classification (#568), `FailureEvidenceCategory` — extended with
the authoring-specific dimension:

| Class | Meaning | Who fixes it |
|---|---|---|
| `authoring_defect` | the manifest is wrong; the schema, blueprint, and deriver are fine | the author (retry with rejection context is the right response) |
| `schema_gap` | the manifest could not express something the design needs | schema change ⇒ blueprint version |
| `blueprint_limitation` | the stack's closed vocabulary cannot express the design | blueprint governance (below) |
| `derivation_defect` | authoring was sound; the deriver mishandled it | M0's code |
| `prd_insufficiency` | the PRD does not determine the answer | `decisions[]`, `unresolved: true`, the HITL gate |

The last class is the one that most needs to exist: without it, a PRD that under-specifies
looks identical to a squad that cannot design — and those have opposite remedies.

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

### S2. Stack #2 — **decided: a Node/TypeScript HTTP stack** *(owner ruling 2026-08-07)*

An Express-or-Fastify API with a typed React frontend. The selection criterion was
cost-per-assumption-broken: stack #2 must differ from `fullstack_fastapi_react` along the
axes the blueprint SIP names as FastAPI-shaped, or it reveals nothing — but 1.6 already
carries two headlines and a measurement window, so the break must not drag the verification
machinery into the experiment alongside the schema.

**What it breaks — three of the four named assumptions:**

| Assumption | How a TS stack breaks it |
|---|---|
| `analysable_suffix: str` (singular) | `.ts` + `.tsx` — two analysable suffixes in one stack |
| `harness_entry_modules` (Python-style import boundary between tests and app) | Node module resolution has no equivalent boundary |
| `qa_test_namespace` (test ownership as directory prefixes) | co-located `*.test.ts` beside source is the convention, not an option |

**What it deliberately holds constant: HTTP.** Endpoints, probes, and the derived
verification contract keep working, so what is under test is the **blueprint schema** rather
than the whole verification stack. That containment matters because M0 is already changing
contract derivation inside the same release.

**Why the cost is low:** the Node toolchain is already in the tree — `agents/Dockerfile`
carries Node.js/npm for the frontend build check and vitest (#306, shipped 1.3.1), and the
sandbox's `EnvironmentContract` is already parameterized by image plus required tools. No new
language runtime enters the pipeline.

**Rejected alternatives, recorded so they are not relitigated:**

- **Go** breaks *more* — single-binary packaging, and tests living inside the package rather
  than in a directory — but costs a new toolchain in the agent image, the sandbox env image,
  the test runner, and the `command_exit_zero` allowlist that #707 already declares
  untrustworthy. Too much S-lane infrastructure for a release whose S lane must also write a
  two-stack schema. **Reconsider as stack #3**, where its packaging break is the point.
- **A Python CLI / non-HTTP stack** breaks the deepest assumption (slots derivable from
  declared entities and routes) but puts the probe machinery under test simultaneously with
  the schema. Wrong experiment for this release.

**The latent break this forces into the open.** `analysable_suffix: str` is *already* wrong
today: the current stack is `.py` backend plus `.jsx` frontend, and the typed checks are
hardcoded to `.py` — which is exactly why #668's `.jsx` half keeps deferring. Stack #2 does
not create that mismatch; it makes the schema answer for one that already exists.

### S3. Promote the Stack Blueprint SIP, schema written against two stacks

Its acceptance gate is literally the existence of a second real stack, because "generalising
from one instance produces the FastAPI contract with generic field names — which is worse
than no contract, because it looks authoritative and the second stack will quietly bend
itself to fit rather than reveal the mismatch." Promotion is therefore a **mid-release
milestone**, and the schema is reconciled across both stack vocabularies.

#### S3 exit criterion — the proof this step was missing

M0 proves derivation against a known-good reference and S1 proves consolidation by exact
byte-equivalence. S3 originally had neither: "the schema works for two stacks" is a
subjective claim, and *accommodating* two stacks is not the same as *modelling* them. The
proof is the inverse of the failure mode the SIP itself names:

1. **The bend register.** Every point where the TS stack had to adopt a convention it would
   not otherwise use — a directory layout, a naming rule, an entry-module shape — purely to
   satisfy the schema is recorded as a **bend**, with the field that forced it. Exit
   criterion: **zero unexplained bends.** A bend that survives must be argued as a genuine
   cross-stack convention, not as a concession, and that argument is reviewable.
2. **The falsification pass.** For each blueprint field, remove or corrupt it and confirm
   something *breaks* in at least one stack. A field whose removal breaks nothing is
   decorative — it is describing a fact no consumer reads, and it should be deleted before
   the schema is frozen rather than after it has accreted meaning.
3. **No single-stack fields by accident.** A field populated meaningfully by exactly one
   blueprint is either a genuine optional capability (**declared as such, with the reason**)
   or a FastAPI assumption wearing a general name. The schema must say which.

Together these convert "works for two stacks" from a judgment call into a reviewable
artifact — which is the same move #730 made for typed checks, where declaration is required
and drift is guarded.

Riding here (ROADMAP's 1.6 S scope): the **QA-decomposition anchor's structural derivation** —
tasks declare produce-vs-verify and `expected_artifacts` derive from the blueprint's ownership
map, making the shk-1 dual-claim class *inexpressible* rather than merely rejected.

### S4 *(capacity)*. Migrate typed checks off hardcoded `.py`

Onto the blueprint's declared source language. This is where #668's `.jsx` territory and
#598's packaging criterion become expressible; both stay capacity-bound.

**Note the coupling S2 creates.** With a TS stack in the tree, "hardcoded `.py`" stops being
a latent inelegance and becomes a live correctness gap — `fill_slot_signature`, `undefined_names`,
and their siblings would silently skip the entire second stack. S4 is classified capacity
because the *release claim* does not depend on it, but if S3's two-stack schema lands and S4
does not, the plan must record that the second stack ships with a narrower enforced surface
than the first. That is a disclosure obligation, not an acceptable silence.

### S5. Blueprint vocabulary governance — **who may add a field**

The plan repeatedly treats the blueprint as *the closed vocabulary that bounds authoring*.
A closed vocabulary with no admission rule is not closed: the path of least resistance,
every time authoring hits a limit, is to add a blueprint field — and the abstraction decays
into a union of stack-specific features while still looking general.

**Admission rule: a new blueprint field must be demonstrated on at least two stacks before
admission.** This is the SIP's own argument applied to its successors — if generalizing from
one instance produces FastAPI-with-generic-names, then *extending* from one instance does
the same thing one field at a time.

Consequences, stated so they are not surprises:

- A one-stack need is expressed as a **declared optional capability with its reason**, not as
  a general field. The schema says "this stack has X" rather than implying every stack does.
- A `blueprint_limitation` from the M6 taxonomy does **not** automatically authorize a new
  field. It authorizes the *question*, which this rule adjudicates.
- Judgment classes promoted out of `decisions[]` by the M2 ratchet enter through this same
  gate. The ratchet identifies candidates; governance admits them.

The rule can be waived, but only explicitly and with the waiver recorded on the field —
the #682 pattern, where a waiver discloses rather than rewrites.

---

## Generalization debt after 1.6 — **what stays unvalidated, stated plainly**

The S lane's headline is "Generalized Build Capability." Honesty about the release claim
requires saying *how* generalized, because holding HTTP constant (S2) is a deliberate
containment and not a completed generalization.

**Validated by 1.6** (two real instances exercise them): source-language plurality
(`.py`/`.jsx` vs `.ts`/`.tsx`), the test/app import boundary, test-ownership convention,
and the build/test command surface.

**Deliberately unvalidated after 1.6**, each with the stack that would settle it:

| Assumption still resting on one instance | What would test it |
|---|---|
| Fill slots derive from declared entities and routes | a non-HTTP stack (CLI, library, batch) — the deepest assumption, untouched here |
| The routing model is expressible as method + path | any non-REST transport (GraphQL, RPC, event-driven) |
| Endpoint discovery is static and declared up front | a framework with dynamic or convention-based routing |
| Packaging is a container with a long-running server | a single-binary or serverless target — **Go, the named stack-#3 candidate** |
| One deployable unit per application | anything multi-service |

**The standing stack-selection rule**, so future expansion is coverage-driven rather than
language-driven: **each additional stack must invalidate at least one assumption still on
this list, and the list is updated when it does.** A stack that adds a language while
breaking nothing on the list adds maintenance and proves nothing. This is why S2 chose
Node/TypeScript over a FastAPI near-twin, and it is why Go is queued rather than dropped —
its packaging break is a row above.

---

## Owed to 1.8 — the one intention this release owns

**B1. Record the pre-memory rejection-class recurrence baseline.** *(Release-defining, and
the only item here whose omission is permanent.)*

Cross-Cycle Memory's entire value claim is that recurrence of the same mistake falls. That
needs a baseline captured from the authored-mode window, **before memory exists**. Once memory
is live the baseline is unrecoverable and the claim becomes unmeasurable.

Concretely: durable per-cycle counts of rejection classes — plan-validation rejections and the
M6 authoring failure taxonomy — emitted as a first-class output of the authored-mode window,
read by nothing in 1.6. Cheap while building authored mode; impossible afterward.

**Two dimensions, not one.** Memory should reduce both how often a mistake recurs *and* how
expensively it is recovered from, so the baseline records both:

- **recurrence** — occurrences per rejection class, per cycle;
- **time-to-resolution** — attempts and re-rolls consumed before that class cleared.

The second is equally unrecoverable after the fact and equally cheap now, since the
instrumentation is already being added for M5 and M6. A memory implementation that halves
recovery cost without changing recurrence is a real win that a recurrence-only baseline
would score as zero.

Full rationale: `docs/plans/post-1-5-roadmap-reconciliation.md`, "Design intentions carried
forward," intention 5.

---

## Gates

**Gate 1 — design commitments and enabling proofs.** SIP-0103 §6's open questions resolved
(authoring decomposition first among them); **M0's derivation proof is already banked** (measured
2026-08-07, zero diffs) — Gate 1 instead requires M0a's standing equivalence guard merged and
M0b's derive-at-seed landed; S1's consolidation merged; the manifest-v5 migration posture
recorded. **S2 is already settled** — Node/TypeScript,
ruled 2026-08-07 at plan time. *Exit:* no release-defining work starts against an unresolved
design question.

**Gate 2 — the authoring loop closes.** M1–M4 land, with M6's taxonomy in place before any authored manifest is rejected (a rejection recorded without a class is data lost); an authored manifest passes schema and
winnability gates, reaches the HITL gate, and — post-approval — runs the existing pipeline
end to end with no mode branch below framing (Guard 1's architecture test green).

**Gate 3 — integration.** M5 provenance and M6's taxonomy; S3 promotion with the two-stack schema (bend register + falsification pass) and S5's admission rule recorded; B1 emitting both dimensions;
enabling riders (SIP-0093 completion, SIP-0102 steps 3–4) landed. Deploy window with
loaded-module verification, per the 1.5 precedent.

**Cut gate.**
1. **Core-claim gate:** M0–M6 and S1–S3 + S5 complete; B1 emitting both dimensions. Removal of any item requires an
   owner-ratified scope change.
2. **Capacity roll:** unfinished capacity items → 1.7 pool with a milestone update.
3. **Full regression green**, and all three guard halves verified (1a no-branch architecture
   test; 1b reference-manifest equivalence; 2's committed pre-registration record).
4. **The measurement:** authored-mode FAY window — pre-registered N, unfiltered, frozen deploy.
   **Gate: FAY repeatably > 0 in authored-manifest mode**, banked as the authored-mode baseline
   that 1.8's memory and campaign work measure against.
5. **The control is protected** — see below.
6. **Confirmation shakedown** on the fully integrated line, green, per the 1.4/1.5 cadence.

### Protecting seeded mode — the control cannot be left uncontrolled

Seeded mode is the permanent control configuration and the replay referent for every future
release. Unit regression does not cover it: a change can keep every test green and still
degrade live seeded yield, and if that happens undetected, 1.8 measures its memory work
against a baseline that quietly moved.

A second full FAY window in seeded mode would answer this and roughly doubles the release's
measurement cost. Three cheaper mechanisms cover the same class, and they are required:

1. **Guard 1b** — the reference manifest through authored mode must produce byte-identical
   downstream artifacts. This catches transformation regressions structurally, before any
   window runs.
2. **The confirmation shakedown runs in seeded mode explicitly**, not in whichever mode is
   convenient. The cut already requires a shakedown; this fixes its configuration so it
   functions as a control observation.
3. **Replay zero-diff over the 1.5 green corpus** — the #734 method, already proven at the
   1.5 cut: stored evaluation rows re-evaluate identically under the new code.

If all three pass and seeded yield has still degraded, the cause is model or environment
drift rather than this release's changes — and a fresh seeded window would not have
attributed it either. That is the honest limit of what the cheap mechanisms buy, stated
rather than glossed.

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
| ~~Derivation can't reproduce v9~~ **RETIRED 2026-08-07** | Premise was false — v9 *is* the deriver's output for v4, exact equality | Replaced by: *the deriver silently drifts from the pinned reference* → M0a's standing equivalence guard |
| **Authored chaos swamps the window** | An authored manifest can fail in ways a seeded one never could | Blueprint grammar + deterministic gates bound the space; free re-roll and hash-freeze at approval bound the blast radius (§5a) |
| **Stack #2 too close to FastAPI** | A near-twin would validate nothing | Settled at plan time: Node/TypeScript breaks three of the four named assumptions while holding HTTP constant (S2) |
| **The TS stack's break is shallower than hoped** | Holding HTTP constant is a deliberate containment, so the slots-derive-from-routes assumption goes untested this release | Recorded, not hidden: that assumption is stack #3's job (a non-HTTP stack), and Go is named as the packaging-break candidate |
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
