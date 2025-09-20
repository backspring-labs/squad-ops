# Agent Profile Tuning Protocol (v0.1)

**Project:** SquadOps • **Owner:** Max (Lead) • **Contributors:** Neo, Data, EVE, Quark, Joi, Nat  
**Status:** Draft (operable Day‑1; extend via WarmBoot)  
**Goal:** Provide a minimal, repeatable way to *tune* agent behavior for quality, speed, cost, and reliability — without code changes.

---

## 1) Purpose & Outcomes

- Externalize the key **levers/switches/knobs** that shape each agent’s reasoning and task style.
- Enable **safe experiments** (A/B) using per‑run overrides and feature flags.
- Tie **outcomes to configs** via a `cfg_hash` so winners persist through WarmBoot.
- Guard **cost/SLA** and enforce **governance as code** (tests, data, security).

**Success looks like:** lead time down, rework down, cost per PID predictable, and stable SLAs — with versioned evidence.

---

## 2) Scope

- Applies to *all* agents (Neo, Max, Joi, Nat, etc.) and to squad‑wide policy.  
- Covers decoding/tokens, sampling strategies, RAG behavior, comms/concurrency, cost/SLA, observability, and approval gates.

---

## 3) Glossary

- **PID** — Problem/Project ID tying artifacts end‑to‑end.  
- **RunID** — WarmBoot run marker (e.g., `run-001`).  
- **cfg_hash** — SHA‑1 hash of the *effective* configuration used for a task.  
- **Self‑consistency** — sample `n>1` responses at low temperature and vote/test.  
- **Quark** — cost & SLA policy controller.  
- **WarmBoot** — repeatable run harness and learning loop.

---

## 4) Tuning Surface (Knobs)

### 4.1 Agent‑level (per persona)
- **Decoding:** `temperature`, `top_p`, `max_tokens`, `stop`, `frequency_penalty` (or local `repetition_penalty`).
- **Sampling:** `self_consistency_n` (0–5), `two_pass` (draft→final), `anneal` (temp schedule).
- **Reasoning policy:** `step_limit`, `checkpoint_interval_s`, `tool_call_budget`, `consult_budget_usd`.
- **RAG:** `top_k`, `similarity_threshold`, `chunk_size`, `overlap`, `citations_required` (bool).
- **Comms:** `urgent_interrupt_policy`, `default_status`, `eta_strategy` (how to estimate).
- **Observability:** `trace_sample_rate`, `log_level`, `pii_redaction` (bool).
- **Security/permissions:** tool allowlist, network allowlist, secrets mount (Vault).
- **Style:** `verbosity` (brief|normal|thorough), tone presets.

### 4.2 Squad‑level (global policy)
- **Routing & queues:** priority, WIP limits, prefetch, TTL, DLQ, idempotency keys, retries/backoff.
- **RunOps/SLOs:** latency targets, error‑rate thresholds, incident Sev mapping & escalation.
- **Governance gates:** required artifacts to ship (TP/TC/QA/SEC/PERF, KDE/lineage, tags).
- **Analytics/flags:** sampling rate, cohorting, experiment namespaces.
- **Profiles:** `speed | balanced | quality` bundles that flip multiple knobs at once.

---

## 5) Config Layering & Precedence

1. **Squad defaults** — `/squad_manifests/squad.yaml`  
2. **Agent overrides** — `/agents/<name>/config.yaml`  
3. **Per‑run/PID overrides** — `/warmboot_runs/run-###/pid-###.yaml`  
4. **ENV/Secrets** — endpoints, tokens (not in Git)

**Effective config =** `squad → agent → run/PID` (null means inherit). Always log a **`cfg_hash`** per task.

---

## 6) Starter Profiles (drop‑in)

```yaml
# /squad_manifests/squad.yaml
warmboot_profile: balanced  # speed | balanced | quality

profiles:
  speed:
    temperature: 0.2
    top_p: 0.9
    self_consistency_n: 1
    checkpoint_interval_s: 90
    consult_budget_usd: 0.00
    trace_sample_rate: 0.05

  balanced:
    temperature: 0.1
    top_p: 0.9
    self_consistency_n: 1
    checkpoint_interval_s: 60
    consult_budget_usd: 1.00
    trace_sample_rate: 0.10

  quality:
    temperature: 0.0
    top_p: 0.9
    self_consistency_n: 3
    checkpoint_interval_s: 45
    consult_budget_usd: 5.00
    trace_sample_rate: 0.20

routing: {message_ttl_s: 900, dlq_enabled: true}
slo: {latency_ms: 2000}
analytics: {tagging_enabled: true, sample_rate_pct: 50}
rag_defaults: {top_k: 4, similarity_threshold: 0.80, chunk: 1000, overlap: 150}
policy: {citation_required: true, tool_call_budget: 3}
```

```yaml
# /agents/neo/config.yaml
decoding: {temperature: null, top_p: null, max_tokens: 2048, frequency_penalty: 0.2}
sampling: {self_consistency_n: 2, two_pass: true}
reasoning: {step_limit: 6, checkpoint_interval_s: null}
rag: {top_k: 3, similarity_threshold: 0.82, chunk: 800, overlap: 120}
comms: {urgent_interrupt_policy: "immediate"}
consult: {budget_usd: null}
observability: {trace_sample_rate: null, log_level: "INFO", pii_redaction: true}
style: {verbosity: "brief"}
```

```yaml
# /warmboot_runs/run-001/pid-042.yaml (optional per‑task experiment)
agent_overrides:
  neo:
    decoding: {temperature: 0.0}
```

---

## 7) Intake Hook (auto‑scaffold)

On new request (US→UC→PID), the intake bot:
1. Creates the PID and **stubs**: `TP-`, `TC-`, `QA-`, KDE entries, `tagging_spec`.
2. Opens `warmboot/run-###` branch and a **per‑PID override** file.
3. Selects initial profile (`speed|balanced|quality`) — toggle via feature flag if desired.

---

## 8) Execution Rules

- If `self_consistency_n > 1`, run `n` low‑temp samples → **vote** or score with tests.  
- Respect `step_limit` and emit **checkpoints** at `checkpoint_interval_s`.  
- Enforce `tool_call_budget`; exceed → escalate to Max or consult premium model (within `consult_budget_usd`).  
- For RAG: use `rag_defaults` unless agent overrides; citations required if `policy.citation_required`.

---

## 9) Observability & Traceability

- Every task logs: `PID`, `RunID`, `Agent`, **`cfg_hash`**, `Start/End`, `Status`, `ETA`, errors.  
- Thread a correlation ID through **messages, HTTP, and DB**.  
- Health page shows green/red status, queue depth, TPS, and SLOs.  
- Optional: OpenTelemetry traces (Jaeger) using the correlation ID.

**cfg_hash (pseudo):**
```python
import json, hashlib
def cfg_hash(effective_cfg: dict) -> str:
    return hashlib.sha1(json.dumps(effective_cfg, sort_keys=True).encode()).hexdigest()[:10]
```

---

## 10) Governance as Code (CI Gates)

Fail the build if any *required* PID artifacts are missing/stale:
- **Testing:** `TP/TC/TCR` present; perf & sec stubs if in scope.
- **Data:** KDE registry entries + metrics map + lineage linkages.
- **Analytics:** `tagging_spec` passes JSON schema.
- **Security:** secrets from Vault, tools/network allowlists respected.

---

## 11) Metrics & Scorecard

**Primary (start here):**
- **Lead Time (s)**, **Blocked Time %**, **Rework Rate %**, **Cost per PID ($)**

**Secondary (phase in):**
- Test pass %, defect density (post‑gate), on‑time %, token/$ per artifact, premium consult rate, throughput per week.

**Scorecard schema (JSON)**
```json
{
  "pid": "PID-042",
  "run_id": "run-001",
  "agent": "neo",
  "cfg_hash": "ab12cd34ef",
  "lead_time_s": 812,
  "blocked_time_pct": 11.2,
  "rework_rate_pct": 0.0,
  "cost_usd": 0.73,
  "premium_consult_usd": 0.00,
  "quality": {"tests_pass_pct": 100, "defects": 0}
}
```

---

## 12) Experiment Design (A/B)

- **Unit:** PID (or a coherent subtask).  
- **Switch:** profile or a single knob; avoid changing multiple at once unless using a named profile.  
- **Cohorts:** stratify by task type (code, analysis, docs) to avoid confounding.  
- **Decision rule:** keep the variant that improves primary metrics without breaching SLOs/budgets.  
- **Power:** as a rule of thumb, collect ≥5–10 comparable PIDs per cohort before declaring a winner.

---

## 13) Security & Supply Chain

- Secrets via Vault; rotate leases per WarmBoot run.  
- Signed images + SBOMs for agent containers.  
- Tool/network allowlists enforced from config.  
- Redact PII in logs/analytics when `pii_redaction=true`.

---

## 14) Versioning & Change Control

- Version **prompts and tools** per agent; store prompt diffs with each run.  
- Persist **effective config** (pretty‑printed) alongside artifacts on merge.  
- Tag releases: `vX.Y-warmboot-###`.

---

## 15) Minimal Implementation Checklist

- [ ] Add `squad.yaml`, agent configs, and per‑PID override file.  
- [ ] Implement loader & precedence merge; compute & log `cfg_hash`.  
- [ ] Wire intake bot to stub tests/governance/tags and open run branch.  
- [ ] Add CI gates for required artifacts.  
- [ ] Emit scorecard JSON after each PID and store under `/metrics/`.  
- [ ] Flip between `speed|balanced|quality` profiles and keep the winner.

---

## 16) Appendix A — Agent Config Schema (YAML)

```yaml
# /agents/<name>/config.yaml
decoding:
  temperature: float|null
  top_p: float|null
  max_tokens: int|null
  stop: [string]|null
  frequency_penalty: float|null  # local: repetition_penalty
sampling:
  self_consistency_n: int  # 1..5
  two_pass: bool
  anneal: {start: float, end: float}|null
reasoning:
  step_limit: int
  checkpoint_interval_s: int|null
  tool_call_budget: int|null
consult:
  budget_usd: float|null
rag:
  top_k: int
  similarity_threshold: float
  chunk: int
  overlap: int
comms:
  urgent_interrupt_policy: "immediate"|"windowed"|"..."
observability:
  trace_sample_rate: float|null
  log_level: "INFO"|"DEBUG"|"WARN"
  pii_redaction: bool
style:
  verbosity: "brief"|"normal"|"thorough"
security:
  tools_allowlist: [string]
  network_allowlist: [string]
```

---

## 17) Appendix B — Squad Manifest Schema (YAML)

```yaml
# /squad_manifests/squad.yaml
warmboot_profile: "speed"|"balanced"|"quality"
profiles: { ... }  # see Section 6
routing:
  message_ttl_s: int
  dlq_enabled: bool
  retries: int|null
  backoff_s: [int]|null
  idempotency_required: bool|null
slo:
  latency_ms: int
  error_rate_pct: float|null
analytics:
  tagging_enabled: bool
  sample_rate_pct: int
rag_defaults:
  top_k: int
  similarity_threshold: float
  chunk: int
  overlap: int
policy:
  citation_required: bool
  tool_call_budget: int
```

---

## 18) Appendix C — Tiny Loader (pseudo‑Python)

```python
def deep_merge(a, b):
    out = {**a}
    for k, v in (b or {}).items():
        out[k] = deep_merge(a.get(k, {}), v) if isinstance(v, dict) else (v if v is not None else a.get(k))
    return out

def effective_config(squad, agent_cfg, pid_override=None):
    base = squad["profiles"][squad["warmboot_profile"]]
    return deep_merge(deep_merge(base, agent_cfg), pid_override or {})
```

---

**End of spec — v0.1**  
Next steps: wire `cfg_hash`, enable one profile flag, and collect two PIDs to compare *lead time* + *cost*. Keep the winner.
