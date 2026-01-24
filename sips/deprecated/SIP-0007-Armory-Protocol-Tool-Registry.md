---
sip_uid: '17642554775849882'
sip_number: 7
title: -SIP-007-Armory-Protocol-Tool-Registry
status: deprecated
author: Unknown
approver: None
created_at: '2025-10-03T18:44:56.924563Z'
updated_at: '2026-01-10T11:15:34.139406Z'
original_filename: SIP-007-Armory-Protocol.md
---
# ✅ SIP-007: Armory Protocol (Tool Registry)

## 📌 Purpose
Define a **central Armory** (formerly ToolShed) as a versioned registry of tools, APIs, and integrations that agents can draw from.  
The Armory ensures **consistency, security, and traceability** in how tools are equipped to squads, without over-engineering a dedicated agent role yet.

---

## 🎯 Objectives
- Maintain a single **source of truth** for approved tools and integrations.  
- Prevent tool drift across squads (e.g., multiple inconsistent Stripe connectors).  
- Support **least privilege**: agents only access tools relevant to their role and current run.  
- Provide a growth path to later introduce a dedicated Quartermaster agent (Q) if needed.  

---

## 🧩 Armory Structure

- **Registry Format:** Versioned YAML/JSON or DB schema (`armory/registry.yaml`).  
- **Entries Include:**  
  - Tool ID (unique name)  
  - Type (API, SDK, CLI, script, wrapper)  
  - Approved version(s)  
  - Role access (who may equip it)  
  - Permissions/limits (read-only, sandbox-only, etc.)  
  - Notes/usage guidelines  
  - Status: Active / Deprecated / Proposed  

Example:
```yaml
- id: stripe_api_v1
  type: api
  version: 1.2.0
  roles: [rom, trin]
  permissions:
    - read_transactions
    - create_charges
  status: active
  notes: "Use for payment reconciliation only. Sandbox key in dev."
```

---

## 🔄 Workflow

1. **Proposal**  
   - New tools proposed via PR to `armory/registry.yaml`.  
   - Reviewed by Max (governance) + you (strategic curator).  

2. **Approval & Versioning**  
   - Merged entries bump Armory version (semver).  
   - Changelog entry created in `armory/changelog.md`.  

3. **Equipping Runs**  
   - At WarmBoot, Max consults Armory registry.  
   - Agents receive only tools tagged for their role + run mode.  

4. **Feedback Loop**  
   - Post-run WBA (SIP-006/6.1) logs tool usage.  
   - Ineffective or risky tools proposed for deprecation.  

---

## 📊 Metrics

- **Tool Utilization** → % of equipped tools actually invoked per run.  
- **Deprecation Rate** → # of tools removed due to poor outcomes.  
- **Drift Index** → # of unapproved/inconsistent tool uses (should trend to 0).  
- **Approval Latency** → avg time from proposal → merge.  

---

## 🚀 Benefits
- Provides a lean **Armory** pattern without adding an agent role yet.  
- Reduces tool drift, duplication, and security risk.  
- Creates a transparent, versioned log of tool evolution.  
- Establishes foundation for a future **Quartermaster agent (Q)**.  

---

## 📌 Status
- **SIP-007 Proposed** — Recommended for adoption as the tool registry protocol across all squads.
