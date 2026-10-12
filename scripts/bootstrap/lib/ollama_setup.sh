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

# The Ollama CLI that pulls and lists models: the host's by default; the local-spark profile
# points it into the container (#2249).
OLLAMA_CLI=(ollama)

# The Spark's Ollama runs in a container (#2249, docker-compose.ollama.yml), reached on squadnet
# at http://ollama:11434 and published on the host's loopback. Its home (the model store and CUDA's
# compiled-kernel cache) is a host install's when one is there, kept with its owner, so nothing is
# downloaded or compiled again; otherwise one of the box's own. A host service still serving would hold port 11434 and load models beside it: disabled.
configure_ollama_container() {
    local home
    if [[ -d /usr/share/ollama/.ollama ]]; then
        home=/usr/share/ollama
    else
        home="${HOME}/.squadops/ollama"
        run_or_dry mkdir -p "${home}/.ollama/models"
    fi
    local uid gid
    uid="$(stat -c %u "${home}/.ollama" 2>/dev/null || id -u)"
    gid="$(stat -c %g "${home}/.ollama" 2>/dev/null || id -g)"
    set_env_value COMPOSE_FILE "docker-compose.yml:docker-compose.ollama.yml"
    set_env_value COMPOSE_PROFILES "gpu"
    set_env_value SQUADOPS__LLM__URL "http://ollama:11434"
    set_env_value SQUADOPS_OLLAMA_HOME "$home"
    set_env_value SQUADOPS_OLLAMA_UID "$uid"
    set_env_value SQUADOPS_OLLAMA_GID "$gid"
    success "Ollama runs in a container: store ${home}/.ollama, owner ${uid}:${gid}"
    if systemctl is-enabled ollama &>/dev/null || systemctl is-active ollama &>/dev/null; then
        info "Disabling the host Ollama service: the container serves port 11434 (#2249)"
        run_or_dry sudo systemctl disable --now ollama
    fi
    OLLAMA_CLI=(docker exec squadops-ollama ollama)
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
    run_or_dry "${OLLAMA_CLI[@]}" pull "$model"
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
    "${OLLAMA_CLI[@]}" list 2>/dev/null | awk 'NR>1 {print $1}' | grep -q "^${model}$"
}
