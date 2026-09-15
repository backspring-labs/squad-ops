---
sip_uid: '17883224960412001'
status: accepted
title: Scoped Code Revision
author: SquadOps Architecture
created_at: '2026-09-06T00:00:00Z'
sip_number: 107
updated_at: '2026-09-13T09:54:01.036245Z'
---
# SIP-0107: Scoped Code Revision

## Status

**Accepted** 2026-09-13, at design review with required revision. **Revision 4.**

| Rev | Date | What changed |
|---|---|---|
| 1 | 2026-09-06 | Filed as *Slot-Scoped Emission* (PR #1325): emit the slot body, not the file. |
| 2 | 2026-09-07 | Renamed. The slot is demoted from the unit of emission to one form of grant-addressable region; the agent describes a revision and the framework realizes it. The evidence is re-read against main after PR #1332 and PR #1354 closed #1323 over the weekend; #1213 is subsumed; the framework's own vocabulary (`WriteGrant`, `compute_revision_id`, the QA slot-body path) replaces coined terms; the review points from the 2026-09-07 read are incorporated throughout. |
| 3 | 2026-09-13 | Re-read against main `3d18130b` (v1.7.5) before the design review that opens the 1.8 line. **No design change.** The seams a revision lands through have names since 1.7.5's extraction (`PatchAcceptance`, `CorrectionRepair`) and the draft names them (§1.5, §3.4, §3.8, §5.5, §20, §30.2, §38); two 1.7.4 mechanisms the draft predates are placed against it — the retry-with-fact (#1372; §21, §22) and framework rows re-derived from the patched set (#1374; §20, §29) — with the untouched-file rule (#1406; §29) and the one LLM seam (#929; §36); the evidence gains 1.7.5 React roll 3 (#1501; §1.2, §30.2); #1444 is named as the extraction that precedes the first feature PR (§3.2, §38); the placement records the owner's 2026-09-12 ruling (Targets, §44); §39.8's readout takes the three-state vocabulary (#1445) and the per-attempt stamp (#1436) and says where N comes from; §43 gains #414 and the stack order as review questions. Every code fact cited was verified by grep on that commit; line numbers are as of it. |
| 4 | 2026-09-13 | **Design review: accepted with required revision.** The owner, the named reviewer (1.8 plan §3.1), accepted this draft on written final review notes; the required revisions are folded here before the number is assigned. **The architecture is unchanged.** One rollout sequence, candidate identity first (§38). N counts successful scoped transactions only, is fixed before any transaction that can count is observed, and sits beside a separate all-attempt integrity reading (§39.8). Coverage is qa and dev on both stacks, builder cells declared (§39.8). Preservation is proved by reconstruction from the base, not by a positional diff (§5.2, §17, §39.2). A formatter effect is a recorded revision or the formatter does not run (§19). Automatic regrant widens only inside a plan-bound ceiling (§15). Whole-file fallback needs explicit authority beyond a whole-file grant (§9.4, §21, §39.5). §22 says what a correction attempt is. Evidence says `verified_revision_id == persisted_revision_id` throughout. The six rulings are recorded in §43. |

**Targets: v1.8 — the Lane M headline** (ruled by the owner 2026-09-12; recorded in
`docs/plans/1-8-0-plan.md` §2.1, §3.1 and §3.3 and in the ROADMAP's 1.8 row, on PR #1508).
**Design review held 2026-09-13** — that line's opening step. The owner, as the named
reviewer, accepted this draft **with required revision** on written final review notes; the
revisions are rev 4, and the rulings on §43.1–§43.6 are recorded in §43, including #414's
shape (§43.5) and the stack order (§43.6). Acceptance precedes the feature branch
(contributor workflow steps 3–4): it landed when PR #1325 merged, 2026-09-13; #1444 is the first
extraction, before the feature's first PR (§3.2, §38). The 1.7.3 plan's earlier placement
beside #1213 and #1176 is superseded: #1213 closes with §38 step 4, and #1176 is an
experiment in that line's idle box, not this SIP's.

## Summary

An agent asked to change one small part of an existing artifact should not be responsible
for reproducing the rest of that artifact.

Revision 1 proposed reducing the unit of emission from a whole file to a whole scaffold
slot. That does not go far enough. The slot is valuable as an **authorization boundary**, but
it is often still larger than the semantic change the agent intends to make, and the files
where repairs die most often have no slots at all (§1.2).

This SIP separates four concepts the current pipeline conflates:

1. **authorization** — where the task is permitted to mutate (a `WriteGrant`);
2. **intent** — what semantic change the agent wants to make;
3. **resolution** — which exact source range realizes that intent;
4. **composition** — how the framework produces the candidate repository state.

For existing artifacts the contract becomes a **version-bound revision transaction**. The
agent names a small revision target and an operation — replace, insert or remove. The
framework resolves the target deterministically to an exact source range, proves the range
lies inside the producer's write grant, splices only that revision into the raw source,
validates the result, assigns the candidate tree an identity, verifies that identity, and
persists the same identity.

The framework, not the agent, owns every byte outside the accepted revision.

The thesis:

> **For an existing artifact, the agent describes the smallest reliable code revision rather
> than regenerating surrounding source. That revision executes under an explicit producer
> `WriteGrant`, resolves to deterministic source ranges, preserves all unmodified source
> byte-for-byte, and produces an identified candidate repository state that is the exact
> state verified and persisted.**

The governing rule:

> **A write grant bounds where change may occur. The agent describes only the intended
> revision. Deterministic infrastructure resolves and realizes that revision while preserving
> everything outside the granted and accepted range.**

Slots remain first-class. Their role changes:

> **A slot is one form of grant-addressable region — a maximum revision authority, not the
> unit an agent must emit.**

This SIP **subsumes #1213** and generalizes anchored editing from a text-replacement
mechanism into a revision contract supporting structural targets, exact anchored targets,
bounded slot replacement, authorization, transactionality and candidate-tree evidence.

---

# 1. The problem

## 1.1 The contract requires whole-file re-emission

A repair task today returns whole files. The repair request template says so in as many
words: *"A file you are not fixing must be re-emitted byte-identical to what is already in
the workspace."* The fenced grammar carries `` ```language:<path> `` blocks and the parser
(`fenced_parser.extract_fenced_files`) yields `{name, content}` artifacts. Everything the
agent is *not* changing has to survive a round trip through a language model.

The fill-only constraint exists, and it is soft on both sides: a prompt section
(`repair_handlers._render_fill_only_section`, dev role, scaffoldable stacks only) that asks,
and a post-hoc integrity pass (`fill_slot_integrity`) that restores a narrow subset of what
was dropped and records the rest.

## 1.2 What it costs: the 1.6.5 rolls (#1213) and 1.7.5 React roll 3 (#1501)

Two of six rolls in the 1.6.5 FastAPI+React set ended as `plan_defect` on whole-file rewrites
of `backend/routes.py` — a file with no scaffold slots (`docs/plans/1-6-6-plan.md`):

- **Roll 5 — collateral destruction.** The rewrite dropped the router and every decorator.
  The structural gate (`unresolved_imports`) refused it. The round was spent.
- **Roll 6 — collateral change.** The rewrite carried the **correct** fix inside a rewrite that
  switched to a prefixed router, and the literal `endpoint_defined` check refused it.

The correction loop is where this is most expensive, because a round is scarce:
`max_correction_attempts: 3` on `validated-fullstack`. The React arm spent `3/1/2/1/2/2`
rounds across its six rolls against Next.js's `0/0/0/0/0/0`. Shapes already filed and closed
downstream of the same cause: #870 (a non-compiling repair passes patch verification and
poisons the re-dispatch), #667 (repairs strip testid anchors the first fill placed), #1014
(a dev repair stored a rewrite of a qa-owned file).

**The current reading — 1.7.5 React roll 3 (`cyc_89153929749f`, #1501).** Three correction
rounds, six patches, 103 minutes, ending `Max correction attempts (3) exhausted` with no named
reason. The failing set went 6, 4, 5, 6 across four qa attempts while three titles failed in
every one of them; the loop's exact-repeat rule never saw the stable core. The oscillation is
the dev repair's blast radius: it re-emitted the same three view files every round
(`CreateRunView.jsx`, `RunDetailView.jsx`, `RunsListView.jsx`), and a wide edit fixed some
assertions while breaking others (`docs/plans/1-7-5-verification-set-record.md` §F-1). #1501
fixes the termination rule — the intersection read beside the exact match, so the round ends
naming three assertions. This SIP addresses the width of the edit: a revision scoped to the
handler one assertion exercises cannot change the other two views. Whether the failing set
still oscillates under it is what §39.8's readout measures.

## 1.3 What it costs on a slotted file: 1.7.2 counted roll 1

1.7.2 counted roll 1 (`cyc_eafdc918e8b0`, deploy `d95af712`) dispatched one repair for one
defect, an import-ordering mistake in `docker/serve.py`. The repair also re-emitted
`backend/routes.py`, which the fix did not touch. `fill_slot_integrity` recorded eleven
divergences on it:

```
SIP-0100 fill_slot_integrity: task=repair-run_877ecfc0-00-builder.assemble_repair
  path=backend/routes.py
  restored POST /runs: status_code=201 declared by the scaffold, emitted as absent
  restored POST /runs/{run_id}/join: status_code=200 declared by the scaffold, emitted as absent
  restored POST /runs/{run_id}/leave: status_code=200 declared by the scaffold, emitted as absent
  observed GET /runs: response_model=list[RunSummary] declared by the scaffold, emitted as absent
  observed GET /runs: scaffold-owned handler name 'get_runs' emitted as 'list_runs'
  observed GET /runs/{run_id}: response_model=Run declared by the scaffold, emitted as absent
  observed GET /runs/{run_id}: scaffold-owned handler name 'get_runs_run_id' emitted as 'get_run'
  observed POST /runs: response_model=Run declared by the scaffold, emitted as absent
  observed POST /runs: scaffold-owned handler name 'post_runs' emitted as 'create_run'
  observed POST /runs/{run_id}/join: response_model=Run … emitted as absent
  observed POST /runs/{run_id}/leave: response_model=Run … emitted as absent
```

The record, read exactly:

| Scaffold-owned detail | Count | Disposition |
|---|---|---|
| declared `status_code` kwargs | 3 | **restored** into the emitted bytes |
| declared `response_model`s | 5 | **observed** only |
| scaffold-owned handler names | 3 | **observed** only |

Only the three status codes were restored. `fill_slot_integrity` restores `status_code` kwargs
and the `router = APIRouter(...)` assignment; it records paths, methods, response models and
function names as evidence and leaves the emitted bytes alone. The other eight discrepancies
were caught downstream by the `fill_slot_signature` typed check, or not at all. Nothing in the
repair's intent required touching any of the eleven. They diverged because unchanged content
made a round trip through the model.

## 1.4 The unrequested file, and what main already learned from it (#1323, closed)

The same roll's builder authored `docker/serve.py` unbidden. The approved plan named two
deliverables, `Dockerfile` and `qa_handoff.md`; the builder's task entry read *"Produce
Dockerfile and qa_handoff.md build artifacts."* (`qa_handoff.md` was itself retired
by PR #1430 in 1.7.4 — required, checked by four surfaces and read by nothing; the retirement
changes nothing in this roll's record.) The invented file acquired criteria
(`undefined_names`, `unterminated_source`) and was the task's only failure — both checks on
the planned artifacts passed. The failed attempt was banked at 06:30:28 through a storage
route that performed no authorization, so the file entered the repair overlay. The repair
fixed it; at 06:32:49.626 patch verification passed on a tree containing the fix; at
06:32:49.629 storage dropped the same file as an `unauthorized_slot_emission`
(`expected_sha256: None` — the path was not a slot). No corrective path followed. The passing
row superseded the failing one, and the defect stayed in the delivered file.

Main closed this while revision 1 was in review:

- **PR #1332** (merged 2026-09-06, closes #1323) — a producer's write grants are enforced
  wherever the executor admits its bytes into a tree the loop evaluates. `_admit_failed_emission`
  authorizes a failed result before it is held, so the overlay base and the triage bank see the
  same set; `_try_accept_patch` authorizes the repair before it is verified, so the verified set
  is the set storage will keep; `ScaffoldIntegrityEvidence.stage` names which seam dropped.
- **PR #1354** (merged 2026-09-07, closes #1350) — the grants follow the producer that emitted
  the bytes. Every repair artifact names its repair step (`producer_task_id`,
  `producer_task_type`); an unnamed repair artifact is refused before any grant is derived.

Under main as it stands, roll 1's file is refused at the failed-emission seam and never enters
the overlay; no repair is framed against it; the builder task is judged on the two artifacts
the plan named. **Authorization precedes verification. SquadOps has taken that lesson.** This
SIP does not re-present it as its own contribution.

## 1.5 What remains

Three defects, with their current state:

| Defect | State on main |
|---|---|
| **Over-emission.** A small change makes the model reproduce unrelated source. | **Open.** #1213 names it; §1.2 and §1.3 measure it. |
| **Authorization after generation.** The model constructs a change outside its authority and the framework refuses it afterwards. | **Closed at the executor's seams** by #1332/#1354. Still open at the agent seam: the model is handed a whole file, authors freely, and learns it cannot admit the fix one round later. |
| **Verification/persistence binding.** Verification evaluates one candidate; persistence stores another. | **Held by call order** in `PatchAcceptance.accept` (`adapters/cycles/patch_acceptance.py`; `_try_accept_patch` is its delegator since 1.7.5's extraction, #1152 — §3.8). The verdict names the *base* tree it verified against (`workspace_revision_id`, register entry 26); nothing in the evidence identifies the candidate tree, so the property is a discipline at one seam rather than a fact the record can check (§20). |

The import-ordering repair did not semantically require emitting a file. It did not require
emitting a slot. It required an import-ordering revision.

---

# 2. Revised diagnosis

Revision 1 said: *the unit of change is a slot; the unit of emission is a file.* Useful, and
incomplete. A slot is the **unit of permission**, not the unit of change:

| Concern | Unit |
|---|---|
| Write authorization | the producer's `WriteGrant` — a slot, a region, a file |
| Intended change | the body of `post_runs`, one import |
| Exact source revision | one resolved source range |
| Persisted artifact | `backend/routes.py` |
| Verified product | one identified candidate tree |

Treating any one of these as interchangeable with the others forces the language model to
reproduce information the framework already possesses. The structural problem:

> **SquadOps asks an LLM to regenerate artifact state outside the semantic change it is
> making.**

Post-hoc restoration makes that safer. It does not remove the unnecessary generation step.

---

# 3. Evidence in the repository

The mechanisms this SIP composes mostly exist, in pieces, on separate lanes. Naming them
narrows the implementation and shows the architecture fits existing seams.

## 3.1 Anchored replacement: #1213 and #451

#1213 (open; it closes with §38 step 4, the 1.8 plan §3.3) proposes exactly §9.2: the repair
states the exact text it replaces and the replacement; the framework asserts the anchor
occurs exactly once; everything else is byte-identical by construction. It rejects line
numbers (arithmetic the model is bad at; an off-by-one corrupts the neighbouring line and
looks like success) and notes that scaffold slots cannot touch a file the framework did not
generate.

#451 is the uniqueness lesson learned once already: an unanchored
`raw.replace(stored, computed)` over a whole manifest replaced every `0` character, because
the stored value was `'0'`. The fix anchored the replacement and replaced one occurrence.
The same rule, at a much larger blast radius, is §9.2's uniqueness requirement.

## 3.2 A bounded slot-body path already ships for QA suites

`verification_scaffold_fill.py` (SIP-0104) is §9.3 built for one lane: a fill fence
(`` ```fill:slot-<id> ``), `parse_fill_emission`, a deterministic `merge_fills` into the
frozen shells, and containment rules (no markers, no imports, no fetch, `MAX_FILL_LINES`).
Its consumers are the `qa_test` handler and `QATestRepairHandler`, which parses fill blocks
into `{name: slot_id, content: body, type: "fill"}` and merges them after emission. Nothing
equivalent exists for dev or builder files. The rollout (§38) begins from this primitive
rather than inventing it.

Its qa consumer is one function. The qa handler's `handle()` is 617 lines on main
(`handlers/cycle/qa_test.py:1217`, in a 1,875-line file) and carries the fill shape and the
whole-file authoring shape under one body, with the self-eval follow-up loop copied into the
dev handler's 332-line `handle()` (`develop.py:408`). A revision transaction is a third output
shape for exactly these handlers. **#1444 splits them by output shape first** — one `handle()`
per shape behind the `_output_shape(inputs)` hook #1285 built, the self-eval loop extracted
once, byte-identical on the stored fixtures, a wiring test at the executor's dispatch — so §38
step 2 lifts the fill path out of a handler that already has one function per shape. That is
the extraction this SIP requires and does not contain.

## 3.3 Write grants exist, and only two producers carry them

`write_authorization.py` defines `WorkspaceOwnership`, `WriteGrant` and `WriteAuthorization`.
Enforcement (`scaffold_enforcement._producer_grants`) builds `WriteGrant.for_qa` for QA
producers and `WriteGrant.for_builder` for builder producers (`scaffold_enforcement.py:139`
and `:144` on main `3d18130b`). **`WriteGrant.for_dev_fill` is
defined and used only by its own unit test.** A dev repair emission therefore has no enforced
revision envelope today; only frozen-path and shell rules bind it. The 1.6.5 rolls in §1.2
were dev repairs. This is the largest remaining exposure, and it is not the builder path
#1323 described.

## 3.4 Authority is derived, not carried

The repair's de facto write set is `expected_artifacts` on the repair envelope, produced by
`CorrectionRepair` (`adapters/cycles/correction_repair.py` — `_resolve_repair_target`, the
own-artifact locus, `_apply_ownership_veto`; extracted from the correction runner in 1.7.5,
#1152) and applied after emission as a veto (`_apply_emission_ownership_veto`, on the same
collaborator). It is prompt guidance plus a post-hoc filter. Enforcement
then reconstructs authority from the task type. No envelope carries a grant, and nothing
negotiates one.

## 3.5 The atomic authorize-before-write shape exists, with no caller

`patch_verification.materialize(artifacts, root, authorization=...)` authorizes the complete
emitted set before any write and, on refusal, writes nothing ("authorize→materialize, never
materialize→restore"). No caller passes `authorization`; every call site uses the
write-everything default. §14's atomicity is this function, wired.

## 3.6 The revision identity exists, and names the wrong tree

`compute_revision_id` (`sandbox/models.py`) hashes sorted paths and per-file content hashes:
a deterministic, order-independent repository-state identity. Patch verification computes it
on `workspace_files` — the base — immediately *before* `materialize_artifacts` applies the
patch, and records it as `PatchVerification.workspace_revision_id`
(`src/squadops/cycles/patch_verification.py:750`, then `:754`/`:758`, on main `3d18130b`; the
acceptance verdict carries that base identity, register entry 26). **The candidate the patch
produces has no identity.** Per-artifact `expected_sha256` / `attempted_sha256` and
`manifest_hash` ride every `ScaffoldIntegrityEvidence` record; no candidate-tree identity
does. §20 names the one-call gap.

## 3.7 A dead field

`ScaffoldIntegrityEvidence.correction_requested` is never set true anywhere in `src/` or
`adapters/`. Historical logs carry `correction_requested: False` faithfully; this SIP does not
reason from it as a retry mechanism. Removing it is implementation cleanup.

## 3.8 What 1.7.4 and 1.7.5 put under this draft (rev 3)

Rev 2 read main at `dcf69d3e`. Main has moved since in ways that change where this SIP lands
and what it must say about budgets and rows, none of which changes the design. Verified on
main `3d18130b`, 2026-09-13; the line numbers are as of that commit.

**The landing seams have names.** `_try_accept_patch` is a delegator
(`adapters/cycles/dispatched_flow_executor.py:3529`) into `PatchAcceptance.accept`
(`adapters/cycles/patch_acceptance.py:185`, 939 lines), whose steps are the seams this SIP
binds: `_authorize_repair_artifacts` (`:326`) → `_build_patch_subject` (`:395`) →
`_verify_patch` (`:452`) → `_refuse_unpassed_patch` (`:566`) → `_retest_patched_suite` (`:630`)
→ `_settle_patch_evidence` (`:770`) → `_accept_patch` (`:906`). Repair-step selection, the
ownership vetoes and the repair dispatch are `CorrectionRepair`
(`adapters/cycles/correction_repair.py:817`). The candidate identity (§20) is taken after the
subject is built and before it is verified, and compared before the set is stored; the dev
grant (§38 step 3) is carried where `CorrectionRepair` composes the repair envelope. Each of
these seams has an entry in `docs/architecture/defended-bespoke-decisions.md` (entries 16–38);
a PR that moves one cites the entry it moves.

**A contract failure is re-prompted before it is corrected (#1372, 1.7.4).** Every producer,
the builder included, retries a contentless or zero-extraction emission once with its own
shape fact (`_apply_emission_retry_feedback`, `handlers/cycle/base.py:305`; the marker rides
exactly one dispatch, register entry 28) on the emission-retry allowance, which is bounded
separately from the correction pool (entry 31). §21's *correction eligible* rows therefore
have a step in front of them, and §22 says which budget a rejected revision response spends.

**Framework rows are re-derived from the patched set (#1374, 1.7.4).** Every row a task type
owes by contract is composed from the *patched* set when a patch is accepted
(`compose_owed_framework_rows`, `src/squadops/cycles/check_registry.py:226`; entry 25). Those
rows are evidence about the candidate whose identity §20 names; a row derived from any other
tree is the identity mismatch §39.4 refuses.

**The untouched-file rule (#1406, 1.7.5).** An environment skip on a repair's retest no longer
erases a criterion another producer executed and passed on a file the repair did not touch
(`_credit_contract_criteria`, `src/squadops/cycles/verification_integrity.py:581`). On main
"did not touch" is read from file membership. Under a scoped transaction it is exact: the
resolved ranges say which bytes changed (§17), so the rule holds per byte, by construction.

**One LLM seam (#929, 1.7.5).** `_llm_call` (`handlers/cycle/base.py:939`) wraps every
generation and records it. §36's derived measures attach to that generation record, once,
rather than at seventeen call sites; every banked emission also carries its attempt stamp
(#1436), so §39.8 counts transactions, never artifacts.

**No dev-lane fault exists.** The fault registry
(`src/squadops/capabilities/handlers/fault_injection.py:252–:299`) carries three `qa.test`
faults, one `qa.test_repair`, one `builder.assemble` and one `data.analyze_failure`. §39.6's
dev-grant refusal — the largest exposure, §3.3 — has no diagnostic until one is registered;
the 1.8 plan registers it in the prelude (its §4.1). #1506 splits the builder's contentless
diagnostic into two faults, because under #1372's retry the accepted-patch rows were not
reachable by the one it had.

---

# 4. Industry evidence

Six independent 2026 lines of work inform the direction. Each is a reference in §45.

## 4.1 Structured program entities outperform flat-text editing (R1)

CODESTRUCT reframes source as named AST entities and gives agents structure-aware read and
edit operations: targeted insertion, replacement and removal against named program elements
rather than line numbers or exact textual patches. On SWE-bench Verified it reports improved
Pass@1 for most evaluated models with substantial token reductions for several, and
attributes many baseline failures to brittle exact-string editing, scope mistakes, repeated
retries and syntax-invalid transformations. The principle this SIP adopts: **semantic intent
and textual realization are separate operations.** It does not require CODESTRUCT or mandate
an AST as the stored representation.

## 4.2 No single edit format is optimal (R2)

SWE-Edit separates code inspection from modification execution behind an edit subagent. Its
abstract reports that GRPO training with **an adaptive find-replace / whole-file-rewrite
policy improves edit success by 12.5 pp**. The reading this SIP takes from it — that exact
replacement and whole-file rewrite have different failure regimes and a system should choose
between bounded mechanisms deliberately — is this SIP's inference from that result, not the
paper's stated claim. The implication is not that the model should freely rewrite files; it is
that SquadOps should expose more than one bounded targeting mechanism behind one contract.

## 4.3 Parser-located spans avoid reserialization entirely (R3)

*Don't Let the Model Write the YAML* (submitted 2026-08-31) evaluates model-authored full
files and unified diffs for GitOps remediation, finds that tolerant diff application can
silently misapply and full-file rewriting can drop fields or change neighbouring material,
and has the model emit only field-change intent. A parser resolves the exact source span;
deterministic machinery splices the raw text without reserializing the rest. This SIP adopts
that realization model: **use structure to locate; use the original text to preserve.** A
parser is a locator and validator, not permission to regenerate a file from an AST.

## 4.4 Correct models still over-edit (R4)

*When Models Edit Too Much* (submitted 2026-09-03, EMNLP 2026 Main) finds that test-passing
repairs from frontier models still make unnecessary changes; explicit preservation
instructions reduce the behaviour, and additional reasoning and scale do not monotonically
eliminate it. Prompting agents to preserve unrelated source remains useful. It is not an
integrity boundary.

## 4.5 Models have difficulty respecting deletion boundaries (R5)

*To Add Is Machine, To Delete Is Human* finds systematic deletion avoidance. Supplying the
exact lines *"nearly eliminate[s] incomplete deletion yet raise[s] success only to 80.5%
because the model then deletes beyond the spans or adds code instead."* Two decisions follow:
`remove` is a first-class operation the model does not simulate by regenerating surrounding
code, and the framework, not the model, owns the physical deletion boundary.

## 4.6 Exact replacement remains a useful fallback (R6–R9)

A 2026 repository-editing training study converts diffs into the smallest exact SEARCH region
that uniquely identifies each revision and validates by round-trip application, requiring
uniqueness, non-overlap and exact reconstruction. Production interfaces expose targeted
editing rather than full-file regeneration: Anthropic's editor supports exact `str_replace`;
Gemini CLI's `replace` expects one exact occurrence by default; Codex uses a constrained patch
grammar with contextual targeting. Exact matching is retained as a fallback. **Fuzzy write
application is not permitted.**

---

# 5. Architectural invariants

## 5.1 Grant invariant

Every revision resolves completely inside the `WriteGrant` carried by the transaction. The
agent cannot create authority by naming a path.

## 5.2 Preservation invariant

For scoped revisions the candidate is exactly the immutable base with the normalized accepted
range edits applied (§11), and nothing else: every untouched base span appears, in order,
byte-identically in the candidate. Source outside accepted revision ranges is therefore
byte-identical to the transaction's base revision, for replace, insert and remove alike. The
framework never regenerates unrelated source.

## 5.3 Revision invariant

Every transaction is bound to one immutable base repository state. A revision produced against
one state cannot silently apply to another.

## 5.4 Atomicity invariant

A transaction is accepted whole or rejected whole. Partial acceptance is not permitted.

## 5.5 Candidate-identity invariant

**Candidate revision identity is assigned after all authorized revisions are materialized and
before verification. Verification evidence records that identity, and persistence proves the
same identity was stored.**

`accepted revisions → compose candidate → candidate_revision_id → verify(candidate_revision_id) → persist(candidate_revision_id)`

No filtering, restoration, formatting, normalization or file removal may alter the candidate
after its identity is assigned. Main holds `verified set == stored set` by call order in
`PatchAcceptance.accept` (#1332; §3.8); this invariant makes the property explicit and
evidence-bearing.

## 5.6 Fail-closed invariant

Missing, stale, ambiguous, overlapping, syntactically invalid or unauthorized targets produce
explicit, typed failure. The framework never guesses the intended target and never silently
discards part of a proposed transaction.

---

# 6. Write grants

## 6.1 Current state

Write authorization is enforced for QA and builder producer paths, at the executor's seams
(#1332/#1354). A dev fill grant exists but is not propagated into the active dev repair path,
so dev repair emissions have no enforced revision envelope. Authority is reconstructed from
task type inside enforcement; `expected_artifacts` on the repair envelope is guidance and a
post-hoc veto (§3.4).

## 6.2 Proposed: authority becomes explicit transaction input

A revision transaction carries or references the `WriteGrant` under which it operates.
Resolution checks that grant directly rather than reconstructing permission downstream from
producer or task conventions. Every producer lane — dev included — carries an enforced grant.
The provenance chain becomes visible in evidence:

`producer → WriteGrant → revision transaction → resolved ranges → candidate revision`

This is what makes the SIP an authority-model change rather than a new edit format.

Read visibility and write authority are separate. An agent may inspect material outside its
grant to diagnose a defect without acquiring permission to revise it.

## 6.3 Grant-addressable regions

A grant permits revision inside one or more **authorized regions**:

- **Scaffold slot.** Existing fill slots (SIP-0100, SIP-0104) remain the narrowest and
  strongest envelope where available.
- **Framework-declared structural region.** A blueprint or language adapter may expose an
  import section, a route collection, a configuration entry, a class body — any
  deterministically addressable region.
- **Whole-file grant.** An existing unscaffolded file may be granted where no narrower
  boundary exists. **Whole-file authority does not imply whole-file emission**; structural and
  exact-range revision remain preferred inside it.
- **New-file grant.** Creating a new artifact necessarily permits its initial complete
  contents. New-file creation is not changed by this SIP.

---

# 7. Grant-addressable targets

For an existing artifact, the agent interface should not require the model to construct
file paths, line numbers, byte offsets or AST coordinates. Repository inspection returns
**addressable references** for material the framework already understands: a region
reference for the `runs_routes` slot; an entity reference for `RunsRouter.post_runs`; an entity
reference for one import declaration; a region reference for the module's import section.

References are bound to a repository revision, associated with a known source location,
nested within one or more authorized regions, and usable as revision targets only while valid
for the transaction's base revision. The serialized reference format is implementation-owned
(§43.1). Human-readable names may accompany references for model usability and evidence; the
reference is authoritative.

The interaction becomes *replace `RunsRouter.post_runs`* rather than *edit characters 1842
through 2117* or *regenerate `backend/routes.py`*.

---

# 8. Revision vocabulary

The initial vocabulary is deliberately small.

## 8.1 Replace

Replace the resolved target with supplied source: one expression, a function or handler body,
a declaration, a bounded import region, or — as the fallback of §9.3 — an entire authorized
slot.

## 8.2 Insert

Insert supplied source relative to a resolved anchor, with explicit placement (before or
after): an import, a method, a route, a configuration entry.

## 8.3 Remove

Remove the resolved target: a branch, an import, a method, a declaration. Removal is
first-class. An agent is not required to re-emit the containing function or slot to delete
something (§4.5).

## 8.4 Why `move` is not initially primitive

Tree-diff literature models movement as a primitive, and import ordering — the motivating
repair — is intuitively a move. Movement has language-specific ownership questions around
comments, decorators, separators and other attached syntax. The first release does not require
a generic `move`.

The first release represents the import-order repair as **`remove` + `insert` in one atomic
transaction**: the existing import resolves as a `remove` target and the insertion anchor
resolves independently, both against the same base revision. That is valid under §13 because
neither edit relies on the other's output for target resolution. Physical application is
deterministic and order-safe (§16). A future revision may add `move` once trivia ownership and
provenance are defined (§43.4).

---

# 9. Target-resolution hierarchy

One response contract supports four targeting modes, in preference order.

## 9.1 Addressable structural target

Preferred. The agent selects an entity or framework-defined region exposed by inspection; the
resolver determines the exact source range. No line number or source reproduction is needed
to identify the target.

## 9.2 Exact anchored target

Fallback for material without an addressable entity, or where a small literal replacement is
simpler. The agent supplies existing source text and the replacement. The framework searches
**only within the authorized region**. Application succeeds only if the anchor has exactly one
permitted match: zero matches fail, multiple matches fail. Whitespace-normalized, fuzzy,
approximate or tolerant write matching is prohibited (#451). The correction path may return
refreshed context so the agent can identify a unique anchor.

This is #1213's mechanism, with a platform issue and evidence trail already behind it.

## 9.3 Authorized-region replacement

Fallback when a change is too structurally broad for smaller operations: replace the contents
of an explicitly authorized region, for example an entire fill slot. This preserves revision
1's idea and the shipped QA slot-body path (§3.2), demoted from the default representation to
a bounded fallback.

## 9.4 Existing whole-file replacement

Last resort, not the normal repair contract. **A whole-file grant alone is not sufficient**
(the design review's ruling on §43.3). From §38 step 7 (§46a), whole-file replacement of an
existing artifact is admitted only when all of these hold:

- the task carries explicit **whole-file-fallback authority**, or the framework produces a
  typed policy decision admitting it;
- the task holds a whole-file grant on the artifact;
- the fallback records a typed reason for each narrower mode it passed over — structural
  target unavailable or inadequate; exact anchored target unavailable or inadequate;
  authorized-region replacement inadequate — before the fallback is admitted;
- no scaffold-owned or framework-owned material is exposed to replacement. For those files
  the fallback is not admitted at all, unless the task exists to replace the scaffold itself;
- the result is validated under the same revision and candidate-identity rules as any
  transaction.

The model does not select whole-file mode because a narrower revision was inconvenient, and
whole-file replacement is never silently selected because a more precise revision failed to
resolve. A whole-file response without the authority is refused with a typed policy outcome
(§21, §39.5).

---

# 10. Structural resolution without source regeneration

Where a parser or language service can identify the target's physical extent:

1. parse the base artifact;
2. resolve the semantic target;
3. obtain the target's exact source range;
4. validate the range against the grant;
5. splice the requested change into the original raw source;
6. reparse or otherwise syntax-check the result.

The framework does not require complete AST serialization because an AST was used for
localization. **Parser for addressing; raw text for preservation.** Comments, formatting,
quoting style, blank lines and every unrelated byte stay out of the generative path.

---

# 11. Canonical internal revision

The agent-facing representation and the framework's internal representation are different by
design. The agent reasons in semantic references and source snippets. After resolution, the
framework normalizes each accepted revision into an internal range edit bound to one source
revision, recording: base repository revision; base artifact identity; the `WriteGrant` and the
authorized region it resolved within; resolved source start and end; pre-revision content
fingerprint; replacement text; originating operation; originating producer and task identity.

The model does not generate these coordinates. The framework does.

---

# 12. Version binding and stale revisions

Every transaction identifies the repository state it was produced against. If the relevant
artifact has changed since, the transaction fails as stale before application. The framework
does not shift the revision to a nearby region, fuzzy-apply it, silently rebase it, or use a
three-way merge to guess intent. The task may be reissued with fresh context (§22 says what
that costs).

---

# 13. Multi-revision transactions

One task result may contain several revision operations across one or more authorized
regions. They form one transaction. Before any candidate is produced the framework validates
that every target resolves; every target lies within the grant; every target is based on the
expected revision; exact anchors are unique; resolved ranges do not conflict; and operation
ordering is deterministic.

Independently resolved edits in one transaction are based on the same starting candidate and
must not require one revision to create the target of another. If a repair needs such
sequential editing, the agent may use a larger bounded replacement, execute another revision
turn against the newly produced candidate (§22), or wait for a future feature designed for
dependent edits. The restriction makes transactions replayable and removes hidden order
sensitivity.

---

# 14. Atomic acceptance

Partial acceptance is prohibited. If a task proposes three revisions and one targets an
unauthorized region, resolves ambiguously, is stale, overlaps another, or creates invalid
syntax, none of the three is accepted. A collection of individually reasonable revisions may
collectively be one semantic repair; removing one changes the repair the agent proposed. Silent
sibling retention would recreate the #1323 class at smaller granularity.

The materialization layer already has the required shape: `materialize(...,
authorization=...)` authorizes the complete emitted set before any write (§3.5). The missing
integration is propagation of the producer's `WriteGrant` into that call and normalization of
all accepted edits into the same transaction.

---

# 15. Scope escalation, with a bounded default policy

A repair agent may discover that the defect lies outside its grant. That is not necessarily
agent error; it may mean the task was framed against the wrong artifact. The correct response
is neither to revise the unauthorized artifact nor to drop the revision. The task returns a
structured **scope request** naming the additional artifact or region, why it is necessary, and
the intended class of revision.

**A producer may request additional authority but may not expand its own write grant.** In
unattended execution the default policy is:

| Case | Disposition |
|---|---|
| **Same-role under-scoping** — the requested region already belongs to the requesting producer's role lane and the plan establishes that ownership | may be automatically regranted **within the plan-bound ceiling** and redispatched |
| **Cross-role ownership** — the requested region belongs to another producer | reframe: route the repair to the owning role, as the correction protocol's ownership routing already does |
| **Unplanned artifact** — nothing in the plan establishes the artifact | reject as a plan/framing defect; reframing is the orchestrator's or operator's, not the loop's |

**The ceiling.** The plan establishes a maximum grant for each producer before generation,
and a task receives a narrower active grant inside it. The ceiling exists on main: the
permanent bind-time `WorkspaceOwnership` and the stage grant derived from it for each producer
(`WriteGrant.for_dev_fill`, `for_qa`, `for_builder`,
`src/squadops/cycles/write_authorization.py:89`, `:94`, `:99`). The active grant is the
transaction's authorized regions (§6.2). An automatic same-role regrant widens the active grant
only inside that pre-existing ceiling; it never derives authority from the scope request
itself, so naming a path cannot widen a grant beyond what the plan bound. A request beyond the
ceiling is the cross-role or the unplanned case. Every regrant records the original active
grant, the requested region, the plan-bound ceiling, the resulting grant and the regrant
reason.

No open-ended loop. A grant expansion is budgeted (§22). Until it is resolved the defect
remains unresolved and visible: an authorization miss cannot make the failing check disappear
because an unauthorized candidate previously passed it.

Applied to 1.7.2 roll 1: `docker/serve.py` was an unplanned artifact. The correct disposition
was never *scope expansion required*; it was refusal at creation, which #1332 now performs
(§32). A scope request is legitimate in the cross-role case of §34.

---

# 16. Composition

Accepted resolved revisions are applied to an ephemeral candidate repository state. For
multiple edits in one file, application order is deterministic and earlier splices cannot
invalidate later coordinates (reverse-range application or equivalent). Composition performs
no unrelated regeneration: there is no reason for `backend/routes.py` to be reconstructed
because an import in another file changed. The stage ends by assigning the candidate its
identity (§20).

---

# 17. Preservation proof

A candidate produced through scoped revision carries evidence that the framework preserved
source outside the accepted ranges: which ranges changed; which accepted revision authorized
each; that no changed source exists outside them.

**The proof is reconstruction, not a positional diff.** Insertions and removals shift every
following offset, so "changed bytes outside accepted ranges" is not measured byte by byte.
Applying exactly the normalized accepted range edits (§11) to the immutable base must
reproduce the candidate byte for byte, with every untouched base span appearing in order
(§5.2). Zero outside-range change is a consequence of that. Every difference between base and
candidate is therefore attributable to a recorded revision, including any framework-owned
formatting revision (§19), and the reconstruction is the fixture harness's deterministic
oracle (§30.2).

For slotted artifacts the stronger property follows: scaffold-owned bytes outside accepted
revisions are unchanged *by construction* rather than restored after generation.

The current integrity path both restores a narrow subset of scaffold-owned properties and
observes a broader set (§1.3). Under this SIP a successful scoped revision drives **both**
classes to zero: no restoration is required, and the observed mismatch set is empty.
`fill_slot_integrity` evolves from repairing scaffold loss to asserting it did not occur. A
preservation failure is a transaction failure, not repaired in place.

---

# 18. Syntax and structural validation

Where the artifact has a parser, composition validates the candidate before broader
verification. A structurally targeted revision that yields invalid syntax fails before
persistence. The sequence: resolve; authorize; compose; parse; verify. A syntactically valid
revision may still be behaviourally wrong; behavioural verification remains necessary.

---

# 19. Formatting

Whole-file formatting after scoped composition would undermine the preservation invariant.
Formatting is not an implicit post-composition side effect. **Any formatter effect in a scoped
transaction is represented as an explicit framework-owned revision in the same transaction,
with its ranges and provenance recorded before the candidate's identity is assigned.
Otherwise the formatter does not run.** There is no bounded-where-possible exception: every
difference between base and candidate is attributable to a recorded revision (§17). No
formatter alters the artifact after the candidate has been identified.

---

# 20. Candidate revision identity: verify exactly what will be stored

After composition and structural validation the framework assigns the candidate an immutable
identity. Verification runs against that candidate. On success, persistence stores that same
candidate. Prohibited:

`verify candidate A → filter / drop / restore → persist candidate B`

Required:

`verified_revision_id == persisted_revision_id`

Any mismatch is a framework integrity failure regardless of whether tests pass. A verification
result is evidence about a repository state, not about a task; the state's identity belongs in
that evidence.

The mechanism exists. `compute_revision_id` is the identity; the gap is *when* it is taken.
Patch verification computes it on the base workspace one call before `materialize_artifacts`
applies the patch (§3.6). Moving that computation after materialization, recording it on
`PatchVerification` as the candidate's identity, and having `PatchAcceptance` recompute and
compare it before `_collect_artifacts_and_checkpoint` stores the set, is the whole of this
section's implementation (§3.8 for the seams). The verdict already names the base tree it
verified against (register entry 26); this section puts the candidate's identity beside it.

---

# 21. Failure semantics

| Condition | Disposition |
|---|---|
| Response does not satisfy the revision contract | reject; correction eligible |
| Target reference does not exist | reject; correction eligible |
| Target reference belongs to a stale base | reject; refresh required |
| Exact anchor has zero matches | reject; correction eligible |
| Exact anchor has multiple matches | reject; correction eligible |
| Resolved target exceeds the grant | reject, or scope request under §15 |
| Whole-file replacement without fallback authority | from §38 step 7: reject; typed policy outcome (§9.4). Before it: accept and record as an unauthorized fallback (§46a) |
| Scope request: same-role under-scoping | regrant within the plan-bound ceiling (§15) and redispatch |
| Scope request beyond the plan-bound ceiling | cross-role or unplanned case, never an automatic regrant |
| Scope request: cross-role ownership | reframe to the owning role |
| Scope request: unplanned artifact | plan/framing defect; run fails naming it |
| Resolved edits overlap | reject transaction |
| Candidate fails syntax validation | reject transaction; correction eligible |
| Preservation proof fails | framework integrity failure |
| Verification fails | repair unsuccessful; candidate not delivered |
| Persisted identity differs from verified identity | framework integrity failure |

There is no `disposition='dropped'` for an individual revision inside an otherwise accepted
transaction.

*Correction eligible* names where a rejection goes, not what happens first. On main since
#1372 (§3.8) a producer's emission that fails its contract is re-prompted once with the typed
reason on the emission-retry allowance before any correction round; a zero-match or
multi-match anchor is that kind of failure. Only a rejection that survives its retry becomes a
correction-round failure. §22 states the budget.

---

# 22. Correction-budget semantics

"Execute another revision turn" is not free. The correction path has three attempts on
`validated-fullstack`. **Every new correction reasoning turn consumes a correction attempt; the
emission-contract retry remains the separately bounded #1372 allowance** (register entry 31).
This SIP does not create a second retry economy, and the design review ruled it so (§43.5).
Default:

- a deterministic resolver failure caused by framework state (stale base, reference drift)
  does **not** consume an attempt until the model is reinvoked;
- a revision response the resolver rejects for the response's own fault — contract shape, a
  zero-match or multi-match anchor, invalid syntax — is re-prompted once with the typed reason
  on the **emission-retry allowance** (#1372's retry-with-fact, bounded separately by register
  entry 31), not the correction pool; if the retry is also rejected, the rejection enters
  correction as a repair failure and the next response consumes an attempt (placed in rev 3
  against the mechanism 1.7.4 shipped; confirmed at design review, §43.5);
- a new agent revision response consumes an attempt;
- an automatic same-role regrant consumes an attempt only when a new model response is
  required;
- a genuinely sequential revision requiring a second reasoning turn consumes a normal
  correction attempt.

The compliance budget (`contract_compliance_attempts`, SIP-0100 3.4a) is unchanged: it counts
unauthorized cross-slot emissions and only those (`_enforce_compliance_budget`, invoked from
`PatchAcceptance._authorize_repair_artifacts`, `patch_acceptance.py:384`); frozen re-emission
is deliberately not counted. A revision that resolves outside its grant is that kind of
emission, and is counted there.

#414 asks whether the single run-level pool should hold a reserve for required checks. The
design review ruled the shape, not the adoption (§43.5): if a reserve is adopted, it is a
reservation inside this one correction pool, never a second pool. Whether to adopt one remains
#414's decision.

---

# 23. What changes for scaffold slots

Before: *slot = region the model fills and later reproduces during repair.* After: *slot =
framework-declared authorized region within which one or more smaller revisions may occur.*

For an initial build where the whole slot genuinely needs implementation, region replacement
remains appropriate. For later repairs the same slot can contain smaller structural or
anchored revisions. A route-handler slot may authorize the whole body; a repair that changes
one conditional revises that conditional, or its enclosing entity if addressable, without
reproducing the body. Precision increases without changing the blueprint's security boundary.

---

# 24. Unslotted existing files

Revision 1 left files without slots on the whole-file path. This revision changes that. An
unscaffolded existing file may receive a whole-file **grant** while still using scoped
revisions within it: framework-owned scaffold files, stack-owned implementation files,
modules created in earlier cycles, tests, configuration. This SIP infers no new security
boundary from arbitrary code; where none narrower exists, the file is the envelope, and the
revision within it can still be surgical. `backend/routes.py` on stack #1 — the file in
§1.2 — is the first beneficiary.

---

# 25. New files

A new file has no prior source to preserve; whole-file generation remains appropriate for
creation. After acceptance, later modifications use the scoped path. **Generation for
creation; revision for evolution.**

---

# 26. Interaction with SIP-0100, SIP-0104 and SIP-0105

- **SIP-0100** (implemented) owns the frozen scaffold record, fill slots and frozen-file
  enforcement. Its fill slots become authorized regions unchanged.
- **SIP-0104** (accepted) owns `slot_id` semantics for the verification scaffold and the
  slot-body path of §3.2. Its slot table (`slot_id` → file, region, bound criterion) is the
  first source of grant-addressable references.
- **SIP-0105** (accepted) owns blueprint-declared structure. A blueprint may additionally
  expose framework-defined structural regions. Stacks need not share slot granularity: a
  Python handler body and a Next.js route module remain different-sized regions, and the
  revision layer operates below that distinction.

---

# 27. Interaction with SIP-LLM-Emission-Contracts

`SIP-LLM-Emission-Contracts` (proposed, rev 2) answers *what forms of LLM response are
syntactically valid?* This SIP answers *what repository revision is the response permitted to
represent, and how does that intent become repository state?* The emission contract should
ultimately type at least: revision transaction; scope request; new-file emission where
permitted; explicit no-change and failure outcomes. Its evidence-first observability
(persisting every raw response) is also the capture source for §30's fixture corpus. This SIP
should precede or be coordinated with finalization of that grammar.

---

# 28. Interaction with deterministic fill-slot work

SIP-0100 and SIP-0104 remain valid; this SIP moves their trust boundary earlier. Instead of
`LLM whole file → detect scaffold loss → restore or observe`, the path becomes
`LLM revision intent → resolve inside the grant → preserve scaffold automatically`.
Restoration and observation logic may remain as migration defence but is not part of the
steady-state success path. A successful scoped revision that requires restoration, or that
produces a non-empty observed set, is a defect in the revision framework.

---

# 29. Interaction with verification contracts

Verification contracts continue to decide whether the candidate satisfies expected behaviour.
This SIP adds repository-state binding: a result identifies the candidate it evaluated, and a
check cannot be satisfied by a revision later removed from that tree. Main prevents the
removal by ordering (#1332); the identity makes the prevention checkable from the record.
Since #1374 the framework rows a task owes are re-derived from the patched set (§3.8), so the
rows and the identity describe one tree; and the untouched-file rule (#1406) keeps a passed
criterion on a file the repair did not touch — a fact a scoped transaction states from its
resolved ranges rather than from file membership.

---

# 30. Validation instruments

## 30.1 Cycle replay (SIP-0101)

The Cycle Replay Harness (accepted) restores a run prefix from a checkpoint boundary under a
compatibility gate (`prd_ref`, `build_profile`, `contract_ref`). It is the instrument for
end-to-end validation from supported checkpoints. It cannot reproduce arbitrary raw emissions,
and this SIP does not ask it to.

## 30.2 Emission and revision fixture replay

The contract under test is much narrower than a cycle. This SIP requires a deterministic
fixture harness of captured historical agent emissions with their workspace and grant state,
replaying at minimum:

- #451 — the unanchored replacement;
- #430, #470, #502 — the "whole files lost" parser classes;
- #1213 / 1.6.5 rolls 5 and 6 — whole-file rewrites, one carrying the correct fix;
- #1501 / 1.7.5 React roll 3 — the same three view files re-emitted on every round;
- #1323 — the unrequested artifact, refused at creation;
- representative `fill_slot_integrity` restoration-heavy and observation-heavy repairs.

The goal is not to show that new parsing handles the old emissions. It is to show that those
emissions are no longer necessary on the normal path, and that each historical failure is
refused with its typed reason.

The harness enters at `PatchAcceptance.accept` with the captured envelope, result and repair
artifacts — the caller the live loop uses (§3.8) — not at a check and not at
`patch_verification` directly. A fixture handed to a seam proves the seam, not the wiring; the
`roll_replays` fixtures on main prove checks, not the accepted-patch path, and this harness is
not them.

---

# 31. Worked example: the 1.6.5 roll 6 handler repair

Under the current system the repair rewrote `backend/routes.py`, switched to a prefixed
router on the way past, and the correct fix was refused by `endpoint_defined`. Under this SIP
the dev repair holds a whole-file grant on `backend/routes.py` (§24); inspection exposes the
handler entity; the agent proposes `replace` on the smallest target that carries the fix; the
framework resolves the range, proves it lies in the grant, splices it, parses, assigns the
candidate identity, verifies and persists. The router declaration is never in the transaction.
It cannot change.

---

# 32. Worked example: 1.7.2 roll 1, the unrequested file

1. The builder attempts to introduce `docker/serve.py`.
2. No write grant exists: the plan never authorized that artifact.
3. Creation is refused before the candidate enters the overlay or verification (#1332's
   `_admit_failed_emission`; under this SIP, the same refusal at the transaction's grant check).
4. No repair against the unauthorized artifact is framed.
5. The task is judged on the artifacts the plan named. In roll 1 both passed, so no correction
   round is spent.

No scope request arises. A scope request here would legitimize an invalid artifact.

---

# 33. Worked example: an import-order repair inside a granted file

Assume the same defect — `import os` mid-file, `os` used above it — in a file the repairing
producer holds a grant for.

1. The repair receives the base revision and its grant.
2. Inspection exposes the import declaration and the module import section as addressable
   targets.
3. The agent proposes `remove` on the mid-file import and `insert` of `import os` after the
   import-section anchor, in one transaction.
4. Both resolve independently against the base; neither creates the other's target (§13).
5. The framework proves both ranges lie in the grant, applies them order-safely, parses the
   result, asserts preservation, assigns the candidate identity, verifies, persists.

Every other file is untouched. `backend/routes.py` never enters the transaction.

---

# 34. Worked example: a legitimate cross-role scope request

A QA repair is authorized on the QA-owned suite. Diagnosis shows the failing probe is right
and the defect is in `post_runs` in `backend/routes.py`, a dev-owned region. The QA producer
does not revise it and does not drop the finding. It returns a scope request naming the
region, the reason and the intended class of revision. Under §15 this is cross-role
ownership: the repair is reframed to the dev producer, whose grant covers the region, and the
failing check stays standing until that repair lands. The correction protocol already routes
repairs to the owning role; the scope request makes the hand-off explicit and evidenced
instead of inferred from a veto.

---

# 35. Worked example: deletion

An obsolete fallback branch must be removed. Where structurally addressable: `remove` on the
branch entity. Where not: `remove` on a unique exact anchor within the grant. The framework
resolves and removes only the target; the model never regenerates the enclosing function.
The deletion boundary is deterministic even where the model would otherwise preserve or
over-edit surrounding code (§4.5).

---

# 36. Observability and provenance

Every transaction produces evidence sufficient to answer: which producer proposed the change;
which task and `WriteGrant` authorized it; which base revision it was based on; which
authorized regions were available; which targets were selected and how they resolved; which
source ranges changed under which operation; how many bytes the agent supplied and how many
changed; whether any changed byte fell outside accepted ranges; which candidate identity was
produced, verified and persisted; how many correction attempts were required.

Derived measures: emitted bytes; changed bytes; authorized-region size; revision-to-region
ratio; target-resolution retries; structural versus anchored versus region-replacement versus
whole-file usage; preservation violations; scope-request frequency by case. The evidence
serves debugging, fixture replay, model comparison and later Continuum explainability, and
draws the provenance line where it belongs: framework-owned source versus agent-authored
revision. The derived measures attach to the generation record `_llm_call` writes for every
producer (#929, §3.8) and to the attempt stamp every banked emission carries (#1436), so each
exists once per generation and never once per call site.

---

# 37. Model portability

The contract encodes no vendor's patch syntax. Anthropic, OpenAI, Google, local Qwen models
and future runtimes differ in their strengths at exact replacement, structured output and
patch generation. SquadOps normalizes those differences behind the revision contract. The
model-facing representation must be simple enough for current local models while allowing
stronger models to use structural addressing. The deterministic guarantees cannot depend on
the model being good at one textual patch dialect.

---

# 38. Rollout

**Precondition, not a step: #1444.** The qa and dev handlers' `handle()` split by output shape
(§3.2), before this SIP's first PR. Extraction only; byte-identical on the stored emissions; a
wiring test at the executor's dispatch.

1. **Candidate identity.** Take `compute_revision_id` after materialization, record it as the
   candidate's identity, and compare it before storage (§20). An integrity improvement to the
   existing accepted-patch path, independent of every later step; each revision transaction
   after it inherits the binding.
2. **Generalize the QA slot-body path.** Lift `verification_scaffold_fill` into the common
   revision-transaction abstraction: one transaction type, grant carried,
   `materialize(..., authorization=)` wired, step 1's identity inherited. The QA lane keeps
   working throughout; the proof runs on the Next.js fill fixtures, where the slot-body path
   ships.
3. **Dev grant.** Propagate `WriteGrant.for_dev_fill` into the dev repair path so every lane
   carries an enforced grant (§3.3).
4. **Exact anchored targets** inside the grant, strict uniqueness (#1213).
5. **Structural read and addressing** for the first stack, React (§43.6), then the
   **structural revision path** (replace, insert, remove) with the preservation proof (§17).
6. **Second stack**, Next.js, demonstrating equivalent semantics across different slot
   granularity.
7. **Default repair path.** Scoped revision becomes the normal path for supported existing
   artifacts; legacy whole-file repair emission becomes the explicitly authorized fallback of
   §9.4. Gated by §39.8's N, and landed as its own release after the one that measures N; before
   it, an unauthorized whole-file response is recorded, not refused (§46a).

**This is the one authoritative sequence: one PR per step, in this order**, each step's proof
the previous step's invariant still holding. **Steps 1–4 establish the stack-independent
transaction machinery; step 5 proves the structural path end to end on the first stack;
together they are the core.** Step 6 adds the structural path on the second stack, and step 7
flips the default. Scoped transactions on the second stack do not wait for step 6: the
anchored and region modes of steps 2–4 reach it, so §39.8's coverage of both stacks is
reachable before the second structural resolver exists.

---

# 39. Acceptance criteria

## 39.1 Historical refusals

Each §30.2 fixture is refused with its typed reason on the normal path, and the roll 1
unrequested artifact is refused at creation with no repair framed.

## 39.2 Zero outside-range revision, proved by reconstruction

For every scoped transaction, the candidate is reconstructible from the immutable base by
applying exactly the normalized accepted range edits, and every untouched base span appears,
in order, byte-identically in the candidate (§5.2, §17). Zero changed bytes outside accepted
ranges follows; it is not measured by a positional diff.

## 39.3 Zero restoration and an empty observed set

A successful scoped revision against a scaffolded artifact requires no restoration and
records no observed divergence. Either is a failure of the new path.

## 39.4 Candidate identity

For every delivered revision, `verified_revision_id == persisted_revision_id`, and both are
in the evidence. No exceptions.

## 39.5 Stale, ambiguous, unauthorized, overlapping, invalid

A stale transaction fails rather than rebasing. A multi-match anchor fails rather than
choosing. An out-of-grant target never enters the candidate and produces an explicit
authorization outcome. A transaction with one invalid revision applies none. Invalid syntax
fails before behavioural verification. From §38 step 7, a whole-file response without fallback
authority is refused with a typed policy outcome (§9.4; before it, recorded, §46a), and no
automatic regrant exceeds the plan-bound ceiling (§15).

## 39.6 Every producer lane carries a grant

A dev repair emission outside its grant is refused with evidence, at the same seams as QA and
builder.

## 39.7 Both current scaffold styles

The mechanism works across narrow handler-body slots and broader route-module slots. Neither
stack's slot size becomes the universal granularity.

## 39.8 Live evidence, counted in transactions

Two readings, never one number.

**Success-path readiness.** Before becoming the default repair path (§38 step 7), observe at
least **N successful scoped revision transactions**. A successful transaction resolved inside
its grant, composed, passed its preservation proof (§17), was verified, and was persisted under
the identity it was verified with (§39.4). **N is fixed in a pre-registration committed before
any transaction that could count toward it is observed** — before the first diagnostic launch,
not only before the first counted roll. A transaction that fails closed, by design under a
diagnostic or otherwise, is audited below and never increases N; neither does a mechanically
valid transaction whose repair failed verification, nor a repair where no revision executed.

**Coverage.** N spans both supported stacks and every producer lane with an existing-artifact
revision surface on that stack. **The qa and dev lanes on both stacks are required cells.**
Each builder cell is declared in the same pre-registration, either with the fault that forces
a builder revision of an existing artifact or as unaskable with its structural reason. The
builder's grant is the fill slots it repackages (`write_authorization.py:99`), and what it may
still revise once its packaging files are a rendering (#598) is read at pre-registration, not
assumed here.

**All-attempt integrity.** Every attempted transaction — successful, refused, failed closed or
behaviourally failed — records zero: outside-grant changes; post-verification drops;
verified/persisted identity mismatches; preservation violations; partial acceptance; automatic
regrant beyond the plan-bound ceiling; whole-file fallback without fallback authority, from §38
step 7 (before it, a reported count per cell, §46a); and, on successful scoped transactions,
restoration or recorded observed divergence.

Rolls are the wrong unit: a roll may carry no repair, and the 1.7.2 pack recorded one drop
across nine counted rolls. For **every attempted repair** the readout reports which of these
occurred: structural target used; exact anchored target used; region replacement used;
whole-file fallback used, with its typed reasons (§9.4); no revision executed; failure reason.
"No revision executed" is evidence about a quiet path, never a transaction. Each field is
read in the driver's three-state vocabulary (#1445): *observed* with its value, *asked_none*
when the producer ran and produced nothing, *unaskable(reason)* when the producer could not
ask on that roll — so a quiet path, an exercised one and a structurally silent one are never
one zero.
Each transaction is counted by the attempt stamp its emission carries (#1436), never by
artifact.

**Where N comes from is tabled in that pre-registration.** 1.7.5's nine counted rolls
attempted five repair rounds in total, on two rolls, both in the qa lane on one stack; seven
rolls took no correction round. A counted set of that shape cannot reach any honest N alone,
so the pre-registration tables, for each required cell, the fault that forces a repair and the
successful transactions it is expected to produce, and the sum against N. A dev-lane fault
must exist first (§3.8). If the deploy moves after the pre-registration is committed, the
commit is void and re-made, and no transaction from the superseded deploy counts.

**What an unmet N means here.** In this SIP, fewer than N successful transactions means §38
step 7 does not happen: the refusal does not land and the pre-flip contract of §46a stays, and
the record states the shortfall
as a budget failure, not a pass. A release plan that adopts the same N as a release gate says
so as its own gate; the 1.8 plan does (its §3.9), and there an unmet N blocks the cut.

Token and emitted-byte reductions against the legacy whole-file baseline are recorded as
supporting evidence, not as correctness gates.

---

# 40. Out of scope

Cross-repository semantic refactoring; symbol-rename propagation across dependency graphs;
transformation-rule synthesis; a universal AST schema; a required parser implementation;
automatic approval of cross-role or unplanned grant expansion; binary-file revision; generated
artifacts whose source of truth lives elsewhere; formatter architecture; three-way merge;
tolerant or fuzzy patch application. Whole-file generation for genuinely new files is not
eliminated.

---

# 41. Risks and tradeoffs

- **Parser coverage.** Not every artifact has a useful parser; anchored targets and region
  replacement remain necessary fallbacks.
- **Structural identity.** Names alone may be ambiguous; display selectors and authoritative
  revision-bound references are distinct for this reason.
- **Larger refactors.** Some changes affect much of an artifact; the hierarchy lets breadth
  expand deliberately rather than forcing dozens of tiny edits.
- **Framework responsibility.** The framework gains target resolution, transactionality,
  preservation evidence and state binding. That replaces a more dangerous complexity spread
  across prompting, parser recovery, restoration, filtering and verification ordering.
- **Resolver defects become critical.** Once deterministic tooling owns realization, its bugs
  matter greatly. Fail-closed resolution, preservation proof, fixture replay and candidate
  identity are architectural requirements, not diagnostics.
- **Budget interaction.** A mis-set §22 policy either starves repairs or reopens unbounded
  retry. The defaults are conservative and are a pre-registration item.

---

# 42. Decisions settled by this revision

- **Slot granularity per stack.** Slots define authorization; revision granularity may be
  smaller; no universal slot size.
- **Multi-region edits.** One atomic transaction may span several authorized regions; partial
  acceptance is prohibited.
- **Migration.** Progressive by resolver and stack, starting from the shipped QA slot-body
  path, converging on one revision contract.
- **Emission contracts.** Complementary: that SIP types the response; this SIP defines revision
  meaning, authorization, realization and state binding.
- **Unauthorized revision.** Not silently dropped; the transaction fails or requests authority
  under a bounded policy.
- **Verification ordering.** Already precedes verification on main by call order; this SIP
  binds it to candidate identity.
- **#1323.** Prior evidence of a lesson taken, not this SIP's motivation.
- **Vocabulary.** `WriteGrant`, authorized region, revision target, candidate revision identity.
- **The design review's rulings (2026-09-13).** Recorded in place under each question of §43,
  and written into the sections they govern: §9.4, §22 and §38.

---

# 43. Design questions — ruled at design review, 2026-09-13

Each question is kept as it was put to the review; the ruling follows it.

## 43.1 Reference representation

How are revision-bound region and entity references serialized so they stay compact,
traceable and model-friendly?

**Ruled.** The serialized representation stays implementation-owned. The SIP requires only an
opaque, revision-bound authoritative identity; a human-readable display selector; and an
evidence round-trip from the reference back to its resolved range. No AST coordinates or
source offsets are standardized here.

## 43.2 Resolver selection

Which parser or language service supplies source ranges for each stack? The SIP specifies
behaviour, not the library.

**Ruled.** No library is chosen in the SIP. The first structural-stack implementation PR (§38
step 5) chooses the resolver under the behavioural contract defined here. The resolver is
replaceable; fail-closed semantics are not. The first stack carries a Python backend and a JSX
frontend, so that PR also names which of the two resolvers comes first; the review did not
order them.

## 43.3 Whole-file fallback policy

Should existing-file whole-file replacement require an explicit task-level capability, or is a
whole-file grant sufficient? The stronger policy is preferable for scaffold-owned files.

**Ruled.** The stronger policy. Explicit whole-file-fallback authority, or a typed policy
decision admitting it, is required in addition to a whole-file grant, with a recorded reason
for each narrower mode passed over. For scaffold-owned and framework-owned files the fallback
is not admitted unless the task exists to replace the scaffold itself. Written into §9.4.

## 43.4 First-class `move`

After experience with replace, insert and remove, should `move` become primitive for imports,
members and other source-preserving relocations? Decide on repair evidence, not vocabulary
completeness.

**Ruled.** No `move` in 1.8. `remove` + `insert` in one atomic transaction is sufficient to
test the abstraction. `move` is added only after real evidence shows that provenance or trivia
ownership makes the pair inadequate.

## 43.5 Budget policy

How do target-resolution failure, stale-context refresh, regrant and genuinely sequential
revisions consume the correction-attempt budget? §22 states the default this SIP proposes —
including rev 3's placement of the emission-retry allowance (#1372) in front of correction —
and design review confirms or amends it. **#414 is raised here:** its priority reserve for
required checks and this SIP's defaults draw on one pool; rule on both, or name why they are
separate.

**Ruled.** One correction pool; no second retry economy for scoped revision. #1372's one-shot
emission-contract retry stays separately bounded. If #414 adopts a priority reserve, it is a
reservation inside the same correction pool, never a second pool. §22 is written to this
ruling; whether to adopt the reserve remains #414's decision.

## 43.6 Stack order for §38 steps 5–6

Which stack takes the structural path first? React is six of nine counted rolls in 1.7.5 and
the demonstration arm; Next.js is where the slot-body path (§3.2) already ships. The review
rules; the plan's sequencing follows the ruling.

**Ruled.** React first for the structural path, Next.js second. React carries the measured
whole-file repair failures that motivate this SIP (§1.2, §1.3) and is six of nine counted
rolls and the demonstration arm; Next.js supplies the QA slot-body primitive that §38 step 2
generalizes. The bootstrap comes from the proven primitive, and the first genuinely new
structural implementation attacks the failure mode that justified the feature. Written into
§38.

---

# 44. Why a feature SIP

This changes the contract between agents and repository state: task framing, write
authorization, agent response contracts, scaffold semantics, composition, integrity
enforcement, repair retries, verification evidence, persistence, replay and observability.
It gates an even minor under the parity convention and is **1.8's Lane M headline** by the
owner's ruling of 2026-09-12 (`docs/plans/1-8-0-plan.md` §2.1 and §3.3; the ROADMAP's 1.8
row), accepted at its design review on 2026-09-13 with the revisions of rev 4. The 1.7.3
plan's earlier placement beside #1213 and #1176 is superseded: #1213 closes with §38 step 4,
and #1176 is an experiment in that line's idle box, not this SIP's.

The progression this SIP completes:

`whole-file generation → post-hoc integrity repair (SIP-0100) → producer write grants (#1332, #1354) → bounded slot replacement (SIP-0104) → grant-scoped structural and anchored revision with deterministic realization → candidate revision identity → verification and persistence bound to that identity`

> **Do not make the model reproduce source the framework can preserve itself.**

---

# 45. References

**Repository**

- #1213 — Correction repairs re-emit whole files to change a few lines; anchored edits (open; subsumed)
- #451 — unanchored `raw.replace` rewrote every `0` in a manifest
- #1323 — a dropped repair emission recorded as a verified patch (closed by PR #1332)
- #1350 — patch-verification grants were the failed task's, not the repairing producer's (closed by PR #1354)
- #430, #470, #502 — fenced-parser classes whose consequence was "whole files lost"
- #870, #667, #1014 — downstream shapes of whole-file repair emission
- #1259, #1264 — repairs judged against trees with inconsistent file membership
- #1372 — a contentless emission is re-prompted with its own shape fact (closed, 1.7.4)
- #1374 — the accepted-patch path derives every framework row from the patched set (closed, 1.7.4)
- #1406 — a repair's verification demoted criteria it could not execute; the untouched-file rule (closed, 1.7.5)
- #929 — the LLM call sequence extracted to one seam (closed, 1.7.5)
- #1436, #1445 — the attempt stamp on every banked emission; the three-state record vocabulary (closed, 1.7.5)
- #1501 — a repair loop burns its budget when the failing set churns around a stable core (open)
- #1444 — the qa and dev handlers' `handle()` split by output shape; the extraction this SIP requires (open)
- #1506 — the contentless-builder diagnostic split so the accepted-patch rows are reachable under #1372 (open)
- #414 — the correction budget's single pool is severity-blind (open; answered at this SIP's review)
- PR #1430 — `qa_handoff.md` retired
- `docs/plans/1-6-6-plan.md` — the 1.6.5 rolls 5 and 6 record
- `docs/plans/1-7-2-verification-set-record.md` §4.3 — roll 1
- `docs/plans/1-8-0-plan.md` — the placement, the review's terms and the rollout's sequencing (§2.1, §3.1, §3.3, §4.1)
- `docs/plans/1-7-3-plan.md` — the earlier 1.8 placement, superseded
- `docs/plans/1-7-5-verification-set-record.md` §F-1 — React roll 3
- `docs/architecture/defended-bespoke-decisions.md` entries 16–38 — the accepted-patch and correction seams, one entry each
- SIP-0100, SIP-0101, SIP-0104, SIP-0105, `SIP-LLM-Emission-Contracts`

**Research**

**[R1]** Kim, M. et al. *CODESTRUCT: Code Agents over Structured Action Spaces.* arXiv:2604.05407, 2026.

**[R2]** Zhang, Y. et al. *SWE-Edit: Rethinking Code Editing for Efficient SWE-Agent.* arXiv:2604.26102, 2026.

**[R3]** Davineni, P. *Don't Let the Model Write the YAML: Deterministic, Minimal-Diff GitOps Remediation from LLM-Proposed Field Changes.* arXiv:2609.00227, 2026.

**[R4]** Zhu, T., Lim, W. H., Kan, M.-Y. *When Models Edit Too Much: On the Fidelity of Minimal Code Edits.* arXiv:2609.04061, EMNLP 2026 Main.

**[R5]** Ebrahimi, A. M. et al. *To Add Is Machine, To Delete Is Human: Measuring and Mitigating Deletion Avoidance in LLM Code Editing.* arXiv:2607.28887, 2026.

**[R6]** Zhu, Q. et al. *Pull Requests as a Training Signal for Repo-Level Code Editing.* arXiv:2602.07457, 2026.

**[R7]** Anthropic. *Text editor tool*, Claude Platform documentation.

**[R8]** Google. *Gemini CLI file-system tools*, Gemini CLI documentation.

**[R9]** OpenAI. *Codex `apply_patch` tool instructions*, Codex repository.

**[R10]** Microsoft. *Language Server Protocol — WorkspaceEdit / TextEdit*, LSP specification.

**[R11]** Tree-sitter. Node and range API documentation.

---

# 46. Post-acceptance amendments

## 46a. 2026-09-13 — the default flip is its own release; before it, an unauthorized whole-file response is recorded, not refused

**What changed.**

1. **§38 step 7 is a separate release from the one that measures N.** Steps 1–6 land and are
   measured; step 7 lands afterwards, on that measurement. For 1.8 the flip is 1.8.1's, by
   design (1.8 plan §3.3).
2. **Before step 7 there is one repair contract and one code path, not a flag or a legacy
   mode.** A repair of a supported existing artifact requests a scoped revision. A whole-file
   response made without the fallback authority of §9.4 is **accepted and recorded as an
   unauthorized whole-file fallback** instead of being refused. It is handled as main handles a
   whole-file repair today, with the producer's write grant still enforced, and it passes through
   candidate identity, verification and persistence like any other response (§20). It is not a
   scoped transaction, so it never counts toward N.
3. **What waits for step 7:** §9.4's authority requirement, the §21 row refusing whole-file
   replacement without fallback authority, and the matching sentence of §39.5. Every other rule
   in this SIP applies from the step that introduces it.
4. **§39.8's all-attempt integrity reading:** before step 7, "whole-file fallback without
   fallback authority" is a **reported count per cell**, not a violation. Every other zero in
   that reading holds from step 1. The unmet-N paragraph of §39.8 reads accordingly: with fewer
   than N successful transactions the refusal does not land, and the pre-flip contract stays.
5. **Step 7's proof:** the pre-flip window's recorded unauthorized whole-file responses replayed
   through the refusal, naming each repair it would have turned away, plus one checkpoint pair on
   the deploy that carries the flip. N met is the precondition, unchanged.

**Evidence.** Rev 4 placed N before step 7 (§39.8) while the 1.8 plan landed all seven steps on
the deploy that measures N. That deploy freezes merges while its set runs, and the cut expects
zero code drift from it, so step 7 could only have landed before N existed or after the cut.
Refusing whole-file responses inside the measured window would change what a verdict means
mid-measurement, which the owner ruled against on 2026-08-15 (detection lands reporting-only;
promotion to a refusal is a separate call), and would put two behaviour changes on one measured
deploy so that a rejected roll could not be attributed to either. Rev 4's own all-attempt reading
also counted every unauthorized whole-file response as a violation, which would have made the
pre-flip window fail by construction. That is a correction to rev 4 itself.

**Ruled by.** The owner, 2026-09-13, on a written recommendation: the flip goes to 1.8.1 by
design, with the refusal held back and everything else in steps 1–6 unchanged.

## 46b. 2026-09-14 — candidate identity as built (§38 step 1): repository state only, and proved at storage as well

**What changed.** §20 described its implementation as "the whole of this section's": take the
identity after materialization, record it on `PatchVerification`, recompute and compare it in
`PatchAcceptance` before storage. Building it showed three places where that description is
narrower or wider than the invariant it serves (§5.5).

1. **The identity is taken over repository state, not every artifact.** `candidate_files`
   (`src/squadops/cycles/patch_verification.py`) is the accepted workspace with the patch's work
   product applied. Evidence artifacts (`EVIDENCE_ARTIFACT_TYPES`: `test_report`,
   `typed_check_evaluation`) are left out. They describe one execution, and the accepted-patch path
   supersedes them after verification by design (#1111, #1318; register entry 24). An identity
   that counted them would change between the verdict and storage on every retested patch, so it
   would report a mismatch where nothing about the delivered tree differs. Only paths `materialize`
   would write are counted.
2. **A verdict that returns before materializing still names its candidate.** A structurally
   unevaluable verdict (`no_typed_criteria`) hands the decision to the behavioural retest
   (register entry 22). That path is accepted, so its candidate has an identity even though the
   verifier wrote no tree. On the evaluated path, the materializer's own record of what it wrote
   proves the tree holds every counted file. A counted file that was not written returns
   `unverifiable` with `candidate_not_materialized:<paths>`.
3. **Persistence is proved at the storage seam too.** `_collect_artifacts_and_checkpoint` applies
   the producers' grants once more after `PatchAcceptance` has compared the identity, so a
   comparison there alone cannot prove what is stored. For a result the accepted-patch path
   rendered (it carries `persisted_revision_id`), `storage_altered_accepted_patch` takes the
   stored work product's identity on both sides of that enforcement. A change fails the run. The
   base is never re-stored, so it cannot move between them. Main kept the two sets equal by call
   order (#1323, #1332), and this makes that property evidence-bearing.

A mismatch at either seam raises `_ExecutionError`, the #1350 precedent for a framework defect no
producer can cause, rather than re-dispatching as an ordinary correction. The accepted result
carries both `candidate_revision_id` (verified) and `persisted_revision_id`, and the executor logs
`patch_candidate_identity` with both. The verification-set driver reads that line as
`loop_texture.candidate_identities`, which is §39.4's evidence on every stored patch.

**Evidence.** Deploy A's archived runtime-api log (four cycles, 1.8.0) carries no storage-stage
`scaffold_integrity` event, so storage enforcement did not alter a stored set there. That is the
property item 3 now asserts rather than assumes. Tests enter at `_try_accept_patch` and
`_collect_artifacts_and_checkpoint`. Three mutations are each caught:
- an identity over the base only;
- no accept-side comparison;
- no storage-side check.

The base-only mutation also failed three pre-existing acceptance tests, because the accept-side
comparison refused them.

**Ruled by.** The implementer, in the PR that builds §38 step 1, for the owner's review with it.
None of the three items changes §5.5 or §39.4. Items 1 and 2 narrow where §20's identity is taken,
and item 3 adds the storage-side proof §5.5 requires.

## 46c. 2026-09-14 — the revision transaction as built (§38 step 2), and what moves to step 3

**What changed.**

1. **One pure module, callable wherever the base is in hand.** `src/squadops/cycles/revision_transaction.py`
   holds the transaction (§13), the canonical internal revision `RangeEdit` (§11), atomic
   resolution and application `resolve_and_apply` (§14), and typed refusals (§21). It does no I/O.
   A region is found by a `RegionResolver` the caller supplies for the artifact's kind, so the
   module holds no marker grammar of its own. For scaffold slots that resolver is
   `verification_scaffold.slot_body_span`. Step 2 calls it agent-side, in the qa handler and the qa
   repair handler (the two callers of `merge_fills`). The runtime verifier calls the same function
   once a repair arrives as a transaction.
2. **The grant is the existing path-level `WriteGrant`, carried and checked directly (§6.2).**
   Region authority is two facts: the grant permits the artifact's path, and the region resolves
   in that artifact. For the fill merge the grant is exactly the scaffold shells, for the producer
   that owns them (`qa.test`, or `qa.test_repair` on the repair path). Nothing is reconstructed
   from task type downstream.
3. **Step 2 ships one operation, `replace_region`** (§9.3), the shape the qa fill path always had.
   `merge_fills` builds one region-replacement revision per slot and applies the transaction. Its
   output is byte-identical to the merge it replaced, and `FillMergeRecord`, the fill-merge evidence
   (#999), keeps its shape. Later steps add exact anchors and structural operations; the atomic
   validation, the edit record and the identity stay.
4. **The candidate carries step 1's identity.** `TransactionOutcome.candidate_revision_id` is
   `patch_verification.candidate_revision_id` over the base and the edited artifacts. No second
   identity function exists.
5. **Not built in step 2, deliberately: `materialize(..., authorization=)`.** §38 lists it for this
   step. Step 2's candidate is the qa suite's own shells, and the test runner writes them into one
   workspace beside the additive suites. No transaction grant covers those suites, so authorizing
   that write with the transaction's grant would either refuse the additive suites or pass a grant
   wider than the transaction. The call is wired in **step 3**, where a grant first crosses a write
   seam the runtime enforces: the dev repair path, verified in `patch_verification`.
6. **The fill transaction's `task_id` is empty at both agent-side callers.** Their seam receives no
   task identity, and step 2 persists no edit record. The producer is recorded. The id is threaded
   when edit records become evidence (§36).

**Evidence.**
- The 445 existing fill and scaffold tests pass unchanged. They include the characterization goldens
  and the property that recovering fills from a merged shell and merging them again reproduces its
  bytes.
- `tests/unit/cycles/test_revision_transaction.py` covers: atomic refusal of a three-revision
  transaction with one out-of-grant revision; stale base; each unresolvable reason; overlap; two
  edits in one artifact applied without moving each other's range; span fingerprints; the inherited
  identity; and the empty and undeclared slot spans.
- Mutations are each caught: ascending application, the grant not consulted, a stale base
  accepted, and partial application. A slot span off by one line breaks 30 tests, including the
  existing fill tests, which is what pins byte identity.

**Ruled by.** The implementer, in the PR that builds §38 step 2, for the owner's review with it.
Item 5 moves one sentence of §38 to step 3.

## 46d. 2026-09-14 — the dev grant as built (§38 step 3), and `materialize(..., authorization=)` left unwired

**What changed.**

1. **Every role family that writes the workspace carries a grant, resolved in one place.**
   `scaffold_enforcement._producer_authorization` keys the grant on the task type's domain:
   - `qa` → `WriteGrant.for_qa`;
   - `development` → `WriteGrant.for_dev_fill`;
   - `builder` → `WriteGrant.for_builder`.

   `enforce_frozen_ownership` is the only caller. That puts the dev grant at the same seams as
   QA and builder (§39.6): the failed-emission bank, patch verification, artifact storage and the
   correction runner's repair emission. The producer an artifact names (#1350) still decides
   whose grant judges it.
2. **What the dev grant permits.**
   - **The fill slots:** allowed.
   - **The QA namespace:** unauthorized. Such a write is dropped with `unauthorized_slot_emission`
     evidence and counted against the contract-compliance budget, as a QA or builder overstep is.
   - **An undeclared path:** passes. A dev producer may create a file the scaffold never
     declared; §6.3's new-file grant is unchanged.

   The builder's #649 rule, that assembly may author no net-new source, is now a field of its
   grant (`may_author_undeclared_source=False`). It is no longer a second authorization threaded
   beside the first.
3. **The QA namespace is read by the scaffold's own rule.** `write_authorization._in_surface`
   read every directory token as a root prefix. `nextjs_ts` declares the co-located `__tests__/`
   convention (#1292), so its co-located suites fell outside its own namespace, and a grant that
   excludes the namespace could not see a write into one. Directory tokens are now read by
   `scaffold.within_namespace`, made public for this. No QA or builder disposition changes:
   - a QA co-located suite moves from undeclared to allowed, and passes either way;
   - a builder's moves from undeclared source to unauthorized, and is dropped either way.
4. **One existing test's expectation changes.** A dev producer making a region-legal edit to a
   verification-scaffold shell's slot bodies used to pass: `test_a_legal_body_edit_passes_any_role`
   read SIP-0104 §4.3's "any role" as permitting it. §4.3 forbids any role from modifying frozen
   regions; it grants no role the slot bodies. SIP-0104 §5 assigns a failing slot assertion to a
   qa repair. The slot bodies are the qa suite's content and live in the QA namespace, so a dev
   edit is now dropped as unauthorized, with evidence. The test is split: the qa lane passes, and
   `development.develop` and `development.correction_repair` are dropped.
5. **`materialize(..., authorization=)` stays unwired.** This supersedes §46c item 5, which
   moved it here. Its authorization is response-atomic and refuses undeclared paths
   (`WriteAuthorization.authorize_response`). On the dev repair path that would:
   - refuse every repair that creates a file the scaffold never declared;
   - turn a per-artifact drop into a whole-response refusal. `enforce_frozen_ownership` rejects
     that shape by design, because the squad still re-emits frozen files (#691).

   The seam §3.5 described is already met, in two places:
   - **for a transaction,** the grant is checked before any edit applies (`resolve_and_apply`,
     step 2);
   - **for a whole-file emission,** authorization runs before verification
     (`enforce_frozen_ownership` at `_try_accept_patch`), so the verified set is the stored set
     (#1323).

   Whether a whole-file emission should be refused atomically is a refusal decision. It belongs
   to the default flip (§38 step 7, §46a), not to a step before it.

**Evidence.**
- **Real emissions.** Across the stored artifacts of bound runs, 171 dev artifacts landed in a QA
  namespace between 2026-07-27 and 2026-08-21: 168 from `development.correction_repair` and 3 from
  `development.develop`. Since then there have been none, across 1,995 dev artifacts in 183
  cycles. The grant drops only what would otherwise be stored, so no stored emission since
  2026-08-22 is changed by it. An emission refused elsewhere, such as a patch that failed
  verification, is not in the store and is not counted here.
- **Tests.**
  - The namespace rule on both stacks: a co-located suite at depth, a root suite, a look-alike
    name, and a location at the root and below it.
  - At the pure seam: a dev repair's suite dropped with evidence, while its slot fix and a new
    helper pass.
  - The shell test, split as described in item 4.
  - Wiring at `_try_accept_patch`: the suite is dropped before the real verifier runs, the
    evidence stage is patch verification, the drop is counted, and the rest is accepted.
  - Wiring at `_collect_artifacts_and_checkpoint`: a `development.develop` emission's suite is
    dropped at storage and counted.
- **Mutations**, each caught by the test aimed at it:
  - the dev lane without a grant;
  - the namespace read as a root prefix;
  - the undeclared-source rule not consulting the grant;
  - the builder allowed to author source;
  - the dev grant widened to the QA namespace.
- **Live.** The dev-lane fault registered in the 1.8 prelude
  (`dev_join_response_omits_declared_fields`) runs a dev repair inside its grant on deploy B. A
  refusal there is fail-closed evidence and never counts toward N (§39.8).

**Ruled by.** The implementer, in the PR that builds §38 step 3, for the owner's review with it.
Item 4 changes a behaviour an existing test pinned. Item 5 reverses §46c item 5. Both are named
for the owner.

## 46e. 2026-09-14 — exact anchored targets as built (§38 step 4, first half)

**What changed.**

1. **Step 4 lands in two PRs.**
   - **This one:** the pure machinery — anchored targets in the transaction and the emission
     grammar — with the plan's step 4 proof (a multi-match anchor fails rather than choosing,
     §39.5; the #451 fixture).
   - **The second:** the agent-side wiring and model-facing contract — the three repair handlers
     (#1213's scope), the request template's edit form, the retry with the refusal's typed reason
     (§22) and the edit record as evidence (§36). #1213 closes with it.

   The split follows a seam: one half is pure and proven in CI, the other changes what a model is
   told and how its response is handled.
2. **`RevisionOperation.REPLACE_ANCHOR`**, §9.2. A revision carries an `anchor`; the framework
   replaces it only where it occurs exactly once inside the authorized region.
   - **The region:** a named `region_id` bounds the search. Without one, the region is the whole
     artifact the grant permits, which is an unslotted file's authorized region.
   - **Refusals:** zero matches refuse as `anchor_not_found`, several as `anchor_ambiguous` (with
     the count), and an empty anchor as `empty_anchor`.
   - **Exact:** nothing is whitespace-normalized, case-folded or chosen.
   - **Overlapping occurrences count:** `aa` occurs twice in `aaa`.
3. **Anchors resolve against the base, not sequentially.** #1213's sketch applied edits in
   emission order, each re-checked against the text the previous edit left. §13 is the ruling:
   every revision resolves against the same starting base, and resolved ranges that overlap refuse
   the transaction. So two anchored edits cannot depend on each other, and one cannot silently
   shift another's match.
4. **The grammar** (`squadops/capabilities/anchored_edits.py`) is #1213's.
   - **Shape:** an `edit:<path>` fence holding one or more `     `>>>>>>> REPLACE` blocks, the markers whole lines. SEARCH and REPLACE text are their lines,
     each ending in a newline, exactly as emitted.
   - **Malformed fences are named with a typed reason:** no divider, no end marker, an empty
     SEARCH, text outside a block, no blocks, an unclosed fence, an unsafe path. A block missing a
     marker ends at its fence's close, so it cannot swallow the files emitted after it.
   - **A bare fence line inside REPLACE is content,** so a replacement may carry fenced text.
   - **`strip_edit_blocks` runs before whole-file extraction.** Unstripped, `edit:backend/routes.py`
     matches the strict `lang:path` header and would be stored as a file whose content is the
     markers.

**Evidence.**
- **The #451 fixture:**
  - anchoring the placeholder's own line changes that line and nothing else;
  - anchoring `0` refuses as ambiguous, with every zero counted, and applies nothing.
- **Transaction tests:**
  - two matches, differing whitespace, differing case and an empty anchor, each refused with its
    reason;
  - overlapping occurrences;
  - a named region bounding the search (the same assertion in two slots resolves when the slot is
    named, and is ambiguous when it is not);
  - an anchored edit beside an overlapping or out-of-grant sibling refusing the whole transaction.
- **Grammar tests:**
  - a well-formed response parsed and applied through a transaction;
  - fence lines inside a replacement, and a deletion;
  - each malformed shape;
  - unsafe paths;
  - stripping, with the unstripped hazard shown.
- **Stored artifacts** in `data/artifacts` carry no edit-block text, so nothing already stored
  reads differently.
- **Mutations: nine, each caught.** A non-overlapping count; the first of several matches chosen;
  a named region ignored; a whitespace-normalized match; an empty anchor allowed; a fence line in
  REPLACE closing the fence; a malformed block swallowing the rest; prose inside a fence ignored;
  an unsafe path accepted.

**Ruled by.** The implementer, in the PR that builds the first half of §38 step 4, for the owner's
review with it. Item 3 records the accepted §13 over #1213's earlier sketch.

## 46f. 2026-09-14 — anchored edits in the repair handlers (§38 step 4, second half)

**What changed.**

1. **Where edits are applied.** Agent-side, in the repair handlers' shared mixin: `development.correction_repair`,
   `builder.assemble_repair`, and `qa.test_repair` outside fill mode. That is #1213's scope; a qa
   repair in fill mode revises slots (§9.3) and is never offered the edit form.
   - **The base is the repair's own tree:** the workspace the verifier materialises
     (`acceptance_workspace_files`), with the failed task's files over it (#1264). The edit is
     resolved against the tree that will be verified.
   - **Accepted edits become ordinary full-content artifacts**, beside any file the response
     emitted whole. Everything downstream is unchanged: enforcement with step 3's lane grants,
     patch verification, candidate identity (§20) and the retest.
2. **The grant is the named files that exist.** A repair may anchor into the files its task
   names (`expected_artifacts`) that are already in its base, and no other file. An edit
   anywhere else refuses as `out_of_grant`.
3. **The edit form reaches the model only where it can apply.** `request.cycle_repair_task`
   (version 7) renders `request.cycle_repair_anchored_edit_appendix` when at least one named file
   exists in the base, listing exactly those files. A repair with nothing to edit is not shown
   the form.
4. **The retry is one re-prompt inside the repair step (§22).** A repair step has no
   executor-level emission retry; #1372's covers a task's own attempts. So a refused or
   malformed edit response is re-prompted once, within the step, with its typed refusal lines
   (`request.cycle_repair_anchored_edit_retry`): each line names the file and the reason. It is
   the one retry §22 allows, not a second economy.
   - **A retry refused too stands.** The step returns no artifacts and an `emission_failure`
     whose reason is `anchored_edit_refused`.
   - **Its round is spent, not refunded.** `CorrectionRepair.judge_emission` does not read it as
     an absent emission, so #1053 does not refund it. #1213 asked for exactly this: a wrong
     anchor is an informative failure, unlike #1129's gate refusal.
5. **Before the flip, a whole-file response is read exactly as before** (§46a). A response that
   both edits a file and re-emits it whole refuses, rather than letting either silently win.
6. **The edit record rides the repair's outputs.**
   - **Where:** `anchored_edits` holds the edits applied or the refusals, and `anchored_edit_retry`
     holds the first refusal. A structured `anchored_edit_transaction` log line carries the same
     facts.
   - **Not yet durable:** the record is not persisted to a store. §39.8's count of successful
     transactions on deploy B reads the log line, as the verification-set driver already reads
     loop texture. A durable edit record (§36) is a named follow-up, not an omission.

**Evidence.**
- **Wiring**, entered at `DevelopmentCorrectionRepairHandler.handle` with the real request
  templates, the real renderer and a scripted model:
  - **Accepted:** the edit form names only the named files that exist, and an anchored repair
    becomes the whole file with only its anchor changed.
  - **Retried:** an ambiguous anchor is retried once, with `anchor_ambiguous — the anchor occurs
    2 times` in the retry prompt.
  - **Refused twice:** a second refusal makes exactly two model calls and returns no artifacts.
  - **Unchanged:** a whole-file response reads as before, and a repair with no existing named file
    is not offered the form.
  - **The right tree:** an edit resolves against the failed attempt's file laid over the
    workspace.
  - **The grant:** an edit to a file the repair was not named for refuses as `out_of_grant`.
- **`run_correction_protocol`:** a refused anchored repair is not an empty emission.
- **Application tests:** accepted records, and refusal lines naming the file and reason for
  `anchor_not_found`, `out_of_grant`, an edit-and-rewrite conflict, and a malformed block.
- **Mutations: nine, each caught.**
  - no retry;
  - a retry without the reasons;
  - the edit form never rendered;
  - the failed attempt's files not overlaid;
  - every workspace file anchorable;
  - a refusal falling back to whole-file reading;
  - a refused repair refunded;
  - the generic no-file marker overwriting the refusal;
  - the conflict ignored.

  A tenth, removing a retry guard, survived. It was equivalent, because the retry calls the base
  handler and cannot re-enter itself, so the dead guard was removed.

**Ruled by.** The implementer, in the PR that completes §38 step 4, for the owner's review with
it. #1213 closes here.

## 46g. 2026-09-14 — structural revision of Python as built (§38 step 5, first half)

**What changed.**

1. **The first structural resolver is Python's, on the stdlib `ast`.** §43.2 left the order of
   React's two resolvers to this step. The backend goes first:
   - the whole-file repair failures that motivate the SIP were `backend/routes.py` rewrites
     (§1.2);
   - `ast` gives exact extents with no dependency.

   The JSX resolver is the second half of step 5, in its own PR, with its library chosen there.
   The resolver is replaceable; its fail-closed contract is not. An unparseable base, an absent
   selector and an ambiguous selector each resolve to nothing, never to a guess.
2. **Entities are named by a selector that is revision-bound through the transaction** (§7,
   §43.1): `function:NAME`, `function:NAME#body`, `class:NAME`, `method:CLASS.NAME`,
   `method:CLASS.NAME#body`, `import:MODULE`, `imports`.
   - **Ranges are whole lines,** from the first decorator's line through the newline ending the
     last line. So a replacement, insertion or removal composes with the lines around it intact.
   - **A body is addressable only when it starts on its own line.**
   - **The selector is the authoritative identity within an artifact;** the base revision the
     transaction names binds it to one revision (§12).
3. **Four entity operations** (§8):
   - `REPLACE_ENTITY`;
   - `INSERT_BEFORE_ENTITY` / `INSERT_AFTER_ENTITY`, zero-width at the entity's start or end;
   - `REMOVE_ENTITY`, whose replacement is always empty.

   They sit in the existing atomic transaction, so a grant, a stale base, an overlap or any
   refusal refuses them all. Refusals are `unresolved_entity`, `ambiguous_entity`,
   `unreadable_structure`, and — for two insertions at one point, whose order no rule fixes —
   `overlapping_ranges`. The import-order repair is `remove` + `insert` in one transaction, as
   §8.4 rules.
4. **Application order at one offset is fixed:** the wider edit applies first. An insertion
   before an entity lands ahead of that entity's replacement, never inside it.
5. **Syntax validation refuses before anything else runs (§18).** A caller-supplied validator
   checks every changed artifact of the composed candidate — `python_syntax_error` for Python —
   and a candidate that does not parse refuses the transaction as `invalid_syntax`.
6. **The preservation proof is reconstruction (§17).** `preservation_proof(base, edits,
   candidate)` requires the candidate to be exactly the base with the recorded edits applied, in
   base order, and every artifact no edit names to be identical.
   - **On acceptance** it is computed and carried on the outcome, and a failure refuses as
     `preservation_failed`.
   - **Standalone** it checks a candidate produced elsewhere against its recorded edits.

**Not in this half:**
- the JSX resolver;
- the model-facing contract: repository inspection returning references, the structural emission
  form and the handler wiring (steps 4b's shape, for entities);
- the §39.2 reading on live transactions.

**Evidence.**
- **Addressing:** every selector names its entity's whole lines, decorators included. An inline
  body, an unparseable file and a redefinition resolve to nothing, nothing, and two spans
  respectively.
- **Transactions:**
  - a body replacement changes only the body, and the proof holds;
  - the import-order pair applies in one transaction;
  - an insertion before, a replacement of and an insertion after one method compose in order;
  - an absent, redefined, unparseable-base, resolver-less, same-point or invalid-syntax revision
    refuses the whole transaction.
- **The proof** fails for an untouched line changed, an unrecorded file changed, the edit
  missing, and a trailing byte added.
- **On the real FastAPI+React scaffold** (§39.3): a scoped body revision of
  `backend/routes.py`'s `post_runs` needs no restoration (`restore_declared_status_codes` returns
  the candidate unchanged, with no divergences) and observes nothing
  (`signature_divergences` is empty).
- **Mutations: nine, each caught.** Decorators excluded from the range; an inline body
  addressable; an ambiguous entity picking the first; the equal-offset order reversed; insert-after
  landing before; syntax not validated; a remove keeping its replacement text; the proof ignoring
  unrecorded files; the proof ignoring the tail.

**Ruled by.** The implementer, in the PR that builds the first half of §38 step 5, for the owner's
review with it. Item 1 is the resolver choice and order §43.2 delegated to this step.

## 46h. 2026-09-14 — the JavaScript/JSX resolver, on tree-sitter (§38 step 5)

**What changed.**

1. **The React frontend's resolver is tree-sitter's JavaScript grammar.** §43.2 left the library
   to step 5. The owner chose it on 2026-09-14 over two alternatives:
   - **a vendored `@babel/parser`** run with the agent containers' node, which checks third-party
     JS into the repository and pins it by hand;
   - **`esprima`**, which is unmaintained and does not read `?.` or `??`, both of which the
     generated views use.

   `tree-sitter` and `tree-sitter-javascript` ship wheels for the images' aarch64 and CI's x86_64.
   They are declared in `requirements/agent.txt`, the `agent` extra, `tests/requirements.txt`
   and CI's constraints, and compiled into `agent.lock`. The parser is imported on first use,
   so no importer that never parses JSX needs it.
2. **Fail-closed over an error-tolerant parser.** tree-sitter returns a tree for broken input.
   Every reading checks for an error or missing node first, and a tree carrying one is neither
   addressed nor accepted: `jsx_syntax_error` refuses it (§18).
3. **Selectors mirror Python's**, on whole lines: `function:NAME` (with its `export`),
   `function:NAME#body`, `const:NAME`, `const:NAME#body` (an arrow or function expression with a
   block body), `class:NAME`, `import:SOURCE`, `imports`.
   - **An entity must own its lines.** Nothing but whitespace may share its first line before it
     or its last line after it; JavaScript allows two statements on one line, and such a
     statement is not addressable.
   - **A body must sit on its own lines,** with its braces owning theirs.
   - **Offsets are characters.** tree-sitter reports byte columns, so ranges are taken from rows,
     never from byte offsets.
4. **TypeScript is not read.** `.ts` and `.tsx` need their own grammar, and the Next.js stack is
   step 6's. This grammar reads `.js`, `.jsx`, `.mjs` and `.cjs`.
5. **The resolver is standalone in this PR.** Wiring both resolvers into one transaction, and the
   model-facing contract, follow in the next PR, beside the Python half (§46g).

**Evidence.**
- **Selectors:** every selector's whole lines in a view using `?.`, `??` and JSX, `export default`
  included.
- **Offsets:** they stay correct after a line of multibyte text.
- **Fail-closed:** broken JSX is neither addressed nor accepted; a redeclaration names two
  entities; a statement sharing its line owns none; a one-line body has none; a `.tsx` file is not
  read.
- **The real scaffold:** `RunsListView.jsx` from the FastAPI+React scaffold, the view 1.7.5 React
  roll 3 re-emitted whole every round (§1.2), parses cleanly and addresses its component and body.
- **Dependency guards:** the import mirror and constraint-drift tests pass with the new
  declaration. `agent.lock` gains exactly the two packages.
- **Mutations: six, each caught.** A tolerant parse addressed; `has_error` ignored; `export` not
  unwrapped; line ownership not checked; TypeScript read by this grammar; byte columns used as
  characters.

**Ruled by.** The owner, on the library (2026-09-14). The implementer, on the selectors and the
fail-closed reading, for the owner's review with them.

## 46i. 2026-09-14 — the repair's structural contract (§38 step 5, completing it for React)

**What changed.** Steps 5a (§46g) and 5b (§46h) built the two resolvers, the entity operations,
syntax validation and the preservation proof. This change puts them in front of the model and
into the repair path, on the seam step 4 built (§46f).

1. **One dispatch for every reader.** `structural_resolution` routes by suffix: `.py` to the
   Python resolver; `.js`, `.jsx`, `.mjs` and `.cjs` to the JSX resolver; anything else to
   nothing. The transaction's entity lookup, the prompt's entity listing and the syntax check all
   ask the same resolver about the same file, so a selector the prompt lists is one the edit will
   find.
2. **References in the prompt (§7).** The edit-form appendix (version 2) lists each editable file
   with the entities its resolver addresses, read from the same base the edits resolve against. A
   file without a structural reading is listed without entities and can still be edited by anchor.
   Listings are capped at forty entities per file, with the remainder counted.
3. **Structural blocks share the edit fence and the transaction.** Each takes one listed selector
   and closes with `>>>>>>> END`: `<<<<<<< REPLACE`, `<<<<<<< INSERT BEFORE`,
   `<<<<<<< INSERT AFTER`, `<<<<<<< REMOVE`. One fence can mix them with anchored blocks. They
   resolve against one base and apply all together or not at all.
   - **Malformed shapes are named:** an unknown verb or a missing selector (`unknown_block`), no
     end marker, a `REMOVE` carrying lines, an `INSERT` carrying none.
   - **Refusals reach the retry appendix (version 2)** with guidance for `unresolved_entity`,
     `ambiguous_entity`, `unreadable_structure` and `invalid_syntax`.
4. **Syntax validation guards a file that parses (§18).** A repair's candidate is refused as
   `invalid_syntax` when the edited file no longer parses — unless its base did not parse either.
   A repair of an already-broken file is judged by verification, because the syntax error may be
   the very failure it was sent to fix; such a file has no structural reading and is edited by
   anchor. This check now also covers anchored blocks.
5. **The edit record names each edit's operation,** so §39.8's count can separate structural
   transactions from anchored ones.

**Not in this change:** step 6, the Next.js stack, which needs the TypeScript grammar.

**Evidence.**
- **The grammar and the transaction:**
  - a `REMOVE`, a body `REPLACE` and an anchored block apply in one transaction, recorded in
    emission order with their operations;
  - `INSERT BEFORE` and `INSERT AFTER` land on their sides of the entity;
  - five malformed shapes are named;
  - on the real FastAPI+React scaffold, `RunsListView.jsx`'s component body is replaced with its
    `export` line and closing brace intact, and the preservation proof holds.
- **Syntax:** an edit that breaks a parsing file refuses; an anchored edit of an already-broken
  file does not.
- **The dispatcher:** Python, JSX, `.tsx` not read, a file with no grammar, and an unparseable file.
- **Wiring**, at `DevelopmentCorrectionRepairHandler.handle` with the real templates and renderer:
  - the prompt lists `backend/routes.py` with `imports`, `import:fastapi`, `function:post_runs`
    and `function:post_runs#body`;
  - a body `REPLACE` applies with the decorator and signature intact;
  - an entity that does not exist is retried with `unresolved_entity — function:delete_run#body is
    not in backend/routes.py`.
- **Mutations: six caught, one equivalent.** One of the six needed a test added first. The resolver not passed to the
  transaction; syntax never validated; a broken base still validated; a `REMOVE` allowed to carry
  lines; the prompt listing no entities; the insertion verbs swapped. The seventh, routing `.tsx`
  to the JSX resolver, is equivalent: that resolver refuses `.tsx` itself.

**Ruled by.** The implementer, in the PR that completes §38 step 5's contract for the React stack,
for the owner's review with it.

## 46j. 2026-09-14 — the structural path on Next.js (§38 step 6)

**What changed.**

1. **TypeScript and TSX read through the same resolver, on the same library.** `structural_jsx`
   now picks a grammar by suffix:
   - `.js`, `.jsx`, `.mjs` and `.cjs` through the JavaScript grammar;
   - `.ts` through `tree-sitter-typescript`'s TypeScript grammar;
   - `.tsx` through its TSX grammar.

   The grammars share node shapes, so one reading serves all three; the dispatcher routes every
   ECMAScript suffix there. The owner approved the dependency on 2026-09-14 ("merge and keep
   going", after the question was put). `tree-sitter-typescript==0.23.2` has aarch64 and x86_64
   wheels and is declared as tree-sitter's other packages are; `agent.lock` gains exactly that
   package.
2. **TypeScript names its own declarations:** `interface:NAME`, `type:NAME` and `enum:NAME`. A
   directive prologue (`'use client'`, `'use strict'`) precedes the import section, the way a
   Python module docstring does, so a Next.js page still has an `imports` entity.
3. **`#try`: the second slot granularity (§39.7).** A Next.js route slot is narrower than its
   function: the scaffold owns each handler's signature and its `catch (err) { return
   errorResponse(err) }` envelope, and the fill is the `try` block.
   - **What it names:** `function:NAME#try` and `const:NAME#try` are the lines inside the `try`
     block when the body is exactly one `try` statement.
   - **Why:** a fill revised through it leaves the signature, the envelope and every sibling
     handler byte-identical by construction. A `#body` revision would have to reproduce the
     envelope.
   - **Stack-neutral:** the entity applies to any such function on either stack.
4. **The second stack meets the same criteria as the first:**
   - preservation by reconstruction (§39.2);
   - a candidate that parses under its own grammar (§18);
   - nothing to restore, because the scaffold-owned bytes are outside the revised range.

   No Next.js integrity instrument restores or observes TypeScript signature drift, so the
   observed-set criterion (§39.3) is met by construction rather than read off an instrument.

**Evidence.**
- **On the real Next.js scaffold:**
  - a `REPLACE function:POST#try` on `app/api/runs/route.ts` leaves `export async function
    POST(request: Request) {`, the `try {` and `} catch (err) { return errorResponse(err) }`
    lines, and the whole sibling `GET` handler intact; the proof holds and the candidate parses
    as TypeScript;
  - a `REPLACE function:RunsListView#body` on `app/page.tsx` parses as TSX, and the proof holds;
  - a fill with an unclosed bracket is refused as `invalid_syntax`.
- **The resolver:**
  - interface, type, enum, the import section after `'use strict'`, and a handler's `try` block,
    each by exact text;
  - `#try` is not offered when the body holds more than the `try` statement;
  - broken TSX and broken TS are refused by the syntax check;
  - the dispatcher now routes `.tsx`.
- **Mutations: six, each caught.** TSX read with the TypeScript grammar; `#try` offered for a
  multi-statement body; the `try` block not required on its own lines; TypeScript declarations
  unaddressable; the prologue not skipped; the dispatcher ignoring TypeScript.

**Ruled by.** The owner, on the dependency (2026-09-14). The implementer, on `#try` and the reading
of §39.3 for a stack without a drift instrument, for the owner's review with them.

## 46k. 2026-09-15 — the repair's revision form is recorded on every repair (§46a, §39.8)

**What changed.** Every repair handler logs one `repair_revision_form` line per repair and puts
the same reading on the task outputs as `revision_form`. The line records:
- **the offer:** each file the edit form listed, with the number of entities listed for it, or
  `{}` when the form was not rendered;
- **the form the response took:** `edits`, `whole_file`, `edits_and_whole_file`, `fill`,
  `new_files_only` or `none`;
- **the transaction's result:** accepted or refused, the refusal count, whether it was
  retried, and the failure reason;
- **§39.8's modes:** `structural`, `anchored` and `region`, from the operations the response
  proposed (the edit record now carries `operations_proposed`, accepted or not).

`whole_file_offered` names the offered files re-emitted whole: §46a's unauthorized whole-file
fallback, counted per cell before step 7. A file the repair creates is not a fallback, and an
edited file whose applied content rides as an artifact is not a re-emission. The verification-set
driver reads the line from the agents' windows into `loop_texture.repair_revision_forms` and
renders it as a record row.

**Evidence: the first live repair on deploy B was unreadable without it.** Deploy B's Next.js
checkpoint roll, `cyc_e62d74598211`, took one correction round:
1. The develop task's `app/runs/[run_id]/page.tsx` failed `frontend_compiles`, because it used
   `router.query` in an App Router page.
2. The lead decided `patch`, calling it "a straightforward one-line fix".
3. The dev repair's emission carried one whole-file path fence and no edit fence.
4. The patch failed the same check, and the develop task was re-dispatched and passed.

Whether the repair was offered the edit form could not be read:
- **The stored prompt is cut short:** LangFuse truncates it at `MAX_OBSERVABILITY_TEXT_LENGTH`
  (10,000 characters, `src/squadops/telemetry/models.py:135`), and this prompt was about 9,500
  tokens, with the edit form past the cut.
- **The transaction line is conditional:** `anchored_edit_transaction` is written only when a
  response carries edits.

So a whole-file answer to an offered form could not be told from a repair never offered one. That
is the distinction §39.8's N and §46a's per-cell count both depend on.

**Tests:**
- **The reading:** separates a whole-file fallback from a new file, an edited file and a prose
  fallback.
- **The wiring:** entered at `DevelopmentCorrectionRepairHandler.handle` for a whole-file answer,
  a scoped edit, a refusal retried, and a repair never offered the form.
- **The driver:** parses the handler's own line, keeps an unparseable line, and reads unaskable
  (never zero) when no line was logged.

**Mutations: five, each caught.**

**Ruled by.** The implementer, on the owner's go for the instrument (2026-09-15). No repair
behaviour changes; §46a's contract is unchanged.

## 46l. 2026-09-15 — the repair prompt asks for the form §46a requests (§9.1, §9.2, §46a)

**What changed.** A repair offered the edit form is now asked for it and nothing else.
`request.cycle_repair_task` v8 renders its output section and its closing instruction from one
decision, the edit form's own (`_anchorable_files`):
- **Offered** (`request.cycle_repair_output_scoped`, `request.cycle_repair_closing_scoped`): the
  existing named files are listed for **edit fences only**, with "do not emit a
  ` ```language:<path> ` fence for any of these files". A file the task names that does not
  exist yet is listed for a whole-file fence. The last instruction says the same.
- **Not offered** (`…_output_whole_file`, `…_closing_whole_file`): v7's output section and
  closing, verbatim. The rendered prompt is byte-identical to v7's, because the renderer collapses
  blank-line runs.

The edit-form appendix (v3) is placed directly after the output section. Its heading drops
"(preferred for a repair)", and its last rule drops "or genuinely rewrite from top to bottom".

**Evidence: the prompt asked for the whole file.** v7 inserted the edit form near the top and
called edits "preferred", then:
- **Line 50:** "The repair MUST produce the following file(s) by name, using fenced code blocks
  … (` ```language:<that path> `)".
- **Line 58:** "A file you are not fixing must be re-emitted byte-identical".
- **The last line:** "Produce the named artifacts now. Use fenced code blocks for every file you
  emit, each header carrying that file's own path".

Deploy B's Next.js repair (`cyc_e62d74598211`) of a change the lead called "a straightforward
one-line fix" came back as a whole file: the form the last instruction named. §46a's pre-flip
contract says a repair of a supported existing artifact **requests** a scoped revision. v7
requested the opposite, so this corrects the implementation to the contract. §46a is unchanged:
a whole-file response is still accepted and recorded until §38 step 7.

**Tests:**
- **Offered:** entered at `DevelopmentCorrectionRepairHandler.handle`, the existing file is listed
  for edits and the new file for a whole fence, neither "MUST produce the following file(s)" nor
  "re-emitted byte-identical" appears, and the closing forbids a whole fence for an existing file.
- **Not offered:** v7's section and closing are unchanged.
- **Minimality:** the template test holds it in both output forms.
- **Mutations: three, each caught.** The scoped form never chosen; the scoped closing replaced by
  the whole-file one; new files listed as editable.

**Not yet shown:** whether qwen3.8 follows the coherent prompt. A readiness probe against the
live model precedes deploy C and any pre-registration (the owner's re-sequence, 2026-09-15).

**Ruled by.** The owner's go on the re-sequence, 2026-09-15; the implementer on the wording.

<<<<<<< HEAD
## 46m. 2026-09-15 — the repair prompt shows the files it asks the model to revise (§9.2; #1576)

**What changed.**

1. **Every repair offered the edit form now sees the files it may revise, verbatim.** A new
   section, *The Files as They Are Now* (`request.cycle_repair_current_files`), renders each
   anchorable file from the tree the edits resolve against — the verifier's workspace with the
   failed task's own files over it (`_repair_base_files`, #1264) — between the output section
   and the edit-fence instructions, on the retry too. Each file is shown in a bare fence longer
   than any backtick run inside it, never in the ` ```language:<path> ` emission form. The
   appendix (v4) and the retry (v3) now say "copy from the file as shown above" instead of "from
   the file as it is now". A repair not offered the edit form is asked exactly as before.
2. **The renderer's blank-line cleanup leaves fenced blocks verbatim.** It collapsed every run
   of three or more newlines, including inside a shown file — a Python file's two blank lines
   between top-level definitions became one — so the text a model copied from would not have
   been the text its anchor is matched against. Outside a fence the cleanup is byte for byte as
   before; inside one, nothing changes. A longer fence is closed only by its own marker.
3. **§9.2's "refreshed context" is this section**, on the first prompt and not only on the
   retry. Exactness (#451) is unchanged: the anchor still has to occur exactly once, unmodified.

**Evidence.** No repair prompt path rendered the file being repaired. `request.cycle_repair_task`
v7 and v8 declare no variable for file content; `_RepairPromptMixin.handle` renders the failure
evidence, the analyzer's summary, the decision, the PRD and the edit form; `artifact_contents` is
rendered by the develop and builder handlers and never by the repair handlers; the failed task's
files and the workspace reached the repair only as the edit base. The readiness probe of
2026-09-15 (three real failed dev repairs rebuilt from the vault, the real handler, live qwen3.8,
v7 and v8, three trials each; `var/probes/2026-09-15-scoped-repair-readiness/`) read against
the rendered prompt:

- the routes.py prompt contains no line of the file (`status_code=201` absent); its six first
  tries all anchored `@router.post("/runs")` for a decorator reading `…, status_code=201)`;
- route.ts guessed the quote style every time; page.tsx's exact anchors were the six lines the
  compiler's excerpt quoted, its import line guessed;
- every routes.py retry that applied switched to `REPLACE function:<name>` for all five
  functions, authoring five bodies it had never read — legal under §17, which proves nothing
  about the inside of an entity, and counted as a scoped transaction by §39.8;
- deploy B's pair 1 (`cyc_e62d74598211`): the dev repair of a one-line fix came back as a
  whole file, under a contract that asked for the unfixed lines re-emitted byte-identical.

Of the 63 SEARCH blocks the probe produced, 35 matched a line exactly, 12 were unique fragments
of a line and 16 misquoted the file — and none matched the workspace's stale copy, so the base
overlay was right and the model was working from the evidence excerpt and recall.

**Tests.** The prompt shows each editable file as the tree the edits resolve against (the failed
task's copy, not the workspace's; a named file that does not exist and an unnamed one absent)
and the applied edit lands on that text with its blank-line run intact; a Markdown file holding a
fence is wrapped in a longer one and its edit still applies; the retry shows the files again; a
repair not offered the form carries no section; the renderer keeps blank-line runs inside a
fence while still collapsing prose, and a fence is closed only by its own marker.

**Not yet shown:** that qwen3.8 copies from the shown file rather than from recall — the
readiness probe's second run, in the dev agent's container with the typed checks executing,
reads that before deploy C.

**Ruled by.** The owner, 2026-09-15 ("start with item 2"), on the probe re-read that found the
missing section; the implementer on the section's placement and the renderer fix.

## 46n. 2026-09-15 — an anchor may be a fragment of a line (§9.2, amending §46e item 4)

**What changed.** The grammar's reading of a SEARCH block. §46e item 4 made SEARCH and REPLACE
text "their lines, each ending in a newline, exactly as emitted", so an anchor was always matched
with a newline after its last line. The newline closing the block's last line is the block's,
not the model's: `'@/lib/store'` on a line of its own is the model naming a piece of a line.

1. **Two exact readings, in order.** The anchor as its lines, newline included, is tried first;
   only when that text occurs nowhere in the file is the anchor read without its final newline
   — a fragment of a line — and its replacement likewise loses the newline the block gave it.
   The line reading wins whenever it occurs at all, so a whole line that is also the prefix of a
   longer one cannot be made ambiguous by this rule.
2. **Nothing else moves.** Each reading is exact — nothing normalized, folded or chosen (#451) —
   and the transaction still requires exactly one occurrence inside the authorized region:
   a fragment occurring twice is `anchor_ambiguous` with its count, a misquote is still
   `anchor_not_found`. §13 (all edits resolve against one base), §17 and §18 are untouched.
3. **Where it lives.** The grammar (`anchored_edits.py`), which added the newline, decides
   whether it is content — against the file the edits will resolve on, before the transaction
   is built. `RevisionTransaction` and §9.2 are unchanged; §9.2 never said lines. The
   application record carries `fragment_anchors`, the count read as fragments, beside the
   modes (§39.8's readout).
4. **The prompt is unchanged.** The model already writes fragments unprompted (below); a rule
   inviting them would be one more rule to obey literally.

**Evidence.** The readiness probe of 2026-09-15 (three real failed dev repairs, live qwen3.8,
18 trials, `var/probes/2026-09-15-scoped-repair-readiness/`): of 63 SEARCH blocks, 12 were
unique fragments of a line — `'@/lib/store'`, `from '@/lib/errors'` — refused only because the
newline after them was read as theirs. Four of the five refused trials would have applied under
this reading. The remaining refusals were misquotes (16 of 63), which this rule does not touch
and §46m addresses at its cause.

**Tests.** A specifier, decorator arguments, a deletion and a multi-line anchor ending in a
fragment each replace only the fragment, with the line's remainder and its newline intact; a
whole line that prefixes another is read as the line and never becomes ambiguous; a fragment
occurring twice is refused as ambiguous with its count, never chosen; a misquote is still not
found. **Mutations: two, each caught** — the fragment reading tried first (the prefix test
refuses as ambiguous), and the fragment reading removed (every fragment case refuses).

**Ruled by.** The owner, 2026-09-15 ("I will want to do 1-3"; item 1), on the probe's reading;
the implementer on the seam and the line-first order.

## 46o. 2026-09-15 — the revision form reads the span each transaction replaced (§39.8, §46k)

**What changed.** The per-repair `repair_revision_form` line (§46k) and the `revision_form`
output gain `replaced`: for every file an accepted transaction touched, the characters its
resolved spans covered — structural spans included — against the file's size in the tree the
edits resolve on, as `{chars, of, pct}`; a file re-emitted whole reads as the whole file, byte-
identical or not. The line also carries `fragment_anchors` (§46n). The verification-set driver
renders both beside the form and the modes (`replaced 93% backend/routes.py`).

**Evidence.** The readiness probe's second run (2026-09-15, the dev agent's image, the live
model, real repair envelopes, typed checks executing; `var/probes/2026-09-15-scoped-repair-
readiness-v2/`): with the file hidden from the model, every routes.py repair that applied did so
by `REPLACE function:` on all five functions — 2,825 of 3,035 characters, 93%, authored blind —
and passed §17's proof, which covers only the bytes outside the entities. With the file shown
(§46m), the same repair was five anchored lines, 163 characters, 5%. Both are "successful scoped
transactions" to §39.8's N and both rendered identically in the readout. The pre-registration's
per-cell readout needs the span to tell them apart, and N's definition may want a ceiling on it;
that is the pre-registration's call, made on this reading.

**Tests.** The reading takes the span from the resolved range, not the replacement's length; a
whole-file re-emission reads as 100% of its file; a refused transaction replaces nothing; the
handler passes the base's sizes so the line carries them; the driver renders the percentage per
file and names an unknown size rather than inventing one. **Mutations: two, each caught** — the
span read from the replacement's length; the whole-file re-emission left unread.

**Ruled by.** The owner, 2026-09-15 ("add the replaced span to the instrument"), on the probe's
reading; the implementer on the shape.

## 46p. 2026-09-15 — a fill-mode repair's free-authored files are anchorable, and a base file re-emitted whole reads as one whether or not it was offered (§9.3, amending §46f and §46k; #1583)

**What changed.**

1. **§46f's fill-mode rule narrows from "the repair" to "the shells".** §46f made a qa repair in
   fill mode revise slots and never anchor, by returning no anchorable files whenever the task
   carried a scaffold. That assumed a scaffold-bound emission is entirely fills. It is not: the
   Next.js qa task authors a free-authored suite beside the scaffold's shells. Now the shells —
   read from the scaffold input the runner threads, pristine and current — are excluded from
   the anchorable files, and every other named file that exists in the base is anchorable,
   offered the edit form and shown (§46m) as on any other repair. A shell is filled by slot
   (§9.3) and is never listed as a file to emit whole. A repair naming only shells is exactly
   what it was.
2. **The revision form reads a base file re-emitted whole as a whole-file response whether or
   not the edit form offered it.** §46k read "re-emitted whole" against the offered files only,
   so a whole-file response in fill mode — where nothing was offered — read as a new file. The
   handler now passes every base file's size to the reading; a file in the base that comes back
   whole and was not offered is `whole_file_unoffered`, the form is `whole_file` (or
   `edits_and_whole_file`), and `replaced` reads it at 100% (§46o). A file not in the base is
   still a new file. The driver names it: `never offered: <path>`.

**Evidence.** Deploy D's Next.js shakeout (`cyc_95c0e2dbb25c`, 2026-09-15): one assertion in
`__tests__/runs-ui.test.ts` was wrong; the analyzer and the lead both blamed the suite; #1582
routed the round to `qa.test_repair`; the repair, offered nothing, emitted 8 slot fills and the
whole suite — 11,245 characters to 7,564, 299 changed lines — which passed 40 checks and the
retest and was accepted and persisted. The `repair_revision_form` line read `form=fill, offered
{}, new_files ["__tests__/runs-ui.test.ts"]`. Neither §39.8 reading could see it: not a scoped
transaction, and not a counted whole-file response. It was found on the owner's question
"were the qa fixes targeted or whole-file?" after the pair had been read as clean.

**Tests.** Entered at `QATestRepairHandler.handle` with the real templates: a free-authored suite
named beside a shell is offered, shown, and edited in place while the shell's fill merges; the
shell is neither anchorable nor listed as a file that does not exist yet; a repair naming only
shells offers nothing and reads as `fill`. The reading: a base file re-emitted whole with
nothing offered reads `whole_file`, `whole_file_unoffered`, 100% replaced, and a file not in
the base stays new; without the base's sizes the reading is what it was. The driver renders
`never offered: <path>`. **Mutations: two, each caught** — fill mode offering nothing again (the
handler test fails); unoffered whole files read as new (three tests fail).

**Ruled by.** The owner, 2026-09-15 ("fix 1583 and plan for deploy E"); the implementer on the
shape.
