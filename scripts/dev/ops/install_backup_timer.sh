#!/usr/bin/env bash
# Install the nightly backup timer (#1181). Needs sudo — it writes host systemd units.
#
# The install logic is shared with every other host timer (#1465): this keeps the path the
# 1.7.5 plan and the release procedure name, and delegates. Do not re-inline it here.
#
#   scripts/dev/ops/install_backup_timer.sh            install and start
#   scripts/dev/ops/install_backup_timer.sh --status   show timer state and last run
#   scripts/dev/ops/install_backup_timer.sh --remove   stop and remove
set -euo pipefail
exec "$(dirname "${BASH_SOURCE[0]}")/install_timer.sh" squadops-backup "$@"
