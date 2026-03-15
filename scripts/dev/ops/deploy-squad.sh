#!/bin/bash
# deploy-squad.sh - Deploy agents based on instances.yaml configuration

set -e

# Get repository root directory
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTANCES_FILE="$REPO_ROOT/agents/instances/instances.yaml"
DOCKER_COMPOSE_FILE="$REPO_ROOT/docker compose.yml"

echo -e "${BLUE}🚀 SquadOps Agent Deployment${NC}"
echo "================================"

# Check if instances file exists
if [ ! -f "$INSTANCES_FILE" ]; then
    echo -e "${RED}❌ Error: $INSTANCES_FILE not found${NC}"
    exit 1
fi

# Check if docker compose file exists
if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
    echo -e "${RED}❌ Error: $DOCKER_COMPOSE_FILE not found${NC}"
    exit 1
fi

# Function to check if yq is installed
check_yq() {
    if ! command -v yq &> /dev/null; then
        echo -e "${RED}❌ Error: yq is required but not installed${NC}"
        echo "Install with: brew install yq (macOS) or apt-get install yq (Ubuntu)"
        exit 1
    fi
}

# Function to deploy a single agent
deploy_agent() {
    local agent_id=$1
    local role=$2
    local display_name=$3
    local model=$4
    
    echo -e "${YELLOW}📦 Deploying $display_name ($agent_id) - Role: $role${NC}"
    
    # Set environment variables for docker compose
    export AGENT_ID="$agent_id"
    export ROLE="$role"
    export DISPLAY_NAME="$display_name"
    export MODEL="$model"
    
    # Deploy the agent
    docker compose up -d "$agent_id"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $display_name deployed successfully${NC}"
    else
        echo -e "${RED}❌ Failed to deploy $display_name${NC}"
        return 1
    fi
}

# Function to deploy all enabled agents
deploy_all() {
    echo -e "${BLUE}🔍 Reading agent configuration...${NC}"
    
    # Get all enabled instances
    local instances=$(yq eval '.instances[] | select(.enabled == true)' "$INSTANCES_FILE")
    
    if [ -z "$instances" ]; then
        echo -e "${YELLOW}⚠️  No enabled agents found in $INSTANCES_FILE${NC}"
        return 0
    fi
    
    echo -e "${BLUE}📋 Found enabled agents:${NC}"
    yq eval '.instances[] | select(.enabled == true) | "- \(.display_name) (\(.id)) - \(.role)"' "$INSTANCES_FILE"
    echo ""
    
    # Deploy each enabled agent
    while IFS= read -r line; do
        if [[ $line =~ ^- ]]; then
            # Extract agent info from yq output
            local agent_id=$(echo "$line" | yq eval '.id')
            local role=$(echo "$line" | yq eval '.role')
            local display_name=$(echo "$line" | yq eval '.display_name')
            local model=$(echo "$line" | yq eval '.model')
            
            deploy_agent "$agent_id" "$role" "$display_name" "$model"
        fi
    done <<< "$instances"
}

# Function to deploy specific agent
deploy_specific() {
    local target_agent=$1
    
    echo -e "${BLUE}🔍 Looking for agent: $target_agent${NC}"
    
    # Check if agent exists and is enabled
    local agent_info=$(yq eval ".instances[] | select(.id == \"$target_agent\" and .enabled == true)" "$INSTANCES_FILE")
    
    if [ -z "$agent_info" ]; then
        echo -e "${RED}❌ Agent '$target_agent' not found or not enabled${NC}"
        echo -e "${YELLOW}Available agents:${NC}"
        yq eval '.instances[] | select(.enabled == true) | "- \(.id) (\(.display_name))"' "$INSTANCES_FILE"
        exit 1
    fi
    
    local agent_id=$(echo "$agent_info" | yq eval '.id')
    local role=$(echo "$agent_info" | yq eval '.role')
    local display_name=$(echo "$agent_info" | yq eval '.display_name')
    local model=$(echo "$agent_info" | yq eval '.model')
    
    deploy_agent "$agent_id" "$role" "$display_name" "$model"
}

# Function to show status
show_status() {
    echo -e "${BLUE}📊 Agent Status${NC}"
    echo "==============="
    
    yq eval '.instances[] | select(.enabled == true) | "\(.display_name) (\(.id)) - \(.role) - \(.model)"' "$INSTANCES_FILE"
}

# Main script logic
main() {
    check_yq
    
    case "${1:-all}" in
        "all")
            deploy_all
            ;;
        "status")
            show_status
            ;;
        "help"|"-h"|"--help")
            echo "Usage: $0 [command]"
            echo ""
            echo "Commands:"
            echo "  all     - Deploy all enabled agents (default)"
            echo "  status  - Show agent status"
            echo "  <agent> - Deploy specific agent (e.g., max, neo)"
            echo "  help    - Show this help"
            ;;
        *)
            deploy_specific "$1"
            ;;
    esac
}

# Run main function
main "$@"
