---
sip_uid: "17642554775845965"
sip_number: 10
title: "Creds-Secrets-Lifecycle-Protocol-Role-First"
status: "accepted"
author: "Unknown"
approver: "None"
created_at: "presence + expiry window (<7d → Warning, expired → Blocking)."
updated_at: "2025-11-27T10:12:48.882894Z"
original_filename: "SIP-010-Creds-Secrets-Lifecycle-Protocol.md"
---

# ✅ SIP-010: Creds & Secrets Lifecycle Protocol

---
id: SIP-010
title: Creds & Secrets Lifecycle Protocol (Role-First)
status: Proposed
version: 1.0.0
owners: [max]
roles_in_scope: [role.*]
layers: [Agent, Squad, Ops]
created: 2025-09-26
updated: 2025-09-26
related: [SIP-007, SIP-009, SIP-006.1]
tags: [secrets, creds, armory, lifecycle, role-first]
---

## 📌 Purpose
Prevent failures caused by expired, missing, or misconfigured tokens, keys, and creds.  
This protocol defines a **complete lifecycle** for managing secrets across dev/test/prod, ensuring **role-scoped access**, proactive rotation, validation, and observability.  

---

## 🎯 Objectives
- Maintain **one source of truth** for secrets (Secrets Manager / Key Vault / Secret Manager).  
- Enforce **role-scoped bindings** only (no identity secrets).  
- Require **expiry and rotation metadata** for all secrets.  
- Automate **nightly readiness checks** to catch expired creds early.  
- Block runs until blocking issues are resolved.  
- Ensure rotation is predictable, tested, and safe.  

---

## 🧩 Components

### 1. Secrets Registry (Role-First)
- All creds/keys live in a secrets manager (AWS/GCP/Azure).  
- Armory entries must reference `secrets:` blocks by **role**, not identity.  
- Example:
```yaml
- id: stripe_api_v1
  type: api
  role_scopes: [role.finance_risk, role.automation_engineer]
  secrets:
    dev: /squadops/dev/stripe_api_key
    test: /squadops/test/stripe_api_key
    prod: /squadops/prod/stripe_api_key
  expires_at: 2025-10-15
  rotates_every_days: 90
```

### 2. Metadata Requirements
- **Mandatory** fields: `owner`, `env`, `tool_id`, `role_scopes`, `expires_at`, `rotates_every_days`, `last_rotated`.  
- CI lints reject any Armory entry missing these fields.  

### 3. Rotation Policy
- **Clock-driven** rotation: rotate before `expires_at`.  
- Use **dual-key overlap** for APIs/webhooks to avoid downtime.  
- Rotation runbooks scripted + tested in sandbox.  
- Stagger rotations by env; never rotate all envs same day.  

### 4. Toolset Readiness Validation (Nightly Check)
- Run via Practice Range (SIP-009).  
- For each secret/tool:  
  - Validate presence + expiry window (<7d → Warning, expired → Blocking).  
  - Ping test endpoint (sandbox mode).  
  - Check quota/usage if available (≥80% → Warning).  
- Generate `practice/reports/toolset-readiness-<date>.md`.  
- Block next WarmBoot if any Blocking issue.  

### 5. Sandbox Safety
- Practice Range must use only **sandbox/test creds**.  
- CI fails if prod secrets referenced in dev/test configs.  
- Secrets rotated/tested in lower envs before prod rollout.  

### 6. Observability & Alerts
- Emit events:  
  - `secret.check.failed`  
  - `secret.expiring_soon`  
  - `quota.near_limit`  
- Blocking → human page/on-call.  
- Warning → Slack/issue for triage.  

### 7. Least Privilege Access
- One **task role per role** (not identity).  
- Each role’s policy limited to Armory tools in `role_scopes`.  
- Deny access for roles not listed.  

### 8. Repo Hygiene & CI
- Lints block:  
  - Identity-based secrets.  
  - Missing metadata.  
  - Prod secrets in non-prod envs.  
- Practice Range verifies parity across envs (secret present in dev/test/prod).  

### 9. Emergency Recovery
- Break-glass prod creds stored separately, audited.  
- Canary tokens used to safely test rotations before touching prod.  

---

## 📊 Example Toolset Readiness Report

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
- 100% of secrets carry expiry + rotation metadata.  
- Readiness run duration ≤ 5 min.  
- All expired creds caught before production run.  
- False positive rate ≤ 2%.  
- Rotation failure rate ≤ 1%.  

---

## 🔁 Integration with SIPs
- **SIP-007 (Armory):** registry entries must include role-scoped secrets with metadata.  
- **SIP-009 (Practice Range):** runs nightly toolset readiness validation.  
- **SIP-006.1 (Ops WBA):** readiness report attached to WBA for audit.  

---

## 📌 Status
- **SIP-010 Proposed** — Full Creds & Secrets Lifecycle Protocol, including nightly readiness validation.
