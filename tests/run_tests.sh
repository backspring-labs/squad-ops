#!/bin/bash
# SquadOps Test Harness Runner
# Convenient script for running different test suites

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Auto-activate virtual environment if it exists and not already activated
if [ -d ".venv" ] && [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${BLUE}Activating virtual environment...${NC}"
    source .venv/bin/activate
fi

echo -e "${BLUE}🧪 SquadOps Test Harness${NC}"
echo "Project root: $PROJECT_ROOT"
if [ -n "$VIRTUAL_ENV" ]; then
    echo "Virtual env: $VIRTUAL_ENV"
fi
echo ""

# Function to run tests with proper error handling
run_tests() {
    local test_type="$1"
    local test_path="$2"
    local extra_args="$3"
    
    echo -e "${YELLOW}Running $test_type tests...${NC}"
    
    if python -m pytest "$test_path" $extra_args; then
        echo -e "${GREEN}✅ $test_type tests passed${NC}"
        return 0
    else
        echo -e "${RED}❌ $test_type tests failed${NC}"
        return 1
    fi
}

# Function to check Python version
check_python_version() {
    echo -e "${BLUE}Checking Python version...${NC}"
    
    local python_version=$(python --version 2>&1 | awk '{print $2}')
    local required_version="3.11"
    
    if ! python -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
        echo -e "${RED}❌ Python version $python_version is too old${NC}"
        echo "SquadOps requires Python >= $required_version"
        echo "Current version: $python_version"
        echo ""
        echo "To fix:"
        echo "  1. Install pyenv: brew install pyenv"
        echo "  2. Install Python 3.11: pyenv install 3.11.14"
        echo "  3. Set local version: pyenv local 3.11.14"
        echo "  4. Create virtual env: python -m venv .venv"
        echo "  5. Activate: source .venv/bin/activate"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Python version OK ($python_version)${NC}"
}

# Function to check if dependencies are installed
check_dependencies() {
    echo -e "${BLUE}Checking dependencies...${NC}"
    
    if ! python -c "import pytest" 2>/dev/null; then
        echo -e "${RED}❌ pytest not installed${NC}"
        echo "Install with: pip install -r tests/requirements.txt"
        exit 1
    fi
    
    if ! python -c "import pytest_asyncio" 2>/dev/null; then
        echo -e "${RED}❌ pytest-asyncio not installed${NC}"
        echo "Install with: pip install -r tests/requirements.txt"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Dependencies OK${NC}"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  unit          Run unit tests"
    echo "  integration   Run integration tests"
    echo "  regression    Run regression tests"
    echo "  performance   Run performance tests"
    echo "  all           Run all tests"
    echo "  coverage      Generate coverage report"
    echo "  smoke         Run quick smoke test"
    echo "  specific      Run specific test file"
    echo "  help          Show this help"
    echo ""
    echo "Options:"
    echo "  --no-cov      Skip coverage reporting"
    echo "  --verbose     Verbose output"
    echo "  --skip-lint   Skip ruff linting (not recommended)"
    echo "  --file FILE   Specific test file (for 'specific' command)"
    echo ""
    echo "Examples:"
    echo "  $0 unit                    # Run unit tests"
    echo "  $0 all --no-cov           # Run all tests without coverage"
    echo "  $0 specific --file tests/unit/test_base_agent.py"
    echo "  $0 coverage               # Generate coverage report"
}

# Parse command line arguments
COMMAND=""
NO_COV=false
VERBOSE=false
SKIP_LINT=false
TEST_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        unit|integration|regression|performance|all|coverage|smoke|specific|help)
            COMMAND="$1"
            shift
            ;;
        --no-cov)
            NO_COV=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --skip-lint)
            SKIP_LINT=true
            shift
            ;;
        --file)
            TEST_FILE="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_usage
            exit 1
            ;;
    esac
done

# Default command
if [[ -z "$COMMAND" ]]; then
    COMMAND="all"
fi

# Show help
if [[ "$COMMAND" == "help" ]]; then
    show_usage
    exit 0
fi

# Check Python version
check_python_version

# Check dependencies
check_dependencies

# Function to run ruff linting
run_ruff() {
    echo -e "${YELLOW}Running ruff linting...${NC}"
    
    if command -v ruff >/dev/null 2>&1; then
        if ruff check .; then
            echo -e "${GREEN}✅ Ruff linting passed${NC}"
            return 0
        else
            echo -e "${RED}❌ Ruff linting failed${NC}"
            echo "Fix issues with: ruff check --fix ."
            return 1
        fi
    else
        echo -e "${YELLOW}⚠️  ruff not found, skipping linting${NC}"
        echo "Install with: pip install ruff"
        return 0
    fi
}

# Run ruff by default (can be skipped with --skip-lint)
if [[ "$SKIP_LINT" == "false" ]]; then
    if ! run_ruff; then
        echo -e "${RED}❌ Linting failed. Fix issues or use --skip-lint to continue${NC}"
        exit 1
    fi
    echo ""
fi

# Build pytest arguments
PYTEST_ARGS="-v"
if [[ "$NO_COV" == "false" ]]; then
    PYTEST_ARGS="$PYTEST_ARGS --cov=agents --cov=config --cov-report=term-missing"
fi

# Run tests based on command
case "$COMMAND" in
    unit)
        run_tests "Unit" "tests/unit/" "$PYTEST_ARGS"
        ;;
    integration)
        run_tests "Integration" "tests/integration/" "$PYTEST_ARGS"
        ;;
    regression)
        run_tests "Regression" "tests/regression/" "$PYTEST_ARGS"
        ;;
    performance)
        run_tests "Performance" "tests/performance/" "$PYTEST_ARGS"
        ;;
    all)
        run_tests "All" "tests/" "$PYTEST_ARGS"
        ;;
    coverage)
        echo -e "${YELLOW}Generating coverage report...${NC}"
        python -m pytest tests/ --cov=src/squadops --cov=adapters --cov-report=html --cov-report=term-missing --cov-report=xml
        echo -e "${GREEN}✅ Coverage report generated${NC}"
        echo "HTML report: htmlcov/index.html"
        ;;
    smoke)
        run_tests "Smoke" "tests/unit/test_base_agent.py::test_agent_initialization" "-v"
        ;;
    specific)
        if [[ -z "$TEST_FILE" ]]; then
            echo -e "${RED}❌ --file required for specific command${NC}"
            show_usage
            exit 1
        fi
        run_tests "Specific" "$TEST_FILE" "$PYTEST_ARGS"
        ;;
    *)
        echo -e "${RED}❌ Unknown command: $COMMAND${NC}"
        show_usage
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}🎉 Test run completed!${NC}"


