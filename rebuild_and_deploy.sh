#!/bin/bash
# Rebuild and deploy SquadOps containers with updated code
# Ensures all infrastructure (including Ollama) is running first
# Can be run in background - logs to rebuild_deploy.log

set -e

# Log file for background execution
LOG_FILE="rebuild_deploy.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "======================================"
echo "Logging to: $LOG_FILE"
echo "Monitor with: tail -f $LOG_FILE"
echo "======================================"
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 SquadOps Rebuild & Deploy${NC}"
echo "================================"

# Function to check if Ollama is running
check_ollama() {
    echo -e "${BLUE}🔍 Checking Ollama (host.docker.internal:11434)...${NC}"
    
    if curl -s --connect-timeout 2 http://localhost:11434/api/version > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Ollama is running on localhost:11434${NC}"
        return 0
    elif curl -s --connect-timeout 2 http://host.docker.internal:11434/api/version > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Ollama is accessible at host.docker.internal:11434${NC}"
        return 0
    else
        echo -e "${RED}❌ Ollama is not running or not accessible${NC}"
        echo -e "${YELLOW}   Please start Ollama first:${NC}"
        echo -e "${YELLOW}   - macOS: ollama serve${NC}"
        echo -e "${YELLOW}   - Or ensure it's running on port 11434${NC}"
        return 1
    fi
}

# Function to check database connectivity
check_database() {
    echo -e "${BLUE}🔍 Checking PostgreSQL connection...${NC}"
    
    # Try to connect via docker exec if postgres container is running
    if docker ps --format '{{.Names}}' | grep -q '^squadops-postgres$'; then
        if docker exec squadops-postgres pg_isready -U squadops -d squadops > /dev/null 2>&1; then
            echo -e "${GREEN}✅ PostgreSQL is healthy${NC}"
            return 0
        else
            echo -e "${RED}❌ PostgreSQL container exists but is not ready${NC}"
            return 1
        fi
    else
        echo -e "${RED}❌ PostgreSQL container is not running${NC}"
        return 1
    fi
}

# Step 1: Check Ollama (external service)
echo ""
echo -e "${BLUE}📊 Step 1: Checking infrastructure prerequisites...${NC}"
if ! check_ollama; then
    echo -e "${RED}⚠️  Ollama check failed - agents that use LLM may not work${NC}"
    echo -e "${YELLOW}   Continue anyway? (y/n)${NC}"
    read -t 10 -n 1 answer || answer="n"
    if [ "$answer" != "y" ]; then
        echo -e "${RED}Exiting - please start Ollama first${NC}"
        exit 1
    fi
fi

# Step 2: Ensure Docker Compose infrastructure is running
echo ""
echo -e "${BLUE}📊 Step 2: Ensuring Docker Compose infrastructure is running...${NC}"

echo "Starting infrastructure services (rabbitmq, postgres, redis, prefect, task-api, health-check)..."
docker-compose up -d rabbitmq postgres redis prefect-server prefect-ui task-api health-check

echo "⏳ Waiting for infrastructure to be healthy (30 seconds)..."
sleep 30

# Verify infrastructure health
echo ""
echo -e "${BLUE}🔍 Verifying infrastructure health...${NC}"

if ! check_database; then
    echo -e "${YELLOW}⚠️  Waiting additional time for PostgreSQL...${NC}"
    sleep 15
    check_database || echo -e "${YELLOW}⚠️  PostgreSQL may still be initializing${NC}"
fi

# Check RabbitMQ
if docker exec squadops-rabbitmq rabbitmq-diagnostics ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ RabbitMQ is healthy${NC}"
else
    echo -e "${YELLOW}⚠️  RabbitMQ may still be starting${NC}"
fi

# Check Redis
if docker exec squadops-redis redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis is healthy${NC}"
else
    echo -e "${YELLOW}⚠️  Redis may still be starting${NC}"
fi

# Check Task API
if curl -s --connect-timeout 5 http://localhost:8001/docs > /dev/null 2>&1 || \
   curl -s --connect-timeout 5 http://localhost:8001/api/v1/execution-cycles 2>&1 | grep -q "method not allowed\|unauthorized\|not found" || \
   docker ps --format '{{.Names}}\t{{.Status}}' | grep squadops-task-api | grep -q "Up"; then
    echo -e "${GREEN}✅ Task API container is running${NC}"
else
    echo -e "${YELLOW}⚠️  Task API may still be starting${NC}"
fi

# Step 3: Rebuild services that changed
echo ""
echo -e "${BLUE}🔨 Step 3: Rebuilding containers with updated code...${NC}"

# Rebuild Task API (has new endpoints)
echo -e "${YELLOW}📦 Rebuilding task-api (new endpoints added)...${NC}"
# Use cache for faster rebuilds - only rebuild changed layers
docker-compose build task-api
docker-compose up -d task-api
echo -e "${GREEN}✅ Task API rebuilt and restarted${NC}"

# Get list of agent services from docker-compose
AGENTS=$(docker-compose config --services | grep -E "^(max|neo|nat|glyph|eve|data|quark|joi|og|hal)$" || echo "max neo")

echo -e "${YELLOW}📦 Rebuilding agent containers (using updated unified config and Task API)...${NC}"
echo -e "${BLUE}   Using Docker layer cache for faster rebuilds (use FORCE_REBUILD=1 for --no-cache)${NC}"
for agent in $AGENTS; do
    if docker-compose config --services | grep -q "^${agent}$"; then
        echo -e "  🔨 Rebuilding ${agent}..."
        if [ "${FORCE_REBUILD:-0}" = "1" ]; then
            docker-compose build --no-cache $agent || echo -e "${RED}  ⚠️  Build failed for ${agent}${NC}"
        else
            docker-compose build $agent || echo -e "${RED}  ⚠️  Build failed for ${agent}${NC}"
        fi
    fi
done

# Step 4: Restart all agent containers
echo ""
echo -e "${BLUE}🔄 Step 4: Restarting agent containers...${NC}"
for agent in $AGENTS; do
    if docker-compose config --services | grep -q "^${agent}$"; then
        echo -e "  🔄 Restarting ${agent}..."
        docker-compose up -d $agent || echo -e "${RED}  ⚠️  Restart failed for ${agent}${NC}"
    fi
done

# Step 5: Wait for agents to be healthy
echo ""
echo -e "${BLUE}⏳ Step 5: Waiting for agents to be healthy (30 seconds)...${NC}"
sleep 30

# Step 6: Verify deployment
echo ""
echo -e "${BLUE}✅ Step 6: Verifying deployment...${NC}"
docker-compose ps

echo ""
echo -e "${GREEN}🎉 Rebuild and deploy complete!${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo -e "  1. Verify agent logs: ${YELLOW}docker-compose logs --tail=50 max neo${NC}"
echo -e "  2. Check Task API health: ${YELLOW}curl http://localhost:8001/health${NC}"
echo -e "  3. Run smoke tests: ${YELLOW}python3 -m pytest tests/smoke/ -v${NC}"
