---
title: Dispatched Flow Executor Decomposition Boundaries
status: proposed
author: jladd
created_at: '2026-07-06T00:00:00Z'
---
# SIP: Dispatched Flow Executor Decomposition Boundaries

## Status
Proposed — **revision 2** (incorporates maintainer design review: six-targets-plus-residual framing, versioned v1.3/v1.4 ledger semantics, interim-vs-final dispatch dependencies, slice-2 internal staging, RunLedger contract, resolved placement questions)

**Targets:** v1.3 (stabilization minor — primarily structural and behavior-preserving; the only intentional behavior addition is the explicitly scoped #295 plan-review validation rider, slice 6)
**Seeded by:** #186 (decompose `DispatchedFlowExecutor`), absorbing #151's targets (correction protocol, run-report generation, test-file split, error-class + agent-config in-passing wins). #185 (task-naming extraction, `adapters/cycles/task_naming.py`) already proved the extraction pattern and is the model for every slice here.
**Builds on:** SIP-0094 (ReplyRouter request/reply transport), SIP-0089 (recruitment via coordinator + FocusLease — semantics untouched), SIP-0086/0092/0070 (correction, typed acceptance, pulse verification — behavior moves, never changes), SIP-0079 (checkpoints/outcome classes).
**Constrained by:** **SIP-0096 §6.4** — the decomposition **must produce a completion collaborator that computes the run verification summary**; SIP-0096's pure aggregation function is that collaborator's first client in 1.4. This SIP shapes that seam; it does not implement SIP-0096.
**Rider:** #295 (hoist `validate_against_profile` to the plan-review gate) lands as the final slice.

---

## 1. Summary

`DispatchedFlowExecutor` (`adapters/cycles/dispatched_flow_executor.py`) has become the convergence point for dispatch, verification, correction, gate handling, completion, reporting, and per-run state: **3,358 lines / 53 methods** in one class (the #186 figures, 3,172/50, are stale), ~6× the next-largest file in `adapters/cycles/`. This SIP fixes the decomposition boundary set *before* the refactor begins, so #186/#151 converge on one design rather than a series of opportunistic extractions.

The accepted end state is **six extraction targets plus the residual executor responsibility set**:

1. **`TaskDispatcher`** — request/reply transport (dispatch, retry, heartbeat, per-task activity + Prefect task-run lifecycle).
2. **`PulseBoundaryRunner`** — boundary verification + bounded repair loop.
3. **`CorrectionRunner`** — the four-step correction protocol.
4. **`RunCompletion`** — terminal-status mapping, observability closeout, run-report generation; **the SIP-0096 §6.4 seam**.
5. **Pure hoists** — the pure static helpers move to `src/squadops/cycles/`; the duplicated control-flow error classes hoist to a shared adapter module.
6. **`RunLedger`** — an explicit per-run accumulator replacing executor-level mutable state.

The deliberately **residual** executor (§6.7) keeps orchestration only: `execute_run`/`execute_cycle`, the sequential/fan-out loops, gate boundaries, recruitment lifecycle, and cancellation.

The key architectural outcome is the **`RunCompletion` + `RunLedger` seam**: in v1.3 it preserves today's reporting/completion behavior while removing executor-level per-run state; in v1.4, SIP-0096 wires verification aggregation into that same seam without re-decomposing the executor.

The refactor is behavior-preserving except for the #295 rider, and lands strangler-style: **one collaborator per PR**, tests split with the moved code, regression suite green, and a live smoke cycle for every slice (the #152 playbook: 4,656-test regression + a smoke cycle on agents rebuilt from the branch).

---

## 2. Motivation / Problem

- **Untestable in isolation.** `_run_correction_protocol` (346 lines) cannot be unit-tested without mocking the whole executor's state (#151). The test file mirrors the problem: `tests/unit/cycles/test_dispatched_flow_executor.py` is ~3,278 lines / 19 test classes.
- **Hidden coupling through instance state.** Three mutable attributes cross concern boundaries: `_pulse_report_entries` (written by pulse verification, reset by `execute_run`, read by report generation), `_forwarding_overrides` (written by `execute_cycle`, read by `execute_run`), `_cancelled`. The first two are per-run/per-cycle state stored on a long-lived object — the pattern that makes extraction risky and concurrent-run reasoning impossible.
- **The completion seam doesn't exist.** Terminal status is set in `execute_run`'s exception handlers; verification records are persisted mid-loop; the report reads accumulated state in a `finally`. SIP-0096 §6.4 requires a completion collaborator that computes the run verification summary — today there is no single place that *could* compute it.
- **Presentation logic in an adapter.** `_generate_run_report` + the report line builders are pure formatting and belong in the domain (#151).
- **Known duplication.** `_ExecutionError`/`_CancellationError` are duplicated with `in_process_flow_executor.py`; `_resolve_agent_config`'s tuple return is destructured 7+ times in the correction loop (#151/#110).
- **The window is right.** 1.3 is the stabilization minor whose purpose is exactly this quarantined structural refactor; #152 (the same treatment for `cycle_tasks.py`) just landed cleanly with the strangler + live-validation playbook; #217 (local suite parity) and #185 (first slice) are closed.

---

## 3. Decision

1. Fix the six extraction targets plus the residual responsibility set (§6) as normative — slices converge on it; no ad-hoc splits.
2. **Behavior preservation is the prime rule** (§7): logic moves verbatim wherever possible; no message-envelope, event, registry-write, artifact-format, or `FlowExecutionPort` change.
3. Kill executor-level per-run mutable state via the **`RunLedger`** (§6.6); after decomposition the executor's only cross-run mutable attribute is `_cancelled`.
4. Shape `RunCompletion` so SIP-0096's aggregation function plugs in at 1.4 with no re-decomposition (§6.4).
5. Land strangler-style, one collaborator per PR, each with the regression suite + a live smoke cycle before merge (§8). **Intermediate slice states may use narrow callables to preserve PR ordering, but the final dependency graph must match §6** (see §6.2/§6.3 interim states).

---

## 4. Scope

- **In:** the collaborator boundaries, state rules, module placement, slicing order, and test-file split for `DispatchedFlowExecutor`; the #151 in-passing wins (shared error classes, `ResolvedAgentConfig` dataclass); the #295 rider.
- **Out (Non-Goals, §5):** everything behavioral.

## 5. Non-Goals

- **No behavior change** outside the slice-6 rider. Correction, pulse, gate, recruitment, checkpoint, and dispatch semantics are moved, not modified. Any bug found mid-slice is filed and fixed in its own PR, never silently in a move.
- **No `FlowExecutionPort` change** and no new port. The collaborators are **decomposition seams inside the existing adapter, not alternate runtime strategies** — they become ports only if and when a second concrete execution strategy exists (the defer-infra-completeness rule); #151's "port + adapter" framing is deliberately narrowed.
- **No SIP-0096 implementation.** This SIP delivers the seam; classification/aggregation/verdict land in 1.4 per SIP-0096's own phasing.
- **No fan-out redesign.** `_execute_fan_out` stays in the executor as-is.
- **No renames during the arc** — neither the #168 residue sweep (Lane-S-tracked) nor the class/module itself. Post-decomposition, `DispatchedFlowExecutor` will name a class that no longer dispatches (that's `TaskDispatcher`'s job); the honest post-arc name is an orchestrator (e.g. `RunOrchestrator`). That rename is deliberately a **standalone follow-up after the final slice** — mid-arc it would pollute every slice diff and stack a second rename debt on top of #168's unswept first one. Tracked as a named follow-up (§13 Q2).
- **No `in_process_flow_executor.py` decomposition** (341 lines; it only donates its duplicated error classes to the shared hoist).

---

## 6. The Boundary Set (normative)

Placement convention: stateful collaborators are flat modules in `adapters/cycles/` (the `task_naming.py`/`reply_router.py` precedent — the directory is small; no subpackage or shim needed since `DispatchedFlowExecutor` itself never moves). Pure logic goes to `src/squadops/cycles/`. All collaborators are constructor-injected into the executor with defaults built in the factory, mirroring the existing DI pattern.

**Observability ownership rule:** per-task observability (activity, Prefect task-run, per-task generation traces) starts and finishes in `TaskDispatcher`; per-run observability starts in the executor (`_init_run_observability`) and closes in `RunCompletion`. No other collaborator opens or closes observability scopes.

**Cancellation ownership rule:** cancellation state (`_cancelled`, written by `cancel_run`) stays on the executor. Long-running collaborators (`PulseBoundaryRunner`, `CorrectionRunner`) receive the same read-only cancellation probe the dispatcher gets, or rely on `TaskDispatcher`'s checks at dispatch/await boundaries. **No collaborator owns or mutates cancellation state.**

### 6.1 `TaskDispatcher` (adapter)

Owns the request/reply transport: `_dispatch_task`, `_dispatch_with_retry`, `_publish_and_await`, `_task_heartbeat`, `_create_task_run_if_enabled`, `_start_task_activity`, `_finish_task_activity`. Dependencies: queue, reply router, workflow tracker (task-run half), activity port, LLM observability (per-task generation), task timeout, and the executor-supplied cancellation probe. Outcome *classification/routing* (`_handle_task_outcome`) stays with the orchestration loop: it decides what the run does next, which is the executor's job.

### 6.2 `PulseBoundaryRunner` (adapter)

Owns boundary verification and the bounded repair loop: `_run_boundary_verification`, `_verify_with_repair`, `_run_pulse_evaluations`, `_evaluate_pulse_boundaries`, `_setup_pulse_context`, `_emit_pulse_event`. Dependencies: cycle registry (record persistence), event bus, LLM observability (event emission only — no scope open/close per the observability rule), the cancellation probe, and — **final state** — the `TaskDispatcher` (repair tasks dispatch through the same transport as everything else). **Interim state:** while extracted before `TaskDispatcher` exists (slice 4 < slice 5), the runner receives a narrow dispatch callable supplied by the executor; slice 5 replaces that callable with `TaskDispatcher`. Verification summaries are **appended to the `RunLedger`**, ending the `_pulse_report_entries` instance attribute. Verification exhaustion continues to surface as the same execution error the run loop already converts to `FAILED`.

### 6.3 `CorrectionRunner` (adapter)

Owns the four-step correction protocol: `_run_correction_protocol`, `_store_correction_task_artifacts`, `_checkpoint_correction_task`. Dependencies: artifact vault, cycle registry, event bus, the cancellation probe, and — **final state** — the `TaskDispatcher`. **Interim state:** slice 3 lands before `TaskDispatcher` (slice 5), so the runner receives a narrow dispatch callable from the executor, replaced in slice 5. The single biggest method in the class (346 lines) becomes independently unit-testable; its internal step decomposition is encouraged but not required by this SIP (moved-then-tidied, in that order, as separate commits).

### 6.4 `RunCompletion` (adapter) — the SIP-0096 §6.4 collaborator

Owns everything that happens once, at the end of a run:

- **Terminal-status mapping:** the exception→`RunStatus` mapping currently inlined in `execute_run`'s handlers (`_CancellationError`→CANCELLED, `_PausedError`/recruitment-rejection→PAUSED, `_ExecutionError`/unhandled→FAILED, clean exit→COMPLETED) becomes a function this collaborator owns; `execute_run` catches, delegates, and re-raises per today's contract. Persistence stays via the idempotent `_safe_transition`.
- **Observability closeout:** `_finalize_run`'s LangFuse trace close + Prefect terminal state (per the observability ownership rule above).
- **Run report:** orchestrates report generation, reading the `RunLedger`; the *formatting* moves to domain (§6.5).
- **The 1.4 socket, versioned precisely:** **in v1.3, `RunCompletion` computes the existing completion/report surface from the `RunLedger` — no new semantics.** In v1.4, SIP-0096 wires its `aggregate_verification(...)` function into this same collaborator as its first client, so the verification verdict is computed from the full set of ledger-recorded check results **without another decomposition** — satisfying SIP-0096 §6.4 with no fallback seam needed, and giving SIP-0096 AC#11 ("the roll-up is constructible only via the aggregation decision, which receives every recorded check result") its collector.

### 6.5 Pure hoists and shared adapter control types

**Domain hoists (pure, to `src/squadops/cycles/`):**

- `run_report_builder.py`: `_generate_run_report`'s markdown assembly + `_build_report_metadata_lines`, `_build_report_quality_lines`, `_build_pulse_report_lines` (the vault write stays in `RunCompletion`).
- `failure_evidence.py`: `_build_failure_evidence`, `_compose_failure_trigger`.
- `agent_config.py`: `_resolve_agent_config` returning a **`ResolvedAgentConfig` frozen dataclass** — retiring the 7+-site tuple destructuring (#151/#110) — plus `_build_agent_resolver`. **Decided:** a dedicated module, not `profile_utils.py` — this resolves an executable agent configuration for cycle execution, not generic profile parsing; keeping it separate avoids bloating `profile_utils.py`.

**Shared adapter control types (adapter-internal, NOT domain):**

- `_ExecutionError`/`_CancellationError`/`_PausedError`/`_RecruitmentRejectedError` hoist to one shared module importable by both executors (`adapters/cycles/execution_errors.py`). They are adapter-internal control flow and deliberately do not move to `src/squadops/cycles/`.

### 6.6 `RunLedger` (the state rule)

A per-run accumulator with an explicit contract:

- **Created once** at the top of `execute_run`; **passed explicitly** to the collaborators that need it — never stored on the executor or any long-lived collaborator, and **not retained by any collaborator after the call that receives it** (finalization is the last reader).
- **Append-oriented:** collaborators append verification evidence; reads happen through immutable accessors. It must not become a new bag of shared mutable state.
- **In-memory accumulator, not a persistence abstraction:** persistence remains owned by the existing registry/reporting paths.
- **Placement (decided):** `src/squadops/cycles/run_ledger.py` — a minimal domain value object with append-only mutation and immutable read accessors, so SIP-0096's pure aggregation can consume it without the domain importing adapters.
- **Contents, versioned:** v1.3 — the pulse verification summaries (today's `_pulse_report_entries`), preserving current report behavior exactly. v1.4 (SIP-0096) — every recorded check result.

Executor state rules that follow:

- After decomposition, the executor carries **no per-run or per-cycle mutable instance state**. `_forwarding_overrides` becomes an **immutable cycle-scoped value passed explicitly into each run invocation**; if a richer object is ever needed it must be constructed per cycle and passed explicitly — it must not be stored on the executor or any other long-lived collaborator (no relocating the side channel).
- `_cancelled` (cross-run, owned by `cancel_run`) is the one surviving mutable attribute, exposed to collaborators only as a read-only probe callable.

### 6.7 Executor residual

`DispatchedFlowExecutor` keeps: `execute_run`, `execute_cycle`, `cancel_run`, `_execute_sequential`, `_execute_fan_out`, `_handle_task_outcome` (routing), gate handling (`_is_gate_boundary`, `_handle_gate`, `_poll_inter_workload_gate`), recruitment/lifecycle (`_prepare_cycle_for_run`, `_init_run_observability`, `_safe_transition`, the SIP-0089 §2.5/§3.5 admission + release paths — **semantics untouched**), artifact/checkpoint plumbing (`_collect_artifacts_and_checkpoint`, `_store_artifact`, `_materialize_run_root`, `_restore_checkpoint_state`, `_seed_prior_artifacts`, `_resolve_artifact_contents`, `_enrich_envelope`, `_check_task_preconditions`).

Artifact handling is acknowledged as a possible *future* collaborator, and it is **residual-but-watched**: it remains executor-resident only for this arc, and **no new artifact responsibilities may be added to the executor during the decomposition** (the residual must shrink monotonically, never grow).

Target residual: **≤ ~1,100 lines** (from 3,358), with `execute_run` shrinking materially as the terminal-status mapping and finalization leave it.

---

## 7. Behavior-Preservation Rules (every slice)

1. Logic moves verbatim where possible; mechanical edits only (`self.` → collaborator refs, parameter threading). Tidying beyond that is a separate commit within the slice PR, so the move diff stays auditable.
2. No changes to: task envelopes, emitted events (types, payloads, ordering), registry writes, artifact names/formats, Prefect/LangFuse surfaces, `FlowExecutionPort`. (Exception: the slice-6 #295 rider, whose behavior addition is its explicit purpose.)
3. Regression suite green (captured exit code, not piped), plus **one live smoke cycle on agents rebuilt from the branch** before merge (the live-validation rule; #152 precedent).
4. **Parity note per PR:** each slice PR body includes the regression command/result, the smoke cycle identifier, and a short before/after parity note for every touched event, artifact, registry, report, and observability surface — even when the note is "unchanged."
5. **Reversibility:** each slice must be independently revertible without requiring later slices. The interim dispatch callables (§6.2/§6.3) are acceptable precisely because they preserve that reversibility, and they are removed by slice 5.
6. The C901 story must not regress silently: `dispatched_flow_executor.py` currently carries a per-file ignore. Moved-but-still-oversized methods get **targeted** per-file entries at their new home with a tracking note (the #152 `cycle/develop.py`/`qa_test.py` precedent); by the final slice the executor's own entry is expected to shrink to zero or be re-justified explicitly. `pyproject.toml` is a shared announce-before-editing file — each slice states its per-file-ignores delta in the PR body.
7. Test-file split rides the slice that extracts the code it covers (§9); assertions move unmodified except mechanical import/patch-path updates, each disclosed in the PR body.

---

## 8. Slicing Plan (one PR per slice, in order)

| Slice | Contents | Risk | Notes |
|---|---|---|---|
| **1** | Pure hoists (§6.5): report builder, failure evidence, `ResolvedAgentConfig`, shared error classes | Low | Pure moves; no state threading |
| **2** | `RunLedger` + `RunCompletion` (§6.4, §6.6): kill `_pulse_report_entries`/`_forwarding_overrides` instance state, extract finalization + terminal-status mapping | **Medium-high** | **Do early — this is the SIP-0096 seam.** Internally staged: (a) introduce ledger + explicit state threading while behavior stays executor-owned; (b) move finalization/report orchestration into `RunCompletion`; (c) move terminal-status mapping **last**, so pause/resume behavior stays auditable at each stage. Live validation includes a paused-and-resumed cycle (§11) |
| **3** | `CorrectionRunner` (§6.3) | Medium | Interim dispatch callable from the executor; re-pointed to `TaskDispatcher` in slice 5 |
| **4** | `PulseBoundaryRunner` (§6.2) | Medium-high | Largest surface; appends to the ledger from slice 2; interim dispatch callable as in slice 3 |
| **5** | `TaskDispatcher` (§6.1); `CorrectionRunner`/`PulseBoundaryRunner` interim callables replaced with the dispatcher | Medium | Transport last, so earlier slices never chase a moving target |
| **6** | **#295 rider:** invoke `ImplementationPlan.validate_against_profile` at the plan-review gate (gate handling stays executor-resident); dispatch-time check remains the final net | Low | Behavior *addition* is confined to this clearly-labeled slice — the one deliberate exception to §7.2, per #295's own acceptance criteria |

Slices 3–5 may reorder if a conflict with in-flight work demands it; slices 1–2 are fixed (everything else leans on the ledger). **If 1.3 cuts before slices 3–5 land, the release notes state which accepted boundaries are implemented versus pending; the SIP remains the governing accepted design until the arc completes** (acceptance is a design commitment, not an implementation artifact — implementation completeness gates *promotion to implemented*, never acceptance).

---

## 9. Test Plan

- Existing 19 test classes in `test_dispatched_flow_executor.py` split along the same seams as the code (`test_run_completion.py`, `test_correction_runner.py`, `test_pulse_boundary_runner.py`, `test_task_dispatcher.py`, domain tests for the hoisted modules), riding their slices.
- The monolithic test file is **retired or reduced to residual executor orchestration coverage only** (run/cycle loops, gates, recruitment, cancellation); collaborator-specific tests live with their extracted seams.
- Each collaborator gains construction-level unit tests proving it is instantiable and testable **without a `DispatchedFlowExecutor` instance** — the point of the exercise.
- New tests follow the test-quality standard (no tautologies; every new file carries error/edge cases — e.g. ledger read-before-write, completion mapping for every exception type, dispatcher timeout paths).
- Live validation per slice per §7.3; slice 2 additionally validates a paused-and-resumed cycle (§11).

---

## 10. Acceptance Criteria

1. All six extraction targets (§6.1–§6.6) exist as merged code; the executor residual matches §6.7 (no method outside the residual list remains on the class; no new artifact responsibilities were added to the residual during the arc).
2. **SIP-0096 §6.4 satisfied structurally, versioned:** in v1.3, `RunCompletion` is the single call site that reads all ledger-recorded verification/reporting entries at run end and owns the terminal outcome surface — with today's semantics exactly. The seam is shaped so that in v1.4 SIP-0096 extends the ledger to every recorded check result and wires its aggregation function into this same collaborator without touching any other collaborator. (This SIP is done when the v1.3 half holds; the v1.4 half is SIP-0096's to claim.)
3. The executor has no per-run/per-cycle mutable instance state — architecture-testable via a **focused guard** that rejects known per-run/per-cycle state on the executor and allows only explicitly allow-listed cross-run state (`_cancelled`, plus anything a future SIP explicitly adds), rather than a brittle blanket assertion over every attribute assignment.
4. Every collaborator is unit-tested without instantiating the executor; the monolithic test file is retired or reduced to residual orchestration coverage per §9.
5. Behavior preservation held: no envelope/event/registry/artifact/port surface changed across the arc (regression + live cycles + per-slice parity notes per §7.4; any intentional deviation is called out per-slice in the PR body — expected total: the #295 gate check in slice 6, nothing else).
6. `_ExecutionError`/`_CancellationError` duplication with `in_process_flow_executor.py` is gone; `_resolve_agent_config` tuple destructuring is retired for `ResolvedAgentConfig`.
7. #295's acceptance criteria met in slice 6: plan↔squad mismatch rejected at the plan-review gate with an actionable message naming the unsatisfiable capability/role; dispatch-time check retained.
8. `pyproject.toml` C901 per-file-ignores reflect reality per §7.6 (no blanket carryover; each surviving entry names its follow-up).
9. Interim dispatch callables (§6.2/§6.3) no longer exist after slice 5 — the final dependency graph matches §6.
10. #186 and #295 close via the final slices' PRs (`Closes #NNN` in bodies).

---

## 11. Risks

- **Slice 2 is the risk concentration point** — it combines state elimination, finalization extraction, and the terminal-status mapping, and terminal status touches the live-validated pause/resume semantics (duty-deferred resume #222, recruitment rejection). *Mitigation:* the mandatory internal staging (§8: ledger threading → finalization/report → status mapping last), and slice 2's live validation includes a paused-and-resumed cycle, not just a happy-path smoke.
- **Pulse repair loop is the deepest tangle** (verify→repair→re-verify→exhaust, 256+145 lines, event-ordering-sensitive telemetry tests). *Mitigation:* it goes fourth, after the ledger exists and two extraction slices have rehearsed the pattern; its telemetry tests move with assertions unmodified.
- **Concurrent in-flight work touching the file.** The file is Lane-M-owned and hot. *Mitigation:* one slice in flight at a time; each slice branches from post-merge main (the #152/#276 sequencing lesson); each slice independently revertible (§7.5).
- **Boundary set proves wrong mid-arc.** *Mitigation:* the SIP process itself — a discovered misfit returns here as a revision (the SIP-0096 Phase-0 precedent), not an ad-hoc divergence.

---

## 12. Relationships

- **SIP-0096** — §6.4's requirement is satisfied by §6.4 here (v1.3 half); slice 2 is scheduled early specifically so 1.4 Phase 1 wires into a real seam, not the fallback.
- **SIP-0089** — recruitment/coordinator/FocusLease/reserve-buffer semantics stay in the executor residual, untouched.
- **SIP-0094** — `ReplyRouter` is already the transport substrate; `TaskDispatcher` composes it, no change.
- **#152 / #332** — the direct precedent: same strangler + live-validated playbook, same release.
- **Issues:** implements #186 (and the absorbed #151); rides #295; touches-not-solves #110 (dataclass return); #168 explicitly out of scope.

---

## 13. Open Questions

1. Slice-6 timing: if 1.3 wants to cut before slice 6, #295 can slip to a 1.3.x patch (it is a fix, patch-legal) — decide at cut time.
2. Post-arc rename: once dispatch has left the class, rename `DispatchedFlowExecutor`/`dispatched_flow_executor.py` to reflect its orchestrator role (candidate: `RunOrchestrator`). Explicitly **after** the final slice, as its own PR, sequenced with (or absorbing) the #168 residue sweep so there is one rename debt, not two. `FlowExecutionPort` keeps its name — the port describes the contract, which doesn't change.

(Resolved in rev 2, formerly open: `ResolvedAgentConfig` placement → `src/squadops/cycles/agent_config.py` (§6.5); `RunLedger` placement → domain value object in `src/squadops/cycles/run_ledger.py` with append-only mutation and immutable read accessors (§6.6).)
