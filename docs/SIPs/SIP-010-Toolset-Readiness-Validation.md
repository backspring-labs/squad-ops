# ✅ SIP-010: Toolset Readiness Validation Protocol

---
id: SIP-010
title: Toolset Readiness Validation
status: Proposed
version: 1.0.0
owners: [max]
roles_in_scope: [role.*]
layers: [Agent, Squad, Ops]
created: 2025-09-26
updated: 2025-09-26
related: [SIP-007, SIP-009, SIP-006.1]
tags: [armory, practice-range, readiness, role-first]
---

## 📌 Purpose
Ensure all **tools, creds, and integrations** required for a daily run are validated *before* the squad enters a long WarmBoot cycle.  
This prevents wasted runtime due to expired keys, missing secrets, or misconfigured tools.

---

## 🎯 Objectives
- Run **nightly toolset validation** using the Practice Range sandbox.  
- Verify **credentials are present, valid, and scoped** correctly.  
- Confirm **sandbox/test environments** are reachable.  
- Produce a **Toolset Readiness Report** with blocking issues highlighted.  
- Block the next run if readiness fails, ensuring human intervention occurs before committing hours of compute.  

---

## 🧩 Components

### 1. Credential Validation
- For each Armory tool (`armory/registry.yaml`):
  - Verify creds exist in Secrets Manager.  
  - Validate not expired (check TTL/expiry metadata).  
  - Perform lightweight API call (ping/test endpoint).  
- Failures flagged as **Blocking**.

### 2. Sandbox Connectivity
- Confirm all practice/test schemas are reachable:  
  - Postgres `practice_*` schemas.  
  - S3/GCS/Azure Blob `practice/` prefixes.  
  - Queues with `practice_` prefix.  
- Failures flagged as **Blocking**.

### 3. Quota / Usage Check
- If Armory tool exposes usage metrics (API rate, monthly quota):  
  - Warn when ≥ 80% of quota used.  
  - Fail if quota exceeded.  

### 4. Report Generation
- Output `practice/reports/toolset-readiness-<date>.md` + JSON.  
- Sections: ✅ OK, ⚠️ Warning, ❌ Blocking.  
- Report must be attached to the **Nightly Plan Proposal**.  

---

## 🔄 Workflow

1. **Nightly Trigger**
   - EventBridge / Scheduler triggers **Toolset Readiness Drill** before daily run.  

2. **Validation**
   - Practice Range executes toolset drills.  
   - Logs outcomes (pass/warn/fail).  

3. **Report**
   - Write readiness report to `/practice/reports/`.  
   - Notify human governor if Blocking issues exist.  

4. **Gatekeeper**
   - If Blocking issues → **next run is blocked** until resolved.  

---

## 📊 Example Report

```markdown
# Toolset Readiness Report — 2025-09-27

✅ OK
- ebay_api_v1 (role.scout, role.signal_miner) → Valid key
- comms_sim (role.customer_liaison) → Connected

⚠️ Warning
- openai_gpt4o (role.creative_enhancer) → Quota at 92%

❌ Blocking
- stripe_api_v1 (role.finance_risk, role.automation_engineer) → Sandbox key expired 2025-09-25
```

---

## ✅ Success Criteria
- Readiness run duration ≤ 5 min.  
- False positive rate ≤ 2%.  
- 100% of expired creds/tools caught before production run.  

---

## 🔁 Integration with SIPs
- **SIP-007 (Armory):** tool entries must expose creds/expiry metadata for validation.  
- **SIP-009 (Practice Range):** reuses sandbox/test mode infra to run validation drills.  
- **SIP-006.1 (Ops WBA):** readiness results feed into WBA as pre-flight evidence.  

---

## 📌 Status
- **SIP-010 Proposed** — Recommend adoption as nightly readiness protocol to prevent wasted cycles.
