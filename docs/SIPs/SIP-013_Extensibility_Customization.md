# SIP-013: Extensibility & Customization Protocol

**Status:** Draft  
**Owner:** Max (Governance)  
**Contributors:** Nat, Neo, Data, EVE, Joi  
**Created:** 2025-09-27  

---

## 📌 Purpose  
Provide a structured method for deciding when product features, integrations, or customizations should be **hardwired in the core** vs. **externalized as extension points**. Ensure extensibility decisions are **documented, testable, and governable** as part of each PRD.  

---

## ✅ Objectives  
- Define **criteria** to guide hardwire vs. externalize decisions.  
- Require **Extensibility Assessment** in every PRD for new products or major versions.  
- Provide **matrix-based scoring** for consistency.  
- Standardize **extension patterns** (plugins, adapters, policies, events, slots).  
- Ensure governance (Max) and product (Nat) sign-off before build.  

---

## 🔄 Workflow  

1. **Requirement Intake (Nat)**  
   - Add **Extensibility Assessment Section** in PRD (see below).  
   - Identify candidate extension/customization points.  

2. **Matrix Scoring (Squad)**  
   - Use `EXT_MATRIX.md` template.  
   - Score candidate on **Change Frequency, Blast Radius, Ecosystem Need, Runtime Variability, Performance, Security, Observability**.  
   - If score ≥ 15 → Externalize. If < 15 → Hardwire.  

3. **Pattern Selection (Neo + Max)**  
   - Choose appropriate pattern (Plugin, Port/Adapter, Event, Policy, Slot).  
   - If uncertain → escalate to Expert Model for review.  

4. **Governance Sign-off (Max)**  
   - Validates decision logged in PRD + ADR.  
   - Checks contract tests, fitness functions, and telemetry hooks exist.  

5. **Implementation (Neo + EVE)**  
   - Neo scaffolds with chosen pattern kit.  
   - EVE enforces contract tests + guardrails.  
   - Data instruments telemetry (`ext_point`, `provider`, `latency_ms`, `errors`).  

6. **Documentation (Joi)**  
   - ADR committed with PID reference.  
   - Extension contracts and usage documented in `/docs/extensions/`.  

---

## 📄 PRD Requirements  

Every PRD must include:  

### Extensibility Assessment Section  

```markdown
## Extensibility Assessment

### Candidate Extension Point
- [Name / Description]

### Assessment Matrix (score 1–5, weighted)
- Change Frequency (x2):  
- Blast Radius (x2):  
- Ecosystem Need (x2):  
- Runtime Variability (x1):  
- Performance Sensitivity (x1):  
- Security Risk (x2):  
- Observability/Governance (x1):  

**Total Score:** [XX]  
**Decision:** Hardwire / Externalize  

### Selected Pattern
- [Strategy / Plugin / Port-Adapter / Event / Policy / Slot]

### Guardrails
- [Contract tests, Fitness functions, Security constraints]  

### Governance Sign-off
- Approved by: [Max / Date]  
```

---

## 📦 Artifacts  

- `EXT_MATRIX.md` — scoring template.  
- `EXT_ADR_TEMPLATE.md` — decision record.  
- `/kits/extensions/` — scaffolds for Plugin loader, Port/Adapter, Policy, Event bus, Slot API.  
- `EXT_REGISTRY.md` — manifest of all active extension points (linked to PIDs).  

---

## ✅ Governance  

- **Max:** approves decisions, ensures ADRs + guardrails exist.  
- **Nat:** includes assessment in PRD, drives catalog updates.  
- **Neo:** implements extension scaffolds.  
- **EVE:** validates tests, chaos injection, regression checks.  
- **Data:** captures telemetry + success metrics.  
- **Joi:** documents extension contracts and dev experience notes.  

---

## 📊 Success Metrics  

- % PRDs with completed Extensibility Assessment = 100%  
- Reduction in ad-hoc code forks / brittle hardwired logic  
- Clear traceability of extension points in `EXT_REGISTRY.md`  
- Externalized modules measurable with latency/error telemetry  
- No ungoverned extension points in production  

---

## 🔮 Future Enhancements  

- Automate decision support: recommend pattern based on matrix score.  
- Visualize extension points across squads in SOC UI.  
- Add plugin signing, SemVer gates, and sandbox enforcement for untrusted extensions.  
- Auto-generate Glyph diagrams for extension topology.  

---

> This protocol ensures SquadOps projects balance **scalability, maintainability, and governance** by making extension decisions explicit, measurable, and repeatable.
