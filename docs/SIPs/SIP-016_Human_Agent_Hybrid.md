# SIP-016: Human–Agent Hybrid Squad Operations

**Status:** Draft  
**Owner:** Max (Governance)  
**Contributors:** Nat (Product), Neo (Dev), EVE (Test), Data (Metrics), Quark (Finance), Joi (Comms), Human Leads  
**Created:** 2025-09-27  

---

## 📌 Purpose  
Define an **operational cadence** for human–agent hybrid squads. Ensure humans engage during working hours for planning, oversight, and interpretation, while agent squads operate autonomously in off-hours to maximize throughput and learning.  

---

## ✅ Objectives  
- Establish **daily rhythms** for hybrid squad activity.  
- Define **human squad roles** required for governance, product direction, and customer alignment.  
- Maximize agent squad productivity without losing human oversight or strategic context.  
- Create a **feedback loop**: nightly agent cycles → morning review → afternoon fixes & alignment → next nightly cycle.  

---

## 🕑 Daily Cadence  

### Morning Session (Human-Led, ~1–2 hrs)  
- **Review** SOC Review Module output (see SIP-014).  
- **Triage** infra alerts, bug failures, regressions.  
- **Interpret metrics**: governance deviations, cost anomalies, customer impact.  
- **Approve fixes**: select SIPs, assign infra tasks, bug patches for agents.  

### Midday Mini-Cycle (Hybrid, ~2–3 hrs)  
- **Kickoff fixes**: Neo + EVE agents run infra/code/test repairs.  
- **Humans validate early fixes** or reprioritize.  
- **Plan next nightly cycle**: update PRDs, extensibility decisions (see SIP-013), pattern choices (see SIP-012).  

### Afternoon Sync (Human-Led, ~30 min)  
- **Close loop**: confirm fixes applied, confirm tomorrow’s scope.  
- **Prep backlog**: human squad ensures clarity for nightly agent run.  

### Nightly Cycle (Agent-Only, 8–10 hrs)  
- **Agents execute plan autonomously**: implement features, run tests, log metrics.  
- **SOC captures results** for morning review.  

---

## 🧩 Human Squad Role Makeup  

| **Role** | **Responsibilities** | **Notes** |
|----------|----------------------|-----------|
| **Product Lead (Human Nat)** | Aligns backlog, reviews PRDs, approves pattern/extensibility choices | Works closely with Nat agent; final decision authority. |
| **Tech Lead (Human Neo)** | Oversees architecture, validates critical code reviews, resolves blockers | Delegates bulk coding to Neo agent. |
| **QA/Release Lead (Human EVE)** | Reviews test coverage, approves fitness functions, greenlights releases | Ensures no blind spots in regression tests. |
| **Metrics/Finance Lead (Human Data/Quark)** | Reviews costs, DORA metrics, usage telemetry | Signs off on budget anomalies, infra spend. |
| **Governance Lead (Human Max)** | Reviews compliance, security posture, and redesign triggers (see SIP-015) | Partner to Max agent for escalations. |
| **DX/Comms Lead (Human Joi)** | Validates UX decisions, communicates results to stakeholders | Ensures agent squads don’t lose customer perspective. |

> Not every project needs every role filled by a different human; in small orgs, one person may cover multiple hats.  

---

## 🔄 Benefits  
- Humans focus on **strategy + judgment**, agents on **execution + iteration**.  
- Every day = **two cycles** (mini + full), effectively doubling iteration speed.  
- Human squad shapes trajectory, agent squad handles grind.  
- Stronger alignment to enterprise workflows (morning standup, afternoon review).  

---

> This protocol ensures SquadOps can scale into **hybrid human–AI teaming**, balancing enterprise oversight with autonomous execution.
