---
title: Pulse Checks and Verification Framework
status: accepted
author: SquadOps Architecture
created_at: '2026-02-15T00:00:00Z'
sip_number: 70
updated_at: '2026-02-15T21:20:00.628108Z'
---
# SIP-0070 --- Pulse Checks and Verification Framework

**Status:** Accepted\
**Target Release:** SquadOps 0.9.9 (Tier 1), SquadOps 1.0 (full)\
**Authors:** SquadOps Architecture\
**Created:** 2026-02-15\
**Revision:** 12 (2026-02-15)

### Revision History

| Rev | Date       | Changes |
|-----|------------|---------|
| 1   | 2026-02-15 | Initial proposal |
| 2   | 2026-02-15 | Scope Tier 1 for 0.9.9; defer Tiers 2-3 to follow-up SIP. Ground agent responsibilities in concrete capability IDs. Add bounded repair retry semantics (`max_repair_attempts`). Specify CRP profiles as acceptance criteria definition path. Remove Switchboard section (deferred to future extension model SIP). Update rollout plan to match phased implementation. |
| 3   | 2026-02-15 | Terminology: replace "gate/gating/pulse gate" with "pulse check" throughout; reserve "gate" for human decision points only. Binding model: pulse-bound checks are canonical; `after_task_types` is a convenience mapping. CRP path: canonical location is `defaults.pulse_checks`. Tier 1 enforcement: add `max_check_seconds`, `max_suite_seconds`, `max_output_bytes` with defaults. Check targets: specify resolution model per check type (`url`, `container`, `command`). Repair injection: Option A — append repair tasks into current pulse, run immediately. State hygiene: no `PAUSED` for automatic verification; use telemetry events only. Consistency: `pulse_checks` (plural noun) everywhere. Add `PulseCheckDefinition` frozen dataclass as the singular domain model for one CRP `defaults.pulse_checks` entry. |
| 4   | 2026-02-15 | (A) Define `pulse_id` as the task-plan Pulse boundary identifier; `after_task_types` resolves to a concrete boundary at plan time. (B) Add deterministic multi-suite matching rules: collect all bound suites, execute in YAML declaration order, rerun only previously-failed suites after repair. (C) Fix `process_running`: check `.State.Running`; if container has healthcheck, also require `.State.Health.Status == "healthy"`; absent healthcheck treated as PASS. (D) `json_schema.schema` resolved relative to CRP profile directory; absolute paths forbidden. (E) `command_exit_code` safety: must run inside runtime container context, `shell=False`, `cwd` limited to run workspace, no host env passthrough. (F) Centralize repair-loop enforcement in executor: truncate excess repair tasks deterministically (dev > strategy > governance > data), emit `pulse_check.repair_plan_truncated` event. (G) After repair, rerun only previously-failed suites (not entire boundary). |
| 5   | 2026-02-15 | (1) Unmatched `pulse_id` emits `pulse_check.binding_skipped` telemetry event + WARN log (not silent). (2) Suite-timeout rerun: timed-out suites rerun from first check, not resume partial. (3) Rename `container` field to `container_name`; remove "service name" wording. (4) Remove unenforceable "no network access" claim; state actual 0.9.9 constraints honestly. (5) Normalize all telemetry event names to `pulse_check.*` prefix. |
| 6   | 2026-02-15 | (1) Standardize required and optional telemetry fields across all `pulse_check.*` events. (2) Add future `verification.strict_bindings` hardening knob forward reference. |
| 7   | 2026-02-15 | (1) Clarify `suite_id` telemetry field: identifies the suite definition, not the boundary; distinguish from required `pulse_id`. (2) `pulse_check.passed` is boundary-scoped (emitted once per boundary, intentionally omits `suite_id`). |
| 8   | 2026-02-15 | Add Section 5 (Verification Intent and Taxonomy): explicit intent split between pulse exit verification (guardrail) and workload close verification (proof). Add `suite_class` field to `PulseCheckDefinition` (default `"guardrail"`; `"proof"` rejected at pulse boundaries in 0.9.9). Define escalation rule: pulse PASS allows continuation, does not certify workload completion. Declare shared definition vocabulary via `AcceptanceCheck` model — placement differs, schema does not. Renumber Sections 5–17 → 6–18. Update all internal cross-references. |
| 9   | 2026-02-15 | Cadence-first pulse redefinition: (1) Abstract — replace "validated capability milestones" with cadence-bounded guardrail language. (2) Terminology — redefine Pulse as "bounded execution interval defined by cadence limits," remove "proof of capability" framing. (3) Add Section 4.1 Cadence Policy with `max_pulse_seconds` and `max_tasks_per_pulse` limits. (4) Section 6.1 — narrow "canonical" to pulse-exit guardrail verification only. (5) Section 5.2 — clarify that proof suites are authored in workload definitions, not `defaults.pulse_checks`. (6) Telemetry — simplify `suite_id` field description, remove claim that suite_id reuses pulse_id. |
| 10  | 2026-02-15 | Terminology and cadence hardening: (1) Cycle definition — ground in pulses + workloads, remove "validated milestones." (2) Pulse definition — make explicit "not an outcome container," clarify cadence-only identity. (3) Cadence Policy — add enforcement timing: between-dispatch evaluation, no preemption of in-flight tasks. (4) Fix task-count inconsistency: standardize on "dispatched" (not "completed"). (5) Plan compilation — executor is enforcement point; plan MAY annotate suggested boundaries. (6) Boundary wording — "zero or more guardrail suites may execute" (not "terminates in Check Execution Phase"). (7) Telemetry `suite_class` — add context that `proof` is rejected at pulse boundaries. |
| 11  | 2026-02-15 | (1) Cadence Policy table — bake "evaluated between dispatches" into field descriptions; remove preemption implication. (2) Section 5.2 — specify proof rejection enforcement point: CRP validation / applied-defaults load, with clear error message. (3) Pulse Check terminology — align with three-state decision model (PASS/FAIL/EXHAUSTED). (4) Abstract + Design Principles — use "pulse-exit guardrail suites" in key sentences to reinforce intent split. |
| 12  | 2026-02-15 | (1) Section 6.1 — consolidate `pulse_id` semantics, skip behavior, and `strict_bindings` future reference into single paragraph. (2) Section 6 — clarify PASS/FAIL/EXHAUSTED as boundary-level decisions; individual suites remain PASS/FAIL/SKIP. (3) Section 9.1 — add justification for truncation priority order (favors execution-oriented repairs under Tier 1 time pressure). |

------------------------------------------------------------------------

## 1. Abstract

This SIP defines the **Pulse Check Verification Framework**, a structured
mechanism for long-duration autonomous execution by SquadOps agent
squads.\
The framework adds **pulse-exit guardrail verification** to each
cadence-bounded execution interval, enforced by fast, mechanical
checks.\
It introduces acceptance criteria schemas, a safety check tier, and a
bounded repair loop that enables autonomous forward progress while preventing
error propagation.

This proposal is critical to SquadOps 1.0 because autonomous multi-hour
cycles fail not from lack of intelligence, but from lack of bounded
feedback.

------------------------------------------------------------------------

## 2. Problem Statement

Autonomous agent squads can execute tasks indefinitely. However, without
structured verification, the probability of deviation from intent
increases monotonically with runtime.

Observed failure modes in long-running LLM execution:

-   Assumption drift
-   API schema divergence
-   Silent runtime errors
-   Compounding workarounds
-   Undetected partial failures
-   Inconsistent system state

The result is "confident garbage" --- internally consistent but
externally invalid systems after long runs.

Human teams naturally correct this through rapid feedback loops.\
Autonomous teams require an explicit mechanism to replicate that
feedback.

The system therefore requires a way to:

1.  Detect reality, not opinion
2.  Prevent error amplification
3.  Preserve velocity
4.  Allow autonomous recovery

------------------------------------------------------------------------

## 3. Design Principles

### 3.1 Verification, Not Review

Pulse-exit guardrail suites must not be reasoning-heavy evaluation.\
They must be **mechanical verification signals**.

Human teams review.\
Autonomous teams sense.

### 3.2 Bounded Error Propagation

The purpose of a pulse-exit guardrail suite is not quality assurance.\
The purpose is:

> Determine whether the next work phase can safely build on the current
> state.

### 3.3 Fast Feedback

Checks must execute in seconds, not minutes. Timeouts are mandatory,
not advisory.

Target: Tier 1 pulse check suite < 30 seconds (enforced by
`max_suite_seconds`).

### 3.4 Local Recovery

Failures must trigger corrective loops inside the same pulse, not a new
cycle and not human intervention. Recovery attempts are bounded to
prevent runaway token consumption.

------------------------------------------------------------------------

## 4. Terminology

### Cycle

A mission-level objective executed through one or more pulses and one
or more workloads. Verification occurs at pulse-exit (guardrail)
boundaries and workload-close (proof) boundaries. A cycle's success is
measured by workload outcomes and system stability over time, not by
"validated milestones."

### Pulse

A **bounded execution interval** defined by cadence limits (e.g., max
runtime, max task dispatch count, optional risk caps). The executor
runs tasks during the interval, then emits a pulse boundary where
guardrail verification may run.

A Pulse is defined by cadence limits, not by scope; it is not an
outcome container and does not certify workload completion. Passing a
pulse only indicates "safe to continue," not "done."

Proof-grade verification belongs to workload close (Section 5).

### 4.1 Cadence Policy

Pulse boundaries are mechanically determined by cadence limits, not by
capability milestones. Two limits define the cadence:

| Limit                  | Type | Default | Description |
|------------------------|------|---------|-------------|
| `max_pulse_seconds`    | int  | `600`   | Maximum wall-clock time per pulse interval. Evaluated between task dispatches; when elapsed time meets or exceeds this limit, the executor closes the pulse before dispatching the next task. |
| `max_tasks_per_pulse`  | int  | `5`     | Maximum number of tasks dispatched during a single pulse interval. Evaluated between dispatches; when this count is reached, the executor closes the pulse before dispatching additional tasks. |

The executor closes a pulse when **either** limit is reached (whichever
fires first). CRP profiles may override these defaults in
`defaults.cadence_policy`.

Cadence limits are enforced between task dispatches. The executor
evaluates cadence thresholds after each task completes (or after each
dispatch decision) and closes the pulse before dispatching additional
tasks when limits would be exceeded. Cadence limits do not preempt an
in-flight task.

Plan compilation MAY annotate suggested pulse boundaries based on
cadence policy, but the executor is the enforcement point. Tasks are
executed during pulses according to runtime cadence limits; pulses are
not treated as deliverable buckets.

Cadence limits are separate from verification limits (`max_suite_seconds`,
`max_check_seconds`). Cadence defines the pulse boundary; verification
runs at that boundary.

### Task

An atomic action: file modification, tool invocation, or command
execution.

### Pulse Check

An automatic, mechanical verification suite that runs at the end of a
Pulse. Produces a boundary decision with no human involvement: PASS
(safe to continue), FAIL (repair loop entered), or EXHAUSTED (repair
attempts depleted; run fails).

### Gate

A **human decision point** where an operator approves or rejects forward
progress. Gates are defined in `task_flow_policy` (SIP-0064) and are
distinct from pulse checks. Gates require manual intervention; pulse
checks are fully automatic.

------------------------------------------------------------------------

## 5. Verification Intent and Taxonomy

The platform has two verification contexts that answer different
questions. This section defines their intents explicitly to prevent
conceptual drift between pulse exit verification and workload close
verification.

### 5.1 Intent Split

This SIP adopts an explicit intent split:

**Pulse Exit Verification** (this SIP, Tier 1 default)

- Purpose: bounded "safe-to-continue" confidence at a pulse boundary
- Nature: local, selective, non-exhaustive guardrails
- Constraints: fast, mechanical, strict time/output limits (Section 11)
- Signal: detects obvious breakage and runtime incoherence
- Does NOT claim integrated correctness or feature completeness
- Passing a pulse exit check does NOT imply workload completion

**Workload Close Verification** (existing workload acceptance, Tier 2+)

- Purpose: integrated "proof-of-done" confidence for a deliverable scope
- Nature: scenario, integration, and acceptance-grade validation
- Constraints: allowed to be heavier, composable, outcome-driven
- Signal: validates end-to-end behavior and acceptance criteria
- Required for workload lifecycle transition to DONE

This SIP will not expand pulse exit checks into integrated regression.
Pulse exit checks are guardrails. Workload close checks are proof.

### 5.2 Suite Categories

Two suite categories enforce the intent split:

| Category    | Intent            | Placement                                  | Tier    | Examples |
|-------------|-------------------|--------------------------------------------|---------|----------|
| `guardrail` | Safe to continue | Pulse boundary (`DistributedFlowExecutor`) | Tier 1  | build passes, service starts, artifact exists, lint clean |
| `proof`     | Done and correct  | Workload close (`WorkloadRunner`)          | Tier 2+ | integration tests, contract tests, e2e scenarios, data integrity |

Each `PulseCheckDefinition` carries a `suite_class` field (default:
`"guardrail"`). The executor enforces that `guardrail` suites respect
Tier 1 constraints (timeouts, no LLM, mechanical checks only). In
0.9.9, `suite_class: "proof"` is rejected if placed at a pulse
boundary; proof suites are reserved for workload close placement.

Enforcement: `suite_class="proof"` MUST be rejected during CRP
validation / applied-defaults load (preferred), or during plan
resolution before execution begins. Rejection MUST produce a clear
error indicating "proof suites are workload-bound in 0.9.9."

**Proof suite authoring:** Proof suites are defined in workload
definitions (via `WorkloadRunner` acceptance criteria), not in
`defaults.pulse_checks`. The `defaults.pulse_checks` CRP key is
exclusively for guardrail suites. This prevents authors from defining
proof suites in the pulse check schema and expecting them to be routed
to workload close verification.

### 5.3 Escalation Rule

Pulse exit verification and workload close verification form a natural
escalation ladder:

1. **Pulse exit** (every configured boundary): guardrail suites run.
   If PASS, execution proceeds to the next pulse. If FAIL, the repair
   loop is entered. Passing a pulse exit check allows the next pulse to
   begin — it does not certify the workload.

2. **Workload close** (when workload is READY_FOR_CLOSE): proof suites
   run. If PASS, the workload transitions to DONE. If FAIL, the
   workload remains open.

Pulse success never implies workload completion. It only allows
execution to proceed safely.

### 5.4 Shared Definition Vocabulary

Check definitions SHOULD be portable across pulse and workload
placements by using the same suite and check schema. The
`AcceptanceCheckEngine` and `AcceptanceCheck` model are the shared
vocabulary:

- Same check types (`file_exists`, `non_empty`, `http_status`, etc.)
- Same template resolution (`{cycle_id}`, `{run_root}`,
  `{task_id.output_name}`, `{vars.*}`)
- Same path safety enforcement (`is_relative_to()` chroot)

Placement determines when and where a suite runs. The check definition
schema does not change between placements. This prevents parallel
schema drift as both systems evolve.

> **Future bridge:** a pulse check MAY reference a workload definition
> by `workload_id` to delegate verification to `WorkloadRunner`. This
> would allow composable DAG-based verification at pulse boundaries.
> Not implemented in 0.9.9.

------------------------------------------------------------------------

## 6. Pulse Check Architecture

At pulse end, the executor emits a pulse boundary where zero or more
guardrail suites may execute (per configuration). Guardrail suites are
Tier 1 by default in 0.9.9 and provide bounded "safe-to-continue"
confidence.

Flow (when guardrail suites are configured):

1.  Pulse tasks execute within `DistributedFlowExecutor`
2.  Artifacts collected and stored in vault
3.  Guardrail suites evaluated by `AcceptanceCheckEngine`
4.  `PulseVerificationRecord` produced and persisted
5.  Decision determines next action

Decision states:

| State     | Meaning                                                            |
|-----------|--------------------------------------------------------------------|
| PASS      | Next pulse may begin                                               |
| FAIL      | Repair loop initiated (if attempts remain)                         |
| EXHAUSTED | Max repair attempts reached; run fails with `VERIFICATION_EXHAUSTED` |

PASS/FAIL/EXHAUSTED are boundary-level decisions derived from suite
outcomes and repair exhaustion. Individual suite outcomes remain
PASS/FAIL/SKIP.

### 6.1 Binding Model

**Canonical: pulse-exit guardrail checks.** Every Pulse optionally ends
with one or more guardrail check suites. The pulse boundary is the
verification boundary for safe-to-continue checks (Section 5.1). Proof
suites are not placed here; they belong to workload close verification.

`pulse_id` identifies the Pulse boundary in the task plan to which a
suite binds. In 0.9.9, a `pulse_id` that does not match any resolved
boundary causes the suite to be skipped (WARN +
`pulse_check.binding_skipped`). A future `verification.strict_bindings`
flag may upgrade this behavior to a hard plan-compilation failure.

**Convenience: `after_task_types` mapping.** CRP profiles may declare
`after_task_types` on a pulse check definition to auto-place that check
at the pulse boundary following the last matching task type. When
`after_task_types` is present, the engine resolves it to a specific
Pulse boundary at plan time and sets the effective `pulse_id` binding
accordingly. This is a shorthand — it does not create per-task checks.

Behavior for mixed task types within one pulse: `after_task_types`
matches once at the pulse boundary after all tasks in the pulse have
completed. It does not fire after each individual matching task.

### 6.2 Multi-Suite Execution at a Boundary

Multiple `PulseCheckDefinition`s may bind to the same pulse boundary
(e.g., one via explicit `pulse_id`, another via `after_task_types` that
resolves to the same boundary). The executor handles this
deterministically:

1. **Collect** all suites bound to the boundary (explicit and resolved).
2. **Order** by declaration order in the CRP YAML (array index).
3. **Execute** all suites in that order.
4. **Decide**: if any suite returns FAIL, the boundary is FAIL and the
   repair loop is entered.
5. **After repair**, rerun only the suites that previously failed (not
   the entire boundary). This preserves Tier 1 speed targets.
6. A suite that failed due to `max_suite_seconds` timeout (partial
   execution) is rerun from the first check on retry — never resumed
   from the point of interruption.
7. A boundary is PASS only when all bound suites are PASS.

### 6.3 Integration Point

Verification executes inside `DistributedFlowExecutor` between task
completion (artifact collection) and the next pulse dispatch.

Pulse checks are **fully automatic** and do not use the `PAUSED` run
state. The run remains `RUNNING` throughout verification and repair.
The `PAUSED` state is reserved exclusively for human gates (SIP-0064).

Verification progress is tracked via telemetry events (Section 13),
not state transitions.

------------------------------------------------------------------------

## 7. Acceptance Criteria Schema

Each pulse may define machine-verifiable criteria. Criteria are defined
in **CRP profiles** (Cycle Request Pack) inside `defaults.pulse_checks`,
following the same pattern used by `defaults.build_tasks` and
`defaults.plan_tasks` (SIP-0068).

### 7.1 Canonical CRP Schema Path

The canonical location is `defaults.pulse_checks` (inside the `defaults`
object). This is consistent with all other execution-shaping keys in
the CRP schema.

``` yaml
# CRP profile YAML — canonical schema
defaults:
  squad_profile_id: full-squad
  task_flow_policy:
    mode: SEQUENTIAL
    gates:                                  # human decision points
      - name: post-dev
        after_task_types: [development.implement]

  pulse_checks:                             # automatic verification
    - pulse_id: post_dev
      suite_class: guardrail
      after_task_types: [development.implement]
      max_repair_attempts: 2
      max_check_seconds: 10
      max_suite_seconds: 30
      max_output_bytes: 65536
      checks:
        - type: file_exists
          path: "{run_root}/artifacts/development.implement/*.md"
        - type: non_empty
          path: "{run_root}/artifacts/development.implement/*.md"

    - pulse_id: post_build
      suite_class: guardrail
      after_task_types: [development.build]
      max_repair_attempts: 3
      max_check_seconds: 10
      max_suite_seconds: 30
      max_output_bytes: 65536
      checks:
        - type: http_status
          url: "http://backend:8080/health"
          expected_status: 200
        - type: process_running
          container_name: backend_server
        - type: command_exit_code
          command: ["python", "-m", "pytest", "tests/smoke/", "-x"]
          cwd: "{run_root}"
          expected_exit_code: 0
```

### 7.2 Pulse Check Definition Fields

Each entry in `defaults.pulse_checks` has:

| Field                | Type       | Default       | Description |
|----------------------|------------|---------------|-------------|
| `pulse_id`           | string     | required      | Identifier of the Pulse boundary in the task plan to which this suite binds. Must match an actual boundary produced by the plan generator. |
| `suite_class`        | string     | `"guardrail"` | Suite category: `"guardrail"` (pulse-bound, Tier 1) or `"proof"` (workload-bound, Tier 2+). In 0.9.9, `"proof"` is rejected at pulse boundaries. See Section 5.2. |
| `after_task_types`   | list[str]  | `[]`          | Convenience mapping: auto-place check at pulse boundary after last matching task type |
| `max_repair_attempts`| int        | `2`           | Max repair cycles before `VERIFICATION_EXHAUSTED` |
| `max_check_seconds`  | int        | `10`          | Per-check hard timeout in seconds. Check killed and marked FAIL on expiry |
| `max_suite_seconds`  | int        | `30`          | Per-suite hard timeout in seconds. Remaining checks skipped and suite marked FAIL on expiry |
| `max_output_bytes`   | int        | `65536`       | Max captured stdout/stderr per check (64 KB). Truncated beyond limit |
| `checks`             | list[Check]| required      | Ordered list of acceptance checks |

### 7.3 Check Types

The existing `AcceptanceCheckEngine` (`src/squadops/capabilities/acceptance.py`)
provides the foundation. This is the shared definition vocabulary
(Section 5.4) — the same check types and template resolution are used
by both pulse exit suites and workload close suites. Current check types:

- `file_exists` --- artifact file exists at path
- `non_empty` --- artifact file has content
- `json_field_equals` --- JSON field matches expected value

New check types introduced by this SIP:

#### `http_status`

HTTP GET probe against a fully-qualified URL.

| Field            | Type   | Required | Description |
|------------------|--------|----------|-------------|
| `url`            | string | yes      | Full URL including scheme, host, port, path (e.g. `http://backend:8080/health`). Supports template resolution. |
| `expected_status`| int    | yes      | Expected HTTP status code |

Resolution: the `url` is used directly. Service name resolution relies
on Docker network DNS (service names resolve to container IPs within
the compose network). No separate `service:` indirection for 0.9.9.

#### `process_running`

Verify a Docker container is running (and healthy, if a healthcheck is
configured).

| Field            | Type   | Required | Description |
|------------------|--------|----------|-------------|
| `container_name` | string | yes      | Docker container name (the `container_name` value from `docker-compose.yml`). |

Check logic: the executor calls
`docker inspect <container_name> --format='{{.State.Running}}'`.

1. If `.State.Running` is not `true`, FAIL.
2. If the container defines a healthcheck (`.State.Health` is present),
   also require `.State.Health.Status == "healthy"`. If `.State.Health`
   is absent (no healthcheck configured), step 1 alone determines PASS.

Resolution for 0.9.9: explicit `container_name` lookup only.
Process-name, PID-file, or docker-compose service-name resolution
deferred to future check type variants.

#### `json_schema`

Validate a JSON document against a JSON Schema file.

| Field    | Type   | Required | Description |
|----------|--------|----------|-------------|
| `path`   | string | yes      | Path to the JSON document to validate. Supports template resolution. |
| `schema` | string | yes      | Path to the JSON Schema file, relative to the directory containing the active CRP profile file. |

`schema` is resolved relative to the CRP profile file's parent
directory. Absolute paths are forbidden and rejected at schema
validation time. The resolved path must pass `is_relative_to()` chroot
enforcement (same as existing acceptance checks).

#### `command_exit_code`

Run a command and verify its exit code.

| Field              | Type      | Required | Default | Description |
|--------------------|-----------|----------|---------|-------------|
| `command`          | list[str] | yes      | —       | Command as argv list (no implicit shell). First element is the executable. |
| `expected_exit_code`| int      | no       | `0`     | Expected exit code |
| `cwd`              | string    | no       | `"{run_root}"` | Working directory. Supports template resolution. |
| `env`              | dict[str,str] | no   | `{}`    | Additional environment variables. Only these keys are injected; the command inherits a minimal base environment (PATH, HOME, LANG). No passthrough of host env. |

**Safety constraints (Tier 1):**
- Commands MUST execute inside the runtime container context, not on
  the host. The executor invokes the command within the container's
  process namespace (e.g., via `docker exec` or equivalent).
- `shell=False` is mandatory. The `command` field is an argv list
  passed directly to the container exec mechanism (no shell
  interpolation, no glob expansion).
- `cwd` MUST resolve to a path within the run workspace root. Paths
  that escape the workspace are rejected at validation time via
  `is_relative_to()` enforcement.
- No host environment passthrough. Only `env` allowlist keys plus a
  minimal base environment (PATH, HOME, LANG) are available.
- Timeout is enforced by `max_check_seconds`.
- **Network access:** not restricted in 0.9.9. Commands inherit the
  container's network namespace. Network isolation (e.g., `--network=none`
  on container exec) is desirable but not enforced until the runtime
  supports it. Do not author checks that depend on this constraint.

All check types support template resolution (`{cycle_id}`, `{run_root}`,
`{run_id}`, `{task_id.output_name}`, `{vars.*}`).

No criteria may depend on subjective agent reasoning.

------------------------------------------------------------------------

## 8. Check Tiers

### Tier 1 --- Safety Check (Every Pulse) --- 0.9.9 Scope

Purpose: Prevent error amplification

Suite class: `guardrail` (Section 5.2). Pulse exit checks exist to
keep execution safe, not to certify completeness.

Examples:
- artifact files exist and are non-empty
- container is running
- endpoint responds with expected status
- smoke test suite passes (exit code 0)

Execution time: enforced by `max_suite_seconds` (default 30s).
Individual checks enforced by `max_check_seconds` (default 10s).
Output capture capped by `max_output_bytes` (default 64 KB).

Checks are purely mechanical: file I/O, HTTP probes, container health,
exit codes. No LLM involvement. Tier 1 checks must not block
indefinitely; timeouts are mandatory.

### Tier 2 --- Integration Check (Future SIP)

Purpose: Validate cross-component interactions

Suite class: `proof`. These checks validate integrated behavior and
belong to workload close verification (Section 5.1), not pulse exit.

Examples: API writes and UI reads, authentication flow end-to-end

Requires a scheduling policy (e.g., "every N pulses" or "after specific
pulse groups"). **Deferred to a follow-up SIP** once the Tier 1
foundation is proven stable.

### Tier 3 --- Audit Review (Future SIP)

Purpose: Reasoning and architectural evaluation

Examples: code quality analysis, architecture critique

This tier involves LLM reasoning and may include human gates for
sign-off. It has fundamentally different performance, cost, and trust
characteristics from mechanical checks. **Deferred to a follow-up SIP**
as it requires a separate design for token budget management and
evaluation prompt engineering.

------------------------------------------------------------------------

## 9. Repair Loop (Critical Behavior)

If a pulse check returns FAIL and `repair_attempts < max_repair_attempts`:

1.  Data agent analyzes failure output (`data.analyze_verification`)
2.  Lead agent performs root cause analysis (`governance.root_cause_analysis`)
3.  Strategy agent generates corrective plan (`strategy.corrective_plan`)
4.  Dev agent executes repair tasks (`development.repair`)
5.  Pulse check suite reruns

If the rerun returns PASS, execution advances to the next pulse.

If the rerun returns FAIL and `repair_attempts >= max_repair_attempts`,
the run transitions to terminal state `FAILED` with reason
`VERIFICATION_EXHAUSTED`. All repair attempt evidence (verification
records, repair task outputs) is preserved for post-mortem analysis.

### 9.1 Repair Task Injection Model

For 0.9.9, repair uses **append-and-execute**: the `strategy.corrective_plan`
handler outputs a list of repair `TaskEnvelope`s which are appended to
the current pulse's task list and dispatched immediately by the executor.

Rules:
- Repair tasks execute within the current pulse. They do not create
  new pulses or modify the plan for subsequent pulses.
- Maximum repair tasks per attempt: **4** (one per repair agent role:
  data, governance, strategy, development). The strategy agent may
  request multiple dev repair tasks, but the total is capped.
- Repair tasks cannot modify the active task plan. They are additive:
  new artifacts may replace or supplement failing artifacts, but the
  original plan tasks are not re-ordered or removed.
- Repair artifacts are stored in the vault with metadata
  `repair_attempt: N` and linked to the run via `append_artifact_refs()`.

**Enforcement point:** The executor is the single enforcement point for
all repair-loop limits (`max_repair_attempts`, max tasks per attempt,
and role-distribution caps), regardless of what the Strategy handler
outputs. If Strategy outputs more tasks than the per-attempt cap, the
executor truncates deterministically using priority order:
`development.repair` > `strategy.corrective_plan` >
`governance.root_cause_analysis` > `data.analyze_verification`. Priority
order favors execution-oriented repairs to maximize fast recovery under
Tier 1 time pressure. A `pulse_check.repair_plan_truncated`
telemetry event is emitted when truncation occurs (see Section 13).

### 9.2 Bounded Retry Semantics

Each pulse's `max_repair_attempts` (default: 2) caps the number of
repair cycles before the run fails. This prevents:

- Unbounded LLM token consumption
- Infinite repair loops on fundamentally broken state
- Silent cost accumulation

The `PulseVerificationRecord` tracks `repair_attempt_number` for each
verification pass, enabling operators to distinguish first-check
failures from repair regression.

### 9.3 Repair Loop Invariant

The system MUST NOT advance to the next pulse until PASS or EXHAUSTED.
This creates local correction rather than global failure, while
guaranteeing termination.

------------------------------------------------------------------------

## 10. Agent Responsibilities (Concrete Capability IDs)

The repair loop dispatches tasks through the existing handler system
using the standard `task_type` routing pattern. Each repair phase maps
to a concrete capability ID.

### 10.1 QA Agent (`qa.define_acceptance`)

Primary role: Define reality checks, not code critique.

- Write acceptance criteria for pulse checks
- Define expected schemas and health check endpoints
- Maintain CRP profile `defaults.pulse_checks` sections

> Note: In 0.9.9, acceptance criteria are author-defined in CRP profiles.
> Automated criteria generation by QA agent is a future enhancement.

### 10.2 Data Agent (`data.analyze_verification`)

Inputs: `PulseVerificationRecord`, prior task outputs, artifact refs

Outputs: structured failure analysis (which checks failed, what
artifacts are missing or malformed, relevant error messages)

- Analyze verification output mechanically
- Summarize pass/fail signals with evidence
- Produce structured input for root cause analysis

### 10.3 Lead Agent (`governance.root_cause_analysis`)

Inputs: Data agent's failure analysis, original PRD, task plan

Outputs: root cause assessment, recommended repair strategy

- Interpret deviation from expected state
- Determine whether failure is recoverable within the pulse
- Produce actionable repair guidance for strategy agent

### 10.4 Strategy Agent (`strategy.corrective_plan`)

Inputs: Lead agent's RCA output, original task plan, available capabilities

Outputs: list of repair `TaskEnvelope`s (max 4 per attempt) to append
to the current pulse

- Generate minimal corrective plan targeting root cause
- Scope repair to the failing pulse (no cross-pulse side effects)
- Output is a concrete task list, not prose

### 10.5 Dev Agent (`development.repair`)

Inputs: Strategy agent's corrective plan, prior artifacts, failure context

Outputs: repaired artifacts

- Execute corrective actions specified in the repair plan
- Produce replacement artifacts for the failing pulse

------------------------------------------------------------------------

## 11. Performance Considerations

Pulse checks must avoid LLM reasoning loops. This constraint follows
directly from the intent taxonomy (Section 5): pulse exit checks are
guardrails, not integrated proof. The Tier 1 time and cost limits exist
to enforce this boundary.

Prohibited inside Tier 1 checks:
- Architecture discussion
- Code critique
- Conversational analysis
- Any LLM API call

Allowed:
- File existence and content checks
- HTTP probes
- Container health checks
- Shell command execution (sandboxed, no implicit shell)
- JSON schema validation

Reason: token-bound evaluation becomes the system bottleneck. Tier 1
checks must complete within `max_suite_seconds` with zero LLM cost.

Enforcement:
- Per-check: killed after `max_check_seconds` (default 10s)
- Per-suite: remaining checks skipped after `max_suite_seconds` (default 30s)
- Per-output: stdout/stderr truncated at `max_output_bytes` (default 64 KB)
- A timed-out check is recorded as FAIL with `error: "timeout after Ns"`

The repair loop (Section 9) does involve LLM calls, but these are
bounded by `max_repair_attempts` and execute as standard task dispatches
with the same timeout and token limits as regular cycle tasks.

------------------------------------------------------------------------

## 12. Flow Executor Integration

Verification is integrated into `DistributedFlowExecutor` at the task
dispatch boundary. No new orchestration abstraction is required.

### 12.1 Sequential Mode Integration

```
for each pulse in task_plan:
    dispatch pulse tasks
    collect artifacts
    if pulse boundary has pulse_checks bound:
        collect all bound suites (YAML order)
        run all suites                             # <-- new
        failed_suites = [s for s in suites if s.FAIL]
        while failed_suites and attempts < max_repair_attempts:
            append + dispatch repair tasks         # <-- new
            rerun only failed_suites               # <-- new
            failed_suites = [s for s in failed_suites if s.FAIL]
        if failed_suites: fail run (EXHAUSTED)     # <-- new
    if pulse has human gate:
        pause for gate decision                    # existing behavior (PAUSED state)
```

Pulse checks execute entirely within the `RUNNING` state. No state
transition occurs for verification. The run only transitions to `PAUSED`
if a human gate follows the pulse check and requires manual approval.

### 12.2 Extension Model (Future)

A plugin-based extension model (e.g., hooks for `on_pulse_check_pass`,
`on_pulse_check_fail`) is desirable for custom verification providers
but is **out of scope for this SIP**. The initial implementation uses
direct integration in the flow executor. A future SIP may introduce an
extension point model.

------------------------------------------------------------------------

## 13. Telemetry and RCA

For each pulse check the system emits structured telemetry events via
`LLMObservabilityPort.record_event()`.

### 13.1 Standard Event Fields

All `pulse_check.*` events carry a common field set to prevent schema
drift across implementations.

**Required fields (present on every event):**

| Field        | Type     | Description |
|--------------|----------|-------------|
| `cycle_id`   | string   | Cycle identifier |
| `run_id`     | string   | Run identifier |
| `pulse_id`   | string   | Pulse boundary identifier |
| `timestamp`  | datetime | Event timestamp (UTC) |

**Optional fields (present when relevant to the event):**

| Field                    | Type   | Description |
|--------------------------|--------|-------------|
| `suite_id`               | string | Identifier of the specific suite definition within a boundary. Distinguishes individual suites when multiple bind to the same `pulse_id` boundary. Format is implementation-defined (e.g., `{pulse_id}:{index}` or a user-supplied label). |
| `suite_class`            | string | Category of the executed suite (expected `guardrail` for pulse checks in 0.9.9; `proof` is workload-bound and rejected at pulse boundaries) |
| `check_id`               | string | Individual check identifier within a suite |
| `repair_attempt_number`  | int    | Current repair attempt (0 = initial check) |
| `status`                 | string | `PASS`, `FAIL`, or `SKIP` |
| `reason_code`            | string | Machine-readable reason (e.g., `unmatched_pulse_id`, `timeout`, `exit_code_mismatch`, `task_cap_exceeded`) |

### 13.2 Event Catalog

| Event Name                         | Emitted When                                 | Notable Optional Fields |
|------------------------------------|----------------------------------------------|------------------------|
| `pulse_check.binding_skipped`      | Suite `pulse_id` unmatched; suite skipped    | `reason_code`, `status=SKIP` |
| `pulse_check.started`              | Check suite begins evaluation                | `suite_id`, `suite_class` |
| `pulse_check.passed`               | All suites at boundary pass (boundary-scoped; emitted once per boundary, intentionally omits `suite_id`) | `status=PASS` |
| `pulse_check.failed`               | One or more suites fail                      | `status=FAIL`, `reason_code` |
| `pulse_check.repair_started`       | Repair loop begins (attempt N)               | `repair_attempt_number` |
| `pulse_check.repair_plan_truncated`| Strategy output exceeded task cap; truncated | `reason_code=task_cap_exceeded` |
| `pulse_check.exhausted`            | Max repair attempts reached; run will fail   | `repair_attempt_number`, `status=FAIL` |

The full `PulseVerificationRecord` is persisted via
`CycleRegistryPort.record_pulse_verification()` and contains:

-   acceptance criteria evaluated
-   per-check results (pass/fail with error messages and truncated output)
-   overall decision state (PASS / FAIL / EXHAUSTED)
-   repair attempt number
-   repair task refs (if repair loop executed)
-   timestamps

This enables deterministic root cause analysis: operators can trace
exactly which check failed, what the repair loop attempted, and why
the run ultimately succeeded or was exhausted.

------------------------------------------------------------------------

## 14. Domain Model Additions

### 14.1 PulseCheckDefinition

A single entry in `defaults.pulse_checks`. Deserialized from the CRP
profile and stored in `applied_defaults` on the `Cycle` model.

``` python
@dataclass(frozen=True)
class PulseCheckDefinition:
    """A pulse check suite definition from a CRP profile.

    pulse_id: identifier of the Pulse boundary in the task plan to
    which this suite binds. Must correspond to an actual boundary
    produced by the task plan generator.

    suite_class: verification intent category. "guardrail" for pulse
    exit (Tier 1, fast, mechanical). "proof" for workload close
    (Tier 2+, integrated). See Section 5.2.
    """
    pulse_id: str
    checks: tuple[AcceptanceCheck, ...]
    suite_class: str = "guardrail"
    after_task_types: tuple[str, ...] = ()
    max_repair_attempts: int = 2
    max_check_seconds: int = 10
    max_suite_seconds: int = 30
    max_output_bytes: int = 65536
```

When `after_task_types` is present, the task plan generator resolves it
to a concrete Pulse boundary at plan time and sets `pulse_id`
accordingly. An unmatched `pulse_id` causes the suite to be skipped
with a `pulse_check.binding_skipped` telemetry event (see Section 13).

### 14.2 PulseVerificationRecord

``` python
@dataclass(frozen=True)
class PulseVerificationRecord:
    pulse_id: str
    run_id: str
    check_results: tuple[AcceptanceResult, ...]
    decision: str          # "PASS", "FAIL", "EXHAUSTED"
    repair_attempt_number: int
    recorded_at: datetime
    repair_task_refs: tuple[str, ...] = ()   # task_ids from repair loop
    notes: str | None = None
```

### 14.3 CycleRegistryPort Extension

``` python
@abstractmethod
async def record_pulse_verification(
    self, run_id: str, record: PulseVerificationRecord
) -> Run:
    """Persist a pulse verification record for a run."""
```

### 14.4 AcceptanceCheckEngine Extension

New `CheckType` enum values: `http_status`, `process_running`,
`json_schema`, `command_exit_code`. Each implemented as a pure function
in the existing acceptance module.

All models follow the frozen dataclass pattern with
`dataclasses.replace()` for mutation, consistent with Cycle/Run/Gate
domain models.

### 14.5 CRP Schema Extension

`_APPLIED_DEFAULTS_EXTRA_KEYS` updated to include `"pulse_checks"`
alongside existing `"build_tasks"` and `"plan_tasks"`. The CRP schema
validator accepts `defaults.pulse_checks` as a valid key and passes
it through to `applied_defaults` on the `Cycle` model.

------------------------------------------------------------------------

## 15. Expected Impact

Without Pulse Checks: Long-run success probability decreases
exponentially with runtime.

With Pulse Checks: Error propagation becomes bounded and recoverable.

This transforms SquadOps from: > task automation

into: > controlled autonomy

------------------------------------------------------------------------

## 16. Backwards Compatibility

Existing cycles continue to operate.\
Cycles without `defaults.pulse_checks` in their CRP profile skip
verification entirely and behave identically to current behavior.

Long-running cycles without pulse checks are considered unsupported
for SquadOps 1.0 autonomy guarantees.

------------------------------------------------------------------------

## 17. Rollout Plan

### Phase 1: Domain Models and Acceptance Extensions (0.9.9)

1.  `PulseCheckDefinition` and `PulseVerificationRecord` frozen dataclasses
2.  `suite_class` field with `"guardrail"` default and `"proof"` rejection
    at pulse boundaries
3.  New `CheckType` variants (`http_status`, `process_running`,
    `json_schema`, `command_exit_code`) with per-type field validation
4.  CRP schema extension: `defaults.pulse_checks` key in
    `_APPLIED_DEFAULTS_EXTRA_KEYS`
5.  `CycleRegistryPort.record_pulse_verification()` in port and adapters
6.  Timeout and output-limit enforcement in check runner

### Phase 2: Verification Runner (0.9.9)

1.  Pulse check suite runner in `DistributedFlowExecutor`
2.  Integration with artifact collection and pulse boundaries
3.  `suite_class` enforcement (reject `"proof"` at pulse boundaries)
4.  Telemetry event emission (`pulse_check.started/passed/failed`)
5.  Unit and contract tests for verification flow

### Phase 3: Repair Loop (0.9.9)

1.  Repair capability handlers (`data.analyze_verification`,
    `governance.root_cause_analysis`, `strategy.corrective_plan`,
    `development.repair`)
2.  Append-and-execute injection model (max 4 tasks per attempt)
3.  Bounded retry logic with `max_repair_attempts`
4.  `VERIFICATION_EXHAUSTED` terminal handling
5.  Telemetry events (`pulse_check.repair_started/exhausted`)
6.  Integration tests for repair scenarios

### Phase 4: CRP Profiles and Documentation (0.9.9)

1.  Reference CRP profiles with `defaults.pulse_checks` enabled
2.  End-to-end integration tests
3.  Operator documentation for acceptance criteria authoring
4.  Documentation of guardrail vs proof intent taxonomy

### Future: Tiers 2-3, Workload Bridge, and Extension Model

-   Tier 2 integration checks (scheduling policy, cross-pulse checks)
-   Tier 3 audit reviews (LLM-based evaluation, human gates, token
    budget management)
-   Workload bridge: pulse check type `workload` that delegates to
    `WorkloadRunner` for DAG-based verification at pulse boundaries
-   Extension model for custom verification providers

------------------------------------------------------------------------

## 18. Conclusion

Autonomous execution requires feedback loops.\
Human teams possess implicit feedback through observation.\
Agent teams require explicit feedback through verification.

Pulse Checks provide the minimal mechanism necessary for safe multi-hour
autonomous operation.

This is not a productivity feature.

It is the reliability foundation of SquadOps 1.0.
