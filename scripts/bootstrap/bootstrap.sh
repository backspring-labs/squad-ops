#!/usr/bin/env bash
# Bootstrap entry point for SquadOps (SIP-0081).
#
# Usage: ./scripts/bootstrap/bootstrap.sh <profile> [options]
#
# Profiles: dev-mac, dev-pc, local-spark
# Options:
#   --skip-docker   Skip Docker service startup
#   --skip-models   Skip Ollama model pulls
#   --dry-run       Print commands without executing
#   --yes / -y      Skip confirmation prompts
#
# NOTE: This script dispatches by profile NAME (R1 — no YAML parsing in shell).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
PROFILE=""
export DRY_RUN=0
export SKIP_DOCKER=0
export SKIP_MODELS=0
export SQUADOPS_BOOTSTRAP_YES="${SQUADOPS_BOOTSTRAP_YES:-0}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-docker) SKIP_DOCKER=1; shift ;;
        --skip-models) SKIP_MODELS=1; shift ;;
        --dry-run)     DRY_RUN=1; shift ;;
        --yes|-y)      SQUADOPS_BOOTSTRAP_YES=1; shift ;;
        -*)            echo "Unknown option: $1" >&2; exit 1 ;;
        *)
            if [[ -z "$PROFILE" ]]; then
                PROFILE="$1"
            else
                echo "Unexpected argument: $1" >&2; exit 1
            fi
            shift ;;
    esac
done

if [[ -z "$PROFILE" ]]; then
    echo "Usage: $0 <profile> [--skip-docker] [--skip-models] [--dry-run] [--yes]"
    echo "Profiles: dev-mac, dev-pc, local-spark"
    exit 1
fi

# ---------------------------------------------------------------------------
# Source library scripts
# ---------------------------------------------------------------------------
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
# shellcheck source=lib/python_setup.sh
source "${SCRIPT_DIR}/lib/python_setup.sh"
# shellcheck source=lib/brew_install.sh
source "${SCRIPT_DIR}/lib/brew_install.sh"
# shellcheck source=lib/apt_install.sh
source "${SCRIPT_DIR}/lib/apt_install.sh"
# shellcheck source=lib/docker_setup.sh
source "${SCRIPT_DIR}/lib/docker_setup.sh"
# shellcheck source=lib/ollama_setup.sh
source "${SCRIPT_DIR}/lib/ollama_setup.sh"

# ---------------------------------------------------------------------------
# Validate and source profile script
# ---------------------------------------------------------------------------
PROFILE_SCRIPT="${SCRIPT_DIR}/profiles/${PROFILE}.sh"

if [[ ! -f "$PROFILE_SCRIPT" ]]; then
    error "Unknown profile: ${PROFILE}"
    error "Expected profile script at: ${PROFILE_SCRIPT}"
    echo "Available profiles:"
    for f in "${SCRIPT_DIR}"/profiles/*.sh; do
        [[ -f "$f" ]] && echo "  $(basename "$f" .sh)"
    done
    exit 1
fi

# shellcheck source=/dev/null
source "$PROFILE_SCRIPT"

# ---------------------------------------------------------------------------
# Run bootstrap
# ---------------------------------------------------------------------------
cd "$PROJECT_ROOT"

info "Bootstrapping SquadOps with profile: ${PROFILE}"
[[ "$DRY_RUN" == "1" ]] && info "(dry-run mode — no changes will be made)"
echo ""

# Profile script must define run_bootstrap()
if ! type run_bootstrap &>/dev/null; then
    error "Profile script ${PROFILE_SCRIPT} does not define run_bootstrap()"
    exit 1
fi

DOCKER_OK=1
run_bootstrap || {
    # run_bootstrap uses fail-fast for system deps/python (R7)
    # but may set DOCKER_OK=0 on docker failure
    true
}

# ---------------------------------------------------------------------------
# Extensibility hook — source user-local customizations if present
# ---------------------------------------------------------------------------
if [[ -f "${HOME}/.squadops/bootstrap.local" ]]; then
    info "Sourcing ~/.squadops/bootstrap.local..."
    # shellcheck source=/dev/null
    source "${HOME}/.squadops/bootstrap.local"
fi

# ---------------------------------------------------------------------------
# Auto-run doctor if Python is available (R7)
# ---------------------------------------------------------------------------
echo ""
if [[ -f ".venv/bin/python" ]] && .venv/bin/python -c "import squadops" 2>/dev/null; then
    info "Running doctor validation..."
    .venv/bin/python -m squadops.cli.main doctor "$PROFILE" || true
else
    warn "Python environment not ready — run 'squadops doctor ${PROFILE}' manually after resolving the issue above."
fi

echo ""
success "Bootstrap complete for profile: ${PROFILE}"

echo ""
info "Next step: authenticate with Keycloak"
info "  .venv/bin/squadops login -u squadops-admin -p admin123"
