# 🧩 **IDEA-006: Project Assessment Protocol (v1.0)**
*(Initiate → Define → Engage → Activate)*

---

## 📘 **Purpose**
Provide a unified engagement model for the Nexa Squad that adapts dynamically to three repository contexts:  
1. **🆕 Net-New Repo** – no existing codebase  
2. **🔁 Existing SquadOps Repo** – already compliant with SquadOps standards  
3. **🧩 Foreign Repo** – external codebase with no prior SquadOps involvement  

This protocol ensures that any entry point—from a 1-line idea to a compliance audit—can be executed responsibly with full traceability and governance.

---

## 🧭 **Repo Classification Variable**

| Code | Repo Type | Description | Typical Entry Behavior |
|------|------------|-------------|------------------------|
| `R0` | **Net-New** | Empty or skeletal repo. | Initialize PID registry, default protocols, and starter app. |
| `R1` | **Existing SquadOps** | Contains `/agents`, `/docs`, `/warmboot_runs/`, etc. | Parse manifest, resume tasks, or launch WarmBoot. |
| `R2` | **Foreign** | External or legacy repo. | Run Repo Assimilation (scan, PID overlay, protocol injection). |

---

## 🔄 **Lifecycle Entry Matrix**

| Stage | Entry Point | Supported Repo Types | Primary Agents | Output Artifacts |
|-------|-------------|----------------------|----------------|------------------|
| **Ideation** | Idea Kickstart | R0 | Nat + Og + Max | Concept Brief → PID 000 scaffold |
| **Product Definition** | PRD Submission | R0 / R1 | Nat + Max + Neo | PRD → App build |
| **Process Design** | Workflow Mapping | R1 / R2 | Nat + Joi + Data | PID registry entries + UC/BP docs |
| **Technical Design** | API or Spec Request | R1 / R2 | Neo + Data + EVE | API spec + sequence diagram |
| **Data Governance** | KDE & KPI Mapping | R1 / R2 | Data + Nat | KDE Registry + Metrics Map |
| **Testing** | QA / Pen Testing | R1 / R2 | EVE + Max | TP/TC/PEN Artifacts |
| **Build Execution** | Task Queue Injection | R1 | Max + Neo | Code commits + Gantt Metrics |
| **Deployment / WarmBoot** | Performance Benchmark | R1 | Max + Data + EVE | WarmBoot Report + Scorecard |
| **Governance Audit** | Compliance Check | R1 / R2 | Max + Data | Governance Report + PID Validation |
| **Optimization** | RCA / SIP Proposal | R1 / R2 | Max + EVE + Data | RCA Log + SIP File |
| **Meta-Level** | Squad Creation | R0 / R1 | Max | New Squad Manifest + WarmBoot-000 |

---

## 🧩 **Repo Assimilation Sequence (R2)**

1. **Context Scan** – Neo + Data parse repo structure, language, deps, and commits.  
2. **Artifact Extraction** – Identify code modules, tests, and configs.  
3. **PID Overlay Creation** – Generate `process_registry.md` mapping files → PIDs.  
4. **Protocol Injection** – Add `/protocols/`, `/testing/`, `/warmboot_runs/` scaffolds.  
5. **Baseline WarmBoot-000** – Run diagnostic scan only.  
6. **Alignment Report** – Output `SQUADOPS_ONBOARDING_REPORT.md`.

---

## 🧠 **Expanded Agent Skill Matrix**

| Agent | New Capabilities | Function in Repo-Aware Ops |
|--------|------------------|----------------------------|
| **Max** | Repo classification logic, permission validation, cross-repo PID governance | Oversees correct entry path and compliance. |
| **Nat** | README and issue context assimilation, PRD auto-generation | Converts code context to business intent. |
| **Neo** | Repo parser, dependency graphing, reverse engineering, build env isolation | Connects foreign code to SquadOps tasks. |
| **EVE** | Coverage audit, CI/CD inspection, diff testing | Validates unknown repos before WarmBoot. |
| **Data** | Schema inference, KDE discovery, metrics diffing | Builds data governance from existing sources. |
| **Joi** | Context summarization from external threads | Bridges human stakeholders ↔ squad. |
| **Glyph** | Repo brand/style inference from assets | Maintains visual continuity. |
| **Og** | Pattern mining across repos + embedding search | Provides historical comparatives. |
| **Quark** | Cost/licensing assessment | Manages financial + legal risk. |
| **Marvin** | Network sandboxing + vuln scanning | Secures foreign imports. |
| **Flynn** | Cross-IDE and container build setup | Ensures compilation and local run. |

---

## ⚙️ **Operational Hooks**

| Function | Trigger | Agents |
|-----------|----------|---------|
| `detect_repo_type()` | URL submitted to Max | Max + Neo |
| `run_repo_scan()` | `repo_type == R2` | Neo + Data |
| `init_squad_manifest()` | First commit in R0 repo | Max + Nat |
| `inject_protocols()` | Missing `/protocols` dir | Neo + Max |
| `warmboot_baseline()` | Post-assimilation diagnostic | Max + EVE + Data |

---

## 📊 **New Metrics**

| Metric | Description |
|---------|-------------|
| **Assimilation Score** | % of repo components successfully mapped to PIDs |
| **Protocol Coverage Rate** | Protocol files present / expected total |
| **Integration Latency** | Time from repo import → WarmBoot ready |
| **Cross-Repo Governance Index** | % of repos meeting minimum traceability standard |

---

## 🪶 **Governance & Compliance**

- **Max** validates repo type assignment and ensures all imports use sandboxed permissions.  
- **EVE + Marvin** verify security compliance before any writes to foreign repos.  
- **Data** ensures KDEs and metrics are properly tagged with source repo identifiers.  
- **Nat** confirms alignment between repo intent and business objectives.

---

## 🧩 **Directory Structure Example**

```
/repo_root/
 ├── /agents/
 ├── /docs/
 │     ├── process_registry.md
 │     ├── protocols/
 │     │     └── IDEA-006-ProjectAssessment.md
 │     └── governance/
 ├── /warmboot_runs/
 ├── /testing/
 └── /analytics/
```

---

## ✅ **Outcome**
IDEA-006 enables the Nexa Squad to:
- Accept **any repo URL** as a valid mission entry.  
- Perform **automated onboarding** of external projects.  
- Maintain **governance, testing, and traceability** regardless of repo origin.  
- Continuously expand the squad’s ability to collaborate across ecosystems.
