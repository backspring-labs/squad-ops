# Neo (Dev Agent) — Build & Deploy Design Guide

> Objective: Equip **Neo** to reliably build and deploy web apps + APIs from Max’s task plans with minimal handholding, using contracts-first development, strong guardrails, a project RAG/graph, and CI/CD quality gates.

---

## 1) Architecture at a Glance

**Flow:** _Intake → Plan → Contracts → Scaffold → Implement → Test → Package → Deploy → Verify → Telemetry/RCA_

- **Intake (from Max):** Receive a `TaskSpec` bundle (YAML/JSON) with objective, acceptance criteria, constraints, dependencies, artifacts, and budget/SLOs.
- **Plan:** Create/update a **Task DAG**; choose model tier via router; compute a step plan (design → contracts → code → tests → docs → deploy).
- **Contracts-first:** Draft **OpenAPI** + schemas + interface contracts. Generate clients and contract tests before code.
- **Scaffold:** Cookiecutter templates for FE/BE, infra, CI, and observability. Create repo modules and service boundaries.
- **Implement:** Tight loop: write code → run tests/lint/typecheck → auto-fix → re-run. Small, frequent commits.
- **Test:** Unit + contract + e2e + perf + security. Block on failing gates.
- **Deploy:** Build container, run DB migrations, deploy to target (local docker-compose or cloud), run smoke checks.
- **Verify:** Post-deploy synthetic checks and contract probes.
- **Telemetry/RCA:** Emit OpenTelemetry spans/metrics/logs. If a gate fails, open an RCA stub and roll back/patch-forward.

---

## 2) Capability Stack

### Core languages & frameworks
- **Backend:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy/SQLModel, Alembic, Celery/RQ (or Prefect for orchestration), Redis, PostgreSQL.
- **Frontend:** Next.js (App Router) + TypeScript, Vite where appropriate, Tailwind + shadcn/ui, Zustand or TanStack Query for state/data.
- **Contracts:** OpenAPI 3.1 (fastapi), JSON Schema, `openapi-typescript` for FE clients, `datamodel-code-generator` for Python models.
- **Real-time:** Server-Sent Events or WebSockets via FastAPI; front-end hooks with native APIs or libraries.
- **Auth (future-ready):** OIDC/OAuth 2.1; session via signed cookies; CSRF for unsafe methods.

### Tooling & DX
- **Project scaffolds:** Cookiecutter templates: `cookiecutter-fe-next-app`, `cookiecutter-be-fastapi-service`, `cookiecutter-infra` (docker, compose, gha).
- **Quality:** Ruff (lint/format), MyPy (types), PyTest + pytest-xdist, Playwright (e2e), Schemathesis (contract fuzz), k6 (perf), Bandit/Semgrep (sec), Trivy (image scan).
- **CI/CD:** GitHub Actions: lint → type → test → build → scan → push → deploy → smoke.
- **Containers:** Docker/Buildx; docker-compose for local; Helm chart (optional) for k8s.
- **Observability:** OpenTelemetry SDK + OTLP to collector; Prometheus/Grafana; Sentry for exceptions; Loki for logs.
- **Feature flags:** Flipt/Unleash for progressive delivery.
- **Docs:** MkDocs Material, ADRs in `/docs/adr`. Auto-publish to Pages.

---

## 3) Knowledge Fabric (RAG + Graph)

### RAG corpora
- **Project-local:** PRDs, PIDs, SIPs, ADRs, coding standards, API specs, test plans, CHANGELOG/RUNBOOKS.
- **Patterns library:** Reusable recipes (auth, queues, caching, retries, idempotency, pagination, rate limiting, telemetry).
- **Code-aware:** Embed source tree with chunking by symbol (functions/classes) + comments + tests.

**Indexing:**
- **Vector store:** FAISS/Chroma with `text-embedding-*` models. Maintain **ephemeral per-PID index** + **long-lived patterns index**.
- **Retrievers:** hybrid (BM25 + vector), tag filtering by `pid`, `module`, `artifact_type`.

### Project Knowledge Graph
- **Graph DB:** Neo4j (or Memgraph). Nodes: `Feature`, `Endpoint`, `Component`, `Schema`, `Test`, `Migration`, `Risk`, `Metric`, `Env`.
- **Edges:** `SATISFIES(Feature→Requirement)`, `IMPLEMENTS(Component→Endpoint)`, `VERIFIES(Test→Endpoint)`, `MIGRATES(Migration→Schema)`, `OBSERVES(Metric→Component)`.
- **Use cases:** impact analysis (what tests/components break if a schema changes), requirement coverage, release notes generation.

**Auto-build graph:** LLM extracts entities/links from PRD/specs on intake; updates graph on each change (commit hook).

---

## 4) Routing, Prompts, and Guardrails

### Model routing
- **Router policy:** `routing/neo.yml` mapping `task_tag → model` with SLOs (latency, cost, context). Start small for PLAN/SCAN, escalate for CODE/GEN.
- **Escalation:** `router.escalate("CODE")` swaps to larger model; budget breaker trips downshift or pause.

### System card (template)
```
You are Neo, the Dev Agent. Objective: deliver shippable code that meets contracts and acceptance criteria.
ALWAYS follow this loop: Plan → Contracts → Scaffold → Implement → Test → Package → Deploy → Verify.
Hard rules:
- Edit only within the workspace path. Never invent environment secrets.
- Do not change public API without updating OpenAPI and client generators.
- Every change must include tests and docs updates.
- Emit OpenTelemetry spans for each major step with pid, task_id, route_version.
- If uncertain, propose options + tradeoffs + your pick, then proceed.
```

### Prompt packs
- `prompts/neo/{PLAN,CODE,TEST,DEPLOY,DOCS}/vN.jinja` with explicit slots: `pid`, `task_id`, `acceptance_criteria`, `repo_paths`, `stack`, `budget`, `route_version`.

### Guardrails
- **Validation:** Pydantic DTOs at edges, strict types, `Annotated` validators.
- **Idempotency:** idempotency keys for POST; safe retries with `backoff` and circuit breakers.
- **Migrations:** forward-only migrations; auto-gen + human check step.
- **Security:** input sanitization, prepared statements, output encoding, CORS/CSRF, rate limits.

---

## 5) Task Intake — `TaskSpec` (from Max)

**Schema (YAML):**
```yaml
pid: "PID-001"
task_id: "T-010"
title: "Implement Activity Feed"
objective: "Users see recent team activities with timestamps and filters."
acceptance_criteria:
  - "GET /api/activities returns paginated results sorted desc by time."
  - "UI shows activity type, agent/user, timestamp, details."
  - "Filter by agent and type; results update without full reload."
constraints:
  stack:
    backend: "fastapi-python"
    frontend: "nextjs-ts"
  perf:
    p95_latency_ms: 300
    tlp_ms: 2000        # time-to-first-interactive
  security:
    - "Input validation on query params"
    - "No PII; all logs redact secrets"
artifacts:
  - "OpenAPI: paths /api/activities"
  - "DB: activities table + index(created_at)"
  - "FE: /dashboard feed component + tests"
dependencies: ["T-005"]  # e.g., DB foundation
budget:
  tokens_max: 1.5e6
  model_tiers: ["mid","large-for-CODE"]
envs: ["local","staging"]
dod:
  - "All tests pass in CI"
  - "Contract tests green (Schemathesis)"
  - "SLO dashboards show healthy p95"
```

**Notes:**
- Each task **must** include testable acceptance criteria + DoD + dependencies. If missing, Neo asks Max to regenerate the spec (automatically).

---

## 6) How Much Detail Should Max Provide?

**Minimum (works, but more risk):**
- Objective, acceptance criteria, constraints (stack/perf/security), artifact list.

**Recommended (sweet spot):**
- Everything above **plus** DB schemas (tables/columns/keys), wireframes or component list, traceability tags (`pid`, `feature`, `epic`), dependency edges.

**Gold Standard (near-autonomous):**
- Also include: OpenAPI draft, example payloads, test fixtures, success/failure UX states, rollout plan, and SLO/SLA targets. Neo can then operate almost entirely mechanically.

---

## 7) Mapping to “HelloSquad”

_Example task graph derived from PRD:_
1. **T-001 Plan & Architecture** — choose stack, repos, CI, scaffolds; create ADRs.
2. **T-002 Contracts** — Draft OpenAPI (Team, Activity, Progress, Meta endpoints); JSON Schemas; client codegen.
3. **T-003 Data Layer** — Postgres schema (team_members, activities, milestones); Alembic migrations.
4. **T-004 Real-time Channel** — SSE/WebSocket for status/feed updates; heartbeat & backoff.
5. **T-005 Team Status** — API + UI panel + contract tests.
6. **T-006 Activity Feed** — API + UI + filters + pagination.
7. **T-007 Progress Tracking** — milestones, % complete calc, UI chart.
8. **T-008 Framework Transparency** — build version, WarmBoot ID, agent attributions in footer.
9. **T-009 Observability** — OTel spans/metrics/logs; dashboards + SLOs.
10. **T-010 Security & Hardening** — rate limiters, CORS/CSRF, headers, input validation.
11. **T-011 Packaging & Deploy** — docker, compose, envs (local/staging), smoke tests, rollout script.
12. **T-012 Docs & Runbook** — README, mkdocs, operational runbook.

---

## 8) CI/CD Pipeline (GitHub Actions)

- **Jobs:** `lint`, `typecheck`, `unit`, `contract`, `e2e`, `build`, `scan`, `deploy`, `smoke`.
- **Gates:** merge blocks on `unit`, `contract`, `e2e`. `deploy` needs `build+scan` green.
- **Artifacts:** coverage reports, OpenAPI bundle, SBOM, container image, test videos (Playwright).

---

## 9) Scaffolds — what Neo should auto-generate

```
/apps
  /api   (fastapi)
  /web   (nextjs)
/infra
  docker-compose.yaml
  k8s/ (optional)
/docs (mkdocs + ADRs)
/tests
  contract/
  e2e/
  perf/
/observability
  otel-collector.yaml
  dashboards/
/scripts
  dev_up.sh, deploy.sh, smoke.sh
```

---

## 10) Quality Bars Neo Enforces

- **No code without tests** matching acceptance criteria.
- **No API without OpenAPI + client regen**.
- **No DB change without Alembic migration + rollback plan**.
- **SLOs tracked** (p95 latency, error rate, TTFB). Failing SLOs block release.
- **Security checks** (Bandit/Semgrep/Trivy) must pass.

---

## 11) Interfaces with Max

- **Input:** `TaskSpec` bundles, PRD/PID links, wireframes, priority ordering.
- **Output:** Step plan, generated contracts, PRs, test reports, deployment URL, post-deploy verification. If gaps exist, Neo raises a **Clarify** task back to Max with a proposed spec patch.

---

## 12) Quick Start Checklist

- [ ] Router + prompt packs in place
- [ ] Cookiecutter scaffolds ready
- [ ] RAG indexes bootstrapped (project + patterns)
- [ ] Graph DB schema migrated
- [ ] CI/CD templates added
- [ ] Observability wired end-to-end
- [ ] Security scanners integrated
- [ ] `TaskSpec` schema validated

---

### Appendix: Minimal OpenAPI seed
```yaml
openapi: 3.1.0
info: { title: HelloSquad API, version: 0.2.0 }
paths:
  /api/status: { get: { responses: { "200": { description: Ok } } } }
  /api/activities: { get: { parameters: [], responses: { "200": { description: Ok } } } }
  /api/progress: { get: { responses: { "200": { description: Ok } } } }
  /api/meta: { get: { responses: { "200": { description: Ok } } } }
```
