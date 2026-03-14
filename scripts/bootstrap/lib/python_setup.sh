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

# Validate system Python meets minimum version requirement (R5: local-spark).
# Sets SQUADOPS_PYTHON_VERSION to the actual major.minor found.
setup_system_python() {
    local min_version="$1"
    local actual
    actual=$(python3 --version 2>/dev/null | awk '{print $2}' | cut -d. -f1,2)
    if [[ -z "$actual" ]]; then
        error "python3 not found"
        exit 1
    fi
    # Compare major.minor as integers (3.12 >= 3.11)
    local min_major min_minor actual_major actual_minor
    min_major="${min_version%%.*}"
    min_minor="${min_version##*.}"
    actual_major="${actual%%.*}"
    actual_minor="${actual##*.}"
    if [[ "$actual_major" -gt "$min_major" ]] ||
       { [[ "$actual_major" -eq "$min_major" ]] && [[ "$actual_minor" -ge "$min_minor" ]]; }; then
        success "System Python ${actual} meets minimum ${min_version}"
        export SQUADOPS_PYTHON_VERSION="$actual"
    else
        error "System Python is ${actual}, need >= ${min_version}"
        exit 1
    fi
}

# Create .venv if not present (R4: required for all profiles).
# Uses SQUADOPS_PYTHON_VERSION (set by setup_system_python) if available,
# falls back to the explicit argument, then plain python3.
create_venv() {
    local python_version="${SQUADOPS_PYTHON_VERSION:-${1:-}}"
    if [[ -d ".venv" ]]; then
        success ".venv already exists"
    else
        local py_bin="python3"
        if [[ -n "$python_version" ]] && check_command "python${python_version}"; then
            py_bin="python${python_version}"
        fi
        info "Creating .venv with ${py_bin}..."
        run_or_dry "$py_bin" -m venv .venv
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
