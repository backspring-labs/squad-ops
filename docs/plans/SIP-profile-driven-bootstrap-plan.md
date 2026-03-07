# Plan: SIP Profile-Driven Bootstrap Implementation

## Context

This SIP introduces a profile-driven bootstrap system so a fresh machine can go from `git clone` to fully operational SquadOps in one command. Three first-class profiles: `dev-mac` (macOS), `dev-pc` (WSL2/Ubuntu), `local-spark` (DGX Spark with GPU).

The system has three layers:
1. **Profile YAML** — authoritative source of what the environment requires
2. **Bootstrap scripts** — how to install/start requirements (shell, works pre-Python)
3. **Doctor command** — Python-based validation of whether the contract is satisfied

**Branch:** `feature/sip-profile-driven-bootstrap` (off main)
**SIP:** `sips/proposed/SIP-Profile-Driven-Bootstrap.md`

### Existing infrastructure to build on
- Config loader (`src/squadops/config/loader.py`) — layered YAML merge, `_select_profile()` from env/CLI
- Deployment profiles (`config/profiles/{local,staging,lab,prod}.yaml`) — auth-only today
- CLI (`src/squadops/cli/main.py`) — Typer app with command group registration
- `scripts/dev/setup_local_env.sh` — pyenv + venv only (to be superseded)
- `scripts/dev/ops/rebuild_and_deploy.sh` — has `check_ollama()`, `check_database()` functions

---

## Phase 1: Bootstrap Profile Schema + Profile YAML Files

### Commit 1a: BootstrapProfile model and schema validation

**New file:**

| File | Contents |
|------|----------|
| `src/squadops/bootstrap/profile.py` | `BootstrapProfile` frozen dataclass, nested models, schema validation |

**Models:**

```python
@dataclass(frozen=True)
class PlatformSpec:
    os: str                              # "darwin" | "linux"
    min_version: str | None = None       # "14.0" for macOS Sonoma+
    distro: str | None = None            # "ubuntu" for Linux
    distro_min_version: str | None = None  # "22.04"

@dataclass(frozen=True)
class PythonSpec:
    version: str                         # "3.11"
    manager: str                         # "pyenv" | "system"
    extras: list[str] = field(default_factory=list)
    test_deps: str | None = None         # "tests/requirements.txt"

@dataclass(frozen=True)
class SystemDep:
    name: str
    check: str                           # Shell command to verify presence
    install: str                         # brew | apt | bundled | script | manual | none
    package: str | None = None           # Package name for brew/apt
    cask: bool = False                   # Only valid with install=brew
    required: bool = True
    confirm: bool = False                # Prompt before installing

@dataclass(frozen=True)
class DockerService:
    name: str
    healthcheck: str                     # http | tcp | docker_health
    port: int | None = None              # Required for tcp
    endpoint: str | None = None          # Required for http
    timeout_seconds: int = 30

@dataclass(frozen=True)
class OllamaModelExact:
    name: str
    required: bool = True

@dataclass(frozen=True)
class OllamaModelAlternative:
    required_one_of: list[str]
    tier: str | None = None              # small | medium | large (informational)

OllamaModel = OllamaModelExact | OllamaModelAlternative

@dataclass(frozen=True)
class BootstrapProfile:
    schema_version: int
    name: str
    description: str
    platform: PlatformSpec
    python: PythonSpec
    system_deps: list[SystemDep] = field(default_factory=list)
    docker_services: list[DockerService] = field(default_factory=list)
    ollama_models: list[OllamaModel] = field(default_factory=list)
    deployment_profile: str | None = None
    squad_profile: str | None = None
```

**Validation function:** `load_bootstrap_profile(name: str) -> BootstrapProfile`
- Load from `config/profiles/bootstrap/<name>.yaml`
- Reject unknown top-level fields
- Reject `schema_version` != 1
- Validate `install` against enum `{brew, apt, bundled, script, manual, none}`
- Validate `cask: true` only with `install: brew`
- Validate `package` required for `brew`/`apt`
- Validate `check` required for all `install` != `none`
- Validate `healthcheck` against `{http, tcp, docker_health}`
- Validate `endpoint` required for `http`, `port` required for `tcp`

**Helper:** `list_bootstrap_profiles() -> list[str]`
- Glob `config/profiles/bootstrap/*.yaml`, return names

### Commit 1b: Three profile YAML files

**New files:**

| File | Profile |
|------|---------|
| `config/profiles/bootstrap/dev-mac.yaml` | macOS dev workstation |
| `config/profiles/bootstrap/dev-pc.yaml` | WSL2/Ubuntu dev workstation |
| `config/profiles/bootstrap/local-spark.yaml` | DGX Spark with GPU |

`dev-mac.yaml`:
- `platform: {os: darwin, min_version: "14.0"}`
- `python: {version: "3.11", manager: pyenv, test_deps: "tests/requirements.txt"}`
- `system_deps`: docker (brew cask, confirm: true), docker-compose (bundled), ollama (brew), git (brew)
- `docker_services`: rabbitmq (tcp:5672), postgres (tcp:5432), redis (tcp:6379), prefect-server (http://.../api/health), runtime-api (http://.../health), squadops-keycloak (http://.../health/ready)
- `ollama_models`: qwen2.5:7b, llama3.1:8b, qwen2.5:3b-instruct (all exact required)
- `deployment_profile: local`, `squad_profile: full-squad`

`dev-pc.yaml`:
- `platform: {os: linux, distro: ubuntu, distro_min_version: "22.04"}`
- `python: {version: "3.11", manager: pyenv, test_deps: "tests/requirements.txt"}`
- `system_deps`: docker (apt, package: docker.io), docker-compose (apt, package: docker-compose-plugin), ollama (script), git (apt), curl (apt)
- Same `docker_services` and `ollama_models` as dev-mac
- `deployment_profile: local`, `squad_profile: full-squad`

`local-spark.yaml`:
- `platform: {os: linux, distro: ubuntu, distro_min_version: "24.04"}`
- `python: {version: "3.11", manager: system, test_deps: "tests/requirements.txt"}`
- `system_deps`: docker (apt), docker-compose (apt), ollama (script), git (apt), curl (apt), nvidia-smi (install: none, check: "nvidia-smi"), nvidia-container-toolkit (install: none, check: "nvidia-container-toolkit --version")
- Same `docker_services` as dev-mac
- `ollama_models`: qwen2.5:72b (exact), llama3:70b (exact), qwen2.5:7b (exact), llama3.1:8b (exact)
- `deployment_profile: staging`, `squad_profile: full-squad`

### Commit 1c: Profile loading and validation tests

**New file:**

| File | Contents |
|------|----------|
| `tests/unit/bootstrap/conftest.py` | Fixtures: `tmp_profile_dir`, `valid_profile_yaml`, `minimal_profile_yaml` |
| `tests/unit/bootstrap/test_profile.py` | Schema validation tests |

**Tests (parametrized where possible):**

| Test | Bug it catches |
|------|----------------|
| `test_load_valid_profile` | Profile loading returns correct BootstrapProfile with all fields |
| `test_load_minimal_profile` | Defaults for optional fields (empty lists, None) work correctly |
| `test_reject_missing_schema_version` | Missing `schema_version` raises clear error |
| `test_reject_wrong_schema_version` | `schema_version: 2` rejected with version-specific message |
| `test_reject_unknown_fields` | Extra top-level keys in YAML raise error (prevent mystery drift) |
| `test_reject_missing_required_fields` (parametrize: name, platform, python) | Missing mandatory fields raise specific error |
| `test_reject_invalid_install_method` | `install: yum` or typos rejected |
| `test_reject_cask_without_brew` | `cask: true` + `install: apt` rejected |
| `test_reject_missing_package_for_brew` | `install: brew` without `package` rejected |
| `test_reject_missing_package_for_apt` | `install: apt` without `package` rejected |
| `test_reject_missing_check_for_non_none` | `install: brew` without `check` rejected |
| `test_allow_missing_check_for_none` | `install: none` without `check` is valid |
| `test_reject_invalid_healthcheck` | `healthcheck: ping` rejected |
| `test_reject_http_without_endpoint` | `healthcheck: http` without `endpoint` rejected |
| `test_reject_tcp_without_port` | `healthcheck: tcp` without `port` rejected |
| `test_model_exact_requirement` | Exact model parsed correctly |
| `test_model_required_one_of` | Alternative model set parsed correctly |
| `test_list_profiles` | Returns names of YAML files in bootstrap dir |
| `test_load_dev_mac_profile` | Real `dev-mac.yaml` loads without error |
| `test_load_dev_pc_profile` | Real `dev-pc.yaml` loads without error |
| `test_load_local_spark_profile` | Real `local-spark.yaml` loads without error |

---

## Phase 2: Doctor Command

### Commit 2a: Check registry and check functions

**New file:**

| File | Contents |
|------|----------|
| `src/squadops/bootstrap/checks.py` | `CheckResult` dataclass, check functions, `run_checks()` orchestrator |

```python
@dataclass(frozen=True)
class CheckResult:
    name: str
    category: str              # python | platform | tools | docker | models | gpu | auth
    passed: bool
    message: str               # "python 3.11.14 via pyenv"
    detail: str | None = None  # Extra info on failure
    fix_command: str | None = None    # "brew install ollama"
    auto_fixable: bool = False
    heuristic: bool = False    # True = best-effort, not definitive
```

**Check functions (each returns `CheckResult`):**

| Function | Category | What it checks |
|----------|----------|----------------|
| `check_python_version(profile)` | python | Python version matches `profile.python.version` |
| `check_venv_exists(profile)` | python | `.venv/` exists and has `squadops` installed |
| `check_platform(profile)` | platform | OS matches, version >= min_version, distro matches |
| `check_system_dep(profile, dep)` | tools | Runs `dep.check` command, verifies exit 0 |
| `check_docker_service(profile, svc)` | docker | HTTP endpoint, TCP port, or docker health based on `svc.healthcheck` |
| `check_ollama_model_exact(profile, model)` | models | `ollama list` contains model name |
| `check_ollama_model_alternative(profile, model)` | models | At least one of `required_one_of` present |
| `check_nvidia_gpu(profile)` | gpu | Layered: nvidia-smi exit code → container toolkit → ollama GPU (heuristic) |
| `check_auth_token(profile)` | auth | Token file exists and not expired |

**Orchestrator:** `run_checks(profile: BootstrapProfile) -> list[CheckResult]`
- Runs all applicable checks for the profile
- GPU checks only if any system dep has `name` containing "nvidia"
- Docker service checks driven by `profile.docker_services`
- Model checks driven by `profile.ollama_models`

### Commit 2b: Doctor CLI command

**New file:**

| File | Contents |
|------|----------|
| `src/squadops/cli/commands/doctor.py` | `doctor` Typer command |

**Registration:** Add `doctor` command to `src/squadops/cli/main.py` (root-level command, not a group).

```python
@app.command()
def doctor(
    profile: str = typer.Argument(..., help="Bootstrap profile name (dev-mac, dev-pc, local-spark)"),
    check: str | None = typer.Option(None, "--check", help="Run single category"),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable output"),
):
```

**Output formatting:**
- Default: grouped by category, `✓`/`✗`/`~` markers, fix guidance on failure
- `--json`: `{"profile": "dev-mac", "checks": [...], "summary": {...}}`
- `--check <category>`: filter to one category
- Exit code: 0 = all pass, 1 = any failure

**Failure output contract:** Every failed check MUST include:
1. What failed (name + category)
2. Why (observed vs expected)
3. Fix command (what bootstrap would run)
4. Auto-fixable flag

### Commit 2c: Doctor tests

**New file:**

| File | Contents |
|------|----------|
| `tests/unit/bootstrap/test_checks.py` | Check function unit tests |
| `tests/unit/cli/test_doctor.py` | CLI command tests |

**Check function tests:**

| Test | Bug it catches |
|------|----------------|
| `test_python_version_pass` | Correct version detected |
| `test_python_version_fail` | Wrong version returns failure with fix command |
| `test_platform_darwin_pass` | macOS version check works |
| `test_platform_linux_distro_fail` | Wrong distro detected and reported |
| `test_system_dep_found` | `check` command exits 0 → pass |
| `test_system_dep_missing` | `check` command fails → returns install command as fix |
| `test_docker_service_http_healthy` | HTTP endpoint returns 200 → pass |
| `test_docker_service_http_down` | HTTP endpoint unreachable → fail with endpoint in message |
| `test_docker_service_tcp_healthy` | TCP port open → pass |
| `test_docker_service_tcp_down` | TCP port closed → fail with port in message |
| `test_ollama_model_present` | Model in `ollama list` output → pass |
| `test_ollama_model_missing` | Model absent → fail with `ollama pull <name>` as fix |
| `test_ollama_alternative_one_present` | One of `required_one_of` found → pass |
| `test_ollama_alternative_none_present` | None found → fail listing all alternatives |
| `test_gpu_nvidia_smi_missing` | nvidia-smi not found → fail, not heuristic |
| `test_gpu_ollama_access_heuristic` | GPU layer check → pass with `heuristic=True` |
| `test_check_result_fix_command_present` | Every failure has a non-None fix_command |
| `test_run_checks_skips_gpu_for_non_spark` | dev-mac profile doesn't run GPU checks |

**CLI tests:**

| Test | Bug it catches |
|------|----------------|
| `test_doctor_all_pass_exit_0` | Exit code 0 when all checks pass |
| `test_doctor_any_fail_exit_1` | Exit code 1 when any check fails |
| `test_doctor_json_output` | `--json` produces valid JSON with expected schema |
| `test_doctor_single_category` | `--check tools` filters output |
| `test_doctor_unknown_profile` | Clear error for non-existent profile |
| `test_doctor_failure_shows_fix` | Failed checks include fix guidance in output |

---

## Phase 3: Bootstrap Shell Scripts + State File

### Commit 3a: Shell script library

**New files:**

| File | Contents |
|------|----------|
| `scripts/bootstrap/lib/common.sh` | Colors, logging (`info`, `warn`, `error`, `success`), `check_command`, `confirm_install` |
| `scripts/bootstrap/lib/python_setup.sh` | `setup_pyenv()`, `setup_system_python()`, `create_venv()`, `install_python_deps()` |
| `scripts/bootstrap/lib/brew_install.sh` | `ensure_homebrew()`, `brew_install_package()`, `brew_install_cask()` |
| `scripts/bootstrap/lib/apt_install.sh` | `apt_install_package()`, `apt_update_once()` |
| `scripts/bootstrap/lib/docker_setup.sh` | `start_docker_services()`, `wait_for_services()` |
| `scripts/bootstrap/lib/ollama_setup.sh` | `install_ollama()`, `pull_model()`, `check_model_present()` |

**Design rules for all scripts:**
- Every function checks before acting (idempotent)
- No hardcoded requirements — scripts read profile YAML via `yq` or parse simple fields
- `confirm_install()` prompts unless `SQUADOPS_BOOTSTRAP_YES=1` is set
- All output goes through `info`/`warn`/`error`/`success` helpers for consistent formatting

### Commit 3b: Profile-specific scripts and entry point

**New files:**

| File | Contents |
|------|----------|
| `scripts/bootstrap/bootstrap.sh` | Main entry point — parses profile arg, sources lib, dispatches to profile script |
| `scripts/bootstrap/profiles/dev-mac.sh` | macOS-specific: Homebrew, Docker Desktop cask, pyenv |
| `scripts/bootstrap/profiles/dev-pc.sh` | WSL2-specific: WSL2 check, apt, Docker Engine |
| `scripts/bootstrap/profiles/local-spark.sh` | Spark-specific: GPU validation, system python, large models |

**`bootstrap.sh` flow:**
1. Parse args: `profile` (required), `--skip-docker`, `--skip-models`, `--dry-run`, `--yes`
2. Validate profile exists in `config/profiles/bootstrap/`
3. Source `lib/common.sh` and all lib scripts
4. Source `profiles/<profile>.sh`
5. Run steps: `setup_python` → `install_system_deps` → `setup_python_env` → `start_docker` → `pull_models`
6. If Python is available after setup, run `squadops doctor <profile>` as final validation

**`--dry-run`:** Each step prints what it would do without executing.

### Commit 3c: Bootstrap state file

**New file:**

| File | Contents |
|------|----------|
| `src/squadops/bootstrap/state.py` | `BootstrapState` dataclass, `write_state()`, `read_state()` |

State file location: `.squadops/bootstrap/<profile>.json`

```python
@dataclass
class BootstrapState:
    profile: str
    schema_version: int
    last_run: str                        # ISO timestamp
    steps_completed: list[str]
    detected_versions: dict[str, str]
    doctor_summary: dict[str, int]       # total, passed, failed, heuristic
```

- Written by bootstrap after each run (overwritten)
- Read by doctor to show "last bootstrap" context in output
- `.squadops/` already gitignored (or will be added)
- State is informational — doctor always re-checks live state

### Commit 3d: Shell script and state file tests

**New files:**

| File | Contents |
|------|----------|
| `tests/unit/bootstrap/test_state.py` | State file read/write tests |

| Test | Bug it catches |
|------|----------------|
| `test_write_state_creates_directory` | `.squadops/bootstrap/` created if missing |
| `test_write_state_overwrites` | Second write replaces first, not appends |
| `test_read_state_missing_file` | Returns None, not crash |
| `test_read_state_valid` | Round-trips correctly |
| `test_read_state_corrupt_json` | Returns None with logged warning |

Shell script testing strategy: `--dry-run` mode validation. Each profile script in dry-run outputs the commands it would run; a test can capture and verify the expected sequence. This avoids actually installing packages in CI.

---

## Phase 4: CLI Bootstrap Command + Integration

### Commit 4a: Bootstrap CLI command

**New file:**

| File | Contents |
|------|----------|
| `src/squadops/cli/commands/bootstrap.py` | `bootstrap` Typer command |

**Registration:** Add `bootstrap` command to `src/squadops/cli/main.py` (root-level command).

```python
@app.command()
def bootstrap(
    profile: str = typer.Argument(..., help="Bootstrap profile (dev-mac, dev-pc, local-spark)"),
    skip_docker: bool = typer.Option(False, "--skip-docker", help="Skip Docker service startup"),
    skip_models: bool = typer.Option(False, "--skip-models", help="Skip Ollama model pulls"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts"),
):
```

**Implementation:**
1. Load bootstrap profile (validates schema)
2. Shell out to `scripts/bootstrap/bootstrap.sh` with appropriate flags
3. Capture step-by-step output and re-render with Rich progress formatting
4. Write bootstrap state file on completion
5. Auto-run `squadops doctor <profile>` at end

**Fallback:** If the CLI is invoked but shell scripts aren't found (e.g., running from installed package without repo), print clear error directing user to `bootstrap.sh`.

### Commit 4b: Bootstrap CLI tests

**New file:**

| File | Contents |
|------|----------|
| `tests/unit/cli/test_bootstrap.py` | CLI command tests |

| Test | Bug it catches |
|------|----------------|
| `test_bootstrap_loads_profile` | Profile validation runs before any install |
| `test_bootstrap_unknown_profile_error` | Clear error for non-existent profile |
| `test_bootstrap_dry_run_no_side_effects` | `--dry-run` doesn't execute install commands |
| `test_bootstrap_skip_docker_flag` | `--skip-docker` skips Docker step |
| `test_bootstrap_skip_models_flag` | `--skip-models` skips model pull step |
| `test_bootstrap_writes_state_file` | State file created after successful run |
| `test_bootstrap_runs_doctor_at_end` | Doctor is invoked as final step |

---

## Phase 5: Documentation + Polish

### Commit 5a: GETTING_STARTED.md

**New file:**

| File | Contents |
|------|----------|
| `docs/GETTING_STARTED.md` | Quick start per profile, verify, troubleshooting |

Sections:
- Quick Start (macOS) — 3 lines: clone, cd, `./scripts/bootstrap/bootstrap.sh dev-mac`
- Quick Start (Windows / WSL2) — same pattern with `dev-pc`
- Quick Start (DGX Spark) — same pattern with `local-spark`
- Verify Your Environment — `squadops doctor <profile>`
- What's Next — `squadops login` → `squadops cycles create`
- Profiles table (target, models, notes per profile)
- Troubleshooting — `--json`, `--check`, common failure scenarios

### Commit 5b: README and CLAUDE.md updates

**Modified files:**

| File | Change |
|------|--------|
| `README.md` | Add "Getting Started" section near top linking to `docs/GETTING_STARTED.md`, replace any ad-hoc setup instructions |
| `CLAUDE.md` | Add `squadops bootstrap` and `squadops doctor` to Commands section |

### Commit 5c: Status command integration

**Modified file:**

| File | Change |
|------|--------|
| `src/squadops/cli/commands/meta.py` | Add bootstrap profile info to `squadops status` output |

`squadops status` should show:
- Current bootstrap profile (from state file, if present)
- Last bootstrap run timestamp
- Doctor summary from last run

---

## File Inventory

### New files (14)

| File | Phase |
|------|-------|
| `src/squadops/bootstrap/__init__.py` | 1a |
| `src/squadops/bootstrap/profile.py` | 1a |
| `src/squadops/bootstrap/checks.py` | 2a |
| `src/squadops/bootstrap/state.py` | 3c |
| `src/squadops/cli/commands/doctor.py` | 2b |
| `src/squadops/cli/commands/bootstrap.py` | 4a |
| `config/profiles/bootstrap/dev-mac.yaml` | 1b |
| `config/profiles/bootstrap/dev-pc.yaml` | 1b |
| `config/profiles/bootstrap/local-spark.yaml` | 1b |
| `scripts/bootstrap/bootstrap.sh` | 3b |
| `scripts/bootstrap/lib/common.sh` | 3a |
| `scripts/bootstrap/lib/python_setup.sh` | 3a |
| `scripts/bootstrap/lib/brew_install.sh` | 3a |
| `scripts/bootstrap/lib/apt_install.sh` | 3a |
| `scripts/bootstrap/lib/docker_setup.sh` | 3a |
| `scripts/bootstrap/lib/ollama_setup.sh` | 3a |
| `scripts/bootstrap/profiles/dev-mac.sh` | 3b |
| `scripts/bootstrap/profiles/dev-pc.sh` | 3b |
| `scripts/bootstrap/profiles/local-spark.sh` | 3b |
| `docs/GETTING_STARTED.md` | 5a |
| `tests/unit/bootstrap/__init__.py` | 1c |
| `tests/unit/bootstrap/conftest.py` | 1c |
| `tests/unit/bootstrap/test_profile.py` | 1c |
| `tests/unit/bootstrap/test_checks.py` | 2c |
| `tests/unit/bootstrap/test_state.py` | 3d |
| `tests/unit/cli/test_doctor.py` | 2c |
| `tests/unit/cli/test_bootstrap.py` | 4b |

### Modified files (3)

| File | Phase | Change |
|------|-------|--------|
| `src/squadops/cli/main.py` | 2b, 4a | Register `doctor` and `bootstrap` commands |
| `README.md` | 5b | Add Getting Started link |
| `CLAUDE.md` | 5b | Add bootstrap/doctor to Commands |

---

## Test Summary

| Phase | New tests (est.) | Focus |
|-------|-----------------|-------|
| 1 | ~22 | Schema validation (accept/reject), profile loading |
| 2 | ~24 | Check functions (pass/fail/heuristic), CLI output, exit codes |
| 3 | ~5 | State file round-trip, directory creation, corruption handling |
| 4 | ~7 | CLI flags, profile validation, dry-run, state write |
| 5 | 0 | Documentation only |
| **Total** | **~58** | |

---

## Dependencies and Risks

| Dependency | Risk | Mitigation |
|------------|------|------------|
| `yq` or YAML parsing in shell | `bootstrap.sh` needs to read profile YAML before Python exists | Use simple `grep`/`sed` for critical fields, or bundle a static `yq` binary, or hardcode profile names to dispatch to profile scripts directly |
| Platform-specific commands in CI | CI runners may not have Homebrew/Docker/Ollama | All check functions mock subprocess calls in tests; shell scripts tested via `--dry-run` |
| `.squadops/` not yet gitignored | State file would show in `git status` | Add `.squadops/` to `.gitignore` in Phase 3 |
| No `pyproject.toml` extras group for dev/test | `pip install -e .[dev]` doesn't exist yet | Profile uses `test_deps: "tests/requirements.txt"` as explicit path; extras group can be added later |

---

## Commit Sequence

| Commit | Description | Tests |
|--------|-------------|-------|
| 1a | BootstrapProfile model + schema validation | — |
| 1b | Three profile YAML files (dev-mac, dev-pc, local-spark) | — |
| 1c | Profile loading + validation tests | ~22 |
| 2a | Check registry + check functions | — |
| 2b | Doctor CLI command + registration | — |
| 2c | Doctor + check tests | ~24 |
| 3a | Shell script library (common, python, brew, apt, docker, ollama) | — |
| 3b | Profile scripts + bootstrap.sh entry point | — |
| 3c | Bootstrap state file model | — |
| 3d | State file tests | ~5 |
| 4a | Bootstrap CLI command + registration | — |
| 4b | Bootstrap CLI tests | ~7 |
| 5a | GETTING_STARTED.md | — |
| 5b | README + CLAUDE.md updates | — |
| 5c | Status command bootstrap info | — |
