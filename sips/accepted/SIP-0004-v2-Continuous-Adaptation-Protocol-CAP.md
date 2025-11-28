---
sip_uid: "17642554775827032"
sip_number: 4
title: "Continuous-Adaptation-Protocol-CAP"
status: "accepted"
author: "Unknown"
approver: "None"
created_at: "2025-10-03T18:44:56.922945Z"
updated_at: "2025-11-27T10:12:48.878051Z"
original_filename: "SIP-004-Continuous-Adaptation-Protocol-Role-First.md"
---

# ✅ SIP-004: Continuous Adaptation Protocol (CAP) — Role-First Addendum

---
id: SIP-004
title: Continuous Adaptation Protocol (CAP)
status: Proposed
version: 1.1.0
owners: [max]
roles_in_scope: [role.*]   # applies to all roles; role-first model
layers: [Agent, Squad]
created: 2025-09-26
updated: 2025-09-26
related: [SIP-005, SIP-006, SIP-007, SIP-009]
tags: [adaptation, governance, role-first]
---

## 📌 Purpose
Formalize daily **micro-adjustments** to roles, guardrails, and tools. **All adjustments refer to roles** (e.g., `role.scout`) with **instances carrying only deltas** in squad space.

## 🔑 Role-First Changes
- **Role DNA** is the canonical baseline: `/roles/<role>/dna/role-dna.md`.
- **Instance DNA** files contain only *deltas* under `/squads/<squad>/dna/<instance>.md`.
- Adjustments, guardrails, and tool access are recorded against **roles**, not identities.

## 🔄 CAP Workflow (unchanged logic, role-first references)
1) Log run outcomes → 2) Extract signals → 3) Propose **role** changes (heuristics/tools/guardrails) → 4) Governance review → 5) WarmBoot with updated role baselines.

## 📊 Metrics & Success
- **role_fitness_delta**: per-role performance change vs previous baseline.
- **adjustment_frequency**: role-level tweaks per run.
- **time_to_recovery** after role-level regression.
measured_by: [KPI-ROLE-FITNESS, KPI-ADJUST-FREQ, KPI-TTR]

## 🧾 Changelog
- 1.1.0 — Converted to role-first conventions; split role vs instance DNA.
- 1.0.0 — Initial.
