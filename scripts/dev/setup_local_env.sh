#!/bin/bash
# SquadOps Local Development Environment Setup
# This script helps set up a consistent Python development environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 SquadOps Local Development Setup${NC}"
echo ""

# Check if pyenv is installed
if ! command -v pyenv &> /dev/null; then
    echo -e "${YELLOW}⚠️  pyenv not found${NC}"
    echo "Installing pyenv via Homebrew..."
    if ! command -v brew &> /dev/null; then
        echo -e "${RED}❌ Homebrew not found. Please install Homebrew first:${NC}"
        echo "   https://brew.sh"
        exit 1
    fi
    brew install pyenv
    
    echo -e "${YELLOW}⚠️  Please add pyenv to your shell configuration:${NC}"
    echo ""
    echo "Add these lines to ~/.zshrc (or ~/.bashrc):"
    echo "  export PYENV_ROOT=\"\$HOME/.pyenv\""
    echo "  [[ -d \$PYENV_ROOT/bin ]] && export PATH=\"\$PYENV_ROOT/bin:\$PATH\""
    echo "  eval \"\$(pyenv init -)\""
    echo ""
    echo "Then restart your terminal or run: source ~/.zshrc"
    exit 1
fi

echo -e "${GREEN}✅ pyenv found${NC}"

# Load pyenv
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Check if Python 3.11.14 is installed
if ! pyenv versions --bare | grep -q "^3.11.14$"; then
    echo -e "${YELLOW}⚠️  Python 3.11.14 not found${NC}"
    echo "Installing Python 3.11.14 via pyenv..."
    pyenv install 3.11.14
else
    echo -e "${GREEN}✅ Python 3.11.14 found${NC}"
fi

# Set local Python version
echo -e "${BLUE}Setting local Python version to 3.11.14...${NC}"
pyenv local 3.11.14

# Verify Python version
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
if python -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
    echo -e "${GREEN}✅ Python version OK ($PYTHON_VERSION)${NC}"
else
    echo -e "${RED}❌ Python version $PYTHON_VERSION is too old${NC}"
    exit 1
fi

# Create or update virtual environment
if [ -d ".venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment already exists${NC}"
    read -p "Remove and recreate? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf .venv
        echo -e "${BLUE}Creating new virtual environment...${NC}"
        python -m venv .venv
    else
        echo -e "${BLUE}Using existing virtual environment${NC}"
    fi
else
    echo -e "${BLUE}Creating virtual environment...${NC}"
    python -m venv .venv
fi

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source .venv/bin/activate

# Upgrade pip
echo -e "${BLUE}Upgrading pip...${NC}"
pip install --upgrade pip

# Install test dependencies
if [ -f "tests/requirements.txt" ]; then
    echo -e "${BLUE}Installing test dependencies...${NC}"
    pip install -r tests/requirements.txt
    echo -e "${GREEN}✅ Test dependencies installed${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Setup complete!${NC}"
echo ""
echo "To activate the virtual environment in the future:"
echo "  source .venv/bin/activate"
echo ""
echo "To verify your setup:"
echo "  ./tests/run_tests.sh smoke"

