# Architectural Review — 2026-06-11

**Scope**: Full codebase (~54k lines of Python across 348 files) reviewed in four parallel passes — core domain, adapters layer, API/CLI/auth edges, and tests/infra/ops. Key claims (line counts, missing CI, unused auth dependencies, boundary imports) were verified directly before inclusion.

**Tracking**: Each fix is a GitHub issue labeled `arch-review` (#149–#158). See the issue index at the bottom.

---

## Verdict

The hexagonal architecture is real, not aspirational — ports are clean, adapters conform faithfully, domain models are frozen and validated, and the migration discipline is production-grade. The foundations are strong.

The problems are almost all **scale problems**: a few modules have absorbed every new SIP for a year and are now 3,000+ line monoliths, and the safety net (CI, integration tests, authorization enforcement) hasn't kept pace with how distributed the system has become. Nothing here is a rewrite — but the next several SIPs get progressively more expensive until the two monoliths are decomposed and a CI gate exists.

## Strengths

- **Port design**: cohesive, single-responsibility interfaces with no RabbitMQ/asyncpg semantics leaking through (one exception: `ports/db.py`, see below). Adapters implement port surfaces exactly — no secret extra methods that domain code relies on.
- **Domain modeling**: frozen dataclasses, declarative state machines in `cycles/lifecycle.py` with validated transitions, `StrEnum` for JSON interop, well-documented field ownership in the new `AgentRuntimeState` (SIP-0089).
- **Persistence**: serializable isolation on `create_run()`, optimistic retry on gate decisions, parameterized queries throughout, idempotent numbered migrations with documented authoring rules (`infra/migrations/README.md`). The most mature layer in the codebase.
- **DTO discipline and error shaping**: domain→DTO mapping centralized (`api/routes/cycles/mapping.py`), one structured error shape across API and CLI.
- **Resilience patterns where they exist are good**: Keycloak JWKS three-tier caching with stampede protection, LangFuse exponential backoff with non-blocking queue, `aio_pika.connect_robust` reconnection.
- **Test fixture architecture**: layered conftest design, auto-marker system, strong cycles-domain coverage (~1:3.5 test-to-source ratio).

## Problems, ranked

### 1. Three god-files (verified line counts)

- `src/squadops/capabilities/handlers/cycle_tasks.py` — **3,226 lines**, 9 handler classes plus shared validation heuristics (`_STUB_PATTERNS`, `_STACK_INDICATORS`, `_PRD_COVERAGE_DISCIPLINE_SECTION`). `planning_tasks.py` (1,573 lines) imports `_CycleTaskHandler` from it, coupling the two.
- `adapters/cycles/distributed_flow_executor.py` — **3,172 lines**, 50+ methods. Simultaneously: flow orchestrator, retry manager, pulse verifier (SIP-0070), correction-protocol runner (SIP-0086; `_run_correction_protocol` alone ~346 lines, `_verify_with_repair` ~256), checkpointer (SIP-0079), and report generator (7 `_build_report_*` methods — pure formatting that belongs in the domain layer). The correction loop cannot be unit-tested without mocking the whole executor's state.
- `tests/unit/cycles/test_distributed_flow_executor.py` — **3,335 lines**.

The proposed SIP renaming DistributedFlowExecutor to "Dispatched" treats the symptom; fold the rename into the decomposition (issue #151).

### 2. No CI pipeline

No `.github/workflows/` exists. The 3,000+ test regression suite only runs when invoked manually via `scripts/dev/run_regression_tests.sh`. Highest-leverage fix in the review: a basic Actions workflow (unit tests + ruff + `lint_test_quality.py`) protects everything else on this list. (#149)

### 3. Authorization wired but never enforced

`require_scopes()` / `require_roles()` exist in `src/squadops/api/middleware/auth.py` but have **zero usages** across `src/squadops/api/routes/` (verified). Any authenticated user can perform any cycle operation. SIP-0062 built the boundary; the routes never adopted it. Related: `_emit_audit()` silently no-ops when the audit port is unconfigured, so token-rejection events can vanish without a warning. (#150)

### 4. Hexagonal boundary leaks

- `src/squadops/ports/db.py:10-11` exposes SQLAlchemy `Engine` and `sessionmaker` in a port interface. (#153)
- `src/squadops/orchestration/orchestrator.py:112` lazy-imports `NoOpLLMObservabilityAdapter` from `adapters/`. The always-inject-NoOp *pattern* is deliberate and good; the *import direction* belongs in `bootstrap/` wiring. Also `agents/entrypoint.py` (~12 adapter factory imports) and `config/loader.py` (imports `adapters.secrets.factory`). (#154)
- **Immutability bug pattern**: `planning_tasks.py:437` (and ~558, plus `wrapup_tasks.py`) mutate `result.outputs` in place on a frozen `TaskResult` — frozen dataclasses don't freeze nested dicts. Becomes nondeterministic the moment results are cached, retried, or shared. (#155)
- `_parse_jsonb` copy-pasted in three adapters: `postgres_cycle_registry.py`, `postgres_squad_profile.py`, `chat_repository.py`. (#156)

### 5. Test coverage inverted relative to risk

The network-touching layers are least covered (#157):

| Area | Source files | Test files | Note |
|------|-------------|-----------|------|
| `src/squadops/api/` | ~32 | ~11 | most routes lack unit tests |
| `src/squadops/comms/` | 4 | 2 | no RabbitMQ failure-mode coverage (nack, retry, dead-letter) |
| `tests/integration/` | — | ~12 files | for a 17-service distributed system |
| `src/squadops/runtime/` | (SIP-0089, growing) | 1 | needs state-machine + concurrency tests as phases land |

By contrast the cycles domain is excellently tested.

### 6. Operational drift risks (#158)

- No `schema_migrations` tracking table — concurrent runtime-api startups can race on migration application; "was this applied?" is undiagnosable in multi-instance deployments.
- No schema-drift check between migration DDL and Python models.
- Hardcoded timeouts in six adapters (ollama 10s/5s, keycloak 10s, rabbitmq 1s consume poll, docker 5s, a2a_client 10s) — operators can't tune without code changes.
- Chat routes use module-level globals (`_chat_repo`, `_a2a_client`) instead of FastAPI `Depends()`; `send_chat_message()` mixes validation, persistence, cache, forwarding, and streaming in one handler.
- `api/runtime/health_checker.py` (703 lines) combines YAML instance cache, HTTP probes, and DB aggregation with mutable cache state shared across concurrent requests.

## Recommended sequencing

1. **CI first** (#149, ~half a day) — everything else compounds on it.
2. **Scope enforcement on cycle routes** (#150, ~half a day) — closes a real gap, completes SIP-0062.
3. **Decompose DistributedFlowExecutor** (#151) — *before* any SIP touching cycle execution; absorb the "Dispatched" rename SIP.
4. **Split `cycle_tasks.py`** (#152) — mechanical, no behavior change.
5. **Hygiene pass** (#153–#156) as one batch.
6. **Coverage and ops hardening** (#157, #158) ongoing.

If the queued plans in `docs/`/`plans/` are feature SIPs, slot a "structural hardening" phase ahead of them.

## Issue index

| Issue | Title |
|-------|-------|
| [#149](https://github.com/backspring-labs/squad-ops/issues/149) | Add CI pipeline: run regression suite + ruff on every PR |
| [#150](https://github.com/backspring-labs/squad-ops/issues/150) | Enforce scopes/roles on cycle API routes |
| [#151](https://github.com/backspring-labs/squad-ops/issues/151) | Decompose DistributedFlowExecutor: extract correction protocol and report generation |
| [#152](https://github.com/backspring-labs/squad-ops/issues/152) | Split `cycle_tasks.py` into per-handler modules |
| [#153](https://github.com/backspring-labs/squad-ops/issues/153) | Remove SQLAlchemy types from DbRuntime port |
| [#154](https://github.com/backspring-labs/squad-ops/issues/154) | Move adapter imports out of domain into bootstrap wiring |
| [#155](https://github.com/backspring-labs/squad-ops/issues/155) | Fix in-place mutation of frozen `TaskResult.outputs` |
| [#156](https://github.com/backspring-labs/squad-ops/issues/156) | Dedupe `_parse_jsonb` (three copies) |
| [#157](https://github.com/backspring-labs/squad-ops/issues/157) | Close test coverage gaps: api/, comms/, integration suite |
| [#158](https://github.com/backspring-labs/squad-ops/issues/158) | Operational hardening: migration tracking table + configurable timeouts |
