#!/usr/bin/env bash
# Homebrew install functions for bootstrap (SIP-0081).
# Sourced by bootstrap.sh — not executed directly.

# Install Homebrew if not present.
ensure_homebrew() {
    if check_command brew; then
        success "Homebrew already installed"
        return 0
    fi
    info "Installing Homebrew..."
    run_or_dry /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
}

# Install a brew package if not present.
brew_install_package() {
    local package="$1"
    if brew list --formula "$package" &>/dev/null; then
        success "${package} already installed (brew)"
        return 0
    fi
    info "Installing ${package} via brew..."
    run_or_dry brew install "$package"
}

# Install a brew cask if not present.
brew_install_cask() {
    local cask="$1"
    local confirm="${2:-false}"
    if brew list --cask "$cask" &>/dev/null; then
        success "${cask} already installed (brew cask)"
        return 0
    fi
    if [[ "$confirm" == "true" ]]; then
        if ! confirm_install "${cask} (cask)"; then
            warn "Skipping ${cask} (user declined)"
            return 0
        fi
    fi
    info "Installing ${cask} via brew cask..."
    run_or_dry brew install --cask "$cask"
}
