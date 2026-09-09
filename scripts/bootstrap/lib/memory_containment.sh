#!/usr/bin/env bash
# Memory-pressure containment (#1178). Sourced by bootstrap.sh — not executed directly.
#
# The kernel's OOM killer does not fire during thrash, because swap is technically still
# available. So a memory runaway on this box does not produce one dead process and a live
# box; it produces a box that pages in and out indefinitely and answers nothing. On
# 2026-08-29 that was 95 minutes unreachable with ~800 MB free throughout, ended by a
# power cycle.
#
# Everything below is read from the profile's `memory_containment:` block, so the
# thresholds have one home that the bootstrap writes and `squadops doctor` verifies.

# Print `key=value` lines for the profile's memory_containment block, or nothing when the
# profile declares none.
_read_memory_containment() {
    local profile_yaml="$1"
    local reader
    reader="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/read_profile_memory.py"
    [[ -f ".venv/bin/python" ]] || { error ".venv not found — cannot read profile YAML"; return 1; }
    .venv/bin/python "$reader" "$profile_yaml"
}

configure_memory_containment() {
    local profile_yaml="$1"
    local daemon="" package="" free_memory="" free_swap="" swappiness=""

    local line
    while IFS='=' read -r key value; do
        case "$key" in
            daemon) daemon="$value" ;;
            package) package="$value" ;;
            free_memory_percent) free_memory="$value" ;;
            free_swap_percent) free_swap="$value" ;;
            swappiness) swappiness="$value" ;;
        esac
    done < <(_read_memory_containment "$profile_yaml") || return 1

    if [[ -z "$daemon" ]]; then
        info "profile declares no memory containment — skipping"
        return 0
    fi

    info "=== Memory Containment (#1178) ==="
    apt_install_package "$package" "$daemon"

    # The thresholds, written where the unit reads them. `-s $free_swap` is the setting
    # the incident forced: earlyoom kills only when available memory AND free swap are
    # both under threshold, and that livelock ran with 23% of swap free from the cliff to
    # the power cycle — so at the stock `-s 10` it would have watched the box die without
    # ever firing. At 100, swap cannot veto the kill.
    local args="-m ${free_memory} -s ${free_swap}"
    info "configuring ${daemon}: ${args}"
    run_or_dry sudo tee "/etc/default/${daemon}" >/dev/null <<EOF
# Managed by squadops bootstrap (#1178) — see config/profiles/bootstrap/*.yaml.
# -m: kill when available memory falls below this percent.
# -s: free-swap threshold. At 100 swap cannot veto the kill, which is what this box
#     needs: the 2026-08-29 livelock ran with 23% of swap still free throughout.
EARLYOOM_ARGS="${args}"
EOF

    run_or_dry sudo systemctl enable "$daemon"
    run_or_dry sudo systemctl restart "$daemon"

    if [[ -n "$swappiness" ]]; then
        # Mitigation, not containment: it lengthens the runway before thrash, it bounds
        # nothing. Persisted so a reboot does not quietly restore the 60 default.
        info "setting vm.swappiness=${swappiness}"
        run_or_dry sudo tee /etc/sysctl.d/60-squadops-swappiness.conf >/dev/null <<EOF
# Managed by squadops bootstrap (#1178): prefer reclaiming pages to swapping them.
vm.swappiness = ${swappiness}
EOF
        run_or_dry sudo sysctl -w "vm.swappiness=${swappiness}"
    fi

    success "memory containment configured — verify with: squadops doctor local-spark --check memory"
}
