#!/usr/bin/env bash
# Bootstrap profile: local-spark (DGX Spark with GPU) — SIP-0081.
# Sourced by bootstrap.sh — not executed directly.
# This script hardcodes install steps matching config/profiles/bootstrap/local-spark.yaml (R1).

run_bootstrap() {
    # ── Sudo access (fail fast if not available) ───────────────────
    ensure_sudo

    # ── GPU validation (hard checks only per R10) ──────────────────
    info "=== GPU Validation ==="

    if check_command nvidia-smi; then
        success "nvidia-smi found"
        run_or_dry nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
    else
        error "nvidia-smi not found — NVIDIA drivers required for local-spark profile"
        exit 1
    fi

    if check_command nvidia-container-toolkit; then
        success "nvidia-container-toolkit found"
    else
        error "nvidia-container-toolkit not found — required for GPU containers"
        exit 1
    fi

    # ── System deps (fail-fast per R7) ─────────────────────────────
    info "=== System Dependencies ==="

    apt_install_package "docker.io" "docker"
    apt_install_package "docker-compose-plugin" "docker"
    apt_install_package "git"
    apt_install_package "curl"
    install_ollama
    configure_ollama_host_binding

    # ── Python (R5: system Python, R4: still uses .venv) ───────────
    info "=== Python Setup ==="

    setup_system_python "3.11"
    create_venv "3.11"
    install_python_deps "" "tests/requirements.txt"

    # ── Docker services ────────────────────────────────────────────
    info "=== Docker Services ==="

    ensure_docker_group
    enable_docker_on_boot
    DEPLOYMENT_PROFILE=local
    ensure_env_file

    local docker_rc=0
    start_docker_services || docker_rc=$?
    if [[ "$docker_rc" == "1" ]]; then
        DOCKER_OK=0
        warn "Docker startup failed — skipping model pulls"
        return 0
    elif [[ "$docker_rc" == "2" ]]; then
        return 0  # --skip-docker
    fi
    wait_for_services 60 || warn "Some services may not be ready"

    # ── Ollama models (large models for DGX Spark) ─────────────────
    info "=== Ollama Models ==="

    pull_models_from_profile "config/profiles/bootstrap/local-spark.yaml"
}
