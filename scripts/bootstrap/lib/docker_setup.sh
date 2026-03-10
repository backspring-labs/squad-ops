#!/usr/bin/env bash
# Docker setup functions for bootstrap (SIP-0081).
# Sourced by bootstrap.sh — not executed directly.

# Prompt to enable Docker daemon on boot (systemd only).
enable_docker_on_boot() {
    if [[ "${SKIP_DOCKER:-0}" == "1" ]]; then
        return 0
    fi
    if ! check_command systemctl; then
        return 0
    fi
    if systemctl is-enabled docker &>/dev/null; then
        success "Docker already enabled on boot"
        return 0
    fi
    if confirm_install "Docker auto-start on boot (systemctl enable docker)"; then
        run_or_dry sudo systemctl enable docker
        success "Docker enabled on boot"
    else
        warn "Skipping Docker on boot — services won't auto-start after reboot"
    fi
}

# Start Docker Compose services.
start_docker_services() {
    if [[ "${SKIP_DOCKER:-0}" == "1" ]]; then
        warn "Skipping Docker services (--skip-docker)"
        return 0
    fi

    if ! check_command docker; then
        error "Docker not found — install Docker first"
        return 1
    fi

    info "Starting Docker Compose services..."
    run_or_dry docker-compose up -d
}

# Wait for services to become healthy.
wait_for_services() {
    local timeout="${1:-60}"
    info "Waiting up to ${timeout}s for services to become healthy..."

    local elapsed=0
    local interval=5
    while [[ $elapsed -lt $timeout ]]; do
        # Check if all services are running
        local not_running
        not_running=$(docker-compose ps --services --filter "status=running" 2>/dev/null | wc -l)
        local total
        total=$(docker-compose ps --services 2>/dev/null | wc -l)

        if [[ "$not_running" == "$total" ]] && [[ "$total" -gt 0 ]]; then
            success "All ${total} services running"
            return 0
        fi

        sleep "$interval"
        elapsed=$((elapsed + interval))
    done

    warn "Timeout waiting for services (${elapsed}s elapsed)"
    return 1
}
