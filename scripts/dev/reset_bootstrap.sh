#!/usr/bin/env bash
# Reset the local SquadOps environment to a pre-bootstrap state.
#
# Removes project-level artifacts (env files, secrets, venv, docker volumes).
# Does NOT touch system packages, docker group, or pyenv (system-level, kept).
#
# Usage:
#   ./scripts/dev/reset_bootstrap.sh          # Standard reset
#   ./scripts/dev/reset_bootstrap.sh --deep   # Also remove Docker images

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "$PROJECT_ROOT"

DEEP=0
for arg in "$@"; do
    case "$arg" in
        --deep) DEEP=1 ;;
        *) echo "Unknown option: $arg" >&2; exit 1 ;;
    esac
done

info()    { echo "[INFO] $*"; }
warn()    { echo "[WARN] $*"; }

# --- Docker services ---
info "Stopping Docker Compose services and removing volumes..."
# Source .env.console before docker compose down (needed for interpolation)
if [[ -f ".env.console" ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env.console
    set +a
fi
if [[ -f ".env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi
docker compose down -v 2>/dev/null || warn "docker compose down failed (services may not be running)"

if [[ "$DEEP" == "1" ]]; then
    info "Removing Docker images built by this project..."
    docker compose config --images 2>/dev/null | xargs -r docker rmi -f 2>/dev/null || true
fi

# --- Env files and secrets ---
info "Removing .env, .env.console, and secrets/..."
rm -f .env .env.console
rm -rf secrets/

# --- Python venv ---
info "Removing .venv/..."
rm -rf .venv/

# --- User-local config ---
info "Removing ~/.squadops/..."
rm -rf "${HOME}/.squadops/"

info "Reset complete. Re-run bootstrap to set up again:"
info "  ./scripts/bootstrap/bootstrap.sh <profile>"
