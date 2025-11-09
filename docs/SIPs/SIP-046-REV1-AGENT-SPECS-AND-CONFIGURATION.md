# SIP-046 Rev 1: Agent Specs and Configuration (ACP‑Aligned, YAML Standard)

**Author:** Jason Ladd  
**Date:** 2025‑11‑08  
**Status:** Draft Revision 1  
**Relates:** SIP‑042 (Memory Protocol), SIP‑044 (Prefect Integration)

---

## 1) Purpose
Unify agent communication and configuration in SquadOps around a clean, **YAML‑based spec** that is fully compatible with ACP while simplifying agent setup.

This revision replaces earlier "manifest" terminology with **`config.yaml`**, moves `capability_bindings.yaml` to the root of the `/agents` folder, and establishes YAML as the canonical agent configuration format.

---

## 2) Scope (MVP)
- Agents: **Max** (orchestrator) and **Neo** (developer)  
- Capabilities (WHAT): `build.artifact`, `test.run`, `validate.warmboot`  
- Routing (WHICH): defined by `/agents/capability_bindings.yaml`  
- Transport: Prefect (params → JSON requests) with optional ACP REST support  
- Memory & Telemetry: per SIP‑042  

---

## 3) Message Envelope (Specs)

### 3.1 AgentRequest
```json
{
  "action": "build.artifact | test.run | validate.warmboot",
  "payload": {},
  "metadata": {
    "pid": "string",
    "ecid": "string",
    "tags": ["optional","labels"]
  }
}
```

### 3.2 AgentResponse
```json
{
  "status": "ok | error",
  "result": {},
  "error": { "code": "string", "message": "string", "retryable": false },
  "idempotency_key": "string",
  "timing": { "started_at": "iso8601", "ended_at": "iso8601" }
}
```

**Rules**
- `action` = capability name from catalog.  
- `payload` = free‑form object with keys like `project`, `component`, `ref`, etc.  
- `metadata.pid` and `metadata.ecid` are required.  
- `idempotency_key` = hash(`agent_id`,`action`,`payload`,`metadata.pid`).  
- `timing` = ISO‑8601 timestamps.  

---

## 4) Governance Files (WHAT / WHO / WHICH)

### 4.1 Capability Catalog (WHAT)
`/agents/capabilities/catalog.yaml`
```yaml
catalog_version: 1.0.0
capabilities:
  - name: build.artifact
    capability_version: 1.0.0
    result: { keys: [artifact_uri, commit] }
  - name: test.run
    capability_version: 1.0.0
    result: { keys: [passed, failed, report_uri] }
  - name: validate.warmboot
    capability_version: 1.0.0
    result: { keys: [match, diffs] }
```

### 4.2 Agent Config (WHO)
`/agents/<agent>/config.yaml`
```yaml
agent_id: neo
role: developer
spec_version: 1.0.0
implements:
  - capability: build.artifact
    min_version: 1.0.0
  - capability: test.run
    min_version: 1.0.0
  - capability: validate.warmboot
    min_version: 1.0.0
constraints:
  repo_allow: ["squad_ops/*"]
  max_runtime_s: 1200
  network_allow: ["git-read", "package-cache"]
defaults:
  model: ollama:codellama
  image: neosquad/neo:latest
  max_concurrency: 1
```

### 4.3 Capability Bindings (WHICH)
`/agents/capability_bindings.yaml`
```yaml
bindings:
  build.artifact: neo
  test.run: neo
  validate.warmboot: neo
```

---

## 5) Folder Layout (Rev 1)
```
/agents/
  specs/
    request.schema.json
    response.schema.json
  capabilities/
    catalog.yaml
  capability_bindings.yaml
  max/
    config.yaml
  neo/
    config.yaml
```

---

## 6) Validation & CI
1. **Schema validation:** all requests/responses → `/agents/specs/*.schema.json`.  
2. **Catalog ↔ Config:** every `implements.capability` exists in `catalog.yaml`.  
3. **Bindings sanity:** each binding maps to a capability and agent that implements it.  
4. **Result sanity:** responses contain only approved result keys.  

---

## 7) Transport Options

### 7.1 Prefect (default)
- Use Prefect Flows to carry AgentRequest/Response.  
- Log `status`, `timing`; record memory on `ok` via SIP‑042.  

### 7.2 HTTP / ACP (optional)
- Each agent may expose `POST /acp/request`.  
- Accept the same JSON envelope and return AgentResponse.  
- Add `GET /acp/config` for runtime discovery if desired.  

---

## 8) Implementation Steps
1. Add `/agents/specs/request.schema.json` and `response.schema.json`.  
2. Create `/agents/capabilities/catalog.yaml` and `/agents/capability_bindings.yaml`.  
3. Replace legacy manifest files with YAML configs under each agent.  
4. Update call sites to use generic `payload`.  
5. Validate CI rules and memory logging behavior.  

---

## 9) Acceptance Criteria
- All agents load from `config.yaml`.  
- All bindings resolve to valid agents + capabilities.  
- Responses are schema‑valid and include `idempotency_key` + `timing`.  
- CI fails on schema or mapping drift.  

---

## 10) Security & Policy
- Honor `constraints` from each config (e.g., repo allow‑list, max runtime).  
- Return `POLICY_VIOLATION` on breach.  
- Future SIPs may add auth and signing.  

---

## Appendix A — ACP Mapping
| SquadOps Field | ACP Equivalent |
|-----------------|----------------|
| `action` | `action` |
| `payload` | `payload` |
| `metadata.pid` | `metadata.pid` |
| `metadata.ecid` | `metadata.correlation_id` |
| (optional) `version`, `id`, `from`, `to` | ACP message headers |

---

## 11) Summary of Changes (Rev 1)
| Change | Reason |
|---------|---------|
| `manifest` → `config.yaml` | More intuitive for developers and runtime parsers. |
| `capability_bindings.yaml` moved out of `specs/` | Represents deployment state, not protocol schema. |
| YAML declared canonical format | Portable, safe, easy to validate. |

---

