---
title: Profile-Driven Bootstrap
status: proposed
author: JL (Maintainer)
created_at: '2026-03-06'
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

---

## Non-Goals

- Replacing `pip install -e .` (Python packaging stays as-is).
- Managing cloud infrastructure (AWS/GCP/Azure provisioning is out of scope).
- Auto-detecting the correct profile (user chooses explicitly).
- Installing CUDA drivers on Spark (NVIDIA ships those pre-installed; we validate, not install).

---

## Design

### D1: Bootstrap Profile Schema

Each bootstrap profile is a YAML file in `config/profiles/bootstrap/`. It declares the system-level contract for that environment.

```yaml
# config/profiles/bootstrap/dev-mac.yaml
name: dev-mac
description: "macOS development workstation"
platform: darwin

python:
  version: "3.11"
  manager: pyenv          # pyenv | system

system_deps:
  - name: docker
    check: "docker --version"
    install: brew
    package: "docker"       # Docker Desktop cask
    cask: true
    required: true

  - name: docker-compose
    check: "docker compose version"
    install: bundled        # Ships with Docker Desktop
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
  - rabbitmq
  - postgres
  - redis
  - prefect-server
  - runtime-api
  - squadops-keycloak

ollama_models:
  - name: "qwen2.5:7b"
    required: true
  - name: "llama3.1:8b"
    required: true
  - name: "qwen2.5:3b-instruct"
    required: true

deployment_profile: local    # Links to existing config/profiles/local.yaml
squad_profile: full-squad    # Links to config/squad-profiles.yaml
```

### D2: Three First-Class Profiles

| Profile | Platform | Python Manager | Package Manager | Models | Docker Services |
|---------|----------|---------------|-----------------|--------|-----------------|
| `dev-mac` | darwin | pyenv | Homebrew | 7b/8b/3b (small) | Full dev stack |
| `dev-pc` | linux (WSL2) | pyenv | apt | 7b/8b/3b (small) | Full dev stack |
| `local-spark` | linux | system (3.11+) | apt | 72b/70b/7b (large) | Full stack + GPU Ollama |

Key differences for `local-spark`:
- `nvidia-container-toolkit` as a system dep (validate, don't install — NVIDIA pre-installs drivers)
- Large models (`qwen2.5:72b`, `llama3:70b`) instead of small ones
- Ollama runs with `--gpus all` flag
- `deployment_profile: staging` (links to the existing DGX Spark auth profile)

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
2. **System deps** — install missing tools via platform package manager
3. **Python environment** — create venv, `pip install -e .`, install test deps
4. **Docker services** — `docker compose up -d` for the profile's service set
5. **Ollama models** — `ollama pull` each required model (skip if present)
6. **Preflight** — run `squadops doctor` automatically at the end

Flags:
- `--skip-docker` — skip Docker service startup (useful for CI or partial setups)
- `--skip-models` — skip Ollama model pulls (useful on slow networks)
- `--dry-run` — show what would be done without executing
- `--yes` / `-y` — skip confirmation prompts

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

  Docker Services
    ✓ rabbitmq ........... healthy (localhost:5672)
    ✓ postgres ........... healthy (localhost:5432)
    ✓ redis .............. healthy (localhost:6379)
    ✓ prefect-server ..... healthy (localhost:4200)
    ✓ runtime-api ........ healthy (localhost:8001, v0.9.18)
    ✓ keycloak ........... healthy (localhost:8180)

  Ollama Models
    ✓ qwen2.5:7b ........ available
    ✓ llama3.1:8b ....... available
    ✓ qwen2.5:3b-instruct available

  Auth
    ✓ token cached, expires in 47m

  Result: 15/15 checks passed ✓
```

Flags:
- `--json` — machine-readable output
- `--check <name>` — run a single check category (python, tools, docker, models, auth)
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
brew install --cask docker

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
nvidia-smi                          # GPU driver
nvidia-container-toolkit --version  # Container GPU passthrough

# System deps via apt
sudo apt-get install -y docker.io docker-compose-plugin git curl

# Ollama with GPU support
curl -fsSL https://ollama.com/install.sh | sh
# Verify GPU detection
ollama run --gpu qwen2.5:7b "test" 2>&1 | head -1

# Large models (Spark has 128GB unified memory)
ollama pull qwen2.5:72b
ollama pull llama3:70b
ollama pull qwen2.5:7b
ollama pull llama3.1:8b

# Link to staging deployment profile (edge proxy, MFA for admin)
export SQUADOPS_PROFILE=staging
```

### D6: Doctor Check Registry

Each check is a named, self-contained validation function. The doctor command runs all checks for the active profile and reports results.

```python
# src/squadops/cli/commands/doctor.py

@dataclass(frozen=True)
class CheckResult:
    name: str
    category: str          # python | tools | docker | models | auth
    passed: bool
    message: str           # "python 3.11.14 via pyenv"
    detail: str | None     # Extra info on failure

CheckFn = Callable[[BootstrapProfile], CheckResult]

# Registry — checks are tagged by which profiles need them
CHECKS: dict[str, CheckFn] = {
    "python_version": check_python_version,
    "venv_exists": check_venv_exists,
    "docker_available": check_docker_available,
    "docker_compose": check_docker_compose,
    "ollama_available": check_ollama_available,
    "git_available": check_git_available,
    "nvidia_smi": check_nvidia_smi,            # local-spark only
    "nvidia_container": check_nvidia_container, # local-spark only
    "docker_service_*": check_docker_service,   # Per declared service
    "ollama_model_*": check_ollama_model,       # Per declared model
    "auth_token": check_auth_token,
    "runtime_api_health": check_runtime_api,
}
```

### D7: Relationship to Existing Profile Layers

This SIP adds a new profile layer that **complements** the existing ones. No existing profiles are modified.

```
Existing (unchanged):
  config/profiles/local.yaml          ← Auth config (Keycloak)
  config/profiles/staging.yaml        ← Auth config (DGX Spark)
  config/squad-profiles.yaml          ← Agent roster + models
  src/squadops/contracts/cycle_request_profiles/  ← Workload behavior

New (this SIP):
  config/profiles/bootstrap/dev-mac.yaml      ← System deps + setup
  config/profiles/bootstrap/dev-pc.yaml
  config/profiles/bootstrap/local-spark.yaml
```

Each bootstrap profile references the deployment profile it pairs with (`deployment_profile: local` or `deployment_profile: staging`), creating a clear link without coupling.

### D8: Documentation

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
| `dev-mac`     | macOS laptop     | 7b/8b/3b      | Homebrew, Docker Desktop |
| `dev-pc`      | Windows WSL2     | 7b/8b/3b      | apt, Docker Engine       |
| `local-spark` | DGX Spark        | 72b/70b/7b/8b | GPU Ollama, large models |

## Troubleshooting

    squadops doctor dev-mac --json    # Machine-readable diagnostics
    squadops doctor dev-mac --check docker  # Check one category
```

---

## Implementation Phases

### Phase 1: Bootstrap Profile Schema + Doctor Command
- Define `BootstrapProfile` model (frozen dataclass, loaded from YAML)
- Write 3 profile YAML files (`dev-mac`, `dev-pc`, `local-spark`)
- Implement `squadops doctor <profile>` with check registry
- Implement check functions for: python, tools, docker services, ollama models, auth
- Tests: profile loading, check pass/fail, output formatting

### Phase 2: Bootstrap Shell Scripts
- Create `scripts/bootstrap/bootstrap.sh` entry point
- Create `scripts/bootstrap/lib/` helper scripts (python, brew, apt, docker, ollama)
- Create profile-specific scripts in `scripts/bootstrap/profiles/`
- Idempotency: every script checks before acting, safe to re-run
- Tests: dry-run mode, mock-based script validation

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
| D2 | `bootstrap.sh` works before `pip install` | A fresh machine has no Python env. The shell script must be self-sufficient for the initial setup. |
| D3 | Doctor checks are a Python registry, not shell scripts | Python gives us structured output (JSON), testability, and richer formatting. Shell scripts do the installing; Python does the validating. |
| D4 | Bootstrap scripts are idempotent | Users re-run after failures, upgrades, or adding new profiles. Every step checks before acting. |
| D5 | DGX Spark validates but does not install NVIDIA drivers/toolkit | NVIDIA pre-installs GPU drivers on DGX hardware. Installing/upgrading GPU drivers remotely is dangerous. We verify, not provision. |
| D6 | Models are pulled by the bootstrap script, not pre-baked into Docker images | Model files are large (4-40GB). Pulling on first run is standard Ollama practice and allows model updates without rebuilding images. |
| D7 | Each bootstrap profile references a deployment profile by name | Creates a link (`dev-mac → local`, `local-spark → staging`) without coupling the schemas. The bootstrap profile says "after setup, use this deployment profile." |
| D8 | Single `docs/GETTING_STARTED.md` for all profiles | One place to maintain, profile-specific sections within. Avoids doc sprawl across multiple getting-started guides. |

---

## Risks

| Risk | Mitigation |
|------|------------|
| Homebrew/apt install commands break across OS versions | Pin to stable package names, test on current LTS versions, document minimum OS versions |
| Docker Desktop licensing changes (macOS/Windows) | Document as a requirement, don't auto-install without consent (`--yes` flag) |
| Large model pulls take hours on slow networks | `--skip-models` flag, progress bars, resume-capable `ollama pull` |
| WSL2 Docker networking differences | Profile-specific Docker Compose overrides if needed |
| Script maintenance burden | Keep scripts thin — delegate to package managers, don't reimplement installers |

---

## Success Criteria

1. A contributor with a fresh macOS laptop can go from `git clone` to `squadops doctor` all-green in under 15 minutes (excluding model download time).
2. A maintainer can set up a DGX Spark from clone to running cycles in under 30 minutes.
3. `squadops doctor` catches 100% of the "missing dependency" issues that currently require trial-and-error discovery.
4. Bootstrap scripts are idempotent — running twice produces the same result with no errors.
5. No tribal knowledge required — `docs/GETTING_STARTED.md` is the complete guide.
