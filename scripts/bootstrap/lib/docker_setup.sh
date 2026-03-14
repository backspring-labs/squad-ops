#!/usr/bin/env bash
# Docker setup functions for bootstrap (SIP-0081).
# Sourced by bootstrap.sh — not executed directly.

# Ensure .env and .env.console exist for Docker Compose.
# Copies .env from .env.example (which contains static dev passwords).
# Generates .env.console from console lock file if missing.
ensure_env_file() {
    local env_file=".env"
    local env_example=".env.example"

    if [[ -f "$env_file" ]]; then
        success ".env file already exists"
    elif [[ ! -f "$env_example" ]]; then
        warn "No .env.example found — cannot generate .env"
        return 1
    else
        info "Creating .env from .env.example..."
        run_or_dry cp "$env_example" "$env_file"
        [[ "${DRY_RUN:-0}" != "1" ]] && success ".env created"
    fi

    # Create Docker secret files from .env passwords
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        info "[dry-run] create secrets/db_password.txt and secrets/rabbitmq_password.txt"
    elif [[ -f "$env_file" ]]; then
        mkdir -p secrets
        if [[ ! -f "secrets/db_password.txt" ]]; then
            grep '^POSTGRES_PASSWORD=' "$env_file" | cut -d= -f2- > secrets/db_password.txt
            success "Created secrets/db_password.txt"
        fi
        if [[ ! -f "secrets/rabbitmq_password.txt" ]]; then
            grep '^RABBITMQ_PASSWORD=' "$env_file" | cut -d= -f2- > secrets/rabbitmq_password.txt
            success "Created secrets/rabbitmq_password.txt"
        fi
    fi

    # Generate .env.console for squadops-console build args
    local gen_console="scripts/dev/gen_console_env.sh"
    if [[ -f "$gen_console" ]]; then
        if [[ -f ".env.console" ]]; then
            success ".env.console already exists"
        else
            info "Generating .env.console from console lock file..."
            run_or_dry bash "$gen_console"
        fi
    fi
}

# Enable Docker daemon on boot and ensure it is running (systemd only).
enable_docker_on_boot() {
    if [[ "${SKIP_DOCKER:-0}" == "1" ]]; then
        return 0
    fi
    if ! check_command systemctl; then
        return 0
    fi
    if systemctl is-enabled docker &>/dev/null; then
        success "Docker already enabled on boot"
    elif confirm_install "Docker auto-start on boot (systemctl enable docker)"; then
        run_or_dry sudo systemctl enable docker
        success "Docker enabled on boot"
    else
        warn "Skipping Docker on boot — services won't auto-start after reboot"
    fi

    # Ensure the daemon is actually running
    if ! systemctl is-active docker &>/dev/null; then
        info "Starting Docker daemon..."
        run_or_dry sudo systemctl start docker
    fi
}

# Ensure current user is in the docker group (Linux only).
ensure_docker_group() {
    if [[ "${SKIP_DOCKER:-0}" == "1" ]]; then
        return 0
    fi
    # macOS Docker Desktop doesn't use group permissions
    if [[ "$(uname -s)" != "Linux" ]]; then
        return 0
    fi
    if id -nG "$USER" | grep -qw docker; then
        success "User $USER is in docker group"
        return 0
    fi
    info "Adding $USER to docker group..."
    run_or_dry sudo usermod -aG docker "$USER"
    if [[ "${DRY_RUN:-0}" != "1" ]]; then
        success "User $USER added to docker group"
        echo ""
        warn "You were just added to the 'docker' group."
        warn "Log out and back in (or run 'newgrp docker'), then re-run bootstrap."
        exit 0
    fi
}

# Start Docker Compose services.
# Returns 0 on success, 1 on failure, 2 when skipped via --skip-docker.
start_docker_services() {
    if [[ "${SKIP_DOCKER:-0}" == "1" ]]; then
        warn "Skipping Docker services (--skip-docker)"
        return 2
    fi

    if ! check_command docker; then
        error "Docker not found — install Docker first"
        return 1
    fi

    # Export .env.console vars so Compose can interpolate build args
    if [[ -f ".env.console" ]]; then
        set -a
        # shellcheck disable=SC1091
        source .env.console
        set +a
    fi

    info "Starting Docker Compose services..."
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        info "[dry-run] docker compose up -d"
    else
        docker compose up -d
    fi
}

# Wait for services to become healthy.
wait_for_services() {
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        info "[dry-run] wait_for_services ${1:-60}"
        return 0
    fi

    local timeout="${1:-60}"
    info "Waiting up to ${timeout}s for services to become healthy..."

    local elapsed=0
    local interval=5
    while [[ $elapsed -lt $timeout ]]; do
        # Check if all services are running
        local running
        running=$(docker compose ps --services --filter "status=running" 2>/dev/null | wc -l)
        local total
        total=$(docker compose ps --services 2>/dev/null | wc -l)

        if [[ "$running" == "$total" ]] && [[ "$total" -gt 0 ]]; then
            success "All ${total} services running"
            return 0
        fi

        sleep "$interval"
        elapsed=$((elapsed + interval))
    done

    warn "Timeout waiting for services (${elapsed}s elapsed)"
    return 1
}
