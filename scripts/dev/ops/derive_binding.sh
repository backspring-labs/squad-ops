# Derive a host-side connectable "address port" pair from a
# `docker compose port <svc> <port>` binding (#327 Step 4b).
#
# Sourceable helper — kept out of rebuild_and_deploy.sh so the parsing is
# unit-testable (tests/unit/scripts/test_derive_binding.py) without running
# a deploy.
#
# Rules:
# - `docker compose port` may emit MULTIPLE bindings (IPv4 + IPv6 lines on
#   dual-stack hosts); the first line wins.
# - A wildcard bind (0.0.0.0 / [::] / ::) maps to loopback — a networking
#   fact, not config: the caller publishes the port on the machine it runs
#   on. An interface-pinned bind is used as-is.
# - Empty/garbage input yields nothing (empty output, rc 1) so callers fail
#   loudly instead of defaulting.
#
# Usage: derive_binding "$(docker compose port langfuse 3000 2>/dev/null)"
# Output: "<address> <port>" on stdout; rc 1 when underivable.

derive_binding() {
    local binding
    binding=$(printf '%s\n' "$1" | head -n 1)
    local addr="${binding%:*}"
    local port="${binding##*:}"
    if [ -z "$binding" ] || [ -z "$port" ] || [ "$addr" = "$binding" ]; then
        return 1
    fi
    case "$port" in
        *[!0-9]*) return 1 ;;
    esac
    case "$addr" in
        0.0.0.0 | "[::]" | ::) addr="127.0.0.1" ;;
    esac
    printf '%s %s\n' "$addr" "$port"
}
