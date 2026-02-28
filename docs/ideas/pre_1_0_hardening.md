# Pre-1.0 Hardening Assessment

**Date:** 2026-02-23
**Version reviewed:** 0.9.12
**Test suite:** 2099 passing, 1 skipped, ~7s execution

## Current State

- Strong security fundamentals (parameterized SQL, path validation, secret management)
- Consistent hexagonal architecture with clean port/adapter separation
- Full E2E pipeline validated (plan → develop → assemble → test) across Python and fullstack stacks

---

## P0 — Must Fix Before 1.0

These are API contract gaps that would be painful to fix after 1.0 (breaking changes to response shapes, status codes, pagination).

| Area | Issue | Location |
|------|-------|----------|
| **Gate decision auth** | `decided_by="system"` hardcoded — should extract from auth context | `api/routes/cycles/runs.py:101` |
| **API pagination** | All list endpoints return full result sets — no limit/offset | `runs.py`, `cycles.py`, `artifacts.py`, `projects.py`, `profiles.py` |
| **Error format inconsistency** | Platform health + auth routes return plain strings instead of standard `{"error": {...}}` shape | `platform_health.py`, `auth.py` |
| **OpenAPI response models** | Zero `response_model=` declarations across all 38 routes — OpenAPI docs have no response schemas | All route files |
| **HTTP status codes** | POST endpoints creating resources return 200 instead of declaring `status_code=201` | `cycles.py`, `runs.py`, `artifacts.py` |

---

## P1 — High Priority (Before Release)

Resilience and test coverage items that won't break API consumers if added post-1.0 but significantly improve reliability.

| Area | Issue | Location |
|------|-------|----------|
| **DB retry logic** | No retry on `SerializationError` or transient DB failures in cycle registry | `adapters/cycles/postgres_cycle_registry.py` |
| **Reconciliation loop** | Catches all exceptions including `CancelledError` — no fatal vs transient distinction | `api/runtime/health_checker.py:269` |
| **Background task errors** | `flow_executor.execute_run()` in FastAPI background task has no outer error reporting wrapper | `api/routes/cycles/cycles.py:105-111` |
| **Artifact filename validation** | No check for path separators in filenames (`../`, `\`) at ingestion | `api/routes/cycles/artifacts.py` |
| **CORS method/header restriction** | `allow_methods=["*"]` and `allow_headers=["*"]` — should whitelist | `api/runtime/main.py:92-93` |
| **Agent skill tests** | 16 role-specific skill modules in `agents/skills/` lack unit tests | `agents/skills/{qa,lead,data,strat}/` |
| **Healthcheck adapter** | `adapters/observability/healthcheck_http.py` has no unit tests | — |

---

## P2 — Polish (Strengthens Confidence)

| Area | Issue | Location |
|------|-------|----------|
| **Silent exception passes** | 7 `except Exception: pass` in health checker — should at minimum `logger.debug()` | `api/runtime/health_checker.py` |
| **Hardcoded timeouts** | HTTP/RabbitMQ timeouts baked in (5s, 1s, 10s) — not configurable | `health_checker.py`, `rabbitmq.py`, `keycloak/auth_adapter.py`, `ollama.py` |
| **Path param validation** | `cycle_id`, `project_id`, `run_id` are bare `str` — no UUID format constraint | All route files |
| **DTO typing** | 8 fields use bare `dict` instead of typed models (`applied_defaults`, `execution_overrides`, etc.) | `api/routes/cycles/dtos.py` |
| **Port interface tests** | 3 port test files only check method existence, not behavioral contracts | `test_registry_port.py`, `test_port.py`, `test_ports.py` |
| **Unused service layer** | `TaskService` and `AgentService` in `api/service.py` are never imported | `api/service.py` |
| **Connection pool exhaustion** | No circuit breaker or graceful degradation when pool is full | `adapters/persistence/factory.py` |

---

## Not Blocking 1.0 (Good Shape Already)

- **SQL injection**: Fully parameterized everywhere
- **Command injection**: Array-based subprocess calls throughout
- **Secret management**: Strong validation, redaction, no leakage
- **Auth middleware**: Proper token validation, no bypass conditions
- **API versioning**: `/api/v1/` prefix consistent
- **State machine**: Lifecycle transitions well-guarded with frozen dataclasses
- **Fenced code parser**: Path traversal protection (rejects `..`, absolute paths, colons)
- **Test suite**: 2099 tests with domain markers, strict markers, auto-async

---

## Recommended Approach

The P0 items are API contract gaps — tackle them as a single "API hardening" SIP or feature branch before any external consumers adopt the API. The P1 resilience items (retry logic, error handling) are important but can land incrementally without breaking compatibility.
