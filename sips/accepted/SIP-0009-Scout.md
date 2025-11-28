---
sip_uid: "17642554775843527"
sip_number: 9
title: "Scout"
status: "accepted"
author: "Unknown"
approver: "None"
created_at: "**Role DNA** (baseline) or **Instance DNA** (delta) as needed (SIP-004)."
updated_at: "2025-11-27T10:12:48.882287Z"
original_filename: "SIP-009-Role-First-Practice-Range-Protocol.md"
---

# ✅ SIP-009: Practice Range (Agent Test Harness) — **Role-First Edition**

## 📌 Purpose
Define a **Practice Range** where roles (not identities) prove their tools and skills *before* entering production runs.  
All specifications, drills, tool bindings, and gates reference **roles** (e.g., `role.scout`, `role.signal_miner`) — never identity nicknames. Identities remain replaceable **instances of roles** and may only add minimal, declarative overrides at the squad level.

---

## 🔑 Role-First Principles
- **No identity hardwiring.** Files, folders, Armory bindings, drills, and CI gates must reference **roles**.
- **Role baselines + instance deltas.** Each role provides a canonical baseline. Instances may layer *small overrides* in squad space.
- **Practice proves capability at the role layer.** Every instance of a role must satisfy that role’s drills to deploy.
- **Traceability to SIPs & KPIs** is recorded by role first, then (optionally) instance notes.

---

## 🎯 Objectives
- Verify **Armory tools** and **role skills** against controlled scenarios.
- Provide **objective scoring** and pass/fail gates by **role**.
- Enable **role drills** and **squad scrimmages** (multi-role) with traceability.
- Feed results into **Agent DNA** (role baseline + instance delta; SIP-004) and **WBA** (SIP-006/6.1).

---

## 🧩 Directory Layout (Role-First)

```
roles/
  scout/
    role.yaml                 # role definition, capabilities, guardrails
    drills/                   # role drills (no identity names)
      scout_snipe_basic.yaml
      scout_timeboxed.yaml
    dna/
      role-dna.md             # baseline heuristics + changelog
  strategist/
  finance_risk/
  signal_miner/
  automation_engineer/
  creative_enhancer/
  customer_liaison/

squads/
  <squad-name>/
    instances.yaml            # identity → role mapping + minimal overrides
    drills/                   # optional additive, instance-specific drills (rare)
    dna/
      <instance>.md           # instance deltas only (references role baseline)

armory/
  registry.yaml               # tool entries with role_scopes (no identity scopes)

practice/
  fixtures/
  reports/
  schema/
```

---

## 🧾 Role Spec (example) — `roles/scout/role.yaml`

```yaml
id: role.scout
title: Scout
capabilities:
  - find_arbitrage_opportunities
  - generate_flip_briefs
inputs:
  - demand_signals
  - marketplace_listings
armory_bindings:
  - tool_id: marketplaces_scraper
    mode: read
  - tool_id: ebay_api_v1
    mode: read
guardrails:
  max_briefs_per_day: 20
  min_roi_pct: 20
metrics:
  - name: role_success_rate
  - name: avg_brief_roi
drills:
  - drills/scout_snipe_basic.yaml
  - drills/scout_timeboxed.yaml
```

> **Note:** No identity nicknames appear anywhere in role specs.

---

## 🧪 Drill Types (Role-First)

### A) Unit Tool Checks (per Armory item)
**Goal:** verify API/SDK behavior and error handling in test mode.  
**Binding:** via `armory.registry.yaml` → `role_scopes`.

### B) Role Drills (per Role)
- **role.scout:** snipe N items in Market Sim within budget; hit ≥25% projected ROI after fees.
- **role.signal_miner:** parse mixed WTB/ISO posts; ≥95% precision/recall on item extraction.
- **role.automation_engineer:** listing/relisting resilience; recover from injected 5xx.
- **role.finance_risk:** enforce per-flip exposure ≤ X%; reject sub-threshold ROI; ledger integrity.
- **role.creative_enhancer:** transform listings; increase simulated CTR ≥15% vs baseline.
- **role.customer_liaison:** resolve ≥90% chats without escalation; SLA p95 reply ≤30s.
- **role.strategist:** choose portfolio mix in volatility sim; outperform naive baseline by ≥5pp ROI.

### C) Squad Scrimmages (multi-role, end-to-end)
- Scenario: 2h simulated market window with mixed signals.
- Success: profit ≥ target, escalation rate ≤ threshold, coordination latency p95 ≤ Xs.

### D) Chaos & Recovery
- Kill one **role** process mid-run; verify degraded targets still met.
- Revoke an Armory tool mid-drill; verify graceful fallback or halt.

---

## 📊 Scoring Rubric (YAML Example) — `roles/scout/drills/scout_snipe_basic.yaml`

```yaml
id: drill-role-scout-snipe-basic
role: role.scout
env: sandbox
inputs:
  signals_fixture: practice/fixtures/market_signals_01.json
  budget_usd: 200
targets:
  min_roi_pct: 25
  max_exposure_pct: 5
  max_time_seconds: 900
metrics:
  - name: projected_roi_pct
    comparator: ">="
    target: 25
  - name: policy_violations
    comparator: "=="
    target: 0
  - name: elapsed_seconds
    comparator: "<="
    target: 900
outcomes:
  pass_if: ["projected_roi_pct", "policy_violations", "elapsed_seconds"]
```

---

## 🔐 Security & Permissions (Role-Scoped)
- **Armory `role_scopes` only.** Tool entries must list roles, never identities.
- **Sandbox IAM** restricts DB writes to `practice_*` schemas/buckets; secrets are **test-only** and ephemeral.
- **CI lint** blocks any identity-named files in `roles/**` or any Armory entries keyed by identity.

---

## 🔄 Workflow

1. **Select Drills (by Role)**
   - Role spec lists required drills (`roles/<role>/drills/*.yaml`).

2. **Provision Sandbox**
   - Orchestrator spins ephemeral env; mock secrets injected from Armory.

3. **Execute & Observe**
   - Run drills; collect metrics/logs/traces.

4. **Score & Report**
   - Scoring engine computes rubric → writes `practice/reports/run-XXX-PR.md` & JSON.

5. **Feedback Loop**
   - Update **Role DNA** (baseline) or **Instance DNA** (delta) as needed (SIP-004).
   - Reference Practice Report in **WBA** (SIP-006/6.1) when graduating to live runs.

---

## ✅ CI Gates (Role-First)
- **Required to merge:** Unit Tool Checks for any **new/changed Armory items** (role-scoped).
- **Required to deploy to stage:** All **role drills** pass for every instance mapped to that role.
- **Required to deploy to prod:** Latest **squad scrimmage** + **chaos/recovery** drills (multi-role) passed within 30 days.

---

## 🔁 Integration with SIPs
- **SIP-004 (Agent DNA):** Results drive role-baseline changes and instance deltas (no identity-only baselines).
- **SIP-005 (Four-Layer Metrics):** Practice validates **Agent (role)** and **Squad** layers pre-run.
- **SIP-006/6.1 (WBA):** Practice Reports attached as pre-flight evidence.
- **SIP-007 (Armory):** Tools must specify `role_scopes`; unit checks must pass before activation.

---

## 🧩 Success Criteria
- Practice → production performance correlation ≥ 80% (90-day window).  
- Median practice run ≤ 10 min; cost/run <$0.50 (dev).  
- **Identity leakage = 0** (CI lints enforce role-only references in roles/ & armory/).

---

## 📌 Status
- **SIP-009 (Role-First) Proposed** — Adopt to validate roles and squads before live WarmBoot runs, with **no identity hardwiring**.
