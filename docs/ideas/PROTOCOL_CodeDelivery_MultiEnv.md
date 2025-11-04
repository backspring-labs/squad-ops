# 🧩 PROTOCOL: Code Delivery Across Multi-Environment Deployments

**Version:** 1.0  
**Date:** 2025-10-15  
**Applies To:** Neo, Devin, EVE, Max, Data  
**Related Docs:** `PROTOCOL_CodeDelivery_LocalGitHybrid.md`, `PROTOCOL_WarmBoot_Modes.md`  

---

## 🧭 Purpose
Define a **single, environment-agnostic code-delivery model** that allows Devin to build and deliver code artifacts consistently across:
- **Local MacBook** development,
- **DGX Spark** local servers,
- **AWS / Azure / GCP** cloud deployments, and
- **Offline / air-gapped** installations.

The goal is one workflow that changes only in configuration, not in behavior.

---

## ⚙️ Unified GitOps Delivery Model
All environments follow the same logical pipeline:

```
Neo → Devin → (deliver code) → EVE → Data → Max
```

Devin always operates in a Git-based workflow; only the **transport layer** changes.

---

## 🔧 Delivery Modes

| Mode | Description | Typical Use |
|------|--------------|--------------|
| `local_fs` | Shared-volume write directly to host file system. | MacBook single-agent testing. |
| `local_git` | Commit + push to a local bare Git repo on shared volume. | DGX Spark multi-agent setups. |
| `remote_git` | Push to remote GitHub/GitLab repo and open PR. | Cloud or production runs. |
| `artifact` | Upload compressed artifacts via HTTP API endpoint. | Offline or air-gapped missions. |

---

## 🧱 Environment Configuration

### `.env.local`  *(MacBook)*
```bash
DELIVERY_MODE=local_fs
LOCAL_REPO_PATH=/Users/jason/squadops_repo
```

### `.env.spark`  *(DGX Spark)*
```bash
DELIVERY_MODE=local_git
LOCAL_REPO_PATH=/mnt/squadops_repo/.git
```

### `.env.aws`  *(Cloud)*
```bash
DELIVERY_MODE=remote_git
REMOTE_GIT_URL=https://github.com/squadops/fitness_tracker.git
REMOTE_GIT_TOKEN=${GITHUB_TOKEN}
```

### `.env.offline`  *(Air-gapped)*
```bash
DELIVERY_MODE=artifact
SQUADOPS_API=http://squadops/api/artifacts/upload
```

---

## 🧠 Devin Behavior by Mode

| Mode | Primary Action |
|------|----------------|
| **local_fs** | Copy build outputs to mounted `/squadops_repo/warmboots/PID-###/`. |
| **local_git** | Push feature branch to local bare repo. |
| **remote_git** | Push feature branch + open PR on remote Git host. |
| **artifact** | POST `.tar.gz` build bundle to SquadOps API. |

Each delivery concludes with a standardized message to SquadComms:

```json
{
  "pid": "PID-024",
  "delivery_mode": "local_git",
  "status": "success",
  "commit_hash": "b83d9a7",
  "files_changed": 8
}
```

---

## 🧩 Auto-Detection Logic (Neo Dispatcher)
```python
if os.getenv("DELIVERY_MODE"):
    mode = os.getenv("DELIVERY_MODE")
elif is_cloud_environment():
    mode = "remote_git"
elif is_local_git_repo():
    mode = "local_git"
else:
    mode = "local_fs"
```
Neo includes this mode in the `TaskSpec` payload to Devin.

---

## 🧭 Governance and Traceability

Regardless of mode:
- Every output must reference its **PID/ECID** in commit or artifact metadata.  
- **EVE** performs test validation before merge/promotion.  
- **Data** records metrics and coverage.  
- **Max** grants final approval.

Governance parity is preserved across environments.

---

## 🧠 Example Flow

**Local (Spark or MacBook):**
```
Devin → commit to local repo  → EVE tests  → Max merge
```

**Cloud (AWS/GCP/Azure):**
```
Devin → push PR → CI/CD triggers tests → EVE validation → Max merge
```

**Air-gapped:**
```
Devin → upload artifact → Neo unpacks → EVE runs tests → Max approve
```

---

## 🧭 Benefits
- **One mental model:** Same logic everywhere.  
- **Portable:** Mode switched by configuration only.  
- **Traceable:** PID tagging in all outputs.  
- **Secure:** Scoped credentials per environment.  
- **Scalable:** Works for single-agent or multi-agent squads.

---

## ✅ Implementation Priority
1. Implement `DELIVERY_MODE` variable in Neo and Devin containers.  
2. Standardize delivery confirmation message schema.  
3. Add EVE/Data hooks for post-delivery testing.  
4. Document environment examples in `/configs/`.  

---

> _This protocol establishes the universal, multi-environment code-delivery standard for SquadOps v1.0 and beyond._
