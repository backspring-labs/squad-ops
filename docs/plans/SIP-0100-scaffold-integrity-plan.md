# SIP-0100 Implementation Plan — Scaffolded Test Harness and Frozen-File Enforcement

**SIP:** `sips/accepted/SIP-0100-Scaffolded-Test-Harness-and.md` (accepted 2026-07-22)
**Extends:** SIP-0099. **Coordinates with:** SIP-0086 (Build Convergence Loop).
**Motivating case:** pf-26 (`cyc_af8800f8943f`) — the backend `qa.test` correction loop oscillated to
exhaustion on a package-root inconsistency, a **QA** correction rewrote the *frozen* `backend/main.py`,
and the system never identified the overwrite as the breach.

## Intent

Turn scaffold ownership from a generation-time hint into a **bind-time→completion lifecycle invariant**
(SIP-0100 §2) enforced as **contract-governed write authority**: the scaffold owns structural invariants
(interface *and* test boundary); named producers write only their declared slots; **no** downstream
producer may mutate a scaffold-owned path; a malformed (ownership-violating) response is a distinct
*contract-compliance* failure, not an implementation defect. The seam this establishes is reusable for
future scaffold-owned infrastructure (DBs, queues, auth boundaries, migrations, generated clients).

## Status snapshot (already true on `main`)

| Item | State | Where |
|------|-------|-------|
| Piece A — expander emits a frozen root `conftest.py` (sys.path anchor + `client` fixture) | **DONE** (PR #538) | `capabilities/scaffold.py` |
| `conftest.py` hash-pinned in the contract | **DONE automatically** — `frozen = expand(manifest) − fill_slot_paths(manifest)`; conftest is a non-slot output | `scaffold_contract.py:46-54` |
| Import *resolution* for the package convention | **DONE, no change** — `_source_dir_pythonpath` (#303/#454) roots package dirs at the workspace | `handlers/test_runner.py:98` |
| Everything below | **NOT built** — this plan | — |

**Chokepoint — CORRECTED by Task 0.1 (proven, not assumed):** there are **two** independent
workspace materializers, not one. `materialize_artifacts` (`patch_verification.py:136`) covers the
typed-acceptance + patch-verify workspaces, but the **qa.test pytest/frontend workspace** is
materialized by `_materialize_files` (`handlers/test_runner.py:67-76`, `mkdtemp` at :173) — which
**bypasses** `materialize_artifacts` and is the workspace pf-26 actually failed in. Phase 2 must
**unify both behind one authorization-aware materializer**. Full inventory + characterization test:
`docs/plans/SIP-0100-phase-0-mutation-path-inventory.md`.

## Normative decisions (resolved up front — no open architectural choices inside implementation steps)

- **D1 — QA test ownership = bounded hybrid.** The scaffold contract declares a deterministic QA test
  **namespace** (root/pattern, e.g. `backend/tests/**`); the plan declares **concrete** test file paths
  *within* that namespace; a QA producer may create/edit only within the authorized QA surface; paths
  outside it are unauthorized. (Resolves review #4; not a single fixed filename, not proposer-free paths.)
- **D2 — Restoration source = persisted bound bytes, never re-derivation.** Bind time persists the
  normalized path, bytes, sha256, scaffold+contract identity for every frozen artifact (a durable
  **bound ownership record**, Task 0.3). Integrity restoration and replay use that immutable bundle;
  re-expansion is a *diagnostic comparison only*, never the restoration authority. (Review #11/#12.)
- **D3 — Scaffold-bound flows MUST supply authorization; absence is a deterministic orchestration error.**
  "Optional authorization, default = legacy behavior" is permitted *only* for explicitly unbound/legacy
  flows. A bound flow that omits it fails binding — enforcement can't be bypassed by missing wiring.
  (Review #21.)
- **D4 — A post-write frozen-integrity mismatch is a high-severity *system* fault** (authorization bypass /
  concurrent writer / normalization mismatch / bug), not a producer correction: restore bound bytes to
  preserve the workspace, record a high-severity enforcement fault, and **stop the attempt** unless the
  cause is a defined recoverable system-owned operation. Distinct from a producer emitting a frozen path
  (which *is* correctable). (Review #10/#16.)
- **D5 — Response-atomic = authorize the complete *normalized* artifact set before the first write.** Not
  iterate-then-rollback. Any forbidden or ambiguous path rejects the whole response; nothing is
  materialized (including staging). (Review #8.)
- **D6 — Compliance violations use a separate bounded counter.** They do **not** consume the
  implementation-convergence counter, but they **do** consume a bounded `contract_compliance_attempt`
  budget and all applicable global execution budgets — violations are not free. (Review #14.)
- **D7 — Authorization uses the same canonical target identity as materialization.** Scope: the Linux
  build sandbox — resolve `./`, `//`, `backend/../backend/…`, reject duplicate emissions normalizing to
  one target, and symlinks resolving outside the workspace or onto a frozen path. Cross-platform
  case/Unicode/trailing-dot policy is explicitly **out of scope**. (Review #9, scoped.)
- **D8 — Bound workspaces are single-writer per attempt.** The dispatched executor runs a run's tasks
  sequentially, so authorize→materialize→verify already occurs inside a single-writer boundary; the plan
  **states and confirms** this (acceptance) rather than adding a lease. If a future concurrent-producer
  path appears, it must bring authorize+materialize+verify inside one mutation boundary. (Review #17.)

---

## Phase 0 — Characterization & decisions (prove assumptions before building)

| # | Task | Files | Acceptance |
|---|------|-------|-----------|
| 0.1 | **Workspace mutation-path inventory.** ✅ **DONE** — `docs/plans/SIP-0100-phase-0-mutation-path-inventory.md` + `tests/unit/capabilities/test_sip0100_mutation_inventory.py`. **Finding: two materializers**, `test_runner._materialize_files` bypasses `materialize_artifacts` (the pf-26 path). Vault + report + PRD-seed writes classified as non-workspace. | — | inventory doc + characterization test (green). (Review #1.) |
| 0.2 | **QA test-slot ownership (D1).** ✅ **DONE** — `scaffold.qa_test_namespace(manifest)` + `is_qa_test_path(path, manifest)`: deterministic per-stack namespace (`backend/tests/`, `frontend/src/tests/`); Phase 2 authorizes QA writes against it. | `capabilities/scaffold.py` | `test_scaffold.py::test_qa_test_namespace_*` (green). |
| 0.3 | **Bound ownership record (D2).** ✅ **DONE (model)** — `BoundScaffoldRecord` + `build_bound_record(manifest, run_id, attempt_id, created_at)`: frozen paths+hashes+**bytes**, fill slots, QA namespace, manifest/contract/expander identity; frozen set derived like the contract (`expand − fill_slot_paths`). Persistence-at-bind wiring is Phase 2. | `cycles/bound_scaffold_record.py` | `test_bound_scaffold_record.py` (round-trip + bytes-for-every-frozen-path, green). |
| 0.4 | **Correction-counter characterization.** ✅ **DONE** — the current single-shared-counter behavior is characterized by `TestMaxCorrectionAttempts` (executor harness), now **marked** as the 3.4-preservation baseline (single counter; every correction consumes it; exhaustion at `max_correction_attempts`). 3.4 must keep it green for implementation-caused corrections. | `tests/unit/cycles/test_correction_runner.py` | existing exhaustion test + baseline marker (green). (Review #20.) |
| 0.5 | **Reason-code + atomicity taxonomy.** ✅ **DONE** — extended the existing `task_outcome.py` (not a parallel taxonomy): `FailureClassification.CONTRACT_COMPLIANCE` + `ContractComplianceViolation` (4 codes) + `CONTRACT_COMPLIANCE_ACTIONS` (each code → distinct disposition; only the integrity fault stops the attempt, D4). | `cycles/task_outcome.py` | `test_contract_compliance_taxonomy.py` (green). Response-atomic semantics fixed in D5. |

## Phase 1 — Harness contract (mechanical, not prompt-only)

Ordered so ownership (0.2) precedes the checks that consume it (Review #18).

| # | Task | Files | Acceptance |
|---|------|-------|-----------|
| 1.1 | **Bind the harness criterion** to QA test slots. ✅ **DONE** — `scaffold.harness_entry_modules(stack)` + `is_qa_test_path_for_stack`; `task_plan._harness_boundary_criteria` injects a `harness_boundary` `TypedCheck` (severity=error) per Python qa.test artifact in the QA namespace, in bind mode. Author mode injects none. | `scaffold.py`, `cycles/task_plan.py` | `test_task_plan_with_plan.py::TestHarnessBoundaryInjection` (bind injects / author-mode doesn't) — green. |
| 1.2 | **Generated-artifact boundary check (post-generation).** ✅ **DONE** — `harness_boundary` typed check (AST, syntax-aware): fails a QA test that imports a stack app entry module (static/from/`importlib.import_module`) or constructs the app client (`client_ctor`, default `TestClient`); stack owns `entry_modules`. Registered in `CHECK_SPECS` (auto-teaches the proposer vocabulary); runs at `patch_verification`. | `cycles/acceptance_checks.py`, `acceptance_check_spec.py` | `test_acceptance_checks.py::TestHarnessBoundary` — import-fail / ctor-fail / dynamic-import-fail / **fixture-pass / pure-unit-pass** (green). |
| 1.3 | **QA test-authoring prompt (guidance only).** ✅ **DONE** — added a "Test boundary" section to the managed `request.qa_test.test_validate` asset (v2): consume the `client` fixture, never import the app entry / construct `TestClient`. Prompt is guidance; 1.2/1.1 are the guarantee. | `prompts/request_templates/request.qa_test.test_validate.md` | prompt suite green (renders, required vars intact). |
| 1.4 | **Runner-shape harness proof.** ✅ **DONE** — materializes the scaffold and runs the fixture smoke test **through `run_generated_tests`** (the production runner, #454 PYTHONPATH), not a dev-shell `pytest`. | `test_scaffold.py::test_scaffold_harness_resolves_under_the_production_test_runner` | fixture smoke reaches assertion under the runner (green). (Review #19.) |

**Phase 1 exit:** the harness is mechanically enforced; **no surface claims lifecycle enforcement yet** (SIP-0100 §8).

## Phase 2 — Ownership & authorization spine (the core)

| # | Task | Files | Notes |
|---|------|-------|-------|
| 2.1 | ✅ **DONE** — `cycles/write_authorization.py`: `WorkspaceOwnership.from_record` (permanent: frozen paths + fill slots + QA namespace) + `WriteGrant` (transient per-producer writable set, resolved before generation; `for_dev_fill`/`for_qa` constructors, §4.4 QA-only) + `WriteAuthorization.authorize`/`authorize_response`. Decisions map to the 0.5 reason codes; `normalize_ws_path` is the shared D7 canonical identity (rejects absolute/escape, resolves `./`/`//`/`..`); response-atomic + dup-normalize rejection. | `cycles/write_authorization.py` | `test_write_authorization.py` (frozen-via-alias, qa/dev grant scoping, response-atomic, dup-normalize) — green. |
| 2.2 | **Unify the two materializers + authorize before materialize (per 0.1).** ✅ **DONE** — one `materialize(artifacts, workspace, authorization=None)` in `patch_verification.py` accepts BOTH shapes (`{name}`/`{path}`); `materialize_artifacts` and `test_runner._materialize_files` now delegate to it (covers the pf-26 workspace). With authorization it authorizes the complete set BEFORE any write (D5/D7) — forbidden/ambiguous → whole response rejected, nothing written, `MaterializeResult(authorized=False, rejected=...)`. No auth (unbound/legacy) → byte-identical prior behavior. **Wiring the auth into callers = 2.4.** | `cycles/patch_verification.py`, `handlers/test_runner.py` | `test_materialize_unified.py` (both shapes / no-auth writes / frozen-in-response rejects whole / path-safety) — green; test_runner delegation regression green. |
| 2.3 | **Post-materialize integrity verify + system-fault handling (D4).** ✅ **PRIMITIVES DONE** — `verify_frozen_integrity(workspace, record)` returns the frozen paths whose bytes changed/vanished (empty = intact; non-empty = high-severity system fault); `restore_frozen_files(workspace, record)` rewrites them from the bound record's persisted bytes (D2 authority, never re-expand). The executor *calling* verify + stopping on fault is part of 2.4's wiring. | `patch_verification.py` | `test_materialize_unified.py` (clean → tamper-detected → restored; missing-file flagged) — green. |
| 2.4 | **Bound-flow authorization guard (D3) + executor wiring — NEXT (substantial).** A scaffold-bound producing call must build `WorkspaceOwnership` from the run's bound record + resolve the per-producer `WriteGrant` + pass authorization to the fill/repair/qa materialize+verify calls; absence on a bound flow = orchestration error. **Investigation finding:** the `interface_manifest` is available at the **executor/run level** (`dispatched_flow_executor.py:345`) but the materialize call sites are in **handlers without it** (`base.py:329` has `contract=None`), and artifacts flow produce→vault(refs)→materialize — so the wiring threads the bound record (or enforces at the executor artifact-accumulation seam). This is the riskiest Phase-2 change; the core it plugs into (2.1/2.2/2.3 primitives) is done + tested. | `dispatched_flow_executor.py`, `handlers/cycle/base.py`, `handlers/test_runner.py` | acceptance §9 (frozen lifecycle). |

## Phase 3 — Repair authority & evidence (SIP-0086 coordination)

| # | Task | Files | Notes |
|---|------|-------|-------|
| 3.1 | **QA-correction write scope (§4.4).** A QA-owned correction's `WriteGrant` authorizes only QA-owned slots. | `correction_runner.py` (`_resolve_repair_target` → produce a *grant*, not a hint), `dispatched_flow_executor.py` | fixes pf-26's QA-rewrites-`main.py`. |
| 3.2 | **Delegation safeguards (Review #13).** Implementation-slot access requires an **explicit, path-bounded, single-correction** delegation issued by orchestration from the bound slot map; it can extend writable slots but **never** frozen paths, expires after one correction, and is recorded in evidence. | `correction_runner.py`, orchestration | delegation is not a broad escape hatch. |
| 3.3 | **Evidence classes (0.5 codes).** Structured `scaffold_integrity`-family evidence: producer/stage, attempted+normalized path, bound identity, expected vs attempted hash, disposition, sibling retention, whether a targeted correction was re-requested. **Separate attempted-emission from post-write integrity fault from system restoration** (Review #10). | `run_completion.py` / evidence models | distinct reason codes → distinct corrective messages. |
| 3.4 | **Compliance counter + targeted correction (D6).** A violation returns a targeted correction naming permitted slots, increments a bounded `contract_compliance_attempt` counter (not the convergence counter), still consumes global budgets, and terminates the task after the bound. | `dispatched_flow_executor.py` correction path, the SIP-0086 counter | coordinate with the loop owner (0.4 characterization first). |

## Phase 4 — Replay & integration

| # | Task | Acceptance |
|---|------|-----------|
| 4.1 | **Path/atomicity replay matrix** — frozen-only repair rejected; mixed valid+frozen → response-atomic; change-then-restore-to-identical is still a violation (attempted-emission), distinct from a byte-match with no emission; `./backend/main.py` / `backend/../backend/main.py` / dup-normalize-to-same / symlink-onto-frozen all rejected (D7). | deterministic tests. |
| 4.2 | **pf-26 replay** — the pf-26 correction pattern **cannot** mutate `backend/main.py`; the corrected QA suite reaches execution through the fixture. | replay test. |
| 4.3 | **Expander-change replay** — replay after the current expander asset changed; restoration/replay use the **persisted bound bytes** (D2), output unchanged. | replay test. |
| 4.4 | **Live integration + enforcement trace** — ≥1 live bind-mode `group_run` completes with no package-root divergence and no frozen mutation, **and** a lightweight enforcement trace (ownership-record id, artifacts evaluated, grant id, integrity result) proves the seam actually ran (Review #22). "No violation" alone is weak if the seam might have been inactive. | one clean roll + trace present. |
| 4.5 | **Legacy/unbound + no-regression** — unbound fill/repair retain current behavior; a bound flow lacking ownership fails binding (not partial enforcement); no caller silently omits authorization; capability/verification-contract/build-convergence suites green. | tests (Review #21). |

---

## Sequencing & dependencies

`Phase 0` (prove + decide) → `Phase 1` (harness contract; 0.2 gates 1.1/1.2) → `Phase 2` (2.1 grant/ownership
gates 2.2–2.4) → `Phase 3` (rides 2.x; 3.4 needs 0.4 characterization + loop-owner sign-off) → `Phase 4`.
**No surface flips to "lifecycle-enforced" until Phase 2 (2.2+2.4) lands** (SIP-0100 §8). The riskiest
change (3.4, SIP-0086 counters) is isolated behind Phase-0 characterization and the stable 2.x seam.

## Risks & open questions (reduced — most resolved by D1–D8)

- **Chokepoint completeness** is the top risk; Task 0.1 is the mitigation (prove, don't assume).
- **SIP-0086 coordination** (3.4): the compliance/implementation counter split needs the loop owner's
  sign-off; gated behind 0.4.
- **Grant resolution point:** grants are resolved *before generation* from the bound slot map; if any
  producer's authorized set isn't known pre-generation, surface it in 0.1/2.1 rather than inferring at
  materialize time.

## Promotion

Status transitions to distinguish at the end: (1) implementation merged; (2) deterministic acceptance
(Phase 4.1–4.3) green; (3) live integration (4.4) green; (4) shipped in a release; (5) SIP promoted
accepted → implemented. Promote via `update_sip_status.py` (+ROADMAP + body Status by hand — a release
step) only after (2)+(3), naming the release/version that proves deployment.
