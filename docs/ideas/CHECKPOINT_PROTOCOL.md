# 🛑 Checkpoint Protocol

## 1. Purpose
A **checkpoint** is a snapshot of squad and app readiness at a defined step.  
It proves the system is in a good, reproducible state before moving to the next phase.  
Checkpoints are immutable and always reference the **PID** and **PID version**.

---

## 2. When to Create a Checkpoint
- After a phase/step passes its acceptance criteria (e.g., infra baseline, HelloSquad v0.1).  
- Before adding a new agent, role, or major config change.  
- When finalizing a warm-boot run to freeze the state for audit.  

---

## 3. Required Contents
Each checkpoint must contain:

### Metadata
- `checkpoint_id` (e.g., `CHK-002`)  
- `pid` (e.g., `PID-001`)  
- `pid_version` (e.g., `v1.2.0`)  
- `wb_id` (warm-boot run ID, if applicable)  
- `squad_profile_version` (e.g., `SP v0.3`)  
- `timestamp` (ISO 8601)  
- `owner` (lead agent/identity)  

### State Proofs
- **Health snapshot** for all agents (status, llm_mode, model_primary).  
- **Routing gates** (routable rules active at the time).  

### Test Evidence
- API & HTML test results (pass/fail + logs).  
- Role-specific tests (QA coverage, Audit checks).  

### Config & Build Fingerprints
- Key config hashes (docker-compose, instances directory).  
- Image tags/digests.  
- Model identifiers and parameters used.  

### Artifact Pointers
- Commit SHA.  
- Links/paths to logs and reports.  
- Optional tarball/checksum archive of artifacts.  

### Verdict
- `verified` | `rework`  
- Acceptance notes.

---

## 4. File Structure
Each checkpoint lives under `/checkpoints/CHK-00X/`:

```
/checkpoints/CHK-002/
  ├── checkpoint.yaml       # manifest (PID + version, wb_id, etc.)
  ├── health.json           # health snapshot of agents
  ├── tests/                # raw test outputs
  │     ├── api_junit.xml
  │     ├── html_junit.xml
  │     └── summary.json
  ├── config_hashes.json    # hashes of compose, configs, instances
  ├── notes.md              # operator notes
  └── artifacts/            # optional attachments
```

---

## 5. Example Manifest
```yaml
checkpoint_id: CHK-002
pid: PID-001
pid_version: v1.2.0
wb_id: WB-002
squad_profile_version: SP-0.3
timestamp: 2025-09-21T14:05:01Z
owner: max
commit: 4f8a1c2
images:
  lead: ghcr.io/org/lead:v0.3@sha256:abc...
  dev:  ghcr.io/org/dev:v0.3@sha256:def...
models:
  dev_primary: llama.cpp:Llama-3B-Q4
llm_mode_matrix:
  lead: real
  dev: real
health_snapshot: health.json
tests:
  summary: tests/summary.json
  api: tests/api_junit.xml
  html: tests/html_junit.xml
config_fingerprints:
  compose_sha256: "1d42...c9"
  instances_dir_sha256: "9a77...1b"
routable_policy: "status==online && llm_mode==real && accept_tasks!=false"
verdict: verified
acceptance_notes: "API+HTML passing; health green; routing gates enforced."
```

---

## 6. Lifecycle Operations
- **Create** → Only after green health + passing tests.  
- **Promote** → Mark a checkpoint as a baseline for the next phase.  
- **Retire** → Keep manifest but prune heavy artifacts. IDs are never reused.  
- **Compare** → Diff two checkpoints’ manifests to analyze changes.  

---

## 7. Relationship to PID and warm-boot
- **PID** → Defines the process/app. Stable across many checkpoints.  
- **PID version** → Identifies the exact spec state at time of checkpoint.  
- **warm-boot (WB)** → Identifies the squad-tuning cycle. A checkpoint may fall inside or outside a WB.  
- **Checkpoint (CHK)** → Immutable record that the system was verified at a specific moment.

---
