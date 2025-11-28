---
sip_uid: "17642554775943561"
sip_number: 33
title: "-LLM-Client-Abstraction-Manifest-First-AppBuilder"
status: "implemented"
author: "Unknown"
approver: "None"
created_at: "2025-10-16T00:00:00Z"
updated_at: "2025-11-27T10:12:48.899115Z"
original_filename: "SIP-033-LLM-Client-Abstraction.md"
---

# SIP-033 — LLM Client Abstraction & Manifest-First AppBuilder

**Status:** Draft  
**Date:** 2025-10-16  
**Owners:** Max (Product/Planning), Neo (Dev), EVE (QA), Data (Telemetry)  
**Related:** AppSpec/TaskSpec standards; PRD process; Observability (Neural Pulse); Router & Prompt Packs

---

## 1. Summary

This SIP equips **Neo (Dev Agent)** to reliably **build and deploy** web apps and APIs from Max's task plans using:
1) **Contracts‑first** development (OpenAPI + schemas)  
2) **Router + Prompt Packs** with budget/SLO awareness  
3) **Real LLM client adapters** (no mock HTML) with tests  
4) **Project RAG** for patterns/ADRs and **optional Graph** for coverage/impact  
5) **CI/CD quality gates** (lint/type/unit/contract/e2e/sec/perf)  
6) **Observability & SLOs** (OpenTelemetry, dashboards, synthetic checks)

The outcome is a repeatable, testable pipeline from **TaskSpec → Contracts → Code → Tests → Deploy → Verify** that eliminates "pretend" behaviors and enforces quality bars.

---

## 2. Motivation & Goals

- Stop agents from producing **mock HTML** that "pretends" to call an LLM.  
- Ensure **every feature** has a contract, tests, and deployment path.  
- Make handoffs from Max **uniform** via TaskSpec profiles.  
- Provide **guardrails** (security, SLOs, rollouts) and **traceability** (PID/task_id).

**Non‑goals:** Replace existing app stacks; adopt Kubernetes immediately; finalize vendor lock‑in.

---

## 3. Requirements

- **R1**: Neo consumes **TaskSpec** (v1) and executes the contracts‑first loop.  
- **R2**: All public APIs must have OpenAPI + generated clients + contract tests.  
- **R3**: LLM calls use **LLMClient** adapters (Local/OAI/Bedrock/etc.), tested end‑to‑end.  
- **R4**: CI/CD blocks merges on failing gates (unit/contract/e2e/security/perf scan).  
- **R5**: Observability is end‑to‑end (OTel traces/logs/metrics with pid/task_id).  
- **R6**: Minimal RAG to retrieve patterns/ADRs; **optional** graph for coverage/impact.  
- **R7**: Rollouts behind **feature flags** with smoke/synthetic post‑deploy checks.

---

## 4. Design Overview

### 4.1 Handoff Artifacts
- **AppSpec.yaml** (per app): goals, stack, SLOs, environments, compliance, telemetry.  
- **TaskSpec.yaml** (per increment): objective, **testable** acceptance criteria, artifacts, constraints, dependencies, DoD, SLO targets, rollout/flags, fixtures.  
- **Profiles**: `web_api`, `web_ui`, `worker`, `infra_migration`.

### 4.2 Contracts‑First
- Draft **OpenAPI 3.1** + JSON Schemas → generate FE/BE clients → create **Schemathesis** contract tests.  
- Build code to satisfy contracts; **no API merges** without spec + regeneration.

### 4.3 LLM Integration (No Mocks)
- `LLMClient` protocol with adapters (Local/vLLM or Ollama, OpenAI, Bedrock, Anthropic).  
- **Router** (`routing/neo.yml`) selects model tier per `PLAN/SCAN/CODE/TEST/DEPLOY` with cost/latency SLOs; supports **escalate()**.  
- **Test**: integration test asserts provider is called (spies), fails if a **DEV_FAKE** flag is not explicitly set.

### 4.4 Knowledge Fabric
- **RAG (minimal)**: vector index of PRDs/ADRs/patterns/code symbols using FAISS/Chroma; hybrid retrieval; per‑PID ephemeral + global patterns index.  
- **Graph (optional)**: Neo4j nodes (Feature/Endpoint/Component/Schema/Test/Migration/Risk/Metric/Env) with edges (`SATISFIES`, `IMPLEMENTS`, `VERIFIES`, `MIGRATES`, `OBSERVES`) for impact & coverage.

### 4.5 Quality & Delivery
- **CI/CD (GitHub Actions)**: `lint` → `typecheck` → `unit` → `contract` → `e2e` → `build` → `scan` → `deploy` → `smoke`.  
- **Security**: Bandit/Semgrep, Trivy image scan; rate limits, CORS/CSRF, validation.  
- **Perf**: k6 baseline scenarios; SLO dashboards (p95 latency, error rate).  
- **Observability**: OpenTelemetry SDK → OTLP collector → Prometheus/Grafana + Sentry + Loki; synthetic checks post‑deploy.

---

## 5. Implementation Plan (Phased)

**Phase 0 — LLM Reality Check (0.5–1 day)**  
- Add `LLMClient` protocol + provider adapters; wire into Neo.  
- Remove/guard any mock HTML paths; add failing test if no real provider set.  
- Minimal router with `PLAN/CODE/TEST` mapping; env‑config.

**Phase 1 — Standards & Scaffolds (3–4 days)**  
- Ship **AppSpec/TaskSpec** schemas + profile templates.  
- Cookiecutter: `fastapi` service, `nextjs` web, `infra` (docker/compose/GHA).  
- Prompt packs skeleton: `prompts/neo/{PLAN,CODE,TEST,DEPLOY,DOCS}`.  
- Router policy `routing/neo.yml` with cost/SLOs.

**Phase 2 — Contracts‑First Path (2–3 days)**  
- OpenAPI seed + codegen (TS/Python); Schemathesis contract test job.  
- Enforce "no API without spec" pre‑merge check.

**Phase 3 — Observability & SLOs (1–2 days)**  
- Wire OTel; add spans with `pid`, `task_id`, `route_version`.  
- Dashboards; basic synthetic ping + smoke tests.

**Phase 4 — RAG Minimal (2 days)**  
- Build project indexer (docs + code symbols); hybrid retriever.  
- Retrieval hook in prompts; per‑PID ephemeral index lifecycle.

**Phase 5 — Security & Perf Gates (1 day)**  
- Bandit/Semgrep + Trivy in CI; k6 smoke perf target and SLO alerts.

**Phase 6 — (Optional) Graph Coverage (1–2 days)**  
- Ingest PRD/specs → nodes/edges; coverage views (Feature→Endpoint→Test).

**Total baseline:** ~**10–15 dev‑days** (single dev), or ~**1–2 weeks** elapsed with reviews.

---

## 6. Effort & Sizing

| Workstream                         | Size | Estimate |
|-----------------------------------|:----:|:-------:|
| Phase 0: LLM adapters + router    |  S   | 0.5–1d  |
| Phase 1: Standards & scaffolds    |  M   | 3–4d    |
| Phase 2: Contracts‑first path     |  M   | 2–3d    |
| Phase 3: Observability & SLOs     |  S   | 1–2d    |
| Phase 4: RAG minimal              |  M   | 2d      |
| Phase 5: Security & perf gates    |  S   | 1d      |
| Phase 6: Optional graph           |  S   | 1–2d    |
| **Total (baseline)**              |  M   | **10–15d** |

Assumes an existing repo + some CI runners; add 1–2d if greenfield infra.

---

## 7. Acceptance Criteria (Definition of Done)

- **AC1**: Neo uses **LLMClient**; integration test fails if real provider isn't configured and **DEV_FAKE** flag isn't set.  
- **AC2**: TaskSpec (v1) + profiles are versioned and validated in CI.  
- **AC3**: "No API without OpenAPI" guard; client codegen and **Schemathesis** contract job pass.  
- **AC4**: CI/CD includes gates: lint, type, unit, contract, e2e, build, scan, deploy, smoke.  
- **AC5**: Observability spans, logs, metrics appear with pid/task_id; dashboards exist.  
- **AC6**: RAG retriever sources patterns/ADRs and is invoked in prompts; index lifecycle documented.  
- **AC7**: Security/perf scans run; SLO checks post‑deploy; release blocks on violations.  
- **AC8 (optional)**: Graph shows coverage/impact for at least one feature.

---

## 8. Risk & Mitigations

- **Hallucinated code paths** → Contract tests + CI gates + retrieval grounding.  
- **Cost blow‑ups** → Router budget breakers; escalate only for CODE steps.  
- **Spec drift** → "no API without spec/gen" rule + PR checks.  
- **Secret handling** → `.env` + vault integration; never hardcode secrets.  
- **Flaky e2e** → Stabilize with Playwright retries and synthetic checks.

---

## 9. Rollout Plan

1. Land Phase 0 to stop mock behaviors immediately.  
2. Migrate one feature (e.g., Activity Feed) through the full contracts‑first path.  
3. Enable CI gates progressively (warn → block).  
4. Turn on SLO alerts + feature‑flagged rollout.  
5. (Optional) Add graph ingestion and coverage views.

---

## 10. Backout Plan

- Feature flags off; rollback last migration via Alembic; revert to previous container image.  
- Disable router escalations; fall back to small model for PLAN/SCAN only.  
- Restore prior CI workflow file if a gate bricks the pipeline.

---

## 11. Repo Changes (proposed)

```
/docs/sips/SIP-033-LLM-Client-Abstraction.md
/specs/{AppSpec.yaml,TaskSpec.schema.yaml,profiles/*.yaml}
/prompts/neo/{PLAN,CODE,TEST,DEPLOY,DOCS}/v1.jinja
/routing/neo.yml
/apps/api (FastAPI)    /apps/web (Next.js)
/observability/{otel-collector.yaml,dashboards}
/tests/{unit,contract,e2e,perf}
/.github/workflows/ci.yaml
/scripts/{dev_up.sh,deploy.sh,smoke.sh}
/tools/indexer (RAG)   /tools/graph_ingest (optional)
/neo/llm/{client.py,router.py,providers/{openai.py,local.py,...}}
```

---

## 12. Appendix — Templates (inline)

### 12.1 AppSpec.yaml (v1)
```yaml
appspec_schema: v1
app_id: APP-XXXX
name: Hello Squad (example)
environments: [local, staging, prod]
slo_targets: {{ api_p95_ms: 300, availability_pct: 99.9 }}
tech_stack: {{ backend: fastapi-python, frontend: nextjs-ts, db: postgres, cache: redis }}
telemetry: {{ tracing: otel, logging: loki, metrics: prometheus }}
deployment: {{ strategy: docker-compose, flags: flipt }}
```

### 12.2 TaskSpec.yaml (v1, profile: web_api)
```yaml
taskspec_schema: v1
profile: web_api
pid: PID-001
task_id: T-006
title: Activity Feed API
objective: Expose paginated activity feed for dashboard.
acceptance_criteria:
  - 'GET /api/activities returns 200; items[] sorted desc by created_at'
  - 'Supports page[size<=100], page[cursor]; returns next_cursor when more'
  - 'Filter by agent and type via query params'
artifacts:
  - kind: openapi
    paths: [/api/activities]
  - kind: db_migration
    name: add_activities_table
  - kind: tests_contract
    tool: schemathesis
constraints:
  perf: {{ p95_latency_ms: 300 }}
  security: ['validate/bound params','60 rpm/ip']
envs: [local, staging]
dod:
  - 'CI jobs pass (lint,type,unit,contract,e2e,scan)'
  - 'Coverage >= 80% for changed files'
slo_targets: {{ api_p95_ms: 300, error_rate_pct: 1.0 }}
rollout: {{ flag: activities_api_enabled, plan: ['staging 100%','prod 1%→25%→100%'] }}
```

### 12.3 Router policy (`routing/neo.yml`)
```yaml
version: 1
routes:
  PLAN:   {{ model: mid,   context: 64k }}
  SCAN:   {{ model: small, context: 32k }}
  CODE:   {{ model: large, context: 128k }}
  TEST:   {{ model: mid,   context: 64k }}
  DEPLOY: {{ model: small, context: 32k }}
budget_breakers:
  - name: cost_guard
    when_cost_usd_exceeds: 2.00
    action: pause_and_notify
```

### 12.4 LLM client contract (Python)
```python
class LLMClient(Protocol):
    def chat(self, messages: list[dict], **kw): ...
    def complete(self, prompt: str, **kw): ...

class Router:
    def choose(self, task_tag: str, hints: dict) -> LLMClient: ...
    def escalate(self, level: str): ...
```

### 12.5 CI workflow (excerpt)
```yaml
name: ci
on: [push, pull_request]
jobs:
  lint:   {{ runs-on: ubuntu-latest, steps: [...] }}
  type:   {{ ... }}
  unit:   {{ ... }}
  contract: {{ ... }}
  e2e:    {{ ... }}
  build:  {{ ... }}
  scan:   {{ ... }}
  deploy: {{ needs: [build, scan], ... }}
  smoke:  {{ needs: [deploy], ... }}
```