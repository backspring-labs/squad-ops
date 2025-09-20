# SquadOps – Agent Squad Framework

## 📌 Overview
**SquadOps** is an operational framework for running AI-powered squads of specialized agents that can build, test, and govern software systems with production-grade rigor.  
This repo provides the starting point for your first **agent squad deployment** and includes infrastructure, agent containers, governance protocols, and reference applications.

---

## 🚀 Mission
- **Build the squad that builds the system**  
- **Operate the business that proves the model**  
- **Publish the guide that teaches others to do the same**

SquadOps is designed as both a **practical toolkit** and a **thought leadership reference** for agent-based software engineering.

---

## 🧩 Core Components
- **Agent Containers** – Specialized reasoning agents (Neo, Max, Nat, Joi, etc.)
- **SquadNet** – Networking mesh for inter-agent communication
- **SquadComms** – Messaging bus (RabbitMQ) for task delegation & status updates
- **Prefect** – Task orchestration and state management
- **Postgres** – Central store for logs, metrics, and governance data
- **SOC (SquadOps Console)** – Dashboard for monitoring agents, tasks, and health

---

## 📚 Protocol Anchors
Every process is mapped via **Process IDs (PIDs)** and linked to governance artifacts.

- **Documentation Traceability Protocol** – PID-based docs & diagrams
- **Testing Protocol** – Test plans, cases, coverage, security, performance, pen testing
- **Data Governance Protocol** – KDEs, KPIs, data lineage, privacy
- **Tagging Protocol** – Analytics event tagging mapped to PIDs
- **Comms & Task Concurrency Protocol** – Ensures coordination without bottlenecks

All protocols live under `/docs/`.

---

## 🏗️ Repo Structure
```
/agents/              # Agent container configs & code
/infra/               # Infra services: RabbitMQ, Postgres, Prefect
/docs/                # Protocols, governance, PIDs
/warmboot_runs/       # Logs & metrics from warmboot runs
/optimizations/       # Improvements & tuning logs
docker-compose.yml    # Multi-container setup
README.md             # Project overview (this file)
```

---

## 🧪 First Reference App: HelloSquad
- **PID-001** is reserved for *HelloSquad*, a simple FastAPI "Hello World" service.  
- It serves as the baseline benchmark for running your first WarmBoot (`warmboot/run-001`).  
- EVE writes the pytest, Neo builds the endpoint, Max orchestrates.

---

## 🛠️ Getting Started
1. Follow **DAY0_KICKOFF.md** to set up local environment & accounts
2. Proceed to **DAY1_KICKOFF.md** for repo + infra scaffolding
3. Spin up containers with `docker-compose up`
4. Verify health endpoints at `/health/infra` and `/health/agents`
5. Run your first WarmBoot and tag the run in Git

---

## 📈 Future Roadmap
- Expand reference apps (fitness trackers, financial trackers, etc.)
- Introduce full SOC UI with metrics dashboards
- Implement governance checks for production readiness
- Extend squads with premium LLM consultations

---

## ✅ Status
This repo is currently in **bootstrap mode**.  
Core infra + HelloSquad reference app will validate the first WarmBoot run.

---

> **Note:** This project is part of the broader **SquadOps Field Guide** initiative – documenting how AI squads can operate as autonomous product-building teams with traceability, governance, and continuous optimization.
