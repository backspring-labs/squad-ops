#!/usr/bin/env bash
# Install the nightly backup timer (#1181). Needs sudo — it writes host systemd units.
#
#   scripts/dev/ops/install_backup_timer.sh            install and start
#   scripts/dev/ops/install_backup_timer.sh --status   show timer state and last run
#   scripts/dev/ops/install_backup_timer.sh --remove   stop and remove
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
UNIT_DIR=/etc/systemd/system
NAME=squadops-backup

case "${1:-install}" in
  --status)
    systemctl status "${NAME}.timer" --no-pager 2>&1 | head -12
    echo "--- last runs ---"; journalctl -u "${NAME}.service" -n 15 --no-pager 2>&1 | tail -15
    exit 0 ;;
  --remove)
    sudo systemctl disable --now "${NAME}.timer" 2>/dev/null || true
    sudo rm -f "$UNIT_DIR/${NAME}.service" "$UNIT_DIR/${NAME}.timer"
    sudo systemctl daemon-reload
    echo "removed"; exit 0 ;;
esac

# The committed .service is a TEMPLATE: substitute this machine's user and checkout path.
# Rendering to a temp file first means a failed substitution never reaches /etc.
rendered=$(mktemp)
sed -e "s|__USER__|$USER|g" -e "s|__REPO_ROOT__|$REPO_ROOT|g" \
    "$REPO_ROOT/infra/systemd/${NAME}.service" > "$rendered"
grep -q "__" "$rendered" && { echo "ERROR: unsubstituted placeholder remains:" >&2
  grep "__" "$rendered" >&2; rm -f "$rendered"; exit 1; }
sudo cp "$rendered" "$UNIT_DIR/${NAME}.service"; rm -f "$rendered"
sudo cp "$REPO_ROOT/infra/systemd/${NAME}.timer" "$UNIT_DIR/"
sudo systemctl daemon-reload
sudo systemctl enable --now "${NAME}.timer"
echo "installed. next run:"
systemctl list-timers "${NAME}.timer" --no-pager 2>&1 | head -3
