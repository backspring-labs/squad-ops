#!/usr/bin/env bash
# Ollama setup functions for bootstrap (SIP-0081).
# Sourced by bootstrap.sh — not executed directly.

# Install Ollama via the official install script.
install_ollama() {
    if check_command ollama; then
        success "Ollama already installed"
        return 0
    fi
    info "Installing Ollama..."
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        info "[dry-run] curl -fsSL https://ollama.com/install.sh | sh"
    else
        curl -fsSL https://ollama.com/install.sh | sh
    fi
}

# Pull a model if not already present.
pull_model() {
    local model="$1"
    if [[ "${SKIP_MODELS:-0}" == "1" ]]; then
        warn "Skipping model pull: ${model} (--skip-models)"
        return 0
    fi
    if check_model_present "$model"; then
        success "Model ${model} already present"
        return 0
    fi
    info "Pulling model ${model}..."
    run_or_dry ollama pull "$model"
}

# Pull all models listed in a bootstrap profile YAML.
# Uses read_profile_models.py (requires PyYAML, available after install_python_deps).
pull_models_from_profile() {
    local profile_yaml="$1"
    local reader
    reader="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/read_profile_models.py"

    if [[ ! -f ".venv/bin/python" ]]; then
        error ".venv not found — cannot read profile YAML for model list"
        return 1
    fi

    local model
    while IFS= read -r model; do
        [[ -n "$model" ]] && pull_model "$model"
    done < <(.venv/bin/python "$reader" "$profile_yaml")
}

# Check if a model is already pulled.
check_model_present() {
    local model="$1"
    ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -q "^${model}$"
}
