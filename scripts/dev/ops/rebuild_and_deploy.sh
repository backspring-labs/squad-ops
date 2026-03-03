#!/bin/bash
# Rebuild and deploy SquadOps containers with updated code
# Ensures all infrastructure (including Ollama) is running first
# Can be run in background - logs to rebuild_deploy.log
#
# Usage:
#   ./scripts/dev/ops/rebuild_and_deploy.sh                           # Rebuild everything (default)
#   ./scripts/dev/ops/rebuild_and_deploy.sh all                       # Rebuild everything
#   ./scripts/dev/ops/rebuild_and_deploy.sh console                   # Rebuild only console service
#   ./scripts/dev/ops/rebuild_and_deploy.sh agents                    # Rebuild default 6 core agents (max, nat, neo, eve, data)
#   ./scripts/dev/ops/rebuild_and_deploy.sh agents max neo            # Rebuild only specified agents
#   ./scripts/dev/ops/rebuild_and_deploy.sh agents max nat neo eve data glyph  # Rebuild specified agents
#   ./scripts/dev/ops/rebuild_and_deploy.sh runtime-api agents        # Rebuild runtime-api and default agents
#   ./scripts/dev/ops/rebuild_and_deploy.sh runtime-api               # Rebuild only runtime-api
#
# Environment variables:
#   FORCE_REBUILD=1                             # Use --no-cache for full rebuild

set -e

# Enable BuildKit for cache mount support in Dockerfiles
export DOCKER_BUILDKIT=1

# Get repository root directory (parent of scripts/)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

# Derive source hash for Docker cache busting (invalidates source layers on new commits)
SOURCE_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
export SOURCE_HASH

# Parse command-line arguments
REBUILD_CONSOLE=false
REBUILD_AGENTS=false
REBUILD_RUNTIME_API=false
REBUILD_ALL=true
AGENT_LIST=()

if [ $# -gt 0 ]; then
    REBUILD_ALL=false
    i=0
    while [ $i -lt $# ]; do
        i=$((i + 1))
        arg="${!i}"
        case "$arg" in
            console)
                REBUILD_CONSOLE=true
                ;;
            agents)
                REBUILD_AGENTS=true
                # Collect agent names after "agents" until next service keyword
                i=$((i + 1))
                while [ $i -le $# ]; do
                    next_arg="${!i}"
                    case "$next_arg" in
                        console|runtime-api|runtime_api|all)
                            # Hit another service keyword, back up and break
                            i=$((i - 1))
                            break
                            ;;
                        *)
                            # Add agent name to list
                            AGENT_LIST+=("$next_arg")
                            ;;
                    esac
                    i=$((i + 1))
                done
                i=$((i - 1))  # Adjust for loop increment
                ;;
            runtime-api|runtime_api)
                REBUILD_RUNTIME_API=true
                ;;
            all)
                REBUILD_ALL=true
                REBUILD_CONSOLE=true
                REBUILD_AGENTS=true
                REBUILD_RUNTIME_API=true
                ;;
            *)
                echo "Unknown argument: $arg"
                echo "Usage: $0 [console] [agents [agent1 agent2 ...]] [runtime-api] [all]"
                echo "  Examples:"
                echo "    $0 console                   # Build only console"
                echo "    $0 agents                    # Build default 6 core agents (max, nat, neo, eve, data)"
                echo "    $0 agents max neo            # Build only max and neo"
                echo "    $0 runtime-api console       # Build runtime-api and console"
                exit 1
                ;;
        esac
    done
else
    # Default: rebuild everything
    REBUILD_CONSOLE=true
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
echo -e "${BLUE}💡 Tip: Monitor progress in another terminal with:${NC}"
echo -e "${YELLOW}   tail -f $LOG_FILE${NC}"
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
    echo -e "  ${YELLOW}✓${NC} All services (runtime-api, console, agents)"
else
    [ "$REBUILD_RUNTIME_API" = true ] && echo -e "  ${YELLOW}✓${NC} runtime-api"
    [ "$REBUILD_CONSOLE" = true ] && echo -e "  ${YELLOW}✓${NC} console"
    [ "$REBUILD_AGENTS" = true ] && echo -e "  ${YELLOW}✓${NC} agents"
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
docker-compose up -d rabbitmq postgres redis prefect-server

# Conditionally start runtime-api and console if they're being rebuilt
if [ "$REBUILD_RUNTIME_API" = true ] || [ "$REBUILD_ALL" = true ]; then
    echo "Starting runtime-api..."
    docker-compose up -d runtime-api || true
fi

if [ "$REBUILD_CONSOLE" = true ] || [ "$REBUILD_ALL" = true ]; then
    echo "Starting console..."
    docker-compose up -d squadops-console || true
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
if curl -s --connect-timeout 5 http://localhost:8001/health > /dev/null 2>&1 || \
   docker ps --format '{{.Names}}\t{{.Status}}' | grep squadops-runtime-api | grep -q "Up"; then
    echo -e "${GREEN}✅ Runtime API container is running${NC}"
else
    echo -e "${YELLOW}⚠️  Runtime API may still be starting${NC}"
fi

# Step 3: Rebuild services that changed
echo ""
echo -e "${BLUE}🔨 Step 3: Rebuilding containers with updated code...${NC}"

# Track build failures for non-blocking services
RUNTIME_API_FAILED=0
CONSOLE_FAILED=0

# Rebuild Runtime API if requested
if [ "$REBUILD_RUNTIME_API" = true ] || [ "$REBUILD_ALL" = true ]; then
    echo -e "${YELLOW}📦 Rebuilding runtime-api...${NC}"
    if [ "${FORCE_REBUILD:-0}" = "1" ]; then
        BUILD_OK=true; docker-compose build --no-cache runtime-api || BUILD_OK=false
    else
        BUILD_OK=true; docker-compose build runtime-api || BUILD_OK=false
    fi
    if [ "$BUILD_OK" = true ]; then
        docker-compose up -d runtime-api
        echo -e "${GREEN}✅ Runtime API rebuilt and restarted${NC}"
    else
        RUNTIME_API_FAILED=1
        echo -e "${RED}  ⚠️  runtime-api build failed — skipping restart${NC}"
    fi
fi

# Rebuild Console if requested
if [ "$REBUILD_CONSOLE" = true ] || [ "$REBUILD_ALL" = true ]; then
    echo -e "${YELLOW}📦 Rebuilding console...${NC}"

    # Generate .env.console from console/continuum.lock (required for Docker build args)
    echo -e "${BLUE}   Generating .env.console from console/continuum.lock...${NC}"
    if ! "$REPO_ROOT/scripts/dev/gen_console_env.sh"; then
        CONSOLE_FAILED=1
        echo -e "${RED}  ⚠️  gen_console_env.sh failed — skipping console build${NC}"
    fi

    if [ "$CONSOLE_FAILED" != "1" ]; then
        if [ "${FORCE_REBUILD:-0}" = "1" ]; then
            BUILD_OK=true; docker-compose build --no-cache squadops-console || BUILD_OK=false
        else
            BUILD_OK=true; docker-compose build squadops-console || BUILD_OK=false
        fi
        if [ "$BUILD_OK" = true ]; then
            docker-compose up -d squadops-console
            echo -e "${GREEN}✅ Console rebuilt and restarted${NC}"
        else
            CONSOLE_FAILED=1
            echo -e "${RED}  ⚠️  Console build failed — skipping restart, continuing with agents${NC}"
        fi
    fi
fi

# Function to get agent role from agent ID
get_agent_role() {
    local agent_id=$1
    # Map agent IDs to roles (from instances.yaml or docker-compose)
    case "$agent_id" in
        max) echo "lead" ;;
        neo) echo "dev" ;;
        nat) echo "strat" ;;
        eve) echo "qa" ;;
        bob) echo "builder" ;;
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
    # Determine which agents to build
    if [ ${#AGENT_LIST[@]} -eq 0 ]; then
        # No agents specified, use default 6 core agents
        AGENTS=$(docker-compose config --services | grep -E "^(max|nat|neo|eve|bob|data)$" || echo "max nat neo eve bob data")
        echo -e "${BLUE}   No agents specified, using default core agents: max, nat, neo, eve, bob, data${NC}"
    else
        # Use specified agents, validate they exist in docker-compose
        AGENTS=""
        AVAILABLE_SERVICES=$(docker-compose config --services)
        for agent in "${AGENT_LIST[@]}"; do
            if echo "$AVAILABLE_SERVICES" | grep -q "^${agent}$"; then
                AGENTS="${AGENTS} ${agent}"
            else
                echo -e "${YELLOW}  ⚠️  Agent '${agent}' not found in docker-compose, skipping${NC}"
            fi
        done
        AGENTS=$(echo $AGENTS | xargs)  # Trim whitespace
        if [ -z "$AGENTS" ]; then
            echo -e "${RED}  ❌ No valid agents specified${NC}"
            exit 1
        fi
        echo -e "${BLUE}   Building specified agents: ${AGENTS}${NC}"
    fi

    echo -e "${YELLOW}📦 Rebuilding agent containers...${NC}"
    echo -e "${BLUE}   Using Docker layer cache for faster rebuilds (use FORCE_REBUILD=1 for --no-cache)${NC}"
    
    # Auto-activate virtual environment if it exists and not already activated
    if [ -d "$REPO_ROOT/.venv" ] && [ -z "$VIRTUAL_ENV" ]; then
        echo -e "${BLUE}   Activating virtual environment...${NC}"
        source "$REPO_ROOT/.venv/bin/activate"
    fi
    
    # First, build agent packages to get build hashes
    echo -e "${BLUE}   Building agent packages...${NC}"
    for agent in $AGENTS; do
        if docker-compose config --services | grep -q "^${agent}$"; then
            role=$(get_agent_role "$agent")
            if [ "$role" != "unknown" ]; then
                echo -e "  📦 Building package for ${agent} (role: ${role})..."
                if ! python3 "$REPO_ROOT/scripts/dev/build_agent.py" "$role"; then
                    echo -e "${RED}  ❌ Build script failed for ${agent}${NC}"
                    exit 1
                fi
                
                # Check for legacy manifest (optional — new arch uses editable install)
                if [ ! -f "$REPO_ROOT/dist/agents/${role}/manifest.json" ]; then
                    echo -e "${YELLOW}  ⚠️  No legacy manifest for ${agent} (new arch uses editable install)${NC}"
                fi
            fi
        fi
    done
    
    # Count total agents for progress tracking
    TOTAL_AGENTS=$(echo $AGENTS | wc -w | xargs)
    CURRENT_AGENT=0
    
    # Now build Docker images with build hashes
    for agent in $AGENTS; do
        CURRENT_AGENT=$((CURRENT_AGENT + 1))
        if docker-compose config --services | grep -q "^${agent}$"; then
            role=$(get_agent_role "$agent")
            build_hash=$(get_build_hash_from_manifest "$role")

            echo -e "  🔨 Rebuilding ${agent} [${CURRENT_AGENT}/${TOTAL_AGENTS}]..."
            if [ -n "$build_hash" ] && [ "$build_hash" != "unknown" ]; then
                echo -e "     Build hash: ${build_hash:0:30}...${NC}"
            fi

            if [ "${FORCE_REBUILD:-0}" = "1" ]; then
                echo -e "     ${BLUE}Building Docker image (no cache)...${NC}"
                docker-compose build --no-cache $agent || {
                    echo -e "${RED}  ⚠️  Build failed for ${agent}${NC}"
                    exit 1
                }
            else
                echo -e "     ${BLUE}Building Docker image...${NC}"
                docker-compose build $agent || {
                    echo -e "${RED}  ⚠️  Build failed for ${agent}${NC}"
                    exit 1
                }
            fi
            echo -e "     ${GREEN}✅ ${agent} built successfully${NC}"
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
    FAILED_AGENTS=()
    
    for agent in $AGENTS; do
        if docker-compose config --services | grep -q "^${agent}$"; then
            role=$(get_agent_role "$agent")
            expected_hash=$(get_build_hash_from_manifest "$role")
            
            if ! verify_build_hash "$agent" "$role" "$expected_hash"; then
                VERIFICATION_FAILED=true
                FAILED_AGENTS+=("$agent")
            fi
        fi
    done
    
    if [ "$VERIFICATION_FAILED" = true ]; then
        echo -e "${RED}❌ Build hash verification failed for: ${FAILED_AGENTS[*]}${NC}"
        echo -e "${YELLOW}   Retrying with --no-cache...${NC}"
        
        # Retry failed agents with --no-cache
        for agent in "${FAILED_AGENTS[@]}"; do
            echo -e "  🔨 Rebuilding ${agent} with --no-cache..."
            docker-compose build --no-cache $agent || {
                echo -e "${RED}  ❌ Rebuild failed for ${agent}${NC}"
                exit 1
            }

            docker-compose up -d $agent
        done
        
        # Wait and verify again
        sleep 15
        VERIFICATION_FAILED=false
        for agent in "${FAILED_AGENTS[@]}"; do
            role=$(get_agent_role "$agent")
            expected_hash=$(get_build_hash_from_manifest "$role")
            if ! verify_build_hash "$agent" "$role" "$expected_hash"; then
                VERIFICATION_FAILED=true
            fi
        done
        
        if [ "$VERIFICATION_FAILED" = true ]; then
            echo -e "${RED}❌ Build hash verification failed after retry. Deployment aborted.${NC}"
            exit 1
        else
            echo -e "${GREEN}✅ All agents verified after retry${NC}"
        fi
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
    echo -e "  3. Check infra probes: ${YELLOW}curl http://localhost:8001/health/infra${NC}"
fi
if [ "$REBUILD_CONSOLE" = true ] || [ "$REBUILD_ALL" = true ]; then
    echo -e "  4. Open Console: ${YELLOW}http://localhost:4040${NC}"
fi
if [ "$REBUILD_AGENTS" = true ] || [ "$REBUILD_ALL" = true ]; then
    echo -e "  5. Run smoke tests: ${YELLOW}python3 -m pytest tests/smoke/ -v${NC}"
fi

# Report any build failures that were deferred
BUILD_FAILURES=0
if [ "${RUNTIME_API_FAILED:-0}" = "1" ]; then
    echo ""
    echo -e "${RED}❌ runtime-api build failed. Fix the error and rebuild:${NC}"
    echo -e "${YELLOW}   ./scripts/dev/ops/rebuild_and_deploy.sh runtime-api${NC}"
    BUILD_FAILURES=1
fi
if [ "${CONSOLE_FAILED:-0}" = "1" ]; then
    echo ""
    echo -e "${RED}❌ Console build failed. Fix the Svelte error and rebuild:${NC}"
    echo -e "${YELLOW}   ./scripts/dev/ops/rebuild_and_deploy.sh console${NC}"
    BUILD_FAILURES=1
fi
if [ "$BUILD_FAILURES" = "1" ]; then
    exit 1
fi
