# SIP-0089 Phase 2 — §2.0 Pre-Implementation Spike Notes

**Status:** Read-only spike complete (2026-06-23). No code changed.
**Scope:** Identify the cycle **recruitment seam** against the **current** dispatch
path (post-SIP-0094) so the §2.5 reserve-buffer guard attaches in the right place.
**Lane:** `track:macbook` · branch `feature/sip-0089-phase-2-assignments`.

All line citations below were verified against `main` @ `af6c308` + the doc-alignment
commit on this branch.

---

## Verdict (headline answers the spike had to settle)

1. **Recruitment is IMPLICIT and bound at *plan-generation* time — not explicit, and
   not at dispatch.** No function "recruits" a roster. Each planned task carries a
   `role`; the role is resolved to a concrete `agent_id` (first *enabled* agent for
   that role in the squad profile) when the task plan is generated. The materialized
   roster lives only as `agent_id` on the `TaskEnvelope`s — there is **no
   `participating_agents` field on `Cycle` or `Run`.**

2. **The dispatch path has no admission/eligibility gate.** The executor publishes
   unconditionally to `{agent_id}_comms`. The only existing "eligibility" filter is the
   profile-level `enabled` flag applied during planning. Heartbeat status is
   observability-only and never blocks dispatch.

3. **Therefore §2.5 is greenfield**, and the right seam is the
   **plan-generation → dispatch boundary inside `execute_run()`**, *after* the roster
   materializes but *before* the dispatch loop — **not** inside the (synchronous, pure)
   domain planner.

---

## 1. Dispatch path (post-SIP-0094) — confirmed

The SIP-0094 cutover is live: the old per-run `cycle_results_{run_id}` poll loop is
gone, replaced by a long-lived per-agent subscription via `ReplyRouter`.

| Step | Where | What |
|------|-------|------|
| Resolve target agent | `src/squadops/cycles/task_plan.py:413` → `:225` | `_resolve_agent_config(profile, role)` → `agent_id` (first `enabled` agent for the role) |
| Build envelopes | `task_plan.py:328` `generate_task_plan(...)` | **synchronous, pure domain fn**; called *without* `await` at `dispatched_flow_executor.py:184` |
| Dispatch | `dispatched_flow_executor.py:619` `_dispatch_task` → `:674` `_publish_and_await` | telemetry/heartbeat wrapper, then publish+await |
| Subscribe / register / publish | `:703` `ensure_subscribed` → `:704` `register(task_id)` → publish to `:699` `f"{agent_id}_comms"` (reply via `:698` `f"{agent_id}_replies"`) | ordering `ensure_subscribed → register → publish` (D14) |
| Correlate reply | `reply_router.py:65` `ensure_subscribed`, `:92` `register`, `:121` `data["payload"]["task_id"]` → `set_result` | **`task_id` is the sole correlation key** (not `correlation_id`); one long-lived subscription per agent on `{agent_id}_replies` |

**No pre-publish admission check exists.** Closest gate is run-level
`_check_task_preconditions` (cancelled / time-budget / checkpoint-skip) — not per-agent
availability.

## 2. Recruitment model — implicit, profile-driven

- Cycle creation stores only the profile id + snapshot hash
  (`src/squadops/api/routes/cycles/cycles.py` `create_cycle`); it does **not** materialize
  a roster.
- The roster materializes at `execute_run()` time:
  `dispatched_flow_executor.py:146` resolves the profile snapshot, `:184` calls
  `generate_task_plan(...)`, which emits one `TaskEnvelope` per planned step with
  `agent_id` set.
- Enabled-role filter: `task_plan.py:354` (`{a.role for a in profile.agents if a.enabled}`).

## 3. Existing eligibility / availability gates

- **Profile `enabled` flag** — the *only* gate in the main path (`task_plan.py:354`).
- **Heartbeat** (`src/squadops/ports/observability/heartbeat.py`) — lifecycle status for
  observability; **does not** block dispatch.
- **Plan/role validation** (`src/squadops/cycles/implementation_plan.py` `validate_against_profile`)
  — authoring-time (SIP-0092), not recruitment-time.
- **No** capacity, duty-window, reserve-buffer, or interruptibility check exists.

## 4. Recommended §2.5 attachment seam

**Primary:** inside `DispatchedFlowExecutor.execute_run()`
(`adapters/cycles/dispatched_flow_executor.py:134`), **immediately after** the plan is
generated at `:184` and **before** the dispatch loop.

```
plan = generate_task_plan(cycle, run, profile, plan=implementation_plan)
# §2.5 reserve-buffer admission check goes HERE:
#   - distinct agent_ids = {e.agent_id for e in plan.envelopes}
#   - assignments = await self._assignment_port.list_active_assignments(now)
#   - for each participating agent with a HARD duty window in `in_reserve_before`/`active`
#     (per §2.1 window_state): reject → emit cycle.recruitment.rejected
#     (reason `upcoming_hard_duty_window`, per D18); soft duty may permit per recall_policy
# then proceed to dispatch
```

**Why here, not inside `generate_task_plan()` (the subagent's first pick):**

- `generate_task_plan()` is **synchronous and pure**, in the domain layer
  (`src/squadops/cycles/`). The reserve check requires an **async Postgres lookup** via
  `AssignmentPort`. Injecting an adapter + `await` into the domain planner breaks the
  hexagonal boundary the repo enforces (ports/adapters do I/O; domain stays pure).
- `execute_run()` is already `async`, already constructs/holds ports, and is the
  natural owner of the run-start admission decision and `cycle.recruitment.rejected`
  emission.
- The §2.5 "recruitment ordering" maps cleanly: **enabled-filter** (in the planner) →
  **reserve check** (`execute_run`) → **FocusLease** (Phase 3, also `execute_run`).

**Granularity:** one `list_active_assignments(now)` query, then filter to the run's
distinct participating `agent_id`s — avoids N per-agent round trips.

## 5. Greenfield checklist (what Phase 2 must create to land §2.5)

1. **`AssignmentPort` + adapter** (§2.3) — not present in the executor today.
2. **Wire the port into the executor** — add `assignment_port: AssignmentPort | None = None`
   to `DispatchedFlowExecutor.__init__` (near `:103`, alongside the existing
   `reply_router` injection) and through the factory (`adapters/cycles/factory.py`).
3. **`window_state()` helper** (§2.1) — drives the reserve decision; keep the
   reject/permit logic reading it rather than re-deriving interval math at the seam.
4. **Events/reasons** — `cycle.recruitment.rejected` + reason `upcoming_hard_duty_window`
   (D18: event ≠ reason).

## 6. Observations / follow-ups (not blocking §2.5)

- **DRY debt:** `_resolve_agent_config` is duplicated — domain copy at
  `task_plan.py:225`, mirrored static copy at `dispatched_flow_executor.py:1855` (used by
  correction paths `:2102`, `:2269`, per issue #110). If the reserve check ever needs to
  run on correction-spawned tasks too, both call sites matter. Out of scope for §2.5 but
  worth tracking.
- **`now` source:** the seam needs a clock. Prefer injecting a time source rather than
  calling `datetime.now()` inline, to keep the check testable (mirrors how the scheduler
  in §2.4 will need the same).
- **Soft-duty semantics** (§2.5 step: soft duty may permit if cycle `can_pause` matches
  `recall_policy`) need the cycle's pause capability surfaced at the seam — confirm it's
  reachable from `cycle`/`run` at `execute_run` time during implementation.
