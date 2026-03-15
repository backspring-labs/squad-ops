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

    # Set SQUADOPS_PROFILE and SQUADOPS_REALM from bootstrap profile's deployment_profile.
    # SQUADOPS_PROFILE drives the config loader; SQUADOPS_REALM selects the Keycloak realm.
    if [[ -n "${DEPLOYMENT_PROFILE:-}" ]] && [[ -f "$env_file" ]] && [[ "${DRY_RUN:-0}" != "1" ]]; then
        local realm="squadops-${DEPLOYMENT_PROFILE}"

        if grep -q '^# *SQUADOPS_PROFILE=' "$env_file"; then
            sed -i "s|^# *SQUADOPS_PROFILE=.*|SQUADOPS_PROFILE=${DEPLOYMENT_PROFILE}|" "$env_file"
            success "Set SQUADOPS_PROFILE=${DEPLOYMENT_PROFILE} in .env"
        elif grep -q '^SQUADOPS_PROFILE=' "$env_file"; then
            sed -i "s|^SQUADOPS_PROFILE=.*|SQUADOPS_PROFILE=${DEPLOYMENT_PROFILE}|" "$env_file"
            success "Updated SQUADOPS_PROFILE=${DEPLOYMENT_PROFILE} in .env"
        else
            echo "SQUADOPS_PROFILE=${DEPLOYMENT_PROFILE}" >> "$env_file"
            success "Added SQUADOPS_PROFILE=${DEPLOYMENT_PROFILE} to .env"
        fi

        if grep -q '^SQUADOPS_REALM=' "$env_file"; then
            sed -i "s|^SQUADOPS_REALM=.*|SQUADOPS_REALM=${realm}|" "$env_file"
            success "Updated SQUADOPS_REALM=${realm} in .env"
        else
            echo "SQUADOPS_REALM=${realm}" >> "$env_file"
            success "Added SQUADOPS_REALM=${realm} to .env"
        fi

        local host="${SQUADOPS_HOST:-localhost}"
        if grep -q '^SQUADOPS_HOST=' "$env_file"; then
            sed -i "s|^SQUADOPS_HOST=.*|SQUADOPS_HOST=${host}|" "$env_file"
        elif grep -q '^# *SQUADOPS_HOST=' "$env_file"; then
            sed -i "s|^# *SQUADOPS_HOST=.*|SQUADOPS_HOST=${host}|" "$env_file"
        else
            echo "SQUADOPS_HOST=${host}" >> "$env_file"
        fi
        success "Set SQUADOPS_HOST=${host} in .env"
    fi

    # Create Docker secret files from .env passwords
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        info "[dry-run] create secrets/{db_password,rabbitmq_password,keycloak_admin_password}.txt"
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
        if [[ ! -f "secrets/keycloak_admin_password.txt" ]]; then
            # Keycloak admin password — matches KEYCLOAK_ADMIN_PASSWORD in docker-compose
            echo -n "admin123" > secrets/keycloak_admin_password.txt
            success "Created secrets/keycloak_admin_password.txt"
        fi
        if [[ ! -f "secrets/keycloak_db_dsn.txt" ]]; then
            # Keycloak DB DSN — matches KC_DB_URL credentials in docker-compose
            echo -n "postgresql://keycloak:keycloak@postgres:5432/keycloak" > secrets/keycloak_db_dsn.txt
            success "Created secrets/keycloak_db_dsn.txt"
        fi
    fi

    # Generate .env.console and append to .env so docker compose auto-loads them.
    local gen_console="scripts/dev/gen_console_env.sh"
    if [[ -f "$gen_console" ]]; then
        if [[ -f ".env.console" ]]; then
            success ".env.console already exists"
        else
            info "Generating .env.console from console lock file..."
            run_or_dry bash "$gen_console"
        fi
        # Append console vars to .env if not already present
        if [[ "${DRY_RUN:-0}" != "1" ]] && [[ -f ".env.console" ]] && [[ -f "$env_file" ]]; then
            if ! grep -q 'CONTINUUM_GIT_URL' "$env_file" 2>/dev/null; then
                echo "" >> "$env_file"
                cat .env.console >> "$env_file"
                success "Console vars appended to .env"
            fi
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
    # Check if the *running process* has docker group (not just the user database).
    # `id -nG` queries /etc/group; `groups` shows the active session's groups.
    if groups | grep -qw docker; then
        success "User $USER has active docker group"
        return 0
    fi
    # User may be in /etc/group but session doesn't have the credential yet.
    if id -nG "$USER" | grep -qw docker; then
        info "User $USER is in docker group but session lacks credential — re-executing with sg"
        exec sg docker -c "'${SQUADOPS_BOOTSTRAP_SCRIPT}' ${SQUADOPS_BOOTSTRAP_ARGS}"
    fi
    info "Adding $USER to docker group..."
    run_or_dry sudo usermod -aG docker "$USER"
    if [[ "${DRY_RUN:-0}" != "1" ]]; then
        success "User $USER added to docker group — re-executing bootstrap with new group"
        exec sg docker -c "'${SQUADOPS_BOOTSTRAP_SCRIPT}' ${SQUADOPS_BOOTSTRAP_ARGS}"
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
