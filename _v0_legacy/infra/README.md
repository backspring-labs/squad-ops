# SquadOps Infrastructure Setup

This directory contains the infrastructure components for SquadOps Tier 1 deployment (MacBook Air with real infrastructure services).

## 🏗️ **Infrastructure Components**

### **Core Services**
- **RabbitMQ** (5672) - Inter-agent messaging (SquadComms)
- **Postgres** (5432) - Central data store, task logs, governance data
- **Prefect** (4200) - Task orchestration and state management
- **Redis** (6379) - Caching, state sync, pub/sub backbone

### **Health Check Service**
- **FastAPI** (8000) - Health monitoring and status dashboard
- **Endpoints:**
  - `/health/infra` - Infrastructure status JSON
  - `/health/agents` - Agent status JSON
  - `/health` - HTML dashboard with auto-refresh

## 🚀 **Quick Start**

### **1. Start Infrastructure**
```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### **2. Access Services**
- **Health Dashboard:** http://localhost:8000/health
- **RabbitMQ Management:** http://localhost:15672 (squadops/squadops123)
- **Prefect UI:** http://localhost:4201
- **Postgres:** localhost:5432 (squadops/squadops123)

### **3. Verify Health**
```bash
# Check infrastructure health
curl http://localhost:8000/health/infra

# Check agent status
curl http://localhost:8000/health/agents
```

## 📊 **Database Schema**

### **Tables Created**
- `agent_task_logs` - Task execution logs
- `agent_status` - Agent status and heartbeat
- `squadcomms_messages` - Inter-agent messages
- `warmboot_runs` - WarmBoot execution records
- `process_registry` - Process ID registry
- `optimization_log` - Optimization tracking

### **Initial Data**
- **Process Registry:** PID-001 (HelloSquad) pre-registered
- **Agent Status:** All 9 agents initialized as offline

## 🔧 **Configuration**

### **Environment Variables**
Copy `infra/config.env` to `.env` and modify as needed:
```bash
cp infra/config.env .env
```

### **Service Ports**
- RabbitMQ: 5672 (AMQP), 15672 (Management)
- Postgres: 5432
- Redis: 6379
- Prefect Server: 4200
- Prefect UI: 4201
- Health Check: 8000

## 📋 **Next Steps**

### **Tier 1 Implementation**
1. ✅ **Docker Compose** with real infrastructure services
2. ✅ **Health check endpoints** with actual service status
3. 🔄 **All 9 agent container stubs** with protocol compliance
4. 🔄 **Mock LLM responses** for agent outputs
5. 🔄 **Complete documentation** for book and Jetson deployment

### **Agent Stubs (Next)**
- Create agent containers with protocol compliance
- Implement mock LLM responses
- Real agent communication via RabbitMQ
- Task orchestration via Prefect

## 🐛 **Troubleshooting**

### **Common Issues**
- **Port conflicts:** Check if ports are already in use
- **Database connection:** Ensure Postgres is healthy before starting Prefect
- **RabbitMQ:** Check management UI for connection issues
- **Health checks:** Verify all services are responding

### **Logs**
```bash
# View all logs
docker-compose logs

# View specific service logs
docker-compose logs rabbitmq
docker-compose logs postgres
docker-compose logs health-check
```

### **Reset Everything**
```bash
# Stop and remove all containers
docker-compose down -v

# Remove volumes (WARNING: deletes all data)
docker-compose down -v --volumes

# Start fresh
docker-compose up -d
```

## 📚 **Documentation**

- **SQUADOPS_CONTEXT_HANDOFF.md** - Complete system overview
- **SQUADOPS_BUILD_PARTNER_PROMPT.md** - AI partner prompt
- **docs/ideas/** - All protocol specifications
- **docker-compose.yml** - Service configuration
- **infra/init.sql** - Database initialization
