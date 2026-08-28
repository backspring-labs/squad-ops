# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SquadOps is a multi-agent orchestration framework for software development. It uses a hexagonal architecture (ports & adapters) with dependency injection for testability.

**Framework Version**: 1.6.6 (single-sourced from `pyproject.toml`; installed metadata is the
install-time copy and is used only when no source tree is present — #1089)
**Python Requirement**: 3.11+ (production runs 3.11); develop and test on **Python 3.12** to match CI

## Commands

### Testing
```bash
# Run regression test suite (recommended, 2900+ tests always pass)
./scripts/dev/run_regression_tests.sh -v

# Run tests affected by your changes
./scripts/dev/run_affected_tests.sh           # Staged changes
./scripts/dev/run_affected_tests.sh --branch  # All changes vs main

# Run a single test file or test function
pytest tests/unit/agents/test_base_agent.py -v
pytest tests/unit/agents/test_base_agent.py::TestBaseAgent::test_init -v

# Run domain-specific tests
pytest tests/unit/agents/ -v          # Agent tests
pytest tests/unit/capabilities/ -v    # Capability tests
pytest tests/unit/api/ -v             # API tests
pytest tests/unit/tasks/ -v           # Task model tests
pytest tests/unit/memory/ -v          # Memory tests
pytest tests/unit/cycles/ -v          # Cycle execution tests
pytest tests/unit/telemetry/ -v       # LangFuse/telemetry tests
pytest tests/unit/auth/ -v            # Auth tests
pytest tests/unit/cli/ -v             # CLI tests

# Run all unit tests (includes legacy tests, some may fail)
pytest tests/unit -v

# Run with coverage
pytest tests/ --cov=src/squadops --cov-report=term-missing
```

### Linting & Formatting
```bash
ruff check . --fix    # Lint with auto-fix
ruff format .         # Format code
```

### Building Agents
```bash
python scripts/dev/build_agent.py <role>           # Build agent package locally (required before Docker build)
./scripts/dev/ops/rebuild_and_deploy.sh agents      # Rebuild and deploy all agents
./scripts/dev/ops/rebuild_and_deploy.sh runtime-api # Rebuild runtime API
./scripts/dev/ops/rebuild_and_deploy.sh all         # Rebuild everything
```

### Docker
```bash
docker-compose up -d                       # Start all services
docker-compose up -d postgres redis rabbitmq  # Start core services only
```

### Bootstrap & Doctor
```bash
# Bootstrap a fresh environment (one command)
./scripts/bootstrap/bootstrap.sh dev-mac           # macOS
./scripts/bootstrap/bootstrap.sh dev-pc            # WSL2/Ubuntu
./scripts/bootstrap/bootstrap.sh local-spark       # DGX Spark (GPU)

# Or via CLI wrapper (validates profile schema first)
squadops bootstrap dev-mac [--skip-docker] [--skip-models] [--dry-run] [--yes]

# Validate environment against profile contract
squadops doctor dev-mac                            # Full check
squadops doctor dev-mac --check python             # Single category
squadops doctor dev-mac --json                     # Machine-readable output
```

### CLI (Cycle Execution)
```bash
squadops login                             # Authenticate via Keycloak
squadops cycles create <project> --squad-profile full --request-profile selftest
squadops cycles show <project> <cycle-id>  # Show cycle status + runs
squadops cycles list <project>             # List cycles for project
squadops runs list <project> <cycle-id>    # List runs for cycle
squadops runs gate <project> <cycle-id> <run-id> <gate-name> --approve  # Approve a gate
squadops artifacts list --project <project> --cycle <cycle-id> --run <run-id>  # List artifacts for run
```

## Architecture

### Hexagonal Structure (Ports & Adapters)
- **`src/squadops/`** - Core domain
  - `ports/` - Abstract interfaces (SecretProvider, QueuePort, CycleRegistryPort, AuthPort, AuditPort, LLMObservabilityPort)
  - `agents/` - BaseAgent with DI, entrypoint for RabbitMQ message handling
  - `tasks/` - TaskEnvelope, TaskResult models (A2A message format with lineage per SIP-031)
  - `capabilities/` - Capability contracts, workload runner, cycle task handlers, build handlers (SIP-0058, SIP-0068)
  - `orchestration/` - AgentOrchestrator, HandlerExecutor
  - `cycles/` - Cycle/Run/Gate domain models, lifecycle state machine, task planning (SIP-0064)
  - `auth/` - Auth models, JWT validation helpers, middleware (SIP-0062)
  - `cli/` - Typer CLI commands, CRP contract packs (SIP-0065)
  - `api/` - FastAPI runtime API service with routes, DTOs, DI wiring (SIP-0048)
  - `telemetry/` - LLM observability models, CorrelationContext, NoOp adapter (SIP-0061)
  - `memory/` - LanceDB semantic memory (SIP-042)
  - `llm/` - LLM router abstraction with dynamic provider registry
  - `config/` - Configuration loading (`SQUADOPS__*` env vars, double underscores for nesting)
  - `core/` - Core utilities (SecretManager)
- **`adapters/`** - Concrete implementations
  - `secrets/` - env, file, docker_secret providers
  - `comms/` - RabbitMQ adapter
  - `persistence/` - PostgreSQL runtime with connection pooling
  - `cycles/` - DispatchedFlowExecutor, MemoryCycleRegistry, PostgresCycleRegistry, factory
  - `telemetry/` - LangFuse adapter (buffered, with redaction) and factory
  - `auth/` - Keycloak adapter, JWT middleware
  - `llm/` - Ollama adapter
  - `capabilities/` - Filesystem repository, ACI executor
- **`infra/`** - Database migrations and DDL

### Key Patterns
- **Dependency Injection**: `BaseAgent` receives its ports (LLM, memory, prompt service, queue, metrics/events, filesystem, LLM observability) via constructor injection
- **Factory Pattern**: Adapters use factories for provider selection based on environment
- **Task Envelope**: A2A message format with lineage (correlation_id, causation_id, trace_id) per SIP-031
- **DTO Purity**: Task adapters return canonical DTOs; API formatting happens in FastAPI layer
- **Frozen Dataclasses**: Cycle/Run/Gate models use `@dataclass(frozen=True)` with `dataclasses.replace()` for mutation
- **Always-inject NoOp**: `BaseAgent` and `AgentOrchestrator` auto-inject `NoOpLLMObservabilityAdapter` when `llm_observability=None`
- **Config-driven Selection**: Registry provider (memory vs postgres), auth, LangFuse all selected via config
- **CRP Applied Defaults**: Extra keys in CRP `defaults` flow into `applied_defaults`: `build_tasks`, `plan_tasks`, `pulse_checks`, `cadence_policy`

### Agent Squad
6 agents when builder role is present: Max (Lead), Neo (Dev), Nat (Strategy), Bob (Builder), Eve (QA), Data (Analytics). Roster is set per profile via `members:` (#173): `full` (27b) and `lite` (7b) carry all 6 incl. Bob; `smoke` (3b) is the 5-agent no-builder plumbing squad. Implementations in `src/squadops/agents/`.

### Agent status vs runtime state
Don't conflate the signals. **Health = `runtime_status`, posture = `mode`** (both from `agent_runtime_state`, SIP-0089); `lifecycle_state`/`network_status` on `agent_status` are heartbeat telemetry (`network_status` is legacy/deprecated). Canonical model + the rule surfaces must conform to: `docs/agent-runtime-status-model.md` (#231).

## Test Configuration

- Tests auto-receive `unit`/`integration` markers based on file location (`tests/conftest.py`)
- Unit test fixtures (mock_database, mock_redis, mock_ports, sample_task_envelope) are in `tests/unit/conftest.py`
- `asyncio_mode = "auto"` in pyproject.toml — async tests work without `@pytest.mark.asyncio`
- `--strict-markers` is enabled — any new `@pytest.mark.X` must be registered in `pyproject.toml`

### Key Markers
```python
@pytest.mark.unit / @pytest.mark.integration / @pytest.mark.smoke / @pytest.mark.slow
@pytest.mark.database / @pytest.mark.rabbitmq / @pytest.mark.redis / @pytest.mark.docker
@pytest.mark.domain_agents / @pytest.mark.domain_capabilities / @pytest.mark.domain_api
@pytest.mark.domain_memory / @pytest.mark.domain_orchestration / @pytest.mark.domain_telemetry
@pytest.mark.domain_cli / @pytest.mark.domain_contracts / @pytest.mark.domain_pulse_checks
@pytest.mark.langfuse / @pytest.mark.auth
```

## SIP System (SquadOps Improvement Proposals)

SIPs govern architectural decisions. Located in `sips/` with lifecycle:
- `sips/proposed/` - Unnumbered drafts
- `sips/accepted/` - Numbered, approved
- `sips/implemented/` - Matched to code
- `sips/registry.yaml` - Canonical index

### Contributor Workflow

| Step | Where | Who | What happens |
|------|-------|-----|-------------|
| 1. Propose | PR to main | Contributor | Adds draft to `sips/proposed/` |
| 2. Design review | That PR | Maintainer + team | Review the SIP spec — approve the *design*, not code |
| 3. Accept | Merge to main | Maintainer | Runs `update_sip_status.py ... accepted`, merges |
| 4. Branch | Feature branch off main | Implementer | `git checkout -b feature/sip-NNNN-...` from main (which now has the accepted SIP) |
| 5. Implement | Feature branch | Implementer | Incremental commits per phase |
| **5a. Amend** | **The diverging PR** | **Implementer** | **Implementation showed the accepted design was wrong, or a decision narrowed it → add an amendment section to the SIP *in the PR that diverges*** |
| 6. Code review | PR to main | Maintainer + team | Review the implementation |
| 7. Merge | main | Maintainer | Merge the feature PR |
| 8. Promote | main | Maintainer | Runs `update_sip_status.py ... implemented` after verification |

Key principle: **acceptance is a design commitment on main, not an implementation artifact.** The feature branch starts from a main that already has the accepted SIP, so the implementer works from an approved spec. This separates "we agree this is the right design" from "the implementation is correct."

**Step 5a is not optional, and it is the step that gets skipped.** Acceptance being a *commitment* is a statement about sequencing — the spec is approved before the branch starts. It is **not** a licence to leave the SIP stale once implementation contradicts it. A SIP whose accepted text no longer describes main is worse than no SIP: it reads as authoritative, and the next implementer builds against a design that was abandoned.

- **Amend in the SIP itself, as a new numbered section** (`## 5d. Post-acceptance amendments`, then `5e`, …). SIP-0103's own `§5a`/`§5b`/`§5c` are exactly this shape — the mechanism already exists and is demonstrated.
- **A release plan is not an amendment.** Plans are superseded at the cut; the SIP is permanent. Recording a divergence only in `docs/plans/*` means it is gone the moment the release closes — the failure that produced SIP-0103's `§5d` (2026-08-09), where three divergences and four unimplemented dispositions lived only in the 1.6 plan.
- **A code comment is not an amendment either.** Necessary, not sufficient: a reader of the SIP never sees it.
- Each amendment names **what changed, the evidence, and who ruled it.** "We decided otherwise" without evidence is how a spec becomes advisory.
- **A disposition that is deliberately not built is an amendment too** — silence reads as "shipped."
- **Do not touch `updated_at`.** It means *last status transition*, not last content change: `update_sip_status.py` is the only writer (frontmatter and registry are stamped separately, hence the millisecond skew between them), so a hand edit invents drift. **The amendment section's own date is the content record** — and it is the better one, since it says *what* changed rather than only when.

### Key Implemented SIPs

- **SIP-0061** – LangFuse LLM Observability Foundation
- **SIP-0062** – Auth Boundary (Keycloak OIDC)
- **SIP-0064** – Project Cycle Request API
- **SIP-0065** – CLI for Cycle Execution
- **SIP-0066** – Distributed Cycle Execution Pipeline
- **SIP-0067** – Postgres Cycle Registry
- **SIP-0068** – Enhanced Agent Build Capabilities
- **SIP-0069** – Console Control-Plane UI (Continuum Plugins)
- **SIP-0070** – Pulse Checks and Verification Framework
- **SIP-0071** – Builder Role (Dedicated Product Builder Agent)
- **SIP-0086** – Build Convergence Loop (Dynamic Task Decomposition, Output Validation, Correction Activation)
- **SIP-0087** – Prefect Task-Scoped Log Streaming (per-task log forwarding to Prefect UI with heartbeats)
- **SIP-0096** – Verification Evidence Integrity (only executed-and-passed credits; `blocked_unverified`; the `CycleOutcome` roll-up with waiver/inert disclosure)

### Moving a SIP (maintainer only)

```bash
export SQUADOPS_MAINTAINER=1

# Promote a proposal to accepted (assigns a number)
python scripts/maintainer/update_sip_status.py sips/proposed/SIP-MyIdea.md accepted

# Promote an accepted SIP to implemented (after code is merged)
python scripts/maintainer/update_sip_status.py sips/accepted/SIP-0067-My-Feature.md implemented
```

## Versioning & Release Cadence

Semver `MAJOR.MINOR.PATCH` with an **even/odd minor convention** layered on top — parity gates *features*, not hardening (#281):

- **Even minor (1.2, 1.4, …) — feature release.** Led by ≥1 headline feature SIP, which gates the version. Hardening rides along freely; the safe, ready stuff lands here alongside features (1.1.0 shipped SIP-0089 on a hardening foundation).
- **Odd minor (1.3, 1.5, …) — stabilization release.** Feature-free by rule (its only constraint). Home for the big, risky structural refactors deliberately quarantined out of feature releases (so a regression is unambiguously the refactor, not a feature) + accumulated debt. Substance gates the cut, not the clock.
- **Patch (x.y.Z) — urgent/small fixes**, any time, either lane. Never hold a critical fix for the next odd release (the 1.1.1 cadence).

Two concurrent lanes feed this. **Feature SIPs gate even minors and are pinned by *file ownership*, not lane identity** (amended 2026-07-14; previously Macbook-pinned): executor/handlers/framing surfaces = Macbook lane; test-runner/build-check/agent-image/deploy-infra = Spark lane. A release may carry one headline per lane (1.4 is the first dual-lane-headline release: Scaffold = M, Sandbox = S). Everything else is shared — **both lanes** emit patches continuously, and **both** emit the big structural refactors that batch into odd minors (the 1.3.0 batch is #186/#152, Macbook-owned, plus #234, Spark-owned). The Spark lane is the primary *hardening* source, but odd-minor refactors are not exclusively its output. Bump via `scripts/maintainer/version_cli.py bump <v>`; keep version markers in this file, `README.md`, and `docs/ROADMAP.md` in sync (they drifted at 1.1.x — don't repeat). Full plan: `docs/plans/1-2-0-release-plan.md`.

### Release cut

The procedure, as distinct from the cut *criteria* a release plan carries. It lives here
because plans are superseded at the cut and a procedure recorded only in one disappears
with it — the same failure SIP-0103 §5d records for amendments. #789 is what a missing
procedure costs: six consecutive releases tagged but never advertised.

| Step | Action |
|------|--------|
| 1 | `scripts/maintainer/version_cli.py bump <version>` — the only sanctioned bump path |
| 2 | Version markers in sync: `CLAUDE.md`, `README.md`, `docs/ROADMAP.md` |
| 3 | Rotate `CHANGELOG.md` — `[Unreleased]` → `[x.y.z] — <date>`, open a fresh `[Unreleased]` |
| 4 | ROADMAP timeline entry |
| 5 | SIP promotion sweep — promote what is genuinely implemented; a phased or umbrella SIP with open children stays `accepted`, with the gap named |
| 6 | `git tag vX.Y.Z && git push origin vX.Y.Z` — the Release publishes itself from the CHANGELOG section (`.github/workflows/release.yml`, #1061) |
| 7 | **Capture the release package** — `python scripts/maintainer/build_release_package.py <version> --cycle <cycle-id> --project <project>` to PREVIEW, read the cycle evidence, then re-run with `--write` and commit `site/content/releases/vX.Y.Z/` |

Steps 1–3 are guarded by `tests/unit/architecture/test_docs_version_sync.py`, and step 6's
Release is now automated on tag push. **Steps 4, 5 and 7 remain unguarded**, which is why
they are written down.

**Why step 6 is automated rather than listed.** Across v1.4.0–v1.6.1, *zero* releases were
published at cut time — every one was backfilled later. The step sat in the cut checklist
from 2026-08-10 and was still missed at both subsequent cuts. Pushing a tag reads as
completion, and nothing signals that a separate artifact on another system is outstanding.
A step with that record needs removing, not restating (#1061).

**Step 7 is capture, not query.** Cycle evidence lives in a running deploy and is
unrecoverable once it moves, so the package is snapshotted at the cut and committed —
the site renders it and never re-derives it. Screenshots (Prefect run, delivered app) go
into that release's `assets/` before the script runs. It reads the tag range, so it must
follow step 6.

**Read step 7's preview before writing it.** The capture needs a running runtime API, a
current `squadops login`, and the right `--project`; when any is missing the package can
still be written. At the 1.6.2 cut it reported `1 cycles` and wrote a roll-up of nulls —
four silent defects behind a guard that treated `{"detail": "Not Found"}` as success,
because valid JSON is valid JSON (#1076). A hollow capture is worse than none: it looks
like the evidence was taken, and the deploy it came from is gone by the time anyone
looks. So run it without `--write` first and confirm the verdict, run count and check
names are actually there.

**Nothing else merges between opening the release PR and merging it.** The release branch
is cut from main at some commit; anything merged after that still lands in the tag, because
the release merge brings main's head with it. At the 1.6.2 cut two PRs merged in that
window and the CHANGELOG said they were excluded — the record was wrong until the branch
was rebased and re-documented. If something must go in, rebase and re-document rather than
letting the tag and the notes disagree.

**Say what the cut evidence does NOT cover.** A release whose headline is "validated by a
green roll" has to be exact about what that roll ran on. Where the tagged tree differs from
the validated deploy, name the difference and say whether it is additive or behavioural —
v1.6.0 could record zero code drift; v1.6.2 could not, and said so.

## Development Workflow

**Branch first**: Always create a feature branch before writing any code for a new feature or SIP implementation. Develop on the branch with incremental commits per phase — not one giant commit at the end. This keeps `main` clean and gives the PR a proper commit history.

**Close issues from PRs**: Every PR body must include `Closes #NNN` (or `Fixes #NNN`) for each issue it fully resolves, so the merge auto-closes them. A bare `(#NNN)` reference does **not** close the issue — that gap left #133/#205 credited-but-open after 1.1.1 (closed 2026-06-29 during the #281 reconcile). If a PR only partially addresses an issue, reference it without `Closes` and say what remains. **Enforced** since 2026-08-26 by `.github/workflows/pr-closure.yml` (#1113 — six 1.6.4 fix PRs shipped without the line): the body must carry `Closes #N` to an *open* issue, or `Refs #N — remaining: …`, or `No issue: …`; `scripts/dev/check_pr_closure.sh` runs the same check locally. The template is `.github/PULL_REQUEST_TEMPLATE.md` (`gh pr create --body-file` bypasses it, which is why the check exists).

**Ownership before extension (edit-time rule)**: Before adding content, config, or a new pattern to ANY file, check whether an existing seam already owns that concern (`ports/`, a service or module named for it). Use the seam or flag the conflict *before* editing — "the neighboring code does it this way" is never justification. Content edits (prompt text, string blocks, config literals) get the same scrutiny as logic; they are where shortcuts hide. Canonical example: prompt content belongs in `src/squadops/prompts/fragments/` via PromptService, not inline string literals in handlers (#448 — two fixes shipped as inline literals while the fragment system sat unused for build handlers).

**Proactive guidance**: If you observe a workflow or code best practice being bypassed, call it out early — don't wait to be asked. Examples:
- Workflow: developing on main instead of a feature branch, skipping tests, hardcoding secrets
- Code structure: copy-pasted logic that should be a shared helper, inconsistent patterns across similar modules, missing registry updates when adding new entries, constants duplicated across files instead of single-sourced
- Cross-cutting surface drift: adding a new HTTP route prefix, API error shape, event type, or `SQUADOPS__*` config-var convention that diverges from the existing standard — flag it and conform; never justify a new variant by "it doesn't collide" or "it's easy" (this is exactly how the runtime-api drifted into 4 URL conventions — see API Conventions below, #218)

## Repository Rules

**Read-Only Areas**:
- Never modify `dist/` or generated metadata (`manifest.json`, `agent_info.json`)
- Version bumps via `scripts/maintainer/version_cli.py` only

**API Conventions** (runtime-api HTTP surface):
- Before adding or moving any route, read the **whole** existing surface — do not reason only about the neighborhood. Conform to the lane standard; if no standard covers your case, surface the gap and propose it **before** adding (#218).
- **Lanes:** authenticated, managed REST resources → `/api/v1/<resource>` (default home for anything new). `/health/*` = read-only, unauthenticated operational probes/heartbeats **only** — never a writable business resource (it's the only no-auth lane). `/auth/*` = identity. **Do not add `/api/v2`** — extend v1.
- A new prefix/variant is a deliberate, justified decision, never a default. "It doesn't collide" is not a justification.
- Known deviations under cleanup: unversioned `/api/chat`+`/api/agents` (#219); `/health`+`/auth` plain-string error bodies vs the standard `{"error": {...}}` envelope (#218). Don't add to these.

**Structure**:
- Permanent utilities: `scripts/dev/`
- Maintainer-only: `scripts/maintainer/`
- Temp migrations: `scripts/dev/migrations/temp_*.py`
- New SIP drafts go in `sips/proposed/` (unnumbered)
- Do not create scripts in the project root

**Tests** (see `docs/TEST_QUALITY_STANDARD.md` for full standard with examples):
- Never delete/skip tests to make suite pass — fix implementation, not tests
- **Before writing any test, answer: "What bug would this catch?"** If you cannot name a specific, realistic bug, do not write the test.
- **Do NOT write**:
  - Tautological tests: checking class attributes equal their hardcoded values (`assert h.capability_id == "foo"`), checking enum/constants members exist, checking dataclass fields store what you pass, checking `_artifact_name` or `_role` attributes
  - Mock-call-count-only assertions as the sole assertion (pair with output/state assertions)
  - `isinstance`/`is not None` as sole assertions
  - Near-duplicate tests that vary only the input data — use `@pytest.mark.parametrize` instead
  - Happy-path-only suites with no error/edge cases
- **DO write**: exact value assertions on outputs, error/edge case tests, varied inputs via parametrize, tests that exercise real code paths (call `handle()`, `execute()`, etc.)
- Every test file must include at least one error/edge case test per public function tested
- Prefer 4 strong tests over 20 weak ones — quality over count
- **Self-check before committing tests**: re-read each test and delete any that only assert class attributes, only check `is not None`, or duplicate another test's coverage with different constants

**Docker**:
- Don't modify `docker-compose.yml` or change service/container names without explicit request

## Services (docker-compose.yml)

| Service | Port | Purpose |
|---------|------|---------|
| rabbitmq | 5672, 15672 | Message queue (inter-agent comms) |
| postgres | 5432 | Database (cycle registry, task logging) |
| redis | 6379 | Cache |
| runtime-api | 8001 | Cycle execution API (SIP-0048/0064) |
| prefect-server | 4200 | Workflow orchestration |
| squadops-keycloak | 8180 | OIDC identity provider (SIP-0062) |
| langfuse | 3001 | LLM observability UI (SIP-0061) |
| grafana | 3000 | Metrics dashboards |
| prometheus | 9090 | Metrics collection |
| otel-collector | 4317, 4318 | OpenTelemetry collector |
| squadops-console | — | Control-plane UI (SIP-0069) |
| caddy | 4040 | Reverse proxy for console and API |
| max/neo/nat/eve/data | — | Agent containers |


## Key Files

- `pyproject.toml` - Python config (ruff, pytest, mypy, coverage settings); ruff line-length is 100
- `tests/conftest.py` - Global fixtures, session event loop, auto-markers by file location
- `tests/unit/conftest.py` - Unit-specific mock fixtures (mock_database, mock_ports, sample_task_envelope)
- `.env.example` - Environment template (`SQUADOPS__*` prefix, double underscores for nesting)
- `docker-compose.yml` - 17-service development environment
- `infra/migrations/` - Postgres DDL migrations (applied at runtime-api startup)

## Python Path Setup

The project uses **editable install** for import resolution. Both `squadops` and `adapters` packages are discoverable:

```bash
pip install -e .  # Required: install in editable mode
```

`pyproject.toml` configures setuptools to find packages in `src/` (for `squadops*`) and project root (for `adapters*`).

**If imports fail** (e.g., `ModuleNotFoundError: No module named 'adapters'`):
1. Verify editable install: `pip list | grep squadops`
2. Re-install: `pip install -e .`
3. Ensure venv is active: `source .venv/bin/activate`

## Docker Troubleshooting

- Database migrations are baked into the runtime-api Docker image (`infra/migrations/`)
- Adapter integration tests don't need agent containers: `SKIP_AGENT_CHECK=1 pytest tests/integration/adapters/ -v`

| Symptom | Fix |
|---------|-----|
| Postgres mount error | Verify `docker-compose.yml` volume paths |
| Tests skip with "agents not running" | Set `SKIP_AGENT_CHECK=1` |
| Import errors in pytest | Run `pip install -e .` |
| JSONB round-trip errors | asyncpg returns JSONB as strings; use `_parse_jsonb()` helper |
| Auth 401 errors | Run `squadops login` first |
