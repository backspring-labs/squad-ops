# SIP-0XXX: API Contract Hardening

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-02-28
**Revision:** 1

## 1. Abstract

SquadOps exposes a REST API (`/api/v1/`) that will become a stability surface for external consumers at 1.0. Several contract gaps — missing pagination, inconsistent error shapes, absent OpenAPI response models, and incorrect HTTP status codes — must be resolved before the API shape becomes a compatibility commitment. This SIP formalizes the P0 contract gaps and select P1 resilience items as a single hardening pass.

## 2. Problem Statement

The runtime API was built iteratively alongside SIP-0064/0065/0068. Functionality is correct, but the contract surface has gaps that would be painful to fix after 1.0 without breaking consumers:

- **No pagination** — all list endpoints return full result sets (no `limit`/`offset`).
- **Inconsistent error format** — platform health and auth routes return plain strings instead of the standard `{"error": {...}}` shape.
- **No OpenAPI response models** — zero `response_model=` declarations across all 38 routes; OpenAPI docs have no response schemas.
- **Wrong HTTP status codes** — POST endpoints creating resources return 200 instead of 201.
- **Hardcoded identity** — `decided_by="system"` on gate decisions instead of extracting from auth context.
- **Missing artifact path validation** — no check for path separators (`../`, `\`) in artifact filenames at ingestion.
- **No DB retry logic** — `SerializationError` and transient DB failures are not retried in the cycle registry adapter.

These are not bugs — the API works. But they are contract gaps that become breaking changes if fixed after external adoption.

## 3. Goals

1. Add `limit`/`offset` pagination to all list endpoints with a consistent query parameter contract.
2. Standardize error responses across all routes to use the `{"error": {"code": ..., "message": ...}}` shape.
3. Add `response_model=` declarations to all routes so OpenAPI docs are complete and accurate.
4. Return correct HTTP status codes (201 for resource creation, 204 for deletion where appropriate).
5. Extract `decided_by` from auth context on gate decisions instead of hardcoding.
6. Add artifact filename validation (reject `../`, `\`, path separators) at ingestion.
7. Add retry logic for transient DB failures (`SerializationError`, connection errors) in the Postgres cycle registry adapter.

## 4. Non-Goals

- Versioning the API (e.g., `/api/v2/`) — the point is to get v1 right before it becomes stable.
- Adding CORS method/header restrictions (P1 polish, can land separately).
- Adding path parameter UUID validation (P2 — no contract break if added later).
- Typed DTO models for all `dict` fields (P2 — internal improvement, not contract-facing).
- Agent skill test coverage (separate concern, not API contract).

## 5. Approach Sketch

### Pagination
- Add `PaginationParams` dependency (limit: int = 50, offset: int = 0) used by all list routes.
- All list responses wrap results in `{"items": [...], "total": N, "limit": N, "offset": N}`.
- Port methods that lack `limit`/`offset` parameters get them added (some already have them from SIP-0067).

### Error Standardization
- Create a shared `ErrorResponse` model with `code`, `message`, and optional `details`.
- Add FastAPI exception handlers for `ValueError`, `KeyError`, `PermissionError`, and domain exceptions.
- Audit all routes that return plain strings and convert to `ErrorResponse`.

### OpenAPI Response Models
- Add `response_model=` to every route decorator.
- Create response DTOs where missing (list wrappers, error shapes).
- Verify generated OpenAPI spec is complete.

### Status Codes
- Add `status_code=201` to all POST routes that create resources.
- Review DELETE/PUT routes for correct codes.

### Gate Identity
- Extract `decided_by` from the `Authorization` header / auth context in the gate decision route.
- Fall back to `"system"` only for programmatic (non-user) gate decisions.

### Artifact Validation
- Add path separator check (`/`, `\`, `..`) to artifact filename at the route level before passing to the vault adapter.

### DB Retry
- Add `tenacity` retry decorator to Postgres registry methods with `retry_if_exception_type(SerializationError)` and exponential backoff.

## 6. Key Design Decisions

1. **Pagination is envelope-based** — responses use `{"items": [], "total": N}` rather than Link headers or cursor-based pagination. Simpler for the current consumer set.
2. **Error shape is the contract, not the HTTP library** — all error responses use the same JSON shape regardless of which route or middleware produces them.
3. **Retry is adapter-internal** — retry logic lives inside the Postgres adapter, not in the API routes. Callers don't know about retries.
4. **One SIP, one branch** — all P0 items land together because they collectively define the stable contract surface.

## 7. Acceptance Criteria

1. All list endpoints accept `limit` and `offset` query parameters and return paginated responses.
2. All error responses across all routes use the standard `{"error": {...}}` shape.
3. OpenAPI spec (`/docs`) shows response schemas for every route.
4. POST creation routes return HTTP 201.
5. Gate decisions extract `decided_by` from auth context.
6. Artifact ingestion rejects filenames containing `../` or path separators.
7. Postgres registry adapter retries on `SerializationError` with bounded backoff.
8. All existing tests pass; new tests cover each hardening item.

## 8. Source Ideas

- `docs/ideas/pre_1_0_hardening.md` — P0 table (pagination, error format, OpenAPI, status codes, gate auth) and P1 items (DB retry, artifact validation).

## 9. Open Questions

1. Should pagination default limit be 50 or 100?
2. Should the error response include a `request_id` field for correlation?
3. Should retry behavior be configurable via `SQUADOPS__DB__` config, or hardcoded with sensible defaults?
4. Should the OpenAPI spec be snapshot-tested to prevent regression?
