#!/usr/bin/env bash
# Ollama setup functions for bootstrap (SIP-0081).
# Sourced by bootstrap.sh — not executed directly.

# Configure Ollama to listen on all interfaces so Docker containers can reach it.
# On Linux, Ollama defaults to 127.0.0.1 which is unreachable from containers
# even with host.docker.internal mapped via extra_hosts.
# On macOS (Docker Desktop), this is unnecessary — the VM handles routing.
configure_ollama_host_binding() {
    local override_dir="/etc/systemd/system/ollama.service.d"
    local override_file="${override_dir}/override.conf"

    if [[ ! -f /etc/systemd/system/ollama.service ]]; then
        info "Ollama not managed by systemd — skipping host binding config"
        return 0
    fi

    # Check if already configured
    if [[ -f "$override_file" ]] && grep -q 'OLLAMA_HOST=0.0.0.0' "$override_file" 2>/dev/null; then
        success "Ollama already configured to listen on 0.0.0.0"
        return 0
    fi

    info "Configuring Ollama to listen on 0.0.0.0 (required for Docker containers)..."
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        info "[dry-run] mkdir -p ${override_dir}"
        info "[dry-run] write ${override_file} with OLLAMA_HOST=0.0.0.0"
        info "[dry-run] systemctl daemon-reload && systemctl restart ollama"
    else
        sudo mkdir -p "$override_dir"
        printf '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0"\n' | sudo tee "$override_file" > /dev/null
        sudo systemctl daemon-reload
        sudo systemctl restart ollama
        success "Ollama now listening on 0.0.0.0:11434"
    fi
}

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
