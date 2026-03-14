#!/usr/bin/env bash
# Bootstrap profile: dev-pc (WSL2/Ubuntu dev workstation) — SIP-0081.
# Sourced by bootstrap.sh — not executed directly.
# This script hardcodes install steps matching config/profiles/bootstrap/dev-pc.yaml (R1).

run_bootstrap() {
    # ── Sudo access (fail fast if not available) ───────────────────
    ensure_sudo

    # ── WSL2 check ─────────────────────────────────────────────────
    if grep -qi microsoft /proc/version 2>/dev/null; then
        success "Running inside WSL2"
    else
        warn "Not running inside WSL2 — this profile is designed for WSL2/Ubuntu"
    fi

    # ── System deps (fail-fast per R7) ─────────────────────────────
    info "=== System Dependencies ==="

    apt_install_package "docker.io" "docker"
    apt_install_package "docker-compose-plugin" "docker"
    apt_install_package "git"
    apt_install_package "curl"
    install_ollama

    # ── Python (fail-fast per R7) ──────────────────────────────────
    info "=== Python Setup ==="

    setup_pyenv "3.11"
    create_venv "3.11"
    install_python_deps "" "tests/requirements.txt"

    # ── Docker services ────────────────────────────────────────────
    info "=== Docker Services ==="

    ensure_docker_group
    enable_docker_on_boot
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

    # ── Ollama models ──────────────────────────────────────────────
    info "=== Ollama Models ==="

    pull_models_from_profile "config/profiles/bootstrap/dev-pc.yaml"
}
