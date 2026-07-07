# 1.3.x Two-Lane Execution Plan (Stabilization)

**Established:** 2026-07-04 · succeeds `1-1-x-two-lane-plan.md` · governed by the
even/odd convention (#281): **1.3 is a stabilization release — feature-free by rule.**

1.3.0 is the first **stabilization** minor. Its purpose is to land the big, *risky
structural refactors* that were deliberately quarantined out of the 1.2 feature release
(so a regression is unambiguously the refactor, not a feature) plus accumulated debt.
No feature SIPs. Substance gates the cut, not the clock.

## The stabilization twist (read this first)

1.3 **inverts** the usual lane balance. In feature minors, Lane M ships features and
Lane S hardens. In 1.3, the risky structural refactors are the *product*, and they are
**split across both lanes** — so both lanes are doing stabilization work at once, and the
collision matrix matters more than usual.

| # | Lane | Surface | Notes |
|---|------|---------|-------|
| **#186** decompose `DispatchedFlowExecutor` | **M** | `adapters/cycles/dispatched_flow_executor.py` (3,358 lines / 53 methods) | 100% Mac-internal — no Spark contention. **Boundary SIP ACCEPTED 2026-07-06: SIP-0097** (PR #340); now slicing (6 slices, #295 rides as slice 6). |
| ~~**#152** split `cycle_tasks.py`~~ | **M** | `capabilities/handlers/cycle/` package | **DONE 2026-07-06** — #332 hoist (PR #338) then package split + compat shim (PR #339, merge `b59f4ef`); live-validated. #276 gate was satisfied by PRs #289/#290. |
| **#295** hoist `validate_against_profile` | **M** | plan-review gate | Rides #186 (finishes SIP-0095's materialized-plan half / #172). |
| **#234** de-leak `DbRuntime` port | **S → M** (2026-07-07) | `ports/` + postgres adapter | Port leaks sqlalchemy vendor types / shaped to legacy backend. **Reassigned to Mac lane** (Spark offline, no in-flight contention; see issue comment). Filler item — no sequencing dependency; audit-first, keep-or-kill decision ratified before any deletion. |
| **#323** comms poll→push consumer | **S → M** (2026-07-07) | `adapters/comms/*` | Replace 1s open/close `consume()` with the persistent `subscribe()` push consumer; removes churn + up-to-1s latency + the `aio_pika` "closing" INFO flood. **Reassigned to Mac lane** (see issue comment); picks up after SIP-0097 slice 2, own branch + live validation. |

## Coordination rules (carried over from 1.1.x — still in force)

1. **Issue-first, branch-first.** Reference a GH issue in every commit/PR; branch off
   `main`; incremental commits per phase; no silent fixes. PR bodies use `Closes #NNN`.
2. **Ownership boundaries — do not edit the other lane's hot files:**
   - **Lane M owns:** `src/squadops/runtime/*`, `src/squadops/api/runtime/*`,
     `adapters/persistence/runtime/*`, `adapters/cycles/dispatched_flow_executor.py`,
     `capabilities/handlers/cycle_tasks.py`, the SIP-0089/0090 surface, `cli/commands/agent.py`.
   - **Lane S owns:** `adapters/comms/*`, `adapters/telemetry/*`,
     `adapters/persistence/postgres/*`, CI/test infra, `adapters/cycles/factory.py`
     + `workflow_tracker_factory.py`, the API-surface/prefix work, the `DbRuntime` port shape.
3. **Shared append-only files — announce before editing, never reformat wholesale:**
   `pyproject.toml`, `ci-constraints.txt`, `tests/requirements.txt`,
   `scripts/dev/run_regression_tests.sh` (REGRESSION_DIRS is append-only).
4. **Format gate is fail-stop:** `ruff format .` before pushing (dev venv on 3.12).
5. **Reduce-scope issues:** corrective comment on the issue *first* (so nobody rebuilds
   what exists), then narrow the work.
6. **Migration ranges:** Mac `1100–1199`, Spark `1000–1099` (prevents DDL filename collisions).

## Collision matrix (the one thing that will bite)

- **`cycle_tasks.py` — #276 (S) before #152 (M), never concurrent.** Spark's #276 (build
  acceptance passing on a non-running app — the stub-fallback-on-ImportError fix) touches the
  same file Mac's #152 splits into per-handler modules. Land #276 first; #152 strangles from
  the post-#276 state. If both are ready at once, #276 merges, main settles, *then* #152 branches.
- **`dispatched_flow_executor.py` — hot but 100% Mac-internal** (#186 + #295). No Spark
  contention; within-lane sequencing only — the #233/#244 lease/txn semantics it depends on
  already landed in 1.2, so #186 can decompose directly.
- Everything else is within-lane and parallel-safe.

## Sequencing

- **Lane M:** ~~boundary SIP for #186~~ **SIP-0097 accepted 2026-07-06** → slices 1–6 per its §8 (one PR each, live-validated);
  ~~#152 waits on #276~~ **#152 done (2026-07-06)**; #295 rides the #186 decomposition.
- **Lane S:** ~~#234 and #323~~ **both reassigned to Lane M 2026-07-07** (Spark offline; issues
  commented + relabeled `track:macbook`). The entire 1.3.0 core scope is now Mac-lane; Spark's
  return blocks nothing for the cut. Mac sequencing: SIP-0097 slices → #323 → #234 (filler,
  independent). ~~#276 unblocks #152~~ (both resolved).

## Out of scope for 1.3 (feature-free rule)

Campaign, Self-Improvement, Test Bay, duty durability (SIP-0091), embodiment Phase 2 — all
**features** → they land on even minors (1.4/1.6/2.0), not here. See
`docs/plans/2-0-roadmap-reconciliation.md`. If a "hardening" item turns out to be a
prerequisite the Campaign/Test-Bay vision depends on (durable Run records, run→artifact
traceability, disposable-workspace lifecycle), it is welcome here **as hardening** — but the
Campaign feature itself is not.

## Cut checklist

Follow the standard release-cut checklist (version bump → CHANGELOG + marker sync →
regression green → release PR → annotated tag + GitHub Release → **rebuild+deploy+verify** →
E2E smoke → **SIP promotion sweep**). 1.3 has no feature SIP to promote, but run the sweep
anyway — a phased SIP's arc may have completed.
