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
- **10-Agent Squad** – Specialized reasoning agents (Max, Neo, Nat, Joi, Data, EVE, HAL, Quark, Og, Glyph)
- **SquadNet** – Networking mesh for inter-agent communication
- **SquadComms** – Messaging bus (RabbitMQ) for task delegation & status updates
- **Prefect** – Task orchestration and state management
- **Postgres** – Central store for logs, metrics, and governance data
- **Health Dashboard** – Web interface for monitoring agents, tasks, and health
- **Version Management** – Centralized agent versioning with CLI tools for rollbacks

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
/agents/              # Agent implementations & shared base class
├── base_agent.py     # Shared base class for all agents
├── max/              # Individual agent folders
│   ├── max.py        # Agent-specific implementation
│   ├── config.py     # Agent-specific configuration
│   ├── requirements.txt
│   └── Dockerfile
└── ... (same for all 10 agents)
/infra/               # Infrastructure services: RabbitMQ, Postgres, Prefect
/config/              # Centralized version management
/docs/                # Protocols, governance, PIDs
docker-compose.yml    # Multi-container setup
version_cli.py        # Version management CLI tool
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
This repo is currently **fully operational** with:
- ✅ **10-Agent Squad** deployed and healthy
- ✅ **Infrastructure Services** running (RabbitMQ, PostgreSQL, Redis, Prefect)
- ✅ **Health Dashboard** monitoring all components
- ✅ **Version Management** system with CLI tools
- ✅ **Heartbeat Monitoring** for real-time status tracking

Ready for **Agent Coordination & Task Execution** phase.

---

> **Note:** This project is part of the broader **SquadOps Field Guide** initiative – documenting how AI squads can operate as autonomous product-building teams with traceability, governance, and continuous optimization.
