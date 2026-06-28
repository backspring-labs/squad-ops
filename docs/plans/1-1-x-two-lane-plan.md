# 1.1.x Two-Lane Execution Plan

**Established:** 2026-06-28 · derived from `issue-triage-2026-06-28.md` ·
supplements `1-1-x-hardening-plan.md`.

Two terminals work in parallel off `main`:
- **Lane S — Spark** = hardening / reliability / tech-debt (`track:spark`).
- **Lane M — Macbook** = runtime / SIP-0089 lane + renames (`track:macbook`).

## Coordination rules (both lanes)

1. **Issue-first, branch-first.** Reference a GH issue in every commit/PR; branch
   off `main`; incremental commits per phase; no silent fixes.
2. **Ownership boundaries — do not edit the other lane's hot files:**
   - **Lane M owns:** `src/squadops/runtime/*`, `src/squadops/api/runtime/*`,
     `adapters/persistence/runtime/*`, `adapters/cycles/dispatched_flow_executor.py`,
     the SIP-0089 surface, `cli/commands/agent.py`.
   - **Lane S owns:** `adapters/comms/*`, `adapters/telemetry/*`,
     `adapters/persistence/postgres/*`, CI/test infra, `adapters/cycles/factory.py`
     + `workflow_tracker_factory.py`, the API-surface/prefix work.
3. **Shared append-only files — announce before editing, never reformat wholesale:**
   `pyproject.toml`, `ci-constraints.txt`, `tests/requirements.txt`,
   `scripts/dev/run_regression_tests.sh` (REGRESSION_DIRS is append-only).
4. **Format gate is fail-stop:** run `ruff format .` before pushing (dev venv on 3.12).
5. **Reduce-scope issues:** post the corrective comment on the issue *first*
   (so nobody rebuilds what exists), then narrow the work.

---

## Lane S — Spark (hardening)

### S0. Board hygiene (close, with the noted check)
- **#132** — close as not-reproducible (CLI already sends `resume_reason`). *Optional:* add one round-trip test first.
- **#217** — verify the `test_correction_protocol.py` ~57% hang on a clean 3.12 venv, then close (3.12 standardization landed in `e9a9144`).
- **#134** — close/reframe to a model-selection note (corrective retry already exists at `planning_tasks.py:358`).
- **#153** — close **into #234** (subset; leaky accessors are test-only).

### S1. Sprint 1 — S-effort cluster (priority order)
| # | Task | Acceptance |
|---|------|-----------|
| **#245** | RabbitMQ `publish()` bounded retry/backoff across the reconnect window (`adapters/comms/rabbitmq.py:123-168`). | Regression test: drop connection → publish recovers (mirror #146). |
| **#239** | Restore global `trace`/`metrics` provider around the `BrokenExporter` test (`tests/unit/telemetry/test_adapters.py:140`; `adapters/telemetry/otel.py:82`). | No atexit traceback on a full regression run. **Do before #216.** |
| **#250** | Route `factory.py:96-100` through `create_workflow_tracker(PrefectConfig(api_url=...))`. | NoOp-fallback + init logging now apply; no behavior change in tests. |
| **#156** | Extract one `_parse_jsonb` helper for the 3 adapters; preserve `chat_repository`'s `None→{}` at its call sites. | All 3 adapters import the shared helper; chat JSONB behavior unchanged. |
| **#133+#205** | One PR: fix the two stale CLI docstrings (`cycles.py:103`, `runs.py:141`). Optionally wire `runs retry`→enqueue. | Help text matches actual behavior. |
| **#168** | Doc sweep: `docs/reviews/...:437` `"distributed"`→`"dispatched"` + 2 filename refs. **Do not touch frozen `sips/`.** | No broken `create_flow_executor("distributed")` example. |
| **#130** | `<think>`-strip before fenced parse + truncated-raw warning log in develop/assemble handlers. | Zero-extraction path logs raw snippet; think-blocks no longer break parsing. |

### S2. Then
- **#216** — add `-n auto` to `run_regression_tests.sh:52` (after #239). Green run = acceptance; M if isolation collisions surface.
- **#224** — model-availability fail-fast at cycle-create + doctor over squad-profile models (lift `profiles.py:71-95` to a shared helper). *Coordinate with Lane M on the #172 combined-preflight SIP.*

### S3. Reduce-scope (corrective comment, then small)
- **#158** — table already exists; remaining = `pg_advisory_lock` + drift test + wire `timeout_seconds` from `SQUADOPS__*`.
- **#154** — inject NoOp into `AgentOrchestrator` from the composition root (kill `orchestrator.py:112`); extend the existing arch test to `orchestration/`.
- **#198** — defer; needs a coordinated x86_64/py3.12 lock-regen, not a mid-lane bump.

### S4. Tech-debt backlog (opportunistic) — **#80**, **#157** (make it an umbrella), **#242** (relocate mocked tests under `tests/unit/`), **#218→#219** (arch test, then move chat routes).
### Blocked on a decision (don't start): **#234**, **#173**, **#218/#219 approach**, **#237**.

---

## Lane M — Macbook (runtime / SIP-0089)

### M0. In flight
- **#254** merge → auto-closes **#253**; then drop the stale "by-hand body Status" line from the release-prep runbook.

### M1. Sprint 1
| # | Task | Acceptance |
|---|------|-----------|
| **#222** | Allow checkpoint-less resume for deferral-paused runs (gate on `reason=upcoming_hard_duty_window`; `runs.py:212-214`). | A hard-duty-deferred run resumes from start; no fabricated checkpoint. |
| **#231** (doc step) | Document the canonical model: Health=`runtime_status`, Mode=`mode`, lifecycle feeds health, `agent_status`=telemetry. | One short doc/SIP-0089 addendum; unblocks #230. |
| **#230** | Additive LEFT JOIN of `agent_runtime_state` into `get_agent_status()` (carry `mode`+`runtime_status`); 2nd pill in `AgentsStatus.svelte` + rebuild `dist/plugin.js`. | agent-list shows status AND mode; null-runtime-row test passes. |

### M2. Then
- **#79** — rename `establish_contract`→`define_done` / `run_contract.json`→`definition_of_done.json` (~14 files; dual-register IDs + dual-read filename one cycle).
- **#94** — per-role `[n/total]` task numbering + framing titles (refresh stale issue pointers first; logic now in `task_naming.py`).

### M3. Feature / SIP backlog (1.2.0+, SIP-governed)
- **#233 → #244** — SIP-0089 follow-up SIP (recruitment→coordinator lease, then single-txn). #244 lands with/after #233.
- **#172 (+#224)** — drive a small **cycle-create preflight SIP** (capability/role + model availability). Mostly placement/wiring; co-own #224's helper with Lane S.
- **#176** — framework smoke invariant test (spec the invariant contract).
- **#194** — SIP-0093 B′ revision loop; *extract the cheaper "alt-D de-noise" as a standalone small item.*
- **#186** — DispatchedFlowExecutor decomposition (boundary SIP first; first slice #185).
- **#152** — split `cycle_tasks.py` (opportunistic, behavior-preserving strangler).

### Blocked on a decision (don't start): **#114** (fix vs remove), **#225** (needs your `docker-compose.yml` OK).

---

## Cross-lane / decisions
- **#172+#224 combined preflight** is the one genuinely shared item: Lane M drafts the SIP (cycle/gate behavior), Lane S provides the model-availability helper.
- **Decision register (you):** #237 (when to drop 3.11), #234 (retire legacy DbRuntime vs de-leak port), #173 (target profile names), #218/#219 (move vs exempt + enforce?), #225 (rename comms id — touches docker-compose), #114 (fix vs remove typed-check plumbing).
