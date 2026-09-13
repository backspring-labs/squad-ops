#!/usr/bin/env bash
# Reclaim Docker disk on a deploy box (#1465).
#
# On 2026-09-09 this box was at 65% of a 870G root with 1,795 dangling images and a 164.7GB
# build cache — five months of `rebuild_and_deploy.sh` accrual that nothing ever reclaimed.
# Each `all` deploy retags ~10 images and orphans the previous ten, so the growth is
# per-deploy and monotonic. A release line that deploys per tranche fills a disk on its own.
#
# WHAT THIS REMOVES, and nothing else:
#   * dangling images — untagged, unreferenced previous builds (`prune`, never `prune -a`);
#   * build cache above a cap, least-recently-used first.
#
# WHAT IT NEVER TOUCHES, deliberately:
#   * TAGGED images — `-a` would evict the agent images, runtime-api and the sandbox env,
#     forcing a cold rebuild of everything for no disk that this script cannot already free;
#   * VOLUMES — `squadops-postgres`'s data lives in one. `docker volume prune` on a deploy
#     box is how a database is lost, and it is not in this script at any flag;
#   * CONTAINERS, running or stopped.
#
# SAFE DURING A VERIFICATION SET, which is why it may run unattended. The measured host must
# not move between the checkpoint and the counted set. A dangling image is untagged and
# unreferenced by definition, and the sandbox runs ONE tagged image pinned by each stack's
# environment contract (`squadops/sandbox/environment.py:28`) rather than building per-run
# images — so there is nothing a cycle reaches that this can remove. The only observable
# effect is that the next image build is slower.
#
#   prune_docker.sh              prune to the cap
#   prune_docker.sh --dry-run    report what would go, remove nothing
#
# Env: CACHE_CAP (default 20GB) — the build cache ceiling, kept most-recently-used first.
set -euo pipefail

CACHE_CAP="${CACHE_CAP:-20GB}"
MODE="${1:-prune}"

say() { echo "[prune_docker] $*" >&2; }
die() { say "ERROR: $*"; exit 1; }

command -v docker >/dev/null || die "docker not on PATH"
docker info >/dev/null 2>&1 || die "cannot reach the docker daemon"

disk() { df -h / | awk 'NR==2 {print $3" used, "$4" free ("$5")"}'; }

dangling=$(docker images -f "dangling=true" -q | wc -l)
cache_before=$(docker system df --format '{{.Type}}\t{{.Size}}' 2>/dev/null | awk -F'\t' '$1=="Build Cache"{print $2}')
say "before: $(disk); dangling images: $dangling; build cache: ${cache_before:-unknown}"

if [ "$MODE" = "--dry-run" ]; then
  say "DRY RUN — nothing removed"
  # `--dry-run` is not a flag docker's prune accepts, so report the inputs rather than
  # inventing a preview that could disagree with what a real run would do.
  say "would run: docker image prune -f"
  say "would run: docker builder prune -f --max-used-space $CACHE_CAP"
  exit 0
fi

# Dangling images first: they hold references INTO the build cache, so pruning them before
# the cache is what makes the cache's space actually reclaimable. Run the other order and
# the image prune reports "Total reclaimed space: 0B" while the bytes stay pinned — measured
# on this box, and the reason this ordering is a comment rather than an accident.
docker image prune -f >/dev/null
docker builder prune -f --max-used-space "$CACHE_CAP" >/dev/null

say "after:  $(disk); dangling images: $(docker images -f 'dangling=true' -q | wc -l)"
