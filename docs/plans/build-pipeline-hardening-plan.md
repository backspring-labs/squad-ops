# Build Pipeline Hardening Plan

## Problem Statement

The `rebuild_and_deploy.sh` script has two recurring pain points:

1. **Slow dependency downloads** — pip resolves the full transitive dependency tree on every build because requirements files pin only direct dependencies. Any new PyPI release invalidates the cache and triggers a full re-download (~30s per service).

2. **Stale code in builds** — Docker layer caching sometimes serves old source code, particularly for the editable install layer. The health endpoint reported `0.9.13` after a rebuild that should have produced `0.9.14`. Discovered during SIP-0076 E2E testing.

Secondary issues:
- Console Svelte build failures abort the entire pipeline, preventing agent restarts
- Build context includes tests, docs, and SIPs unnecessarily
- No file-level change detection — always rebuilds everything

## Fix 1: Lock files for deterministic dependency resolution

### What

Use `pip-compile` (from `pip-tools`) to generate pinned lock files for all three dependency sets.

### Files

| Source | Lock file |
|--------|-----------|
| `requirements.txt` | `requirements.lock` |
| `requirements-api.txt` | `requirements-api.lock` |
| `requirements-agent.txt` | `requirements-agent.lock` |

### Steps

1. Install pip-tools: `pip install pip-tools`
2. Generate lock files:
   ```bash
   pip-compile requirements.txt -o requirements.lock
   pip-compile requirements-api.txt -o requirements-api.lock
   pip-compile requirements-agent.txt -o requirements-agent.lock
   ```
3. Update Dockerfiles to install from lock files:
   ```dockerfile
   # Before
   RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements-api.txt
   # After
   RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements-api.lock
   ```
4. Add a maintainer script `scripts/maintainer/update_deps.sh`:
   ```bash
   pip-compile requirements.txt -o requirements.lock
   pip-compile requirements-api.txt -o requirements-api.lock
   pip-compile requirements-agent.txt -o requirements-agent.lock
   ```
5. Commit lock files to the repo.

### Effect

- pip skips dependency resolution entirely (all versions pre-determined)
- Cache mount hits 100% of the time when lock file unchanged
- Dependency install drops from ~30s to <2s on cache hit
- Reproducible builds across machines and CI

### When to regenerate

- When adding or updating a direct dependency in `requirements*.txt`
- Periodic refresh for security patches (monthly or on advisory)
- Never automatically — lock updates should be intentional and reviewed

---

## Fix 2: Source hash cache busting

### What

Add a `SOURCE_HASH` build arg derived from the git SHA to ensure Docker never serves stale source code.

### Steps

1. Update both Dockerfiles (runtime-api and agents):
   ```dockerfile
   # Add before source copy layers
   ARG SOURCE_HASH=unknown
   COPY src/ ./src/
   COPY adapters/ ./adapters/
   RUN --mount=type=cache,target=/root/.cache/pip pip install -e .
   ```

2. Update `rebuild_and_deploy.sh` to pass the arg:
   ```bash
   SOURCE_HASH=$(git rev-parse --short HEAD)
   docker-compose build --build-arg SOURCE_HASH=$SOURCE_HASH runtime-api
   docker-compose build --build-arg SOURCE_HASH=$SOURCE_HASH <agent>
   ```

### Effect

- Any new commit produces a different `SOURCE_HASH`, invalidating source + editable install layers
- Dependencies layer (above the ARG) remains cached
- Eliminates the "rebuilt but still running old code" failure mode

---

## Fix 3: Tighten `.dockerignore`

### What

Exclude files that are never needed in containers from the build context.

### Add to `.dockerignore`

```
tests/
docs/
sips/
htmlcov/
_v0_legacy/
*.pyc
__pycache__/
.git/
.venv/
warm-boot/
*.md
!README.md
rebuild_deploy.log
```

### Effect

- Smaller build context = faster `COPY` and `docker-compose build` startup
- Fewer irrelevant file changes invalidating source copy layers

---

## Fix 4: Isolate console failures

### What

The rebuild script uses `set -euo pipefail` globally. A console Svelte build error exits the entire script, which can leave agent containers un-restarted with stale images.

### Steps

1. Wrap the console build in a subshell with error trapping:
   ```bash
   if ! docker-compose build squadops-console 2>&1; then
       echo "⚠️  Console build failed (non-blocking). Continuing with agents."
       CONSOLE_FAILED=1
   fi
   ```

2. At the end of the script, report the console failure:
   ```bash
   if [ "${CONSOLE_FAILED:-0}" = "1" ]; then
       echo "⚠️  Console build failed. Fix the Svelte error and rebuild console separately."
       exit 1  # Non-zero exit but agents are deployed
   fi
   ```

### Effect

- Runtime-api and agents always get rebuilt and restarted, even if console is broken
- Console failure is reported clearly at the end, not silently swallowed

---

## Fix 5: Skip unchanged services (optional)

### What

Before building each service, check if any relevant files changed since the last successful build. Skip the build if nothing changed.

### Approach

```bash
# Check if runtime-api needs rebuild
API_FILES="src/squadops/api/ src/squadops/ports/ src/squadops/cycles/ adapters/ requirements*.txt"
if git diff --quiet HEAD~1 -- $API_FILES 2>/dev/null; then
    echo "⏭️  Skipping runtime-api (no changes)"
else
    docker-compose build runtime-api
fi
```

### Caveat

This is a heuristic. When in doubt, `FORCE_REBUILD=1` should always be available. This optimization is lower priority than fixes 1-4.

---

## Implementation Order

| Priority | Fix | Impact | Effort |
|----------|-----|--------|--------|
| 1 | Lock files | Eliminates slow pip resolves | ~1 hour |
| 2 | Source hash cache busting | Eliminates stale code | ~30 min |
| 3 | `.dockerignore` tightening | Faster build context | ~15 min |
| 4 | Console failure isolation | Prevents incomplete deploys | ~30 min |
| 5 | Skip unchanged services | Faster no-op rebuilds | ~1 hour |

Fixes 1-4 can be done in a single PR. Fix 5 is optional and can follow later.
