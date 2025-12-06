#!/bin/bash
# Rebuild and deploy SquadOps containers with updated code
# Ensures all infrastructure (including Ollama) is running first
# Can be run in background - logs to rebuild_deploy.log
#
# Usage:
#   ./scripts/dev/ops/rebuild_and_deploy.sh                    # Rebuild everything (default)
#   ./scripts/dev/ops/rebuild_and_deploy.sh all                # Rebuild everything
#   ./scripts/dev/ops/rebuild_and_deploy.sh health-check        # Rebuild only health-check service
#   ./scripts/dev/ops/rebuild_and_deploy.sh agents              # Rebuild only agent containers
#   ./scripts/dev/ops/rebuild_and_deploy.sh health-check agents # Rebuild health-check and agents
#   ./scripts/dev/ops/rebuild_and_deploy.sh runtime-api         # Rebuild only runtime-api
#
# Environment variables:
#   FORCE_REBUILD=1                             # Use --no-cache for full rebuild

set -e

# Get repository root directory (parent of scripts/)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

# Parse command-line arguments
REBUILD_HEALTH_CHECK=false
REBUILD_AGENTS=false
REBUILD_RUNTIME_API=false
REBUILD_ALL=true

if [ $# -gt 0 ]; then
    REBUILD_ALL=false
    for arg in "$@"; do
        case "$arg" in
            health-check|health_check)
                REBUILD_HEALTH_CHECK=true
                ;;
            agents)
                REBUILD_AGENTS=true
                ;;
            runtime-api|runtime_api|task-api|task_api)
                REBUILD_RUNTIME_API=true
                ;;
            all)
                REBUILD_ALL=true
                REBUILD_HEALTH_CHECK=true
                REBUILD_AGENTS=true
                REBUILD_RUNTIME_API=true
                ;;
            *)
                echo "Unknown argument: $arg"
                echo "Usage: $0 [health-check] [agents] [runtime-api] [all]"
                exit 1
                ;;
        esac
    done
else
    # Default: rebuild everything
    REBUILD_HEALTH_CHECK=true
    REBUILD_AGENTS=true
    REBUILD_RUNTIME_API=true
fi

# Log file for background execution (in repo root)
LOG_FILE="$REPO_ROOT/rebuild_deploy.log"
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
echo -e "${BLUE}Target services:${NC}"
if [ "$REBUILD_ALL" = true ]; then
    echo -e "  ${YELLOW}✓${NC} All services (health-check, agents, runtime-api)"
else
    [ "$REBUILD_HEALTH_CHECK" = true ] && echo -e "  ${YELLOW}✓${NC} health-check"
    [ "$REBUILD_AGENTS" = true ] && echo -e "  ${YELLOW}✓${NC} agents"
    [ "$REBUILD_RUNTIME_API" = true ] && echo -e "  ${YELLOW}✓${NC} runtime-api"
fi
echo ""

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

# Always start infrastructure services (they're dependencies)
echo "Starting infrastructure services (rabbitmq, postgres, redis, prefect)..."
docker-compose up -d rabbitmq postgres redis prefect-server prefect-ui

# Conditionally start runtime-api and health-check if they're being rebuilt
if [ "$REBUILD_RUNTIME_API" = true ] || [ "$REBUILD_ALL" = true ]; then
    echo "Starting runtime-api..."
    docker-compose up -d runtime-api || true
fi

if [ "$REBUILD_HEALTH_CHECK" = true ] || [ "$REBUILD_ALL" = true ]; then
    echo "Starting health-check..."
    docker-compose up -d health-check || true
fi

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

# Check Runtime API
if curl -s --connect-timeout 5 http://localhost:8001/docs > /dev/null 2>&1 || \
   curl -s --connect-timeout 5 http://localhost:8001/api/v1/execution-cycles 2>&1 | grep -q "method not allowed\|unauthorized\|not found" || \
   docker ps --format '{{.Names}}\t{{.Status}}' | grep squadops-runtime-api | grep -q "Up"; then
    echo -e "${GREEN}✅ Runtime API container is running${NC}"
else
    echo -e "${YELLOW}⚠️  Runtime API may still be starting${NC}"
fi

# Step 3: Rebuild services that changed
echo ""
echo -e "${BLUE}🔨 Step 3: Rebuilding containers with updated code...${NC}"

# Rebuild Runtime API if requested
if [ "$REBUILD_RUNTIME_API" = true ] || [ "$REBUILD_ALL" = true ]; then
    echo -e "${YELLOW}📦 Rebuilding runtime-api...${NC}"
    if [ "${FORCE_REBUILD:-0}" = "1" ]; then
        docker-compose build --no-cache runtime-api || echo -e "${RED}  ⚠️  Build failed for runtime-api${NC}"
    else
        docker-compose build runtime-api || echo -e "${RED}  ⚠️  Build failed for runtime-api${NC}"
    fi
    docker-compose up -d runtime-api
    echo -e "${GREEN}✅ Runtime API rebuilt and restarted${NC}"
fi

# Rebuild Health Check if requested
if [ "$REBUILD_HEALTH_CHECK" = true ] || [ "$REBUILD_ALL" = true ]; then
    echo -e "${YELLOW}📦 Rebuilding health-check...${NC}"
    if [ "${FORCE_REBUILD:-0}" = "1" ]; then
        docker-compose build --no-cache health-check || echo -e "${RED}  ⚠️  Build failed for health-check${NC}"
    else
        docker-compose build health-check || echo -e "${RED}  ⚠️  Build failed for health-check${NC}"
    fi
    docker-compose up -d health-check
    echo -e "${GREEN}✅ Health Check rebuilt and restarted${NC}"
fi

# Function to get agent role from agent ID
get_agent_role() {
    local agent_id=$1
    # Map agent IDs to roles (from instances.yaml or docker-compose)
    case "$agent_id" in
        max|neo) echo "dev" ;;
        nat) echo "strat" ;;
        eve) echo "qa" ;;
        glyph) echo "comms" ;;
        data) echo "data" ;;
        quark) echo "finance" ;;
        joi) echo "curator" ;;
        og) echo "creative" ;;
        hal) echo "audit" ;;
        *) echo "unknown" ;;
    esac
}

# Function to extract build hash from manifest.json
get_build_hash_from_manifest() {
    local role=$1
    local manifest_path="$REPO_ROOT/dist/agents/${role}/manifest.json"
    
    if [ ! -f "$manifest_path" ]; then
        echo ""
        return 1
    fi
    
    # Try jq first, then python, then grep
    if command -v jq &> /dev/null; then
        jq -r '.build_hash' "$manifest_path" 2>/dev/null || echo ""
    elif command -v python3 &> /dev/null; then
        python3 -c "import json; print(json.load(open('$manifest_path')).get('build_hash', ''))" 2>/dev/null || echo ""
    else
        grep -o '"build_hash"[[:space:]]*:[[:space:]]*"[^"]*"' "$manifest_path" | cut -d'"' -f4 || echo ""
    fi
}

# Function to verify build hash propagation
verify_build_hash() {
    local agent_id=$1
    local role=$2
    local expected_hash=$3
    
    if [ -z "$expected_hash" ] || [ "$expected_hash" = "unknown" ]; then
        echo -e "${YELLOW}  ⚠️  Build hash not available for ${agent_id} (manifest.json may not exist)${NC}"
        return 0  # Not a failure, just not available
    fi
    
    # Wait a moment for container to be ready
    sleep 2
    
    # Get runtime build hash from container
    local container_name="squadops-${agent_id}"
    local runtime_hash=""
    
    if docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
        # Try to get from agent_info.json
        runtime_hash=$(docker exec "$container_name" cat /app/agent_info.json 2>/dev/null | \
            (command -v jq &> /dev/null && jq -r '.build_hash' || \
             python3 -c "import json, sys; print(json.load(sys.stdin).get('build_hash', ''))" 2>/dev/null || \
             grep -o '"build_hash"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4) 2>/dev/null || echo "")
    fi
    
    if [ -z "$runtime_hash" ]; then
        echo -e "${YELLOW}  ⚠️  Could not read runtime build hash for ${agent_id} (container may still be starting)${NC}"
        return 0  # Not a failure, container may still be initializing
    fi
    
    if [ "$expected_hash" = "$runtime_hash" ]; then
        echo -e "${GREEN}  ✅ Build hash verified for ${agent_id}: ${expected_hash:0:20}...${NC}"
        return 0
    else
        echo -e "${RED}  ❌ Build hash mismatch for ${agent_id}!${NC}"
        echo -e "${RED}     Expected: ${expected_hash}${NC}"
        echo -e "${RED}     Runtime:  ${runtime_hash}${NC}"
        echo -e "${YELLOW}     ⚠️  Container may be running old code - consider force rebuild${NC}"
        return 1
    fi
}

# Rebuild Agents if requested
if [ "$REBUILD_AGENTS" = true ] || [ "$REBUILD_ALL" = true ]; then
    # Get list of agent services from docker-compose
    AGENTS=$(docker-compose config --services | grep -E "^(max|neo|nat|glyph|eve|data|quark|joi|og|hal)$" || echo "max neo")

    echo -e "${YELLOW}📦 Rebuilding agent containers...${NC}"
    echo -e "${BLUE}   Using Docker layer cache for faster rebuilds (use FORCE_REBUILD=1 for --no-cache)${NC}"
    
    # First, build agent packages to get build hashes
    echo -e "${BLUE}   Building agent packages...${NC}"
    for agent in $AGENTS; do
        if docker-compose config --services | grep -q "^${agent}$"; then
            role=$(get_agent_role "$agent")
            if [ "$role" != "unknown" ]; then
                echo -e "  📦 Building package for ${agent} (role: ${role})..."
                python3 "$REPO_ROOT/scripts/dev/build_agent.py" "$role" 2>/dev/null || echo -e "${YELLOW}  ⚠️  Build script may have failed for ${agent}${NC}"
            fi
        fi
    done
    
    # Now build Docker images with build hashes
    for agent in $AGENTS; do
        if docker-compose config --services | grep -q "^${agent}$"; then
            role=$(get_agent_role "$agent")
            build_hash=$(get_build_hash_from_manifest "$role")
            
            echo -e "  🔨 Rebuilding ${agent}..."
            if [ -n "$build_hash" ] && [ "$build_hash" != "unknown" ]; then
                echo -e "     Build hash: ${build_hash:0:30}...${NC}"
                # Export BUILD_HASH as environment variable for docker-compose
                export BUILD_HASH="$build_hash"
                if [ "${FORCE_REBUILD:-0}" = "1" ]; then
                    BUILD_HASH="$build_hash" docker-compose build --no-cache $agent || echo -e "${RED}  ⚠️  Build failed for ${agent}${NC}"
                else
                    BUILD_HASH="$build_hash" docker-compose build $agent || echo -e "${RED}  ⚠️  Build failed for ${agent}${NC}"
                fi
                unset BUILD_HASH
            else
                echo -e "${YELLOW}     ⚠️  Build hash not available, building without hash verification${NC}"
                if [ "${FORCE_REBUILD:-0}" = "1" ]; then
                    docker-compose build --no-cache $agent || echo -e "${RED}  ⚠️  Build failed for ${agent}${NC}"
                else
                    docker-compose build $agent || echo -e "${RED}  ⚠️  Build failed for ${agent}${NC}"
                fi
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
    
    # Step 5b: Verify build hash propagation
    echo ""
    echo -e "${BLUE}🔍 Step 5b: Verifying build hash propagation...${NC}"
    VERIFICATION_FAILED=false
    for agent in $AGENTS; do
        if docker-compose config --services | grep -q "^${agent}$"; then
            role=$(get_agent_role "$agent")
            expected_hash=$(get_build_hash_from_manifest "$role")
            if ! verify_build_hash "$agent" "$role" "$expected_hash"; then
                VERIFICATION_FAILED=true
            fi
        fi
    done
    
    if [ "$VERIFICATION_FAILED" = true ]; then
        echo -e "${YELLOW}⚠️  Some build hash verifications failed - containers may be running old code${NC}"
        echo -e "${YELLOW}   Consider running with FORCE_REBUILD=1 to ensure fresh builds${NC}"
    fi
else
    echo -e "${BLUE}⏳ Step 4: Waiting for services to be healthy (10 seconds)...${NC}"
    sleep 10
fi

# Step 6: Verify deployment
echo ""
echo -e "${BLUE}✅ Step 6: Verifying deployment...${NC}"
docker-compose ps

echo ""
echo -e "${GREEN}🎉 Rebuild and deploy complete!${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
if [ "$REBUILD_AGENTS" = true ] || [ "$REBUILD_ALL" = true ]; then
    echo -e "  1. Verify agent logs: ${YELLOW}docker-compose logs --tail=50 max neo${NC}"
fi
if [ "$REBUILD_RUNTIME_API" = true ] || [ "$REBUILD_ALL" = true ]; then
    echo -e "  2. Check Runtime API health: ${YELLOW}curl http://localhost:8001/health${NC}"
fi
if [ "$REBUILD_HEALTH_CHECK" = true ] || [ "$REBUILD_ALL" = true ]; then
    echo -e "  3. Check Health Check dashboard: ${YELLOW}curl http://localhost:8000/health${NC}"
    echo -e "  4. Open Agent Console: ${YELLOW}http://localhost:8000/health${NC} (click 'Agent Console' tab)"
fi
if [ "$REBUILD_AGENTS" = true ] || [ "$REBUILD_ALL" = true ]; then
    echo -e "  5. Run smoke tests: ${YELLOW}python3 -m pytest tests/smoke/ -v${NC}"
fi
