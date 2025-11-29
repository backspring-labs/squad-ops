---
sip_uid: '17642554775836826'
sip_number: 6
title: Warm-Boot-Analysis-WBA
status: deprecated
author: Unknown
approver: None
created_at: '2025-10-03T18:44:56.924084Z'
updated_at: '2025-11-28T15:53:50.637543Z'
original_filename: SIP-006-Warm-Boot-Analysis-Role-First.md
---
# ✅ SIP-006: Warm Boot Analysis Protocol (WBA) — Role-First

---
id: SIP-006
title: Warm Boot Analysis (WBA)
status: Proposed
version: 1.1.0
owners: [max]
layers: [Agent, Squad, App/Ops]
roles_in_scope: [role.*]
created: 2025-09-26
updated: 2025-09-26
related: [SIP-004, SIP-005, SIP-007, SIP-009]
tags: [retro, governance, role-first]
---

## 📌 Purpose
Require a **Good/Bad/Ugly** retro after every run. Findings and recommendations are **role-first**; instances are noted only for deltas.

## 🧰 WBA Output Sections
- **Role Outcomes**: per `role.*` improvements/regressions.
- **Squad Coordination**: role-origin latency/escalations.
- **Ops/App KPIs**: mapped back to affected roles.
- **Recommendations**: role baseline changes, Armory role_scopes updates, squad protocol tweaks.

## 📊 Measured By
measured_by: [KPI-WBA-LAT, KPI-ROLE-FITNESS, KPI-THROUGHPUT]
success_criteria:
- WBA p95 latency ≤ 60s
- ≥1 role-level improvement per run or explicit “hold” rationale

## 🧾 Changelog
- 1.1.0 — Role-first framing.
- 1.0.0 — Initial.
