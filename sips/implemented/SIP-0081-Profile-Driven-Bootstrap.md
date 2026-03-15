---
title: Profile-Driven Bootstrap
status: implemented
author: JL (Maintainer)
created_at: '2026-03-06'
sip_number: 81
updated_at: '2026-03-07T08:40:05.509725Z'
---
# SIP: Profile-Driven Bootstrap

**Status:** Proposed
**Owner:** JL (Maintainer)
**Created:** 2026-03-06
**Idea:** `docs/ideas/IDEA-profile-driven-bootstrap.md`

---

## Purpose

Define a profile-driven bootstrap system that takes a fresh machine from clone to running SquadOps in a single command. Each bootstrap profile declares its system-level dependencies, provides installation scripts, and includes a doctor/preflight validator — so a new contributor (or a maintainer setting up a DGX Spark) never discovers a missing dependency by trial and error.

---

## Objectives

1. A new user runs **one command** after `git clone` to fully prepare their machine.
2. A **doctor command** validates readiness before any cycle is attempted.
3. Bootstrap profiles extend the existing `config/profiles/` mechanism with system-level dependency declarations.
4. Three first-class profiles ship in Phase 1: `dev-mac`, `dev-pc`, `local-spark`.
5. Scripts are idempotent — safe to re-run after partial failures or upgrades.
6. v1.0 bootstrap runs on the **target machine itself**. Remote orchestration (e.g., bootstrapping a Spark over SSH from a laptop) is out of scope.

---

## Non-Goals

- Replacing `pip install -e .` (Python packaging stays as-is).
- Managing cloud infrastructure (AWS/GCP/Azure provisioning is out of scope).
- Auto-detecting the correct profile (user chooses explicitly).
- Installing CUDA drivers on Spark (NVIDIA ships those pre-installed; we validate, not install).
- Remote bootstrap orchestration (SSH-based setup of remote machines).

---

## Design Principles

Three rules govern the relationship between profiles, scripts, and doctor:

1. **Profile YAML defines what is required.** It is the authoritative source of environment expectations. Scripts must not hardcode requirements that are absent from the profile.
2. **Bootstrap scripts define how to install or start it.** Scripts are the execution layer — they read the profile contract and act on it.
3. **Doctor defines whether the declared contract is satisfied right now.** It validates the profile's requirements against the actual machine state.

If a requirement is not in the profile YAML, it does not exist. If a script installs something not declared in the profile, that is a bug.

---

## Design

### D1: Bootstrap Profile Schema

Each bootstrap profile is a YAML file in `config/profiles/bootstrap/`. It declares the system-level contract for that environment.

All profiles require a `schema_version` field. In v1, unknown fields are rejected and missing required fields fail load immediately. Future schema changes must bump the version explicitly.

```yaml
# config/profiles/bootstrap/dev-mac.yaml
schema_version: 1
name: dev-mac
description: "macOS development workstation"

platform:
  os: darwin
  min_version: "14.0"           # macOS Sonoma+

python:
  version: "3.11"
  manager: pyenv                # pyenv | system
  extras: []                    # pip extras groups (empty = base only in v1)
  test_deps: "tests/requirements.txt"

system_deps:
  - name: docker
    check: "docker --version"
    install: brew               # brew | apt | bundled | script | manual | none
    package: "docker"           # Required for brew/apt
    cask: true                  # Only valid with install: brew
    required: true
    confirm: true               # Heavyweight install — require confirmation unless --yes

  - name: docker-compose
    check: "docker compose version"
    install: bundled            # Ships with Docker Desktop
    required: true

  - name: ollama
    check: "ollama --version"
    install: brew
    package: "ollama"
    required: true

  - name: git
    check: "git --version"
    install: brew
    package: "git"
    required: true

docker_services:
  - name: rabbitmq
    healthcheck: tcp
    port: 5672
    timeout_seconds: 30

  - name: postgres
    healthcheck: tcp
    port: 5432
    timeout_seconds: 30

  - name: redis
    healthcheck: tcp
    port: 6379
    timeout_seconds: 15

  - name: prefect-server
    healthcheck: http
    endpoint: "http://localhost:4200/api/health"
    timeout_seconds: 60

  - name: runtime-api
    healthcheck: http
    endpoint: "http://localhost:8001/health"
    timeout_seconds: 60

  - name: squadops-keycloak
    healthcheck: http
    endpoint: "http://localhost:8180/health/ready"
    timeout_seconds: 90

ollama_models:
  - name: "qwen2.5:7b"
    required: true
  - name: "llama3.1:8b"
    required: true
  - name: "qwen2.5:3b-instruct"
    required: true

deployment_profile: dev         # Links to existing config/profiles/dev.yaml
squad_profile: full-squad       # Links to config/squad-profiles.yaml
```

#### Schema Validation Rules (v1)

| Rule | Behavior |
|------|----------|
| `schema_version` missing or != 1 | Fail load with clear error |
| Unknown top-level fields | Rejected — fail load |
| Missing `name`, `platform`, `python` | Fail load |
| `install` not in `{brew, apt, bundled, script, manual, none}` | Rejected |
| `cask: true` with `install` != `brew` | Rejected |
| `package` missing when `install` is `brew` or `apt` | Rejected |
| `check` missing when `install` != `none` | Rejected |
| `healthcheck` not in `{http, tcp, docker_health}` | Rejected |
| `endpoint` missing when `healthcheck` is `http` | Rejected |
| `port` missing when `healthcheck` is `tcp` | Rejected |

### D2: Three First-Class Profiles

| Profile | Platform | Python Manager | Package Manager | Models | Docker Services |
|---------|----------|---------------|-----------------|--------|-----------------|
| `dev-mac` | darwin (14.0+) | pyenv | Homebrew | 7b/8b/3b (small) | Full dev stack |
| `dev-pc` | linux/WSL2 (Ubuntu 22.04+) | pyenv | apt | 7b/8b/3b (small) | Full dev stack |
| `local-spark` | linux (Ubuntu 24.04+) | system (3.11+) | apt | 72b/70b/7b (large) | Full stack + GPU Ollama |

Key differences for `local-spark`:
- `nvidia-smi` and `nvidia-container-toolkit` as system deps with `install: none` (validate only — NVIDIA pre-installs drivers on DGX hardware)
- Large models (`qwen2.5:72b`, `llama3:70b`) in addition to small ones
- Ollama runs with `--gpus all` flag
- `deployment_profile: local` (links to the existing DGX Spark auth profile)

#### Flexible Model Requirements

Models can be declared as exact requirements or as alternatives:

```yaml
ollama_models:
  # Exact requirement — this specific model must be present
  - name: "qwen2.5:7b"
    required: true

  # Alternative — at least one of these must be present
  - required_one_of:
      - "qwen2.5:72b"
      - "qwen2.5:32b"
    tier: large               # Informational label for doctor output
```

This prevents profile rewrites when a specific model tag changes, while keeping the contract precise when an exact model is needed.

### D3: CLI Entry Points

Two new command groups on the existing Typer CLI:

```
squadops bootstrap [PROFILE]     # Prepare machine for the selected profile
squadops doctor [PROFILE]        # Validate environment readiness
```

#### `squadops bootstrap <profile>`

Orchestrates the full setup sequence:

```
$ squadops bootstrap dev-mac

  SquadOps Bootstrap — dev-mac (macOS development workstation)
  ════════════════════════════════════════════════════════════

  [1/6] Python .................. pyenv 3.11.14 ✓ (already installed)
  [2/6] System deps ............. docker ✓  ollama ✓  git ✓
  [3/6] Python environment ...... .venv created, pip install -e . ✓
  [4/6] Docker services ......... rabbitmq ✓  postgres ✓  redis ✓  ...
  [5/6] Ollama models ........... qwen2.5:7b ✓  llama3.1:8b ↓ pulling...
  [6/6] Preflight checks ........ 12/12 passed ✓

  Ready! Run: squadops login
```

Steps in order:
1. **Python** — ensure correct version via configured manager
2. **System deps** — install missing tools via platform package manager; deps with `confirm: true` prompt for confirmation unless `--yes` is passed
3. **Python environment** — create venv, `pip install -e .`; if `test_deps` is set, also install from that file; if `extras` is non-empty, install those extras groups
4. **Docker services** — `docker compose up -d` for the profile's service set
5. **Ollama models** — `ollama pull` each required model (skip if present)
6. **Preflight** — run `squadops doctor` automatically at the end

Flags:
- `--skip-docker` — skip Docker service startup (useful for CI or partial setups)
- `--skip-models` — skip Ollama model pulls (useful on slow networks)
- `--dry-run` — show what would be done without executing
- `--yes` / `-y` — skip confirmation prompts (required for heavyweight installs like Docker Desktop)

#### Docker Desktop vs Docker Engine

- `dev-mac` expects **Docker Desktop** via Homebrew cask. Docker Desktop has licensing requirements; bootstrap prompts for confirmation before installing.
- `dev-pc` expects **Docker Engine** + compose plugin via `apt`. No licensing concerns.
- Heavyweight installs that may affect licensing or require user login always require confirmation unless `--yes` is passed.

#### `squadops doctor <profile>`

Validates that every declared requirement is satisfied:

```
$ squadops doctor dev-mac

  SquadOps Doctor — dev-mac
  ═════════════════════════

  Python
    ✓ python 3.11.14 via pyenv
    ✓ .venv exists with squadops installed

  System Tools
    ✓ docker 27.5.1
    ✓ docker compose v2.32.4
    ✓ ollama 0.6.2
    ✓ git 2.48.1

  Platform
    ✓ macOS 15.3 (requires 14.0+)

  Docker Services
    ✓ rabbitmq ........... healthy (tcp:5672)
    ✓ postgres ........... healthy (tcp:5432)
    ✓ redis .............. healthy (tcp:6379)
    ✓ prefect-server ..... healthy (http://localhost:4200/api/health)
    ✓ runtime-api ........ healthy (http://localhost:8001/health, v0.9.18)
    ✓ keycloak ........... healthy (http://localhost:8180/health/ready)

  Ollama Models
    ✓ qwen2.5:7b ........ available
    ✓ llama3.1:8b ....... available
    ✓ qwen2.5:3b-instruct available

  Auth
    ✓ token cached, expires in 47m

  Result: 16/16 checks passed ✓
```

When a check **fails**, doctor outputs:
1. **What** failed — the check name and category
2. **Why** it failed — the observed vs expected state
3. **How to fix** — the exact command or step bootstrap would use to remediate
4. **Auto-fixable?** — whether `squadops bootstrap` can fix it automatically or manual action is needed

```
  System Tools
    ✗ ollama ............. not found
      Fix: brew install ollama
      Auto-fixable: yes (run squadops bootstrap dev-mac)
    ✗ docker ............. not found
      Fix: brew install --cask docker
      Auto-fixable: yes (requires confirmation)
```

Flags:
- `--json` — machine-readable output
- `--check <name>` — run a single check category (python, platform, tools, docker, models, auth)
- Exit code 0 = all pass, 1 = any failure

### D4: Bootstrap Script Machinery

The CLI commands are thin orchestrators. The actual work lives in shell scripts for platform-specific reliability:

```
scripts/
  bootstrap/
    bootstrap.sh              # Entry point (can run before pip install)
    lib/
      common.sh               # Shared helpers (colors, logging, checks)
      python_setup.sh          # pyenv / system python detection + venv
      brew_install.sh          # macOS Homebrew installer
      apt_install.sh           # Debian/Ubuntu apt installer
      docker_setup.sh          # Docker service startup + health wait
      ollama_setup.sh          # Ollama install + model pull
    profiles/
      dev-mac.sh               # Profile-specific overrides/hooks
      dev-pc.sh
      local-spark.sh
```

**Critical design choice**: `scripts/bootstrap/bootstrap.sh` is callable **before** `pip install` — it's a standalone shell script that can prepare the machine from scratch. The Typer CLI command (`squadops bootstrap`) calls the same scripts but provides richer output. This means the "one command" experience works even before Python is set up:

```bash
# Fresh machine — no Python, no venv, nothing
git clone https://github.com/backspring-labs/squad-ops.git
cd squad-ops
./scripts/bootstrap/bootstrap.sh dev-mac
```

After bootstrap, the CLI version is also available:
```bash
squadops bootstrap dev-mac    # Same result, richer output
```

### D5: Profile-Specific Behavior

#### `dev-mac`
```bash
# Python via pyenv + Homebrew
brew install pyenv
pyenv install 3.11.14
pyenv local 3.11.14

# System deps via Homebrew
brew install ollama git
brew install --cask docker    # Prompts for confirmation (licensing)

# Models (small, suitable for laptop)
ollama pull qwen2.5:7b
ollama pull llama3.1:8b
ollama pull qwen2.5:3b-instruct
```

#### `dev-pc` (WSL2)
```bash
# Verify WSL2 (not WSL1)
wsl.exe --status | grep "Default Version: 2"

# Python via pyenv
curl https://pyenv.run | bash
pyenv install 3.11.14

# System deps via apt
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin git curl

# Ollama (Linux installer)
curl -fsSL https://ollama.com/install.sh | sh

# Same small models as dev-mac
ollama pull qwen2.5:7b
ollama pull llama3.1:8b
ollama pull qwen2.5:3b-instruct
```

#### `local-spark` (DGX Spark)
```bash
# Python — use system Python 3.11+ (pre-installed on Ubuntu 24.04)
python3 --version  # validate >= 3.11

# Validate NVIDIA stack (pre-installed, don't attempt to install)
nvidia-smi                          # GPU driver presence
nvidia-container-toolkit --version  # Container GPU passthrough

# System deps via apt
sudo apt-get install -y docker.io docker-compose-plugin git curl

# Ollama with GPU support
curl -fsSL https://ollama.com/install.sh | sh

# Large models (Spark has 128GB unified memory)
ollama pull qwen2.5:72b
ollama pull llama3:70b
ollama pull qwen2.5:7b
ollama pull llama3.1:8b

# Link to local deployment profile (edge proxy, MFA for admin)
export SQUADOPS_PROFILE=local
```

### D6: DGX Spark GPU Validation

GPU checks use a layered validation strategy rather than ad hoc CLI output parsing:

| Layer | Check | Method | Result Type |
|-------|-------|--------|-------------|
| 1. Driver presence | `nvidia-smi` exits 0 | Exit code | Definitive |
| 2. Container runtime | `nvidia-container-toolkit --version` exits 0 | Exit code | Definitive |
| 3. Ollama GPU access | `ollama ps` shows GPU layers after a brief model load | Output parse | Heuristic |

When a GPU check result is heuristic (layer 3), doctor marks it explicitly in output:

```
  GPU
    ✓ nvidia-smi ......... driver 570.86.15
    ✓ nvidia-container ... toolkit 1.17.3
    ~ ollama GPU access .. detected (heuristic — verify with ollama ps)
```

The `~` marker distinguishes heuristic results from definitive pass/fail, preventing false confidence.

### D7: Doctor Check Registry

Each check is a named, self-contained validation function. The doctor command runs all checks declared in the active profile and reports results.

```python
# src/squadops/cli/commands/doctor.py

@dataclass(frozen=True)
class CheckResult:
    name: str
    category: str              # python | platform | tools | docker | models | gpu | auth
    passed: bool
    message: str               # "python 3.11.14 via pyenv"
    detail: str | None         # Extra info on failure
    fix_command: str | None    # "brew install ollama"
    auto_fixable: bool         # Can bootstrap fix this automatically?
    heuristic: bool = False    # True if result is best-effort, not definitive

CheckFn = Callable[[BootstrapProfile], CheckResult]
```

Docker service checks are driven entirely by the profile's `docker_services` declarations — the check function reads `healthcheck`, `endpoint`/`port`, and `timeout_seconds` from the profile YAML. No service-specific logic is hardcoded in doctor.

### D8: Bootstrap State File

Bootstrap writes a local state file for idempotency tracking and debugging:

```
.squadops/bootstrap/dev-mac.json
```

Contents:
```json
{
  "profile": "dev-mac",
  "schema_version": 1,
  "last_run": "2026-03-06T14:32:18Z",
  "steps_completed": ["python", "system_deps", "python_env", "docker", "models", "doctor"],
  "detected_versions": {
    "python": "3.11.14",
    "docker": "27.5.1",
    "ollama": "0.6.2"
  },
  "doctor_summary": {
    "total": 16,
    "passed": 16,
    "failed": 0,
    "heuristic": 0
  }
}
```

This file is:
- Written after each bootstrap run (overwritten, not appended)
- Read by `squadops doctor` to show "last bootstrap" context
- Useful for debugging partial failures ("which steps completed?")
- `.squadops/` is gitignored
- Future use: detect when a profile schema change requires re-bootstrap

### D9: Relationship to Existing Profile Layers

This SIP adds a new profile layer that **complements** the existing ones. No existing profiles are modified.

```
Existing (unchanged):
  config/profiles/dev.yaml            ← Auth config (Keycloak, laptop dev)
  config/profiles/local.yaml          ← Auth config (DGX Spark)
  config/squad-profiles.yaml          ← Agent roster + models
  src/squadops/contracts/cycle_request_profiles/  ← Workload behavior

New (this SIP):
  config/profiles/bootstrap/dev-mac.yaml      ← System deps + setup
  config/profiles/bootstrap/dev-pc.yaml
  config/profiles/bootstrap/local-spark.yaml
```

Each bootstrap profile references the deployment profile it pairs with (`deployment_profile: dev` or `deployment_profile: local`), creating a clear link without coupling.

### D10: Documentation

A single `docs/GETTING_STARTED.md` replaces ad-hoc setup instructions:

```markdown
# Getting Started with SquadOps

## Quick Start (macOS)

    git clone https://github.com/backspring-labs/squad-ops.git
    cd squad-ops
    ./scripts/bootstrap/bootstrap.sh dev-mac

That's it. The script installs Python, Docker, Ollama, pulls models,
starts services, and validates everything.

## Quick Start (Windows / WSL2)

    git clone https://github.com/backspring-labs/squad-ops.git
    cd squad-ops
    ./scripts/bootstrap/bootstrap.sh dev-pc

## Quick Start (DGX Spark)

    git clone https://github.com/backspring-labs/squad-ops.git
    cd squad-ops
    ./scripts/bootstrap/bootstrap.sh local-spark

## Verify Your Environment

    squadops doctor dev-mac     # or dev-pc, local-spark

## What's Next?

    squadops login
    squadops cycles create my-project --profile selftest

## Profiles

| Profile       | Target           | Models        | Notes                    |
|---------------|------------------|---------------|--------------------------|
| `dev-mac`     | macOS 14+ laptop | 7b/8b/3b      | Homebrew, Docker Desktop |
| `dev-pc`      | WSL2 Ubuntu 22+  | 7b/8b/3b      | apt, Docker Engine       |
| `local-spark` | DGX Spark 24.04+ | 72b/70b/7b/8b | GPU Ollama, large models |

## Troubleshooting

    squadops doctor dev-mac --json    # Machine-readable diagnostics
    squadops doctor dev-mac --check docker  # Check one category
```

---

## Implementation Phases

### Phase 1: Bootstrap Profile Schema + Doctor Command
- Define `BootstrapProfile` model (frozen dataclass, loaded from YAML)
- Implement strict schema validation (v1 rules: reject unknowns, require mandatories, validate enums)
- Write 3 profile YAML files (`dev-mac`, `dev-pc`, `local-spark`)
- Implement `squadops doctor <profile>` with check registry
- Implement check functions for: python, platform, tools, docker services (declarative from profile), ollama models, GPU (Spark only), auth
- Doctor failure output includes: what failed, why, fix command, auto-fixable flag
- Tests: profile loading, schema validation (accept/reject), check pass/fail, output formatting, failure guidance

### Phase 2: Bootstrap Shell Scripts + State File
- Create `scripts/bootstrap/bootstrap.sh` entry point
- Create `scripts/bootstrap/lib/` helper scripts (python, brew, apt, docker, ollama)
- Create profile-specific scripts in `scripts/bootstrap/profiles/`
- Implement bootstrap state file (`.squadops/bootstrap/<profile>.json`)
- Idempotency: every script checks before acting, safe to re-run
- Confirmation prompts for heavyweight installs (`confirm: true` deps)
- Tests: dry-run mode, state file write/read, idempotency assertions

### Phase 3: CLI Bootstrap Command + Integration
- Implement `squadops bootstrap <profile>` Typer command
- Wire CLI to shell scripts with rich progress output
- Auto-run doctor at end of bootstrap
- Add `--skip-docker`, `--skip-models`, `--dry-run`, `--yes` flags
- Tests: CLI argument parsing, flag behavior, exit codes

### Phase 4: Documentation + Polish
- Write `docs/GETTING_STARTED.md`
- Update `README.md` quick-start section
- Update `CLAUDE.md` with bootstrap commands
- Add profile listing to `squadops status` output
- End-to-end validation on each target platform

---

## Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Bootstrap profiles are separate YAML files in `config/profiles/bootstrap/`, not extensions to existing deployment profiles | Separation of concerns — auth config and system deps are different layers. Avoids bloating existing profiles. |
| D2 | `schema_version: 1` is required; unknown fields rejected; missing required fields fail load | Prevents "mystery YAML" drift. Makes the profile layer safe to evolve with explicit version bumps. |
| D3 | Profile YAML is the authoritative source of requirements — scripts must not hardcode requirements absent from the profile | Keeps the design profile-first. If it's not in the YAML, it doesn't exist. |
| D4 | `install` method validated against closed enum: `brew`, `apt`, `bundled`, `script`, `manual`, `none` | Prevents typo-driven silent failures. Makes doctor/bootstrap output deterministic. |
| D5 | `bootstrap.sh` works before `pip install` | A fresh machine has no Python env. The shell script must be self-sufficient for the initial setup. |
| D6 | Doctor checks are a Python registry, not shell scripts | Python gives us structured output (JSON), testability, and richer formatting. Shell scripts do the installing; Python does the validating. |
| D7 | Docker service health checks are declarative in the profile (`healthcheck`, `endpoint`/`port`, `timeout_seconds`) | Prevents doctor from accumulating service-specific hardcoded logic. Keeps validation profile-driven. |
| D8 | Bootstrap scripts are idempotent, with a state file at `.squadops/bootstrap/<profile>.json` | Users re-run after failures. State file aids debugging and enables future "needs re-bootstrap" detection. |
| D9 | DGX Spark validates but does not install NVIDIA drivers/toolkit | NVIDIA pre-installs GPU drivers on DGX hardware. Installing/upgrading GPU drivers remotely is dangerous. We verify, not provision. |
| D10 | GPU validation uses layered checks with heuristic results marked explicitly | Prevents false confidence. Makes Spark readiness easier to troubleshoot. |
| D11 | Models support `required_one_of` alternative syntax alongside exact requirements | Makes profiles resilient to model tag changes without rewriting scripts. |
| D12 | Models are pulled by the bootstrap script, not pre-baked into Docker images | Model files are large (4-40GB). Pulling on first run is standard Ollama practice and allows model updates without rebuilding images. |
| D13 | Each bootstrap profile references a deployment profile by name | Creates a link (`dev-mac → dev`, `local-spark → local`) without coupling the schemas. |
| D14 | `dev-mac` expects Docker Desktop (confirmation required); `dev-pc` expects Docker Engine + compose plugin | Makes licensing and operator intent explicit. Heavyweight installs always prompt unless `--yes`. |
| D15 | Doctor failure output always includes: what failed, why, fix command, auto-fixable flag | Makes doctor valuable even for users who don't want bootstrap to mutate their machine. |
| D16 | v1.0 bootstrap runs on the target machine only — no remote orchestration | Keeps the first version grounded. Remote deployment tooling is a future concern. |
| D17 | Single `docs/GETTING_STARTED.md` for all profiles | One place to maintain, profile-specific sections within. Avoids doc sprawl. |
| D18 | Python extras and test deps are declared in the profile (`extras`, `test_deps` fields) | Avoids bootstrap becoming a hidden place where dependency policy drifts. Explicit is better than implicit. |
| D19 | Platform compatibility declared with `os`, `min_version`, `distro`, `distro_min_version` | Lets doctor fail fast with a clear explanation instead of allowing obscure downstream install failures. |

---

## Risks

| Risk | Mitigation |
|------|------------|
| Homebrew/apt install commands break across OS versions | Pin to stable package names, test on current LTS versions, enforce `platform.min_version` in doctor |
| Docker Desktop licensing changes (macOS/Windows) | `confirm: true` on Docker dep — always prompt before installing. Document licensing in GETTING_STARTED. |
| Large model pulls take hours on slow networks | `--skip-models` flag, progress bars, resume-capable `ollama pull` |
| WSL2 Docker networking differences | Profile-specific Docker Compose overrides if needed |
| Script maintenance burden | Keep scripts thin — delegate to package managers, don't reimplement installers |
| Profile YAML schema drift | `schema_version` + strict validation. Unknown fields rejected. |
| GPU check brittleness | Layered validation (exit codes first, output parsing last). Heuristic results marked explicitly. |
| Bootstrap state file stale after manual changes | State file is informational, not authoritative. Doctor always re-checks live state. |

---

## Success Criteria

1. A contributor with a fresh macOS laptop can go from `git clone` to `squadops doctor` all-green in under 15 minutes (excluding model download time).
2. A maintainer can set up a DGX Spark from clone to running cycles in under 30 minutes.
3. `squadops doctor` catches 100% of the "missing dependency" issues that currently require trial-and-error discovery.
4. Doctor failure output always includes the fix command — no check fails without guidance.
5. Bootstrap scripts are idempotent — running twice produces the same result with no errors.
6. No tribal knowledge required — `docs/GETTING_STARTED.md` is the complete guide.
7. Profile schema validation rejects malformed YAML at load time, not at runtime.
