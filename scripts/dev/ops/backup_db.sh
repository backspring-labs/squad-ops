#!/usr/bin/env bash
# Back up the deployment Postgres, and prove the backup restores (#1181).
#
# On 2026-08-30 `pytest tests/integration` emptied cycle_gate_decisions (291 rows) because
# the suite defaulted to the deployment database. There were no backups of any kind —
# archive_mode off, no dumps on disk — so three rows were reconstructed from a terminal
# transcript and ~288 were simply gone. This exists so that is recoverable next time.
#
# The database holds the cycle registry, run history, gate decisions and verification
# summaries: the evidence base every release record and A/B artifact is written from, and
# none of it is reproducible once the deploy it came from moves on.
#
#   backup_db.sh                 take a dump, prune old ones
#   backup_db.sh --verify        take a dump, then RESTORE it into a scratch database and
#                                compare row counts — a backup nobody has restored is a
#                                hypothesis, not a backup
#   backup_db.sh --verify-only   verify the newest existing dump without taking a new one
#
# Env: BACKUP_DIR (default ~/squadops-backups), KEEP_DAILY (7), CONTAINER (squadops-postgres)
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-$HOME/squadops-backups}"
KEEP_DAILY="${KEEP_DAILY:-7}"
CONTAINER="${CONTAINER:-squadops-postgres}"
DB="${DB:-squadops}"
DB_USER="${DB_USER:-squadops}"
VERIFY_DB="squadops_restore_check"

MODE="${1:-dump}"
# Logs go to stderr: take_dump echoes the dump PATH on stdout for command substitution,
# so a log line on stdout would be captured as part of the filename.
say() { echo "[$(date -Is)] $*" >&2; }
die() { echo "ERROR: $*" >&2; exit 1; }

docker ps --filter "name=^${CONTAINER}$" --filter status=running -q | grep -q . \
  || die "$CONTAINER is not running"
mkdir -p "$BACKUP_DIR"

take_dump() {
  local stamp out
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out="$BACKUP_DIR/${DB}-${stamp}.dump"
  say "dumping $DB -> $out"
  # -Fc (custom format) so pg_restore can be selective; --no-owner keeps it restorable
  # into a scratch database owned by someone else, which is what --verify needs.
  docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB" -Fc --no-owner > "$out"
  [ -s "$out" ] || { rm -f "$out"; die "dump came out empty — refusing to keep it"; }
  say "wrote $(du -h "$out" | cut -f1)"
  echo "$out"
}

prune() {
  local n
  n=$(ls -1t "$BACKUP_DIR"/${DB}-*.dump 2>/dev/null | tail -n +$((KEEP_DAILY + 1)) | wc -l)
  if [ "$n" -gt 0 ]; then
    ls -1t "$BACKUP_DIR"/${DB}-*.dump | tail -n +$((KEEP_DAILY + 1)) | xargs -r rm -f
    say "pruned $n dump(s), keeping $KEEP_DAILY"
  fi
}

# Row counts for the tables whose loss actually costs evidence. Compared across the
# restore so a dump that restores STRUCTURE but no rows fails instead of passing.
COUNT_SQL="select 'cycle_registry='||(select count(*) from cycle_registry)
        ||' cycle_runs='||(select count(*) from cycle_runs)
        ||' gate_decisions='||(select count(*) from cycle_gate_decisions);"

verify() {
  local dump="$1"
  [ -f "$dump" ] || die "no dump to verify"
  say "verifying $dump by restoring into $VERIFY_DB"
  local live restored
  live=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB" -t -A -c "$COUNT_SQL" | tr -d ' ')

  docker exec "$CONTAINER" psql -U "$DB_USER" -d postgres -q \
    -c "drop database if exists $VERIFY_DB;" -c "create database $VERIFY_DB;"
  # pg_restore's exit code is checked, not discarded. An earlier revision had `|| true`
  # here on the guess that it warns about extensions it cannot own; measured against this
  # database a clean restore exits 0 with EMPTY stderr, and a corrupt dump exits 1 — so the
  # code is a reliable signal and swallowing it made the whole verification decorative.
  # A truncated dump was reported "verified" because its errors were discarded and the
  # cycle tables happened to fit in the surviving bytes.
  local err rc=0
  err=$(docker exec -i "$CONTAINER" pg_restore -U "$DB_USER" -d "$VERIFY_DB" --no-owner < "$dump" 2>&1) || rc=$?
  if [ "$rc" -ne 0 ] || grep -q "error:" <<<"$err"; then
    docker exec "$CONTAINER" psql -U "$DB_USER" -d postgres -q -c "drop database if exists $VERIFY_DB;" || true
    echo "$err" | head -5 >&2
    die "pg_restore failed (exit $rc) — this dump is NOT a usable backup"
  fi
  restored=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$VERIFY_DB" -t -A -c "$COUNT_SQL" | tr -d ' ')
  docker exec "$CONTAINER" psql -U "$DB_USER" -d postgres -q -c "drop database if exists $VERIFY_DB;"

  say "live     : $live"
  say "restored : $restored"
  [ "$live" = "$restored" ] || die "RESTORE MISMATCH — the dump does not reproduce the database"
  say "restore verified: the dump reproduces the live row counts"
}

case "$MODE" in
  dump)        d=$(take_dump); prune ;;
  --verify)    d=$(take_dump); prune; verify "$d" ;;
  --verify-only)
               d=$(ls -1t "$BACKUP_DIR"/${DB}-*.dump 2>/dev/null | head -1) || true
               [ -n "${d:-}" ] || die "no dumps in $BACKUP_DIR"
               verify "$d" ;;
  *)           die "usage: $0 [--verify|--verify-only]" ;;
esac
say "done"
