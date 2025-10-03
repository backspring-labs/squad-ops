# 📝 Change Request — Agent Folder Structure Refactor (v6)

## 📌 Summary
Refactor the **agent folder structure** to decouple reusable **roles** from named **instances**.  
This avoids hardcoding specific agent identity names (e.g., `max/`) in the core app tree, making the framework reusable for generic squads.

---

## ✅ Current State
- Agent folders are identity-specific (e.g., `/agents/max/`, `/agents/neo/`).
- Container deploy files and role logic are coupled with the agent’s personal identity name.
- Works for the current squad, but **limits reusability** for other squads or public release.

---

## 🚨 Problem Statement
Hardcoding identities into the repo structure:  
- Couples framework code with personal squad lore.  
- Makes open-sourcing difficult (others must rename or fork your naming).  
- Hinders ability to spin up multiple instances of the same role (e.g., two developers).  

---

## 🎯 Proposed Solution
### 1. Split Roles vs. Instances
- **Roles:** Define reusable agent logic, tools, and Dockerfiles.  
- **Instances:** Bind roles to **identity + config**.  

### 2. Add Squad Manifest
Introduce `/manifests/squad.yaml` listing active instances.  
This enables launching different squads without code changes.

### 3. Update Docker Compose
Parameterize by `${ROLE}` and `${AGENT_ID}` so that containers can be dynamically instantiated from the manifest.

### 4. Backward Compatibility
Keep existing `agents/max/` path as a **symlink/shim** → points to `roles/lead/`.  
Deprecation note in `README.md`.

---

## 📂 Proposed Repo Layout

```
/agents/
  /roles/
    /lead/
    /strat/
    /creative/
    /dev/
    /qa/
    /data/
    /finance/
    /comms/
    /curator/
    /audit/
  /instances/
    /max/    -> lead
    /nat/    -> strat
    /glyph/  -> creative
    /neo/    -> dev
    /eve/    -> qa
    /data/   -> data
    /quark/  -> finance
    /joi/    -> comms
    /og/     -> curator
    /hal/    -> audit
/manifests/
  squad.yaml
/infra/
  docker-compose.yaml
```

---

## 🔑 Role → Instance Mapping (Initial 10 Agents)

| **Identity** | **Role**    |
|--------------|-------------|
| Max          | Lead        |
| Nat          | Strat       |
| Glyph        | Creative    |
| Neo          | Dev         |
| EVE          | QA          |
| Data         | Data        |
| Quark        | Finance     |
| Joi          | Comms       |
| Og           | Curator     |
| HAL          | Audit       |

---

## ⚙️ Example: Instance Manifest

```yaml
# agents/instances/max/instance.yaml
agent_id: max
display_name: Max
role: lead
model:
  provider: local
  name: llama3-8b
tools:
  - rabbitmq
  - postgres
```

---

## 🔄 Migration Steps
1. Move `agents/max/` → `agents/roles/lead/`  
2. Create `agents/instances/max/instance.yaml`  
3. Create `manifests/squad.yaml` listing active instances  
4. Update `docker-compose.yaml` to parameterize by `${ROLE}`/`${AGENT_ID}`  

---

## ✅ Benefits
- **Framework-agnostic:** No identity baked into repo structure.  
- **Scalable:** Multiple instances of the same role can be spun up.  
- **Portable:** Easy to share/open-source without rewriting lore.  
- **Governance-ready:** Roles and instances are clearly separated.  

---

## 📅 Priority
**High** — required before releasing SquadOps as a generic framework.

---


