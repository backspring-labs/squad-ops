#!/usr/bin/env bash
# Python setup functions for bootstrap (SIP-0081).
# Sourced by bootstrap.sh — not executed directly.

# Install pyenv if not present.
setup_pyenv() {
    local python_version="$1"
    if check_command pyenv; then
        success "pyenv already installed"
    else
        info "Installing pyenv..."
        run_or_dry curl -fsSL https://pyenv.run | bash
    fi

    # Install requested Python version if not present
    if pyenv versions --bare 2>/dev/null | grep -q "^${python_version}"; then
        success "Python ${python_version} already installed via pyenv"
    else
        info "Installing Python ${python_version} via pyenv..."
        run_or_dry pyenv install "${python_version}"
    fi

    run_or_dry pyenv local "${python_version}"
}

# Validate system Python meets version requirement (R5: local-spark).
setup_system_python() {
    local python_version="$1"
    local actual
    actual=$(python3 --version 2>/dev/null | awk '{print $2}' | cut -d. -f1,2)
    if [[ "$actual" == "$python_version" ]]; then
        success "System Python ${actual} matches requirement"
    else
        error "System Python is ${actual:-not found}, need ${python_version}"
        exit 1
    fi
}

# Create .venv if not present (R4: required for all profiles).
create_venv() {
    local python_version="$1"
    if [[ -d ".venv" ]]; then
        success ".venv already exists"
    else
        info "Creating .venv..."
        run_or_dry "python${python_version}" -m venv .venv
    fi
}

# Install Python dependencies in order (R8).
install_python_deps() {
    local extras="${1:-}"
    local test_deps="${2:-}"

    info "Installing base package..."
    run_or_dry .venv/bin/pip install -e .

    if [[ -n "$extras" ]]; then
        info "Installing extras: ${extras}..."
        run_or_dry .venv/bin/pip install -e ".[${extras}]"
    fi

    if [[ -n "$test_deps" ]]; then
        info "Installing test deps from ${test_deps}..."
        run_or_dry .venv/bin/pip install -r "${test_deps}"
    fi
}
