# The runtime-api URL surface — lanes, versioning, and the rule for new routes

**Status:** the owning standard for the runtime-api HTTP surface (#218). `CLAUDE.md`'s
"API Conventions" summarises it; this document is the full statement, the audit of the
current surface against it, and the record of the decisions the audit forced.
**Enforced** by `tests/unit/api/test_route_lanes.py`, which enumerates every router the
runtime API registers and asserts each route sits in a lane.

## Why a standard

By 1.1 the surface carried four URL-prefix conventions, each chosen per SIP in isolation:
`/api/v1/*` (SIP-0064/74/75), unversioned `/api/chat` + `/api/agents` (SIP-0085, one
commit, no rationale), `/health/*` (SIP-0069/0089) and `/auth/*` (SIP-0062). Nothing owned
the surface as a whole; one document claimed it was already consistent; and the SIP-0089
assignment API needed a rule for where a new resource goes and found none. A prefix is
not a neighbourhood decision — it is a statement about auth, stability and who may call.

## The lanes — classified by the nature of the endpoint, not by which SIP added it

| lane | prefix | auth | what belongs | rule |
|---|---|---|---|---|
| **Resource API** | `/api/v1/<resource>` | required (`AuthMiddleware`) | every authenticated, managed REST resource: projects, cycles, runs, gates, artifacts, squad profiles, cycle-request profiles, models, assignments, agent status writes, chat sessions | **the default home for anything new** |
| **Operational probes** | `/health/*` | **none** for GET/HEAD — the only no-auth lane | read-only liveness, infra probes, agent status and runtime-state *projections* | never a writable business resource; any non-GET method under `/health` requires a token like everything else (#326) |
| **Identity** | `/auth/*` | mixed | userinfo and the token surface; the rest of `/auth/*` is the console BFF | identity only |

Documentation (`/docs`, `/openapi.json`, `/redoc`) is exposed only when
`expose_docs=True` and is not a lane.

### Rules

1. **Read the whole surface before adding or moving a route.** Conform to a lane; if no
   lane covers the case, surface the gap and propose it *before* adding. "It doesn't
   collide" and "it's easy" are not justifications — they are how four conventions
   happened.
2. **No `/api/v2`.** Extend v1. The framework's declared OpenAPI `version` is the
   framework version, not an API contract version, and the API is not yet stable enough to
   version by prefix (the proposed `SIP-API-Contract-Hardening` stance: get v1 right first).
3. **`/health` is read-only and unauthenticated.** A writable resource there is a security
   regression. Heartbeat and status *ingest* are writes and live on `/api/v1/agents`
   (#326 moved them off `/health`).
4. **Split by nature, not by feature.** SIP-0089 is the worked example: `runtime-state` is a
   read-only status projection and stays under `/health`; `assignments` are a managed
   resource and live under `/api/v1`. One feature, two lanes, correctly.
5. **Error bodies** on `/api/v1` use the standard `{"error": {...}}` envelope; `/health`
   and `/auth` still return plain strings — a known deviation, tracked under #218 and not
   to be extended.

## Audit of the surface — 2026-09-06

Every router registered in `src/squadops/api/runtime/main.py`:

| router | prefix | lane | conforms |
|---|---|---|---|
| projects, cycles, runs, artifacts, squad-profiles, cycle-request-profiles, models | `/api/v1/…` | resource | yes |
| assignments (SIP-0089 §2.7) | `/api/v1/…` | resource | yes |
| agent status writes (`POST /status`, `PUT /status/{id}`) | `/api/v1/agents` | resource | yes (#326) |
| platform health: `/infra`, `/agents`, `/agents/status/{id}`, `/agents/{id}/runtime-state`, `/agents/{id}/activity` | `/health` | probe | yes — all GET |
| auth (`/userinfo`) | `/auth` | identity | yes |
| chat (`POST /chat/{agent_id}`, `GET /chat/sessions/{sid}/messages`, `GET /chat/{agent_id}/sessions`) and `GET /agents/messaging` — SIP-0085 | `/api/v1/chat`, `/api/v1/agents` | resource | yes — since #219 (they were unversioned `/api/chat`, `/api/agents`) |

**Decisions the audit forced:**

- **The chat routes moved to `/api/v1`** (#219): `/api/v1/chat/*` and
  `/api/v1/agents/messaging`. They are authenticated managed resources — sessions and
  messages — and the streaming transport (SSE) is a response shape, not a reason for a
  separate prefix. The blast radius was one browser consumer (browser → Caddy → console BFF →
  runtime-api), moved in lockstep; the chat surface still rides the console BFF for auth and
  SSE, and Caddy's longer `/api/v1/chat/*` matcher wins over `/api/v1/*` by its own ordering
  rule. The lane test's recorded-deviation list is empty.
- **`runtime-state` stays under `/health`** — a read-only projection, the probe lane's
  purpose; the writes it reflects are on `/api/v1/agents`.
- **An OpenAPI snapshot contract test is not added now.** The lane test pins the prefix
  taxonomy and the auth boundary, which is what drifted; a full schema snapshot pins
  response shapes, which the DTO tests already cover per resource. Revisit with
  `SIP-API-Contract-Hardening`.
- `docs/ideas/pre_1_0_hardening.md` claimed the `/api/v1/` prefix was "consistent"; corrected
  to point here.

## Adding a route — the checklist

1. Which lane? If you cannot answer from the table, stop and propose.
2. Resource API: `/api/v1/<resource>`, authenticated, `{"error": {...}}` envelope.
3. Probe: GET only, no side effects, no auth, nothing a client would write.
4. Add the route; `tests/unit/api/test_route_lanes.py` will tell you if it is off-lane.
