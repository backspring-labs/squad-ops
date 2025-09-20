# 🚀 Day 1 – Kickoff Plan (Repo + Infra Setup)

This plan gets you from **ready environment → initialized repo → first agent tasks → logged WarmBoot run**.

---

## 1. Repo Setup
- [ ] Create GitHub repo: `squad_ops`
- [ ] Initialize repo with:
  ```
  /agents/
  /infra/
  /docs/
  /warmboot_runs/
  /optimizations/
  docker-compose.yml
  README.md
  ```
- [ ] Add `.gitignore` (Python, Docker, venv, etc.)
- [ ] Commit **DAY0_KICKOFF.md**, **DAY1_KICKOFF.md**, and `README.md`

---

## 2. Local Infra (Dockerized)
- [ ] Define **Infra container** with:
  - RabbitMQ (SquadComms)
  - Postgres (task logs + governance data)
  - Prefect (orchestration + scheduling)
- [ ] Create **Agent containers**:
  - Start with **Max** (orchestrator) + **Neo** (developer)
- [ ] Configure **Networking**: `squadnet` bridge in `docker-compose.yml`
- [ ] Scaffold **Health Check Endpoints** (FastAPI):
  - `/health/infra`
  - `/health/agents`

---

## 3. Protocol Anchors
- [ ] Adopt **PID Traceability**
  - First PID: `PID-001` → HelloSquad test app
- [ ] Add `process_registry.md` with first entry
- [ ] Create stubs:
  - `BP-001-HelloSquad.md` (business process doc)
  - `UC-001-HelloWorld.md` (use case)
  - `TC-001-HelloWorld.md` (test case)

---

## 4. First Reference App: HelloSquad
- [ ] Neo builds `hello.py` (FastAPI endpoint `/hello`)
- [ ] EVE writes `pytest` case for `/hello`
- [ ] Run WarmBoot v0.1 with just Max + Neo
- [ ] Tag run branch: `warmboot/run-001`

---

## 5. Logging & Metrics
- [ ] Enable **task logging** table in Postgres
- [ ] Add JSON schema for logs (agent, task, pid, duration, status)
- [ ] Generate a **Mermaid Gantt chart snippet** after first run

---

## 6. Commit & Push
- [ ] Commit all stubs, Docker Compose, health check, and HelloSquad app
- [ ] Push to GitHub
- [ ] Tag release: `v0.1-warmboot-001`

---

## 7. Stretch Goals
- [ ] Add **SOC UI** scaffold (HTML/Bootstrap showing task status)
- [ ] Containerize **Nat** (product strategy) → 3 agents online
- [ ] Add **tagging layer** (`/analytics/tagging_spec.md`)

---

✅ **At the end of Day 1 you’ll have:**
- Repo live on GitHub  
- Infra containers running (RabbitMQ, Postgres, Prefect)  
- Health checks online  
- First reference app (`HelloSquad`) running  
- Logged & tagged WarmBoot run  
