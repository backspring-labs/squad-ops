# 💡 IDEA-008: Senior Developer Agent Integration (OpenCode as Mentor)

**Date:** 2025-10-15  
**Status:** Backlog (For Future Evaluation)  
**Proposed By:** Jason  
**Category:** SquadOps Agent Enhancement  

---

## 🧩 Summary
Explore integrating **OpenCode (or successor “Crush”)** as a **Senior Developer Agent (SDA)** within SquadOps.  
The SDA would act as a high-context, code-aware assistant that Neo or other dev agents can escalate to for advanced debugging, refactoring, or pattern consultation.

---

## 🎯 Motivation
Neo performs well for structured builds but can stall when:
- Code complexity exceeds local context,
- Repeated test failures occur, or
- Design tradeoffs require deeper architectural reasoning.

OpenCode’s diff-based patching, LSP integration, and multi-model support make it a strong candidate for the “senior developer” role that supports or mentors other dev agents.

---

## ⚙️ Concept Overview

**Primary Use Case:**  
Neo detects a low-confidence build or test failure → Escalates to SDA for review → SDA proposes diffs → EVE validates → Max approves merge.

**Key Functions:**  
- Code review and patch generation  
- Architecture or refactoring guidance  
- Automated re-testing feedback loop  
- Knowledge graph of past fixes to inform future recommendations  

---

## 🔄 Potential Integration Points

| Layer | Integration Type | Description |
|-------|------------------|-------------|
| **SquadComms** | RMQ topic `escalation.senior_help` | Neo publishes escalation event |
| **SquadNet** | Shared container network | SDA container accesses repo volume |
| **Prefect** | Task orchestration | Logs SDA patch tasks and outcomes |
| **EVE** | Test validation | Runs regression tests post-patch |
| **Data** | Metrics analysis | Tracks frequency and success rate of SDA consultations |

---

## ⚠️ Risks & Considerations
- Requires controlled sandbox access to codebase  
- Must enforce review gates (no blind auto-merge)  
- Potential GPU/CPU overhead for duplicate LSP analysis  
- OpenCode repo is archived; long-term viability depends on forking or replacing with Crush  

---

## 🧭 Next Steps (Future Exploration)
1. Evaluate viability of integrating **Crush** or a forked **OpenCode runtime**.  
2. Prototype message schema for `escalation.senior_help`.  
3. Add SDA container to WarmBoot stack as an optional service.  
4. Measure impact on developer agent performance and test pass rate.

---

> _Captured for review in future SquadOps iterations. Not yet scheduled for implementation._
