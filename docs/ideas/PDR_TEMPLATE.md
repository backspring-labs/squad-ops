# 📝 PDR Template (Agent Squad Prompt Guide)

## 1. Metadata (always required)
- **PID:**  
- **App Name:**  
- **Version:**  
- **warm-boot ID (if applicable):**  
- **Date:**  
- **Agents involved:**  

---

## 2. Overview
> *Prompt cue:* Summarize what this app is, which squad roles are responsible, and how it validates or extends a process.

---

## 3. Objectives
- Feature or process to validate  
- Expected squad learning (e.g., new config tuning, error handling, routing rules)  

---

## 4. Scope
- **In Scope:**  
  > *Prompt cue:* What must be delivered in this iteration?  
- **Out of Scope:**  
  > *Prompt cue:* What is explicitly excluded for now?  

---

## 5. Requirements

### Functional
> *Prompt cue:* List each functional requirement as a testable statement.

### Non-Functional
> *Prompt cue:* What constraints matter (performance, latency, cost, etc.)?

---

## 6. Deliverables
- Source code  
- Docs (BP, UC, TC)  
- Registry entry update  
- warm-boot log linkage  

---

## 7. Test Plan
> *Prompt cue:* For each requirement, define the test case ID, precondition, action, expected result.

---

## 8. Acceptance Criteria
> *Prompt cue:* Define explicit, binary checks for verification.

---

## 9. Risks & Mitigations
> *Prompt cue:* Identify potential blockers, how to catch them early, and mitigation strategies.

---

## 10. Timeline
> *Prompt cue:* Align to squad SDLC: PID proposal → Build & Test → warm-boot run → Retrospective.

---

# 🔑 Why this guide matters
- **Optimizes builds:** forces clarity on scope + tests before coding.  
- **Consistent artifacts:** every PID has the same doc structure.  
- **Traceable:** always includes PID, warm-boot ID, and agent assignments.  
- **Prompt-ready:** agents can literally be fed this template and fill it out.  
