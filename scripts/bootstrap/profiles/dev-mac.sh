#!/usr/bin/env bash
# Bootstrap profile: dev-mac (macOS dev workstation) — SIP-0081.
# Sourced by bootstrap.sh — not executed directly.
# This script hardcodes install steps matching config/profiles/bootstrap/dev-mac.yaml (R1).

run_bootstrap() {
    # ── System deps (fail-fast per R7) ─────────────────────────────
    info "=== System Dependencies ==="

    ensure_homebrew

    brew_install_cask "docker" "true"  # confirm: true
    # docker-compose is bundled with Docker Desktop — no separate install
    brew_install_package "ollama"
    brew_install_package "git"

    # ── Python (fail-fast per R7) ──────────────────────────────────
    info "=== Python Setup ==="

    setup_pyenv "3.11"
    create_venv "3.11"
    install_python_deps "" "tests/requirements.txt"

    # ── Docker services ────────────────────────────────────────────
    info "=== Docker Services ==="

    if ! start_docker_services; then
        DOCKER_OK=0
        warn "Docker startup failed — skipping model pulls"
        return 0
    fi
    wait_for_services 60 || warn "Some services may not be ready"

    # ── Ollama models ──────────────────────────────────────────────
    info "=== Ollama Models ==="

    pull_model "qwen2.5:7b"
    pull_model "llama3.1:8b"
    pull_model "qwen2.5:3b-instruct"
}
