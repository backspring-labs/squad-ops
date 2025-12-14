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
1. **Max** (v0.6.5) - Task Lead (Governance & Coordination) - **JSON Workflow Orchestration** with local LLM (llama3.1:8b)
2. **Neo** (v0.6.5) - Developer (Technical Implementation) - **Manifest-First Development** with file modification capabilities (qwen2.5:7b)
3. **Nat** (v0.6.5) - Product Strategy (Strategic Planning) - **PRD Capabilities** and product domain features
4. **EVE** (v0.6.5) - QA & Security (Testing & Security) - **Test Design, Development, and Execution** with counterfactual reasoning
5. **Joi** (v0.0.0) - Communications (Team Coordination) - Mock agent
6. **Data** (v0.0.0) - Analytics (Data & Insights) - Mock agent
7. **HAL** (v0.0.0) - Monitoring (System Health) - Mock agent
8. **Quark** (v0.0.0) - Finance & Ops (Business Operations) - Mock agent
9. **Og** (v0.0.0) - R&D & Curation (Research & Development) - Mock agent
10. **Glyph** (v0.0.0) - Creative Design (Visual Assets & Inspiration) - Mock agent

### JSON Workflow Engine (SIP-033A)
- **Structured LLM Output** - Eliminates markdown parsing issues
- **Manifest-First Development** - Architecture design before implementation
- **Framework Enforcement** - Programmatic vanilla_js constraint
- **Agent Coordination** - Max orchestrates design_manifest → build → deploy
- **Comprehensive Testing** - 46/46 unit tests passing (100% coverage)
- **Production Ready** - Integration tests, smoke tests, governance logging

### Health Monitoring
- **Health Dashboard** - Real-time status of all infrastructure and agents
- **Heartbeat Monitoring** - Agents report status every 30 seconds
- **Status Consistency** - All services show "online" with green checkmarks

### Version Management
- **Centralized Configuration** - All agent versions managed in `config/version.py`
- **CLI Tools** - Use `python scripts/maintainer/version_cli.py` for version management
- **Agent-Specific Configs** - Each agent has its own configuration in `agents/<agent>/config.py`
- **Rollback Capability** - Easy rollback to previous agent versions if needed

#### Version Management Commands:
```bash
# List all agent versions
python scripts/maintainer/version_cli.py list

# Show specific agent details
python scripts/maintainer/version_cli.py show Max

# Update agent version (example)
python scripts/maintainer/version_cli.py update Neo 1.1.0 gpt-4 deductive-v2 "Testing GPT-4"

# Rollback to previous version
python scripts/maintainer/version_cli.py rollback Neo 1.0.0
```

### Docker Build Process

SquadOps uses a **build-time assembly approach** for creating agent containers:

#### Building Individual Agent Containers

1. **Build Agent Package**:
   ```bash
   # Build the agent package (assembles required files)
   python scripts/dev/build_agent.py <role>
   
   # Example: Build Max (lead agent)
   python scripts/dev/build_agent.py lead
   ```

2. **Verify Package Contents**:
   ```bash
   # Check what was assembled
   ls -la dist/agents/<role>/
   ```

3. **Build Docker Image**:
   ```bash
   # Build Docker image using multi-stage Dockerfile
   docker build -t squadops/<agent>:latest \
     --build-arg AGENT_ROLE=<role> \
     -f agents/roles/<role>/Dockerfile .
   
   # Example: Build Max container
   docker build -t squadops/max:latest \
     --build-arg AGENT_ROLE=lead \
     -f agents/roles/lead/Dockerfile .
   ```

#### Build Process Details

- **Build Script** (`scripts/dev/build_agent.py`): Automatically resolves dependencies from `config.yaml`, assembles only required files
- **Multi-Stage Build**: Stage 1 runs build script with cache-busting, Stage 2 creates minimal runtime image
- **Cache Busting**: Source file hash passed as `CACHE_BUST` build arg ensures Docker cache invalidates when source changes
- **Build Artifacts**: Generates `manifest.json` (build metadata) and `agent_info.json` (runtime identity)
- **Deterministic Builds**: SHA256 build hash ensures reproducible builds
- **Hash Verification**: Rebuild script verifies container hash matches expected hash, auto-retries with `--no-cache` on mismatch

#### Rebuild and Deploy Script

The recommended way to rebuild agents:
```bash
# Rebuild all 5 core agents (max, nat, neo, eve, data)
./scripts/dev/ops/rebuild_and_deploy.sh agents

# Force rebuild without cache
FORCE_REBUILD=1 ./scripts/dev/ops/rebuild_and_deploy.sh agents
```

The script:
1. Builds agent packages locally (required)
2. Calculates source file hash for cache busting
3. Builds Docker images with `CACHE_BUST` and `BUILD_HASH` args
4. Verifies container build hash matches expected hash
5. Auto-retries with `--no-cache` if verification fails
6. Fails immediately if build or verification errors occur

#### Special Cases

- **Dev Role**: Requires Docker CLI installation (for Docker-in-Docker operations)
- **All Agents**: Use standard multi-stage pattern with build script and cache-busting

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

### If Docker builds fail:
- Verify build script ran successfully: `ls -la dist/agents/<role>/`
- Check for missing dependencies in `agents/roles/<role>/config.yaml`
- Verify `ENV SQUADOPS_BASE_PATH=/app` is set in Dockerfile
- Check build script logs for dependency resolution errors

### If ports are in use:
- Stop conflicting services or change ports in `docker-compose.yml`
- Check what's using ports: `lsof -i :<port-number>`

## Next Steps
The framework is now ready for:
- **Integration Testing** - Fix integration tests to work with real Ollama API
- **Actual WarmBoot Execution** - Run real WarmBoot with JSON workflow
- **Production Validation** - Ensure JSON workflow is production-ready
- **Multi-Agent Expansion** - Scale beyond Max + Neo + Nat + EVE coordination
- **Task Adapter Testing** - Validate Prefect adapter implementation when ready

## Support
- Check the `docs/SQUADOPS_CONTEXT_HANDOFF.md` for detailed architecture
- All agent implementations are in the `agents/` directory
- Infrastructure configuration is in `docker-compose.yml`
- Health monitoring code is in `infra/health-check/`

**Welcome to SquadOps! 🚀**
