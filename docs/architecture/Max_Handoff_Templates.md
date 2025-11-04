# Max → Neo Handoff Templates & Rubrics

This pack standardizes how **Max** specifies work for **Neo** across any app.

---

## 1) `AppSpec.yaml` (project-level, one per app)

```yaml
appspeс_schema: v1
app_id: "APP-XXXX"
name: "Your App Name"
overview:
  problem: "What user/business problem are we solving?"
  goals: ["Primary outcome 1", "Outcome 2"]
  non_goals: ["Out of scope item"]
stakeholders:
  product: ["PM Name"]
  engineering: ["Lead Eng"]
  design: ["UX Lead"]
  compliance: ["DPO/Sec"]
environments: ["local","staging","prod"]
slo_targets:
  api_p95_ms: 300
  availability_pct: 99.9
  error_rate_pct: 0.5
tech_stack:
  backend: "fastapi-python"
  frontend: "nextjs-ts"
  db: "postgres"
  cache: "redis"
security_compliance:
  data_classes: ["public","internal"]
  pii: false
  controls: ["rate_limits","csrf","cors","input_validation"]
telemetry:
  tracing: "otel"
  logging: "loki"
  metrics: "prometheus"
deployment:
  strategy: "docker-compose (local), gha to staging/prod"
  feature_flags: "flipt"
data_model:
  glossary: ["Term → definition", "Event → meaning"]
  initial_entities: ["User","Team","Activity"]
dependencies:
  external_apis: []
  internal_services: []
risks:
  - id: R-001
    description: "Example risk"
    mitigation: "Feature flag + staged rollout"
```

---

## 2) `TaskSpec.yaml` (atomic work item; many per app)

> Use the same schema across projects. Add a `profile` to tailor fields for the work type.

```yaml
taskspec_schema: v1
profile: "web_api"        # web_api | web_ui | worker | infra_migration
pid: "PID-001"            # process/thread of work
task_id: "T-001"
title: "Implement Activity Feed API"
objective: "Expose paginated activity feed for dashboard."
acceptance_criteria:
  - "GET /api/activities returns 200 with items[] sorted desc by created_at."
  - "Supports page[size<=100], page[cursor]; returns next_cursor when more."
  - "Filter by agent and type via query params."
artifacts:
  - kind: "openapi"
    paths: ["/api/activities"]
  - kind: "db_migration"
    name: "add_activities_table"
  - kind: "tests_contract"
    tool: "schemathesis"
  - kind: "tests_unit"
    packages: ["apps.api.activities"]
constraints:
  stack:
    backend: "fastapi-python"
  perf:
    p95_latency_ms: 300
  security:
    - "Validate and bound all query params"
    - "Rate limit: 60 rpm per IP"
dependencies: ["T-003"]   # e.g., DB foundation exists
envs: ["local","staging"]
dod:                       # Definition of Done
  - "All CI jobs pass (lint,type,unit,contract,e2e,scan)"
  - "Coverage >= 80% in changed files"
  - "SLO dashboards green for new endpoint"
slo_targets:
  api_p95_ms: 300
  error_rate_pct: 1.0
rollout:
  flag: "activities_api_enabled"
  plan: ["staging 100%", "prod 1%→25%→100%"]
fixtures:
  - "sample_payloads/activities.json"
test_plan_refs:
  - "docs/testplans/TP-activities.md"
budget:
  tokens_max: 1.5e6
  model_tiers: ["mid","large-for-CODE"]
traceability:
  epic: "EP-HELLOSQUAD-01"
  feature: "Activity Feed"
  links: ["PRD-001-HelloSquad.md#activity-feed"]
```

---

### 2.a Profiles

#### `profile: web_api`
```yaml
openapi_draft:
  path: "/api/activities"
  method: "GET"
  request_params:
    page[size]: "int<=100"
    page[cursor]: "string?"
    filter[agent]: "string?"
    filter[type]: "string?"
  responses:
    "200":
      content_type: "application/json"
      example_file: "fixtures/activities_200.json"
```

#### `profile: web_ui`
```yaml
ui:
  route: "/dashboard"
  components:
    - name: "ActivityFeed"
      props: ["items","onFilterChange","isLoading"]
  states:
    - "empty"
    - "loading"
    - "error"
    - "populated"
wireframes: ["links/figma#feed"]
a11y:
  - "Keyboard navigable"
  - "aria-live updates for new items"
```

#### `profile: worker`
```yaml
worker:
  queue: "events"
  jobs:
    - name: "IngestActivity"
      idempotency_key: "event_id"
      retry:
        backoff: "exponential"
        max_attempts: 5
  schedules: []
```

#### `profile: infra_migration`
```yaml
migration:
  plan: "alembic revision add_activities_table"
  rollback: "drop table activities if created in this migration"
  backfill: "n/a"
  data_guardrails: ["fk checks on", "no cascade delete"]
```

---

## 3) Max’s Handoff Checklist (quick)

- [ ] AppSpec updated (goals, stack, SLOs, environments)
- [ ] TaskSpec complete (objective, **testable** acceptance criteria, artifacts, constraints, DoD)
- [ ] Profile-specific fields filled (OpenAPI draft, wireframes, queues, or migration plan)
- [ ] Dependencies ordered; DAG updated
- [ ] Links to PRD/PID/ADRs added
- [ ] Rollout plan + feature flag named
- [ ] Fixtures/examples attached
- [ ] SLO targets stated (latency, error rate)
- [ ] Budget/model-tier hints included

---

## 4) Acceptance-Criteria Rubric (for Max)

- **Observable:** Can EVE/automation observe pass/fail without interpretation?
- **Measurable:** Includes numbers/limits (e.g., p95 ≤ 300ms, page[size] ≤ 100).
- **Unambiguous:** Single expected behavior per criterion; includes negative case if helpful.
- **Traceable:** Links to endpoint/component and PRD section.
- **Environment:** States where it must pass (local/staging/prod/synthetic).

**Good example:**  
- “`GET /api/activities` returns 200 within **300ms p95** for **1 RPS** baseline in **staging**; payload matches schema `ActivityList` and is sorted desc by `created_at`.”

---

## 5) Router Policy Skeleton (`routing/neo.yml`)

```yaml
version: 1
defaults:
  latency_ms: 3000
  cost_ceiling_usd: 1.50
routes:
  PLAN:   { model: "mid",   context: 64k }
  SCAN:   { model: "small", context: 32k }
  CODE:   { model: "large", context: 128k }
  TEST:   { model: "mid",   context: 64k }
  DEPLOY: { model: "small", context: 32k }
budget_breakers:
  - name: "cost"
    when_cost_usd_exceeds: 2.00
    action: "pause_and_notify"
```

---

## 6) Prompt-Pack Layout (`prompts/neo`)

```
/prompts/neo/
  PLAN/v1.jinja
  CODE/v3.jinja
  TEST/v2.jinja
  DEPLOY/v1.jinja
  DOCS/v1.jinja
```

Jinja slots to support across packs:
- `pid`, `task_id`, `acceptance_criteria`, `repo_paths`, `stack`, `budget`, `route_version`

---

## 7) Task Grain Guidance (how small should tasks be?)

- Aim for **0.5–2 developer days** per TaskSpec.  
- Each TaskSpec should yield a **shippable or testable artifact** (API, component, migration, doc).  
- Avoid “grab-bag” tasks; split by contract, data layer, UI slice, or infra step.  
- If acceptance criteria exceed ~8 bullets, **split the task**.

---

## 8) Example: Minimal OpenAPI Seed

```yaml
openapi: 3.1.0
info: { title: "HelloSquad API", version: "0.2.0" }
paths:
  /api/status:
    get: { responses: { "200": { description: "Ok" } } }
  /api/activities:
    get: { responses: { "200": { description: "Ok" } } }
```

---

**How to use:**  
- Max drafts/updates **AppSpec** once per app.  
- Max emits **TaskSpec** per increment of work using the appropriate **profile**.  
- Neo consumes TaskSpec, runs contracts-first, builds/tests/deploys, and returns artifacts & URLs.  
- EVE validates against acceptance criteria + SLOs.
