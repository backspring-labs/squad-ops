---
sip_uid: "17642554775827020"
sip_number: 5
title: "-SIP-005-Four-Layer-Metrics-Root-Cause-Attribution-Protocol-MRCA"
status: "accepted"
author: "Unknown"
approver: "None"
created_at: "2025-10-03T18:44:56.923409Z"
updated_at: "2025-11-27T10:12:48.878732Z"
original_filename: "SIP-005-Four-Layer-Metrics-Protocol.md"
---

# ✅ SIP-005: Four-Layer Metrics & Root Cause Attribution Protocol (MRCA)

## 📌 Purpose
Establish a structured framework for monitoring **four layers of squad performance** — *Product Definition, Agents, Squad, and Application* — in order to distinguish root causes of failure and ensure that **feedback drives evolution at the correct level(s).**  

The central thesis:  
> Success or failure of an app run is multi-layered. By monitoring PRDs, agents, squads, and app KPIs separately, we can evolve the system precisely where improvement is needed.

---

## 🎯 Objectives  
- Monitor **requirements quality, agent DNA, squad coordination, and app outcomes** independently.  
- Ensure **feedback loops target the right layer(s)**.  
- Preserve version history and traceability of changes at every level.  
- Demonstrate compounding improvement through continuous adaptation across layers.  

---

## 🧩 The Four Monitoring Layers  

### 1. **Product Definition Layer (PRD / Requirements)**  
- **Artifacts:** PRD, PIDs, user stories, use cases.  
- **Monitored by:** Nat/Yelena (strategy), Max (governance).  
- **Metrics:**  
  - Ambiguity Index → % of requirements with vague language.  
  - Coverage → % of app features mapped to requirements.  
  - Change Frequency → # of mid-cycle requirement changes.  
- **Feedback Actions:**  
  - Rewrite ambiguous PIDs.  
  - Strengthen acceptance criteria.  
  - Add missing use cases.  
- **Versioning:** PRD version history maintained in `prd/` with changelogs.  

---

### 2. **Agent Layer (Config, Tools, DNA)**  
- **Artifacts:** `agent_dna/` changelogs, tool access manifests.  
- **Monitored by:** Each agent’s steward + Max enforcing governance.  
- **Metrics:**  
  - Success rate vs. prior version.  
  - Error rate (% of tasks rejected by governance).  
  - Efficiency delta (time-to-completion vs. prior run).  
- **Feedback Actions:**  
  - Refine heuristics (Pak adjusts snipe timing).  
  - Expand/restrict toolkits (Trin gains API access, Rune loses ineffective tools).  
  - Tweak guardrails (Rom lowers exposure %).  
- **Versioning:** Agents increment **DNA version** (MAJOR.MINOR.PATCH) after adjustments.  

---

### 3. **Squad Layer (Profile & Collaboration)**  
- **Artifacts:** Squad config, comms/concurrency logs, escalation logs.  
- **Monitored by:** Max (governance), EVE (QA/test).  
- **Metrics:**  
  - Coordination Latency → avg time from signal to execution.  
  - Escalation Frequency → % of tasks needing governance/human intervention.  
  - Throughput Success → % of coordinated tasks completed without delay.  
- **Feedback Actions:**  
  - Adjust collaboration protocol.  
  - Rebalance role responsibility (e.g., Lore vs. Pak in scouting).  
  - Add/remove checkpoints in the comms workflow.  
- **Versioning:** Squad profile updates versioned in `squad_config/` with changelogs.  

---

### 4. **Application Layer (KPIs / Business Outcomes)**  
- **Artifacts:** App metrics dashboards, customer analytics, revenue logs.  
- **Monitored by:** Data, Rom, Max.  
- **Metrics:**  
  - KPI attainment (% vs. PRD-defined success criteria).  
  - ROI / profit margins.  
  - Adoption, retention, uptime, user satisfaction.  
- **Feedback Actions:**  
  - If KPIs fail but PRD quality was low → refine Product Layer.  
  - If KPIs fail but PRD solid → review Agent + Squad layers.  
  - If all upstream layers were solid → business hypothesis may be flawed.  
- **Versioning:** App KPIs tracked per WarmBoot run in `app_metrics/`.  

---

## 🔄 Root Cause Attribution Flow  

1. **App KPIs measured** (success/failure, profit/loss, adoption, etc.).  
2. **If KPI shortfall detected → RCA cycle triggered.**  
   - Check Product Layer → ambiguous/incomplete PRD?  
   - If clean → Check Agent Layer → regressions or gaps?  
   - If clean → Check Squad Layer → coordination bottlenecks?  
   - If clean → Accept that App/business hypothesis itself failed.  
3. **Assign root cause** → Product, Agent, Squad, or App (1 or multiple).  
4. **Apply Feedback** → Trigger adjustments at the identified level(s).  
5. **Version Bumps:**  
   - PRD → `prd/versions.md`  
   - Agent DNA → `agent_dna/{agent}.md`  
   - Squad → `squad_config/changelog.md`  
   - App → `app_metrics/run-xxx.md`  

---

## 🧠 Example Scenarios  

- **App failed due to unclear PRD**  
  - Ambiguity Index = 40%.  
  - Feedback: Rewrite PID, strengthen acceptance criteria. Agents and squad unchanged.  

- **App failed but PRD was strong**  
  - Pak v1.4 had lower ROI vs. v1.3.  
  - Feedback: Patch Pak DNA (v1.4.1).  

- **App failed despite strong PRD + agents**  
  - Escalation rate = 60%. Coordination latency doubled.  
  - Feedback: Adjust comms protocol, rebalance Lore/Pak.  

- **App failed despite solid upstream layers**  
  - KPIs show lack of adoption.  
  - Feedback: Revisit business hypothesis or product-market fit.  

---

## 📊 Feedback-Driven Evolution  

After every cycle, **at least one layer must evolve**:  
- **PRD →** clarified docs, stronger requirements.  
- **Agent →** DNA version bump.  
- **Squad →** collaboration protocol refinement.  
- **App →** KPI adjustments or pivot in business hypothesis.  

If multiple layers evolve together, the system compounds faster.  

---

## 🚀 Benefits  
- Prevents misattribution of failure to “the squad” when root cause was upstream.  
- Ensures **targeted adaptation** at the right level.  
- Creates version history across **PRD, Agent, Squad, and App** layers.  
- Reinforces the SquadOps thesis: *role diversity + targeted continuous adaptation → higher success rates over time.*  

---

## 📌 Status  
- **SIP-005 Proposed** — Recommended for adoption across all active squads as the canonical metrics and attribution protocol.  
