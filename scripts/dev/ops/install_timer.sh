#!/usr/bin/env bash
# Install one SquadOps host timer from its committed template (#1465). Needs sudo — it
# writes host systemd units.
#
# Generalized out of install_backup_timer.sh when the Docker-reclaim timer needed the same
# render-guard-install dance. The substitution guard below is the whole reason this is
# shared rather than copied: a second copy is a second place for it to rot.
#
#   install_timer.sh <name>            install and start
#   install_timer.sh <name> --status   show timer state and last runs
#   install_timer.sh <name> --remove   stop and remove
#
# <name> is the unit basename in infra/systemd/, e.g. squadops-backup, squadops-docker-prune.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
UNIT_DIR=/etc/systemd/system

NAME="${1:-}"
[ -n "$NAME" ] || { echo "usage: install_timer.sh <name> [--status|--remove]" >&2; exit 1; }
[ -f "$REPO_ROOT/infra/systemd/${NAME}.timer" ] || {
  echo "ERROR: no template infra/systemd/${NAME}.timer — available:" >&2
  ls -1 "$REPO_ROOT/infra/systemd/"*.timer 2>/dev/null | xargs -rn1 basename >&2; exit 1; }

case "${2:-install}" in
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
