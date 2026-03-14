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

# Check if a model is already pulled.
check_model_present() {
    local model="$1"
    ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -q "^${model}$"
}
