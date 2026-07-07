---
title: Dispatched Flow Executor Decomposition Boundaries
status: proposed
author: jladd
created_at: '2026-07-06T00:00:00Z'
---
# SIP: Dispatched Flow Executor Decomposition Boundaries

## Status
Proposed

**Targets:** v1.3 (stabilization minor — this is a structural refactor, the release's stated purpose; feature-free by construction)
**Seeded by:** #186 (decompose `DispatchedFlowExecutor`), absorbing #151's targets (correction protocol, run-report generation, test-file split, error-class + agent-config in-passing wins). #185 (task-naming extraction, `adapters/cycles/task_naming.py`) already proved the extraction pattern and is the model for every slice here.
**Builds on:** SIP-0094 (ReplyRouter request/reply transport), SIP-0089 (recruitment via coordinator + FocusLease — semantics untouched), SIP-0086/0092/0070 (correction, typed acceptance, pulse verification — behavior moves, never changes), SIP-0079 (checkpoints/outcome classes).
**Constrained by:** **SIP-0096 §6.4** — the decomposition **must produce a completion collaborator that computes the run verification summary**; SIP-0096's pure aggregation function is that collaborator's first client in 1.4. This SIP shapes that seam; it does not implement SIP-0096.
**Rider:** #295 (hoist `validate_against_profile` to the plan-review gate) lands as the final slice.

---

## 1. Summary

`adapters/cycles/dispatched_flow_executor.py` is **3,358 lines / 53 methods** in one class (the #186 figures, 3,172/50, are stale) — the entire dispatch/verification/correction/gate/report surface tangled into the run loop, ~6× the next-largest file in `adapters/cycles/`. Per the #186 governance note, the extractions must converge on one design rather than ad-hoc splits.

This SIP **fixes the collaborator boundary set** before any slice lands:

1. **`TaskDispatcher`** — request/reply transport (dispatch, retry, heartbeat, activity + Prefect task-run lifecycle).
2. **`PulseBoundaryRunner`** — boundary verification + bounded repair loop.
3. **`CorrectionRunner`** — the four-step correction protocol.
4. **`RunCompletion`** — terminal-status mapping, observability closeout, run-report generation; **the SIP-0096 §6.4 seam**.
5. **Domain hoists** — the pure static helpers move to `src/squadops/cycles/`.
6. **`RunLedger`** — an explicit per-run accumulator replacing executor-level mutable state.

The executor keeps only orchestration: `execute_run`/`execute_cycle`, the sequential/fan-out loops, gate boundaries, recruitment lifecycle, and cancellation. Strangler-style, **one collaborator per PR**, behavior-preserving, each slice live-validated (the #152 playbook: 4,656-test regression + a smoke cycle on agents rebuilt from the branch).

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

1. Fix the six-part boundary set (§6) as normative — slices converge on it; no ad-hoc splits.
2. **Behavior preservation is the prime rule** (§7): logic moves verbatim wherever possible; no message-envelope, event, registry-write, artifact-format, or `FlowExecutionPort` change.
3. Kill executor-level per-run mutable state via the **`RunLedger`** (§6.6); after decomposition the executor's only cross-run mutable attribute is `_cancelled`.
4. Shape `RunCompletion` so SIP-0096's aggregation function plugs in at 1.4 with no re-decomposition (§6.4).
5. Land strangler-style, one collaborator per PR, each with the regression suite + a live smoke cycle before merge (§8).

---

## 4. Scope

- **In:** the collaborator boundaries, state rules, module placement, slicing order, and test-file split for `DispatchedFlowExecutor`; the #151 in-passing wins (shared error classes, `ResolvedAgentConfig` dataclass); the #295 rider.
- **Out (Non-Goals, §5):** everything behavioral.

## 5. Non-Goals

- **No behavior change.** Correction, pulse, gate, recruitment, checkpoint, and dispatch semantics are moved, not modified. Any bug found mid-slice is filed and fixed in its own PR, never silently in a move.
- **No `FlowExecutionPort` change** and no new port. `CorrectionRunner` et al. are plain injected collaborators, not ports — there is no concrete second implementation to justify port ceremony (the defer-infra-completeness rule); #151's "port + adapter" framing is deliberately narrowed.
- **No SIP-0096 implementation.** This SIP delivers the seam; classification/aggregation/verdict land in 1.4 per SIP-0096's own phasing.
- **No fan-out redesign.** `_execute_fan_out` stays in the executor as-is.
- **No rename sweeps** (#168 residue is Lane-S-tracked, out of scope).
- **No `in_process_flow_executor.py` decomposition** (341 lines; it only donates its duplicated error classes to the shared hoist).

---

## 6. The Boundary Set (normative)

Placement convention: stateful collaborators are flat modules in `adapters/cycles/` (the `task_naming.py`/`reply_router.py` precedent — the directory is small; no subpackage or shim needed since `DispatchedFlowExecutor` itself never moves). Pure logic goes to `src/squadops/cycles/`. All collaborators are constructor-injected into the executor with defaults built in the factory, mirroring the existing DI pattern.

### 6.1 `TaskDispatcher` (adapter)

Owns the request/reply transport: `_dispatch_task`, `_dispatch_with_retry`, `_publish_and_await`, `_task_heartbeat`, `_create_task_run_if_enabled`, `_start_task_activity`, `_finish_task_activity`. Dependencies: queue, reply router, workflow tracker (task-run half), activity port, LLM observability (per-task generation), task timeout. Cancellation is checked through a probe callable supplied by the executor (which retains `_cancelled`) — the dispatcher never owns cancellation state. Outcome *classification/routing* (`_handle_task_outcome`) stays with the orchestration loop: it decides what the run does next, which is the executor's job.

### 6.2 `PulseBoundaryRunner` (adapter)

Owns boundary verification and the bounded repair loop: `_run_boundary_verification`, `_verify_with_repair`, `_run_pulse_evaluations`, `_evaluate_pulse_boundaries`, `_setup_pulse_context`, `_emit_pulse_event`. Dependencies: cycle registry (record persistence), event bus, LLM observability, and the `TaskDispatcher` (repair tasks dispatch through the same transport as everything else). Verification summaries are **written to the `RunLedger`**, ending the `_pulse_report_entries` instance attribute. Verification exhaustion continues to surface as the same execution error the run loop already converts to `FAILED`.

### 6.3 `CorrectionRunner` (adapter)

Owns the four-step correction protocol: `_run_correction_protocol`, `_store_correction_task_artifacts`, `_checkpoint_correction_task`. Dependencies: artifact vault, cycle registry, event bus, and the `TaskDispatcher`. The single biggest method in the class (346 lines) becomes independently unit-testable; its internal step decomposition is encouraged but not required by this SIP (moved-then-tidied, in that order, as separate commits).

### 6.4 `RunCompletion` (adapter) — the SIP-0096 §6.4 collaborator

Owns everything that happens once, at the end of a run:

- **Terminal-status mapping:** the exception→`RunStatus` mapping currently inlined in `execute_run`'s handlers (`_CancellationError`→CANCELLED, `_PausedError`/recruitment-rejection→PAUSED, `_ExecutionError`/unhandled→FAILED, clean exit→COMPLETED) becomes a function this collaborator owns; `execute_run` catches, delegates, and re-raises per today's contract. Persistence stays via the idempotent `_safe_transition`.
- **Observability closeout:** `_finalize_run`'s LangFuse trace close + Prefect terminal state.
- **Run report:** orchestrates report generation, reading the `RunLedger`; the *formatting* moves to domain (§6.5).
- **The 1.4 socket:** `RunCompletion.finalize(ledger, ...)` is the single place that sees every recorded verification result at run end. SIP-0096 Phase 1 wires `aggregate_verification(...)` here as this collaborator's first client — satisfying §6.4 with no fallback seam needed, and satisfying SIP-0096 AC#11's "the roll-up is constructible only via the aggregation decision, which receives every recorded check result" because the ledger is the collector.

### 6.5 Domain hoists (pure, to `src/squadops/cycles/`)

- `run_report_builder.py`: `_generate_run_report`'s markdown assembly + `_build_report_metadata_lines`, `_build_report_quality_lines`, `_build_pulse_report_lines` (the vault write stays in `RunCompletion`).
- `failure_evidence.py`: `_build_failure_evidence`, `_compose_failure_trigger`.
- `agent_config.py` (or fold into `profile_utils.py`): `_resolve_agent_config` returning a **`ResolvedAgentConfig` frozen dataclass** — retiring the 7+-site tuple destructuring (#151/#110) — plus `_build_agent_resolver`.
- `_ExecutionError`/`_CancellationError`/`_PausedError`/`_RecruitmentRejectedError` hoist to one shared module importable by both executors (placement candidate: `adapters/cycles/execution_errors.py`; they are adapter-internal control flow, not domain).

### 6.6 `RunLedger` (the state rule)

A per-run mutable accumulator **created at the top of `execute_run` and passed explicitly** to the collaborators that need it. v1.3 contents: the pulse verification summaries (today's `_pulse_report_entries`). v1.4 (SIP-0096): every recorded check result. Rules:

- After decomposition, the executor carries **no per-run or per-cycle mutable instance state**. `_forwarding_overrides` becomes an explicit parameter threaded from `execute_cycle` into `execute_run` (or its cycle-scoped equivalent object); `_pulse_report_entries` dies into the ledger.
- `_cancelled` (cross-run, owned by `cancel_run`) is the one surviving mutable attribute, exposed to collaborators only as a probe callable.

### 6.7 Executor residual

`DispatchedFlowExecutor` keeps: `execute_run`, `execute_cycle`, `cancel_run`, `_execute_sequential`, `_execute_fan_out`, `_handle_task_outcome` (routing), gate handling (`_is_gate_boundary`, `_handle_gate`, `_poll_inter_workload_gate`), recruitment/lifecycle (`_prepare_cycle_for_run`, `_init_run_observability`, `_safe_transition`, the SIP-0089 §2.5/§3.5 admission + release paths — **semantics untouched**), artifact/checkpoint plumbing (`_collect_artifacts_and_checkpoint`, `_store_artifact`, `_materialize_run_root`, `_restore_checkpoint_state`, `_seed_prior_artifacts`, `_resolve_artifact_contents`, `_enrich_envelope`, `_check_task_preconditions`). Artifact handling is acknowledged as a possible *future* collaborator; it is deliberately not sliced here (six boundaries is the convergence target, not the maximum ever).

Target residual: **≤ ~1,100 lines** (from 3,358), with `execute_run` shrinking materially as the terminal-status mapping and finalization leave it.

---

## 7. Behavior-Preservation Rules (every slice)

1. Logic moves verbatim where possible; mechanical edits only (`self.` → collaborator refs, parameter threading). Tidying beyond that is a separate commit within the slice PR, so the move diff stays auditable.
2. No changes to: task envelopes, emitted events (types, payloads, ordering), registry writes, artifact names/formats, Prefect/LangFuse surfaces, `FlowExecutionPort`.
3. Regression suite green (captured exit code, not piped), plus **one live smoke cycle on agents rebuilt from the branch** before merge (the live-validation rule; #152 precedent).
4. The C901 story must not regress silently: `dispatched_flow_executor.py` currently carries a per-file ignore. Moved-but-still-oversized methods get **targeted** per-file entries at their new home with a tracking note (the #152 `cycle/develop.py`/`qa_test.py` precedent); by the final slice the executor's own entry is expected to shrink to zero or be re-justified explicitly. `pyproject.toml` is a shared announce-before-editing file — each slice states its per-file-ignores delta in the PR body.
5. Test-file split rides the slice that extracts the code it covers (§9); assertions move unmodified except mechanical import/patch-path updates, each disclosed in the PR body.

---

## 8. Slicing Plan (one PR per slice, in order)

| Slice | Contents | Risk | Notes |
|---|---|---|---|
| **1** | Domain hoists (§6.5): report builder, failure evidence, `ResolvedAgentConfig`, shared error classes | Low | Pure moves; no state threading |
| **2** | `RunLedger` + `RunCompletion` (§6.4, §6.6): kill `_pulse_report_entries`/`_forwarding_overrides` instance state, extract finalization + terminal-status mapping | Medium | **Do early — this is the SIP-0096 seam; 1.4 Phase 1 depends on it existing** |
| **3** | `CorrectionRunner` (§6.3) | Medium | Depends on nothing new; dispatch stays via executor until slice 5, then re-points |
| **4** | `PulseBoundaryRunner` (§6.2) | Medium-high | Largest surface; writes to the ledger from slice 2 |
| **5** | `TaskDispatcher` (§6.1); `CorrectionRunner`/`PulseBoundaryRunner` re-point their dispatch dependency | Medium | Transport last, so earlier slices never chase a moving target |
| **6** | **#295 rider:** invoke `ImplementationPlan.validate_against_profile` at the plan-review gate (gate handling stays executor-resident); dispatch-time check remains the final net | Low | Behavior *addition* is confined to this clearly-labeled slice — the one deliberate exception to §7.2, per #295's own acceptance criteria |

Slices 3–5 may reorder if a conflict with in-flight work demands it; slices 1–2 are fixed (everything else leans on the ledger). If 1.3 must cut before slices 3–5 land, the release notes state which boundaries are realized vs pending — the SIP stays `accepted` until all slices merge.

---

## 9. Test Plan

- Existing 19 test classes in `test_dispatched_flow_executor.py` split along the same seams as the code (`test_run_completion.py`, `test_correction_runner.py`, `test_pulse_boundary_runner.py`, `test_task_dispatcher.py`, domain tests for the hoisted modules), riding their slices.
- Each collaborator gains construction-level unit tests proving it is instantiable and testable **without a `DispatchedFlowExecutor` instance** — the point of the exercise.
- New tests follow the test-quality standard (no tautologies; every new file carries error/edge cases — e.g. ledger read-before-write, completion mapping for every exception type, dispatcher timeout paths).
- Live validation per slice per §7.3.

---

## 10. Acceptance Criteria

1. All six boundaries (§6.1–§6.6) exist as merged code; the executor residual matches §6.7 (no method outside the residual list remains on the class).
2. **SIP-0096 §6.4 satisfied structurally:** `RunCompletion` computes/owns the run's terminal outcome surface and is the single call site that sees all ledger-recorded verification results at run end; SIP-0096's aggregation function can be wired there without touching any other collaborator.
3. The executor has no per-run/per-cycle mutable instance state; `_cancelled` is the only surviving mutable attribute (architecture-testable: assert the set of instance attributes assigned outside `__init__`).
4. Every collaborator is unit-tested without instantiating the executor; the monolithic test file is retired (fully split).
5. Behavior preservation held: no envelope/event/registry/artifact/port surface changed across the arc (regression + live cycles per slice; any intentional deviation is called out per-slice in the PR body — expected total: the #295 gate check in slice 6, nothing else).
6. `_ExecutionError`/`_CancellationError` duplication with `in_process_flow_executor.py` is gone; `_resolve_agent_config` tuple destructuring is retired for `ResolvedAgentConfig`.
7. #295's acceptance criteria met in slice 6: plan↔squad mismatch rejected at the plan-review gate with an actionable message naming the unsatisfiable capability/role; dispatch-time check retained.
8. `pyproject.toml` C901 per-file-ignores reflect reality per §7.4 (no blanket carryover; each surviving entry names its follow-up).
9. #186 and #295 close via the final slices' PRs (`Closes #NNN` in bodies).

---

## 11. Risks

- **Moving the terminal-status mapping perturbs pause/resume.** The PAUSED paths (duty-deferred resume #222, recruitment rejection) are live-validated behaviors. *Mitigation:* slice 2's live validation includes a paused-and-resumed cycle, not just a happy-path smoke.
- **Pulse repair loop is the deepest tangle** (verify→repair→re-verify→exhaust, 256+145 lines, event-ordering-sensitive telemetry tests). *Mitigation:* it goes fourth, after the ledger exists and two extraction slices have rehearsed the pattern; its telemetry tests move with assertions unmodified.
- **Concurrent in-flight work touching the file.** The file is Lane-M-owned and hot. *Mitigation:* one slice in flight at a time; each slice branches from post-merge main (the #152/#276 sequencing lesson).
- **Boundary set proves wrong mid-arc.** *Mitigation:* the SIP process itself — a discovered misfit returns here as a revision (the SIP-0096 Phase-0 precedent), not an ad-hoc divergence.

---

## 12. Relationships

- **SIP-0096** — §6.4's requirement is satisfied by §6.4 here; slice 2 is scheduled early specifically so 1.4 Phase 1 wires into a real seam, not the fallback.
- **SIP-0089** — recruitment/coordinator/FocusLease/reserve-buffer semantics stay in the executor residual, untouched.
- **SIP-0094** — `ReplyRouter` is already the transport substrate; `TaskDispatcher` composes it, no change.
- **#152 / #332** — the direct precedent: same strangler + shim-free live-validated playbook, same release.
- **Issues:** implements #186 (and the absorbed #151); rides #295; touches-not-solves #110 (dataclass return); #168 explicitly out of scope.

---

## 13. Open Questions

1. Should `_build_agent_resolver`/`_resolve_agent_config` land in a new `cycles/agent_config.py` or fold into the existing `profile_utils.py`? (Decide in slice 1 review; no downstream coupling.)
2. Does `RunLedger` live adapter-side or in domain? Leaning **domain** (`src/squadops/cycles/run_ledger.py`) since SIP-0096's pure aggregation consumes it and domain must not import adapters.
3. Slice-6 timing: if 1.3 wants to cut before slice 6, #295 can slip to a 1.3.x patch (it is a fix, patch-legal) — decide at cut time.
