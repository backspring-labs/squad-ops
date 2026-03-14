#!/usr/bin/env bash
# APT install functions for bootstrap (SIP-0081).
# Sourced by bootstrap.sh — not executed directly.

_APT_UPDATED=0

# Run apt update once per session.
apt_update_once() {
    if [[ "$_APT_UPDATED" == "0" ]]; then
        info "Updating apt package list..."
        run_or_dry sudo apt-get update -qq
        _APT_UPDATED=1
    fi
}

# Install an apt package if not present.
# Usage: apt_install_package <package> [command_to_check]
# If command_to_check is given, skip install when that command exists
# (handles cases like docker-ce satisfying a docker.io request).
apt_install_package() {
    local package="$1"
    local check_cmd="${2:-}"
    if [[ -n "$check_cmd" ]] && check_command "$check_cmd"; then
        success "${package} already satisfied (${check_cmd} found)"
        return 0
    fi
    if dpkg -l "$package" 2>/dev/null | grep -q "^ii"; then
        success "${package} already installed (apt)"
        return 0
    fi
    apt_update_once
    info "Installing ${package} via apt..."
    run_or_dry sudo apt-get install -y -qq "$package"
}
