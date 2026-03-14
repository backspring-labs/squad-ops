#!/usr/bin/env bash
# Common utilities for bootstrap scripts (SIP-0081).
# Sourced by bootstrap.sh — not executed directly.

set -euo pipefail

# ---------------------------------------------------------------------------
# Colors (disabled if not a terminal)
# ---------------------------------------------------------------------------
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    RED='' GREEN='' YELLOW='' BLUE='' NC=''
fi

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

# Check if a command exists on PATH.
check_command() {
    command -v "$1" &>/dev/null
}

# Verify the current user can run sudo.
# Call this early in any profile that uses apt/systemctl.
# Skipped in dry-run mode since no privileged commands will execute.
ensure_sudo() {
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        return 0
    fi
    if [[ "$(id -u)" == "0" ]]; then
        return 0  # already root
    fi
    if sudo -n true 2>/dev/null; then
        return 0  # passwordless sudo works
    fi
    # Need a password — check we have a terminal to prompt
    if [[ ! -t 0 ]]; then
        error "Bootstrap needs sudo but no terminal is available for a password prompt."
        error "Re-run in an interactive terminal, or configure passwordless sudo."
        exit 1
    fi
    info "Sudo access required — you may be prompted for your password."
    if ! sudo -v; then
        error "Could not obtain sudo access."
        exit 1
    fi
}

# Prompt user for confirmation before installing.
# Skipped if SQUADOPS_BOOTSTRAP_YES=1 or --yes flag was set.
confirm_install() {
    local package="$1"
    if [[ "${SQUADOPS_BOOTSTRAP_YES:-0}" == "1" ]]; then
        return 0
    fi
    read -rp "Install ${package}? [y/N] " answer
    [[ "$answer" =~ ^[Yy] ]]
}

# Run a command, or print it if DRY_RUN is set.
run_or_dry() {
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        info "[dry-run] $*"
    else
        "$@"
    fi
}
