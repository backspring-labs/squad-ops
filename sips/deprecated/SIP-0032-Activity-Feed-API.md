---
sip_uid: "17642554775949717"
sip_number: 32
title: "Activity-Feed-API"
status: "implemented"
author: "Unknown"
approver: "None"
created_at: "2025-10-16T00:00:00Z"
updated_at: "2025-11-27T10:12:48.898527Z"
original_filename: "SIP-032-Neo-Role-First-Foundations.md"
---

# SIP_032 — Role‑First Agent Foundations for Build & Deploy (supersedes SIP_031)

**Status:** Draft  
**Date:** 2025-10-16  
**Owners (by role):** planner, dev, qa, data, ops  
**Amends:** SIP_031 (rename agents to roles; add anti‑hardcoding policy; Prefect mapping)  

---

## 1) Summary

This SIP patches SIP_031 to make the design **role‑first** (no framework logic keyed to agent display names). It also confirms that the **TaskSpec** format drives both **basic DB structure work** and **Prefect** orchestration equally well.

Key updates:
- Replace name references (e.g., “Max/Neo”) with **roles** (`planner`, `dev`, `qa`, `data`, `ops`).  
- Introduce **agents.yaml** to bind a configurable `display_name` to a `role` and `agent_instance_id`.  
- Update **TaskSpec v1** to include `assignee_role`/`reviewer_role`.  
- Add CI policy to block **hardcoded display names**.  
- Show how the same TaskSpec powers **DB migrations** and maps **1:1 to a Prefect Flow/DAG**.

---

## 2) Policy: Roles, not Names

- All routing, prompt selection, telemetry, memory/RAG, and access control MUST key off **`role`** and **`agent_instance_id`**.  
- `display_name` is presentation only (UI/log field).  
- Add a CI rule that fails if “Neo”, “Max”, or any non‑role display name appears outside `/docs/` or test fixtures.

**agents.yaml (example):**
```yaml
agents:
  - agent_instance_id: "agt-1a2b"
    display_name: "Neo"
    role: "dev"
    prompt_profile: "dev_v3"
    model_route_profile: "dev_default"
  - agent_instance_id: "agt-9f88"
    display_name: "Max"
    role: "planner"
    prompt_profile: "planner_v2"
    model_route_profile: "planner_default"
```

---

## 3) TaskSpec v1 (role‑first)

Add:
- `assignee_role`: which role is expected to execute the work (e.g., `dev`, `qa`).  
- `reviewer_role`: which role verifies or reviews completion (e.g., `qa`, `planner`).

Excerpt:
```yaml
taskspec_schema: v1
profile: web_api | web_ui | worker | infra_migration
pid: "PID-001"
task_id: "T-006"
title: "Activity Feed API"
assignee_role: "dev"
reviewer_role: "qa"
objective: "Expose paginated activity feed for dashboard."
acceptance_criteria:
  - "GET /api/activities returns 200; items[] sorted desc by created_at"
  - "p95 latency <= 300ms in staging for baseline load"
artifacts:
  - kind: "openapi";  paths: ["/api/activities"]
  - kind: "tests_contract"; tool: "schemathesis"
constraints:
  perf: { p95_latency_ms: 300 }
envs: ["local","staging"]
dod:
  - "CI gates (lint,type,unit,contract,e2e,scan) pass"
```

---

## 4) DB Structure Work — does TaskSpec fit? **Yes**

Use the `infra_migration` profile. Example TaskSpec for a basic schema addition (see `examples/TaskSpec_T003_db_migration.yaml`):

```yaml
taskspec_schema: v1
profile: infra_migration
pid: "PID-001"
task_id: "T-003"
title: "Create activities table"
assignee_role: "dev"
reviewer_role: "qa"
objective: "Add activities table with indexes to support feed."
artifacts:
  - kind: db_migration
    name: "add_activities_table"
    engine: "alembic"
    statements:
      - "CREATE TABLE activities (...);"
      - "CREATE INDEX ix_activities_created_at ON activities(created_at);"
acceptance_criteria:
  - "Alembic upgrade heads succeeds in CI and staging"
  - "Rollback down to base succeeds without data loss"
  - "Contract tests for /api/activities pass with new schema"
constraints:
  data_guardrails: ["no cascade delete", "FK checks on"]
  perf: { p95_query_ms: 50 }
envs: ["local","staging"]
dod:
  - "Migration up/down tested; backup snapshot noted in runbook"
```

---

## 5) Prefect Mapping — does TaskSpec drive Prefect? **Yes**

**Mapping:**
- `task_id` → node/task name.  
- `dependencies` → Prefect task wiring (`downstream=...`).  
- `profile` → selects task factory (web_api/web_ui/worker/infra_migration).  
- `acceptance_criteria`/`dod` → assertions in Flow or post‑task checks; CI gate ensures they run.  
- `envs` → deployment parameters (work pool/queue).  
- `budget`/`model_tiers` → router hints for steps that call LLMs.  

See `examples/prefect_flow_example.py` for a minimal loader that turns a TaskSpec into a Prefect Flow with a migration step.

---

## 6) CI/CD & Guards (unchanged from SIP_031, role‑first wording)

- **No API without OpenAPI** + client regen + Schemathesis contract job.  
- **Security & perf scans** (Bandit/Semgrep/Trivy/k6).  
- **Observability**: OTel spans with `pid`, `task_id`, `role`, `agent_instance_id`, `route_version`.  
- **Name‑hardcoding lint**: block merges if display names appear in code paths.

---

## 7) Effort & Timeline

Same as SIP_031 baseline: **~10–15 dev‑days** for Phases 0–5; **+1–2 days** if enabling the optional graph coverage.

---

## 8) Acceptance Criteria for this Patch

- AC‑R1: TaskSpec includes `assignee_role` + `reviewer_role`.  
- AC‑R2: Router/prompts/routing config keyed by **role**; names are presentation only.  
- AC‑R3: CI rule in place preventing hardcoded display names outside `/docs/` and tests.  
- AC‑R4: Prefect example Flow executes `infra_migration` profile from TaskSpec.

---

## 9) Backout

Revert to SIP_031 (name‑based docs), but **keep** the CI name‑hardcoding rule as a best practice.

