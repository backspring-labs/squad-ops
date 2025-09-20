# 🚀 Day 0 – Kickoff Plan (Pre-Repo Setup)

This checklist gets you from **zero → environment ready → Day 1 repo initialization**.

---

## 1. Local Environment Prep
- [ ] Install **Docker + Docker Compose**
- [ ] Install **Git + GitHub CLI (gh)**
- [ ] Install **Python 3.10+** (venv recommended)
- [ ] Install **FastAPI + Uvicorn** (`pip install fastapi uvicorn`)
- [ ] Install **pytest** for testing (`pip install pytest`)
- [ ] Verify **Jetson Nano drivers** + CUDA support (if applicable)
- [ ] Optional: Set up **VS Code / Cursor IDE** with Python + Docker extensions

---

## 2. Accounts & Access
- [ ] GitHub account created + SSH keys configured
- [ ] DockerHub account (for pulling base images)
- [ ] Optional: Prefect Cloud account (if not running local Prefect server)
- [ ] Optional: Flagsmith account for feature flagging

---

## 3. Networking & Security
- [ ] Confirm local firewall/ports allow Docker containers to talk (5672 RabbitMQ, 5432 Postgres, 4200 Prefect)
- [ ] Generate initial `.env` file with secrets (DB password, JWT secret, etc.)
- [ ] Add `.gitignore` template (Python, Docker, venv, secrets)

---

## 4. SquadOps Kickoff Checklist
- [ ] Create local directory structure for SquadOps project:
  ```
  squad_ops/
      /agents/
      /infra/
      /docs/
      /warmboot_runs/
      /optimizations/
  ```
- [ ] Initialize empty Git repo locally
- [ ] Draft initial `README.md` with mission + scope
- [ ] Add `process_registry.md` stub for PID assignments
- [ ] Decide on first reference app (HelloSquad)

---

## 5. Governance Anchors
- [ ] Adopt PID standard (`PID-001` for HelloSquad)
- [ ] Link to **Traceability Protocol** for process docs
- [ ] Link to **Testing Protocol** for test artifacts
- [ ] Link to **Data Governance Protocol** for KDEs & metrics

---

## ✅ Ready for Day 1
At this point, infra and accounts are ready.  
Proceed to **Day 1 Plan** → repo creation, Dockerized infra, first agent tasks.
