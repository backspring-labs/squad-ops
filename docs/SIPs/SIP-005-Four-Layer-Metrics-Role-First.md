# ✅ SIP-005: Four-Layer Metrics & Root Cause Attribution — Role-First Edition

---
id: SIP-005
title: Four-Layer Metrics & RCA (Role-First)
status: Proposed
version: 1.1.0
owners: [max]
layers: [PRD, Agent, Squad, App/Ops]
roles_in_scope: [role.*]
created: 2025-09-26
updated: 2025-09-26
related: [SIP-004, SIP-006, SIP-007, SIP-009]
tags: [metrics, attribution, governance, role-first]
---

## 📌 Purpose
Separate **PRD**, **Agent (Role)**, **Squad**, and **App/Ops** layers; attribute failures correctly and feed changes back to the right layer. **All agent-layer metrics are by role**.

## 🧩 Monitoring Layers (highlights)
- **Agent Layer → Role Metrics**: success rate, error rate, efficiency, by `role.*`.
- **Squad Layer**: coordination latency, escalation frequency (role-origin tracked).
- **PRD & App/Ops**: unchanged, but impact mapped back to affected **roles**.

## 🔄 RCA Flow
1) KPI shortfall → 2) Check PRD → 3) Check **role** metrics → 4) Check Squad → 5) Business hypothesis. Assign root cause(s) and issue **role-first** recommendations.

## 📊 Metrics & Success
measured_by: [KPI-ROLE-SUCCESS, KPI-ESCALATION-RATE, KPI-KPI-ATTAINMENT]
success_criteria:
- Role success ↑ across 3 consecutive runs
- Escalations ↓ p95
- KPI attainment meets PRD targets

## 🧾 Changelog
- 1.1.0 — Role-first metric scopes.
- 1.0.0 — Initial.
