#!/bin/bash
# Integration Test Execution Script
# Checks prerequisites and runs all integration tests in optimal order

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=========================================="
echo "SquadOps Integration Test Runner"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

# Check if pytest is available
if ! python3 -m pytest --version &> /dev/null; then
    echo -e "${RED}❌ pytest is not installed. Install with: pip install pytest${NC}"
    exit 1
fi

# Check service prerequisites
echo "🔍 Checking service prerequisites..."
echo ""

SERVICE_CHECK_SCRIPT="$SCRIPT_DIR/check_services.py"
if [ -f "$SERVICE_CHECK_SCRIPT" ]; then
    if python3 "$SERVICE_CHECK_SCRIPT" --verbose; then
        echo -e "${GREEN}✅ All required services are healthy${NC}"
        echo ""
    else
        echo -e "${YELLOW}⚠️  Some services are not available${NC}"
        echo "   Tests may skip if services are unavailable"
        echo ""
    fi
else
    echo -e "${YELLOW}⚠️  Service check script not found: $SERVICE_CHECK_SCRIPT${NC}"
    echo "   Continuing without service check..."
    echo ""
fi

# Run integration tests
echo "🧪 Running integration tests..."
echo ""

cd "$PROJECT_ROOT"

# Run tests with verbose output and show test names
# Order: fastest tests first, then by category
# 1. Service integration tests (fastest)
# 2. Memory integration tests
# 3. Workflow tests (may require Ollama)
# 4. Agent communication tests (may require RabbitMQ and agents)

TEST_ARGS=(
    "-v"                    # Verbose
    "--tb=short"            # Short traceback format
    "--strict-markers"      # Strict marker validation
    "-m" "integration"      # Only integration tests
)

# Check if specific test file or marker is requested
if [ "$1" != "" ]; then
    if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
        echo "Usage: $0 [test_file|marker]"
        echo ""
        echo "Examples:"
        echo "  $0                                    # Run all integration tests"
        echo "  $0 test_workflow.py                   # Run workflow tests only"
        echo "  $0 -m service_postgres                # Run PostgreSQL-dependent tests"
        echo "  $0 -m service_ollama                  # Run Ollama-dependent tests"
        echo ""
        exit 0
    elif [[ "$1" == "-m" ]]; then
        # Marker specified
        TEST_ARGS+=("$1" "$2")
        shift 2
    else
        # Test file specified
        TEST_ARGS+=("$SCRIPT_DIR/$1")
        shift
    fi
fi

# Add remaining arguments
TEST_ARGS+=("$@")

# Run pytest
if python3 -m pytest "${TEST_ARGS[@]}" "$SCRIPT_DIR"; then
    echo ""
    echo -e "${GREEN}=========================================="
    echo "✅ All integration tests passed!"
    echo "==========================================${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}=========================================="
    echo "❌ Some integration tests failed"
    echo "==========================================${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check service status: python3 $SERVICE_CHECK_SCRIPT"
    echo "  2. Check agent containers: docker ps --filter 'name=squadops'"
    echo "  3. Check service logs: docker logs squadops-max"
    echo "  4. Run specific test: $0 test_workflow.py"
    echo ""
    exit 1
fi

