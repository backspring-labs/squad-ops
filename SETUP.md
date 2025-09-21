# SquadOps Quick Start Guide

## Prerequisites
- Docker Desktop installed and running
- Git (to clone the repository)
- At least 4GB RAM available for Docker
- Ports 5432, 5672, 6379, 4200, 4201, 8000 available

## Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/jasonLadd/squad-ops.git
cd squad-ops
```

### 2. Start the SquadOps Framework
```bash
docker-compose up -d
```

### 3. Verify Everything is Running
```bash
# Check all containers are healthy
docker-compose ps

# Check agent status
curl http://localhost:8000/health/agents

# Check infrastructure status  
curl http://localhost:8000/health/infra
```

### 4. View the Health Dashboard
Open your browser and go to: **http://localhost:8000/health**

You should see:
- ✅ **Infrastructure Status** (RabbitMQ, PostgreSQL, Redis, Prefect)
- ✅ **10-Agent Squad Status** (Max, Neo, Nat, Joi, Data, EVE, HAL, Quark, Og, Glyph)

## What You Get

### Infrastructure Services
- **RabbitMQ** (port 5672) - Message broker for inter-agent communication
- **PostgreSQL** (port 5432) - Central database for tasks, logs, and agent status
- **Redis** (port 6379) - Caching and pub/sub for real-time updates
- **Prefect Server** (port 4200) - Task orchestration and workflow management
- **Prefect UI** (port 4201) - Web interface for Prefect workflows

### 10-Agent Squad
1. **Max** - Task Lead (Governance & Coordination)
2. **Neo** - Developer (Technical Implementation)
3. **Nat** - Product Strategy (Strategic Planning)
4. **Joi** - Communications (Team Coordination)
5. **Data** - Analytics (Data & Insights)
6. **EVE** - QA & Security (Testing & Security)
7. **HAL** - Monitoring (System Health)
8. **Quark** - Finance & Ops (Business Operations)
9. **Og** - R&D & Curation (Research & Development)
10. **Glyph** - Creative Design (Visual Assets & Inspiration)

### Health Monitoring
- **Health Dashboard** - Real-time status of all infrastructure and agents
- **Heartbeat Monitoring** - Agents report status every 30 seconds
- **Status Consistency** - All services show "online" with green checkmarks

### Version Management
- **Centralized Configuration** - All agent versions managed in `config/version.py`
- **CLI Tools** - Use `python version_cli.py` for version management
- **Agent-Specific Configs** - Each agent has its own configuration in `agents/<agent>/config.py`
- **Rollback Capability** - Easy rollback to previous agent versions if needed

#### Version Management Commands:
```bash
# List all agent versions
python version_cli.py list

# Show specific agent details
python version_cli.py show Max

# Update agent version (example)
python version_cli.py update Neo 1.1.0 gpt-4 deductive-v2 "Testing GPT-4"

# Rollback to previous version
python version_cli.py rollback Neo 1.0.0
```

## Troubleshooting

### If containers fail to start:
```bash
# Check logs
docker-compose logs

# Restart specific service
docker-compose restart <service-name>

# Rebuild and restart everything
docker-compose down
docker-compose up -d --build
```

### If agents show as "offline":
- Wait 30-60 seconds for heartbeat initialization
- Check agent logs: `docker logs squadops-<agent-name>`
- Verify database connections are working

### If ports are in use:
- Stop conflicting services or change ports in `docker-compose.yml`
- Check what's using ports: `lsof -i :<port-number>`

## Next Steps
The framework is now ready for:
- Inter-agent communication implementation
- WarmBoot protocol for benchmarking
- Task coordination and delegation
- Agent specialization and reasoning styles

## Support
- Check the `SQUADOPS_CONTEXT_HANDOFF.md` for detailed architecture
- All agent implementations are in the `agents/` directory
- Infrastructure configuration is in `docker-compose.yml`
- Health monitoring code is in `infra/health-check/`

**Welcome to SquadOps! 🚀**
