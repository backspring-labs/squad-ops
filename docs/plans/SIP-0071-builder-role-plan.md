# SIP-0071: Builder Role — Implementation Plan

## Context

SIP-0071 adds a `builder` role to SquadOps alongside the existing five (`lead`, `dev`, `strat`, `qa`, `data`). The builder specializes in producing runnable, testable application artifacts from approved plans. Today, `dev` handles both planning (`development.implement`) and building (`development.build`) via SIP-0068's `DevelopmentBuildHandler`. This SIP separates those concerns.

**SIP spec:** `sips/accepted/SIP-0071-Builder-Role-Dedicated-Product.md`
**Depends on:** SIP-0068 (Enhanced Agent Build Capabilities), SIP-0066 (Cycle Execution Pipeline), SIP-0058 (Capability Contracts)

---

## Branching Strategy

All implementation work happens on a feature branch, merged to main via PR.

```bash
git checkout -b feature/sip-0071-builder-role
```

- One PR per phase (Phase 1 PR, Phase 2 PR, etc.) or a single PR for all phases — maintainer's discretion.
- Each phase must pass the full regression suite before merge.
- PR title format: `feat: SIP-0071 Phase N — <description>`
- PR body references the SIP and this plan doc.

---

## Binding Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | `BuilderBuildHandler` extends `_CycleTaskHandler` (cycle_tasks.py) | Same LLM→artifact pattern as `DevelopmentBuildHandler`; override `handle()` for multi-file + QA handoff output |
| D2 | `BuildProfile` is a frozen dataclass in new file `src/squadops/capabilities/handlers/build_profiles.py`. V1 profiles are code-defined dataclass instances, not externalized config. External profile loading is out of scope for SIP-0071. Handlers must not mutate profile fields; treat `get_profile()` return as read-only | Typed registry, not ad hoc handler logic. Profiles are data, not code |
| D3 | `BUILDER_ROLE` added to `DEFAULT_ROLES` in `src/squadops/agents/models.py` (line 99) | Same registration pattern as existing 5 roles |
| D4 | `BuilderAgent` class in `src/squadops/agents/roles/builder.py` | Follows existing per-role module pattern (dev.py, qa.py, etc.) |
| D5 | Alias routing resolved at plan-generation time in `task_plan.py`, not at dispatch. Dispatch executes the task type emitted in the plan; runtime role availability may fail execution but must not mutate planned task type | Deterministic; resolved task type written to plan. No runtime ambiguity |
| D6 | `qa_handoff` added to `ArtifactType` constants (models.py:68) | String constant, same pattern as existing types |
| D7 | `_BUILD_ARTIFACT_FILTER` in executor extended with `"builder.build"` entry. V1 duplicates `development.build` filter inputs for parity; a shared filter constant may be introduced later if build input requirements diverge | Same filter as `development.build` — needs strategy + implementation plan artifacts |
| D8 | `_APPLIED_DEFAULTS_EXTRA_KEYS` gains `"build_profile"` | Build profile name flows through `applied_defaults`, consumed by handler at execution time |
| D9 | Builder added to warmboot handler roles in bootstrap | Builder agents need warmboot capability like all other roles |
| D10 | `full-squad-with-builder` squad profile in `config/squad-profiles.yaml` | 6-agent profile; existing `full-squad` stays unchanged |
| D11 | New cycle request profile `builder-build.yaml` in profiles directory | References `full-squad-with-builder` and sets `build_tasks: [builder.build, qa.build_validate]` |
| D12 | QA handoff required section names defined as constants in `build_profiles.py` (single canonical source) | Prevents drift between handler, tests, and docs |
| D13 | `BuilderBuildHandler` reuses existing `_classify_file()` helper and `_EXT_MAP` from cycle_tasks.py for artifact typing. `qa_handoff` is always a separate explicit artifact regardless of other markdown files. V1 retries overwrite artifacts at the same `run_id + step_index`; uniqueness across attempts is not guaranteed and not required | No new classification logic; consistent artifact types |
| D14 | `routing_reason` values are enum-like string constants, not free text: `"builder_role_present"`, `"fallback_no_builder"` | Prevents test brittleness and string drift in diagnostics |

---

## Phase 1: Builder Role + Handler + Routing

### 1.1 Builder role definition

**Modified file:** `src/squadops/agents/models.py`

Add after `DATA_ROLE` (line 96):

```python
BUILDER_ROLE = AgentRole(
    role_id="builder",
    display_name="Builder Agent",
    description="Artifact production from approved plans",
    default_skills=(
        "artifact_generation",
        "code_generation",
    ),
)
```

Add to `DEFAULT_ROLES` dict (line 99):

```python
DEFAULT_ROLES = {
    "lead": LEAD_ROLE,
    "dev": DEV_ROLE,
    "qa": QA_ROLE,
    "strat": STRAT_ROLE,
    "data": DATA_ROLE,
    "builder": BUILDER_ROLE,
}
```

### 1.2 Builder agent class

**New file:** `src/squadops/agents/roles/builder.py`

Follows `dev.py` pattern exactly:

```python
class BuilderAgent(BaseAgent):
    ROLE_ID = "builder"
    DEFAULT_SKILLS = ("artifact_generation", "code_generation")
    # Task type routing for builder
    TASK_TYPE_SKILL_MAP = {
        "build": "artifact_generation",
        "builder.build": "artifact_generation",
    }
```

**Modified file:** `src/squadops/agents/roles/__init__.py`

Add import and `__all__` entry for `BuilderAgent`.

### 1.3 Build profile registry

**New file:** `src/squadops/capabilities/handlers/build_profiles.py`

```python
# Canonical QA handoff section names (D12 — single source of truth)
QA_HANDOFF_REQUIRED_SECTIONS = ("## How to Run", "## How to Test", "## Expected Behavior")
QA_HANDOFF_OPTIONAL_SECTIONS = (
    "## Files Created", "## Implemented Scope",
    "## Known Limitations", "## Build Results",
)

# Routing reason constants (D14)
ROUTING_BUILDER_PRESENT = "builder_role_present"
ROUTING_FALLBACK_NO_BUILDER = "fallback_no_builder"

# Artifact output mode constants
ARTIFACT_MODE_MULTI_FILE = "multi_file"
ARTIFACT_MODE_SINGLE_FILE = "single_file"
ARTIFACT_MODE_STRUCTURED_BUNDLE = "structured_bundle"

@dataclass(frozen=True)
class BuildProfile:
    """Typed build profile definition (SIP-0071 §5.2)."""
    name: str
    system_prompt_template: str
    required_files: list[str]
    optional_files: list[str]
    validation_rules: list[str]
    artifact_output_mode: str        # ARTIFACT_MODE_MULTI_FILE | ARTIFACT_MODE_SINGLE_FILE | ARTIFACT_MODE_STRUCTURED_BUNDLE
    qa_handoff_expectations: list[str]
    default_task_tags: dict[str, str]

BUILD_PROFILES: dict[str, BuildProfile] = {
    "python_cli_builder": BuildProfile(...),
}

def get_profile(name: str) -> BuildProfile:
    """Resolve build profile by name. Raises ValueError with structured message if unknown."""
```

Unknown `build_profile` values produce a `ValueError` listing the requested name and available profiles — never an uncaught `KeyError` from bare dict access.

V1 ships with `python_cli_builder` only. `static_web_builder` and `web_app_builder` added in Phase 2.

### 1.4 BuilderBuildHandler

**Modified file:** `src/squadops/capabilities/handlers/cycle_tasks.py`

Add after `QABuildValidateHandler` (end of file):

```python
class BuilderBuildHandler(_CycleTaskHandler):
    """Builder handler: generates source code + QA handoff from plan (SIP-0071).

    Selects build profile from applied_defaults, generates artifacts,
    emits qa_handoff alongside source files. Uses existing _classify_file()
    helper for artifact type classification (D13).
    """
    _handler_name = "builder_build_handler"
    _capability_id = "builder.build"
    _role = "builder"
    _artifact_name = "build_output"

    async def handle(self, inputs, context=None):
        # 1. Resolve build profile from inputs["resolved_config"]["build_profile"]
        # 2. Resolve plan artifacts via _resolve_with_vault_fallback()
        # 3. Build prompt from profile.system_prompt_template + plan content
        # 4. Call LLM
        # 5. Parse response with extract_fenced_files()
        # 6. Classify + store each file as artifact (via _classify_file(), D13)
        # 7. Generate qa_handoff artifact with required sections (from QA_HANDOFF_REQUIRED_SECTIONS, D12)
        # 8. Validate output against profile.required_files (exact basename match, case-sensitive, intentionally path-agnostic in V1)
        # 9. Emit routing diagnostics in result metadata
```

Key differences from `DevelopmentBuildHandler`:
- Reads `build_profile` from `resolved_config` to select prompt template
- Emits `qa_handoff` artifact with required sections (How to Run, How to Test, Expected Behavior)
- Validates output against `profile.required_files` (exact basename match, case-sensitive, intentionally path-agnostic in V1)
- Duplicate filenames in LLM output are a validation failure in V1 (last-write-wins is too fragile)
- Emits routing diagnostics (`resolved_handler`, `build_profile`, `validation_summary`) into task result metadata (V1 source of truth; no separate diagnostics sink)

### 1.5 QA handoff artifact type

**Modified file:** `src/squadops/cycles/models.py`

Add to `ArtifactType` class (line 68):

```python
class ArtifactType:
    PRD = "prd"
    CODE = "code"
    TEST_REPORT = "test_report"
    BUILD_PLAN = "build_plan"
    CONFIG_SNAPSHOT = "config_snapshot"
    QA_HANDOFF = "qa_handoff"  # SIP-0071
```

### 1.6 Handler registration

**Modified file:** `src/squadops/bootstrap/handlers.py`

Add import:
```python
from squadops.capabilities.handlers.cycle_tasks import BuilderBuildHandler
```

Add to `HANDLER_CONFIGS` list (after line 84):
```python
    # Builder handlers (SIP-0071: Builder Role)
    (BuilderBuildHandler, ("builder",)),
```

Add `"builder"` to warmboot handler roles (line 74):
```python
    (WarmbootHandler, ("lead", "dev", "qa", "strat", "data", "builder")),
    (ContextSyncHandler, ("lead", "dev", "qa", "strat", "data", "builder")),
```

### 1.7 Applied defaults: build_profile key

**Modified file:** `src/squadops/contracts/cycle_request_profiles/schema.py`

Add `"build_profile"` to `_APPLIED_DEFAULTS_EXTRA_KEYS` (line 20):

```python
_APPLIED_DEFAULTS_EXTRA_KEYS = {
    "build_tasks", "plan_tasks", "pulse_checks", "cadence_policy", "build_profile",
}
```

### 1.8 Artifact filter for builder tasks

**Modified file:** `adapters/cycles/distributed_flow_executor.py`

Add `"builder.build"` entry to `_BUILD_ARTIFACT_FILTER` (line 361):

```python
_BUILD_ARTIFACT_FILTER: dict[str, dict[str, list[str]]] = {
    "development.build": {
        "by_producing_task": ["strategy.analyze_prd", "development.implement"],
        "by_type_fallback": ["document"],
    },
    # V1: duplicates development.build filter for parity (D7)
    "builder.build": {
        "by_producing_task": ["strategy.analyze_prd", "development.implement"],
        "by_type_fallback": ["document"],
    },
    "qa.build_validate": {
        "by_producing_task": ["qa.validate"],
        "by_type": ["source", "config"],
    },
}
```

### 1.9 Alias routing in task plan generator

**Modified file:** `src/squadops/cycles/task_plan.py`

After existing `BUILD_TASK_STEPS` (line 30), add builder-aware step resolution:

```python
# Builder-aware build steps (SIP-0071)
BUILDER_BUILD_TASK_STEPS: list[tuple[str, str]] = [
    ("builder.build", "builder"),
    ("qa.build_validate", "qa"),
]


def _has_builder_role(profile: SquadProfile) -> bool:
    """Check if squad profile includes a builder role agent.

    V1: presence-only detection (any(...)). Multi-builder selection
    behavior is out of scope and not specified by this plan.
    """
    return any(a.role == "builder" and a.enabled for a in profile.agents)
```

Modify `generate_task_plan()` to select the right build steps. `builder_used` is computed once before step expansion (D14):

```python
    # Compute routing decision once before step expansion (D5, D14)
    builder_used = include_build and _has_builder_role(profile)

    if include_build:
        if builder_used:
            steps.extend(BUILDER_BUILD_TASK_STEPS)
        else:
            steps.extend(BUILD_TASK_STEPS)
```

**Routing diagnostics:** Add `routing_reason` to build task envelope metadata only (not plan steps). Uses constants from `build_profiles.py` (D14):

```python
    # Import at top of file
    from squadops.capabilities.handlers.build_profiles import (
        ROUTING_BUILDER_PRESENT, ROUTING_FALLBACK_NO_BUILDER,
    )

    # In envelope construction, for build steps only:
    routing_reason = ROUTING_BUILDER_PRESENT if builder_used else ROUTING_FALLBACK_NO_BUILDER
    metadata={
        "step_index": step_index,
        "role": role,
        "routing_reason": routing_reason,  # only on build task envelopes
    }
```

### 1.10 Tests

**New file:** `tests/unit/capabilities/test_builder_build_handler.py`
- Handler instantiation and capability_id
- Profile selection from resolved_config
- QA handoff generation with all required sections present
- QA handoff missing a required section → validation failure reported
- Required file validation (pass/fail)
- Missing artifact_contents/vault fallback
- Routing diagnostics in result metadata

**New file:** `tests/unit/capabilities/test_build_profiles.py`
- `get_profile()` returns correct profile
- `get_profile()` raises ValueError for unknown name
- `BuildProfile` frozen dataclass immutability
- `python_cli_builder` has expected required_files
- `QA_HANDOFF_REQUIRED_SECTIONS` contains expected headings

**Modified file:** `tests/unit/cycles/test_task_plan.py`
- Builder-aware routing: with builder in squad profile → emits `builder.build`
- Fallback routing: without builder → emits `development.build`
- `routing_reason` in metadata matches constants (not free text)
- `routing_reason` only on build step envelopes
- Builder not present + no build_tasks → no build steps (unchanged)

**New file:** `tests/unit/agents/roles/test_builder_agent.py`
- `BuilderAgent.ROLE_ID == "builder"`
- Task routing via `TASK_TYPE_SKILL_MAP`

**Modified file:** `tests/unit/agents/test_agent_models.py`
- `BUILDER_ROLE` in `DEFAULT_ROLES`
- Role fields correct

**Modified file:** `tests/unit/bootstrap/test_handler_bootstrap.py`
- `BuilderBuildHandler` registered for `("builder",)` role
- `DevelopmentBuildHandler` still registered for `("dev",)` — no shadowing
- Warmboot handlers include `"builder"`

### Phase 1 Exit Criteria

- [ ] `builder` role registered in `DEFAULT_ROLES` and bootstraps cleanly
- [ ] `BuilderAgent` class instantiates with correct `ROLE_ID`
- [ ] `builder.build` handler callable via `create_handler_registry()`
- [ ] `DevelopmentBuildHandler` still resolves for `development.build` (no shadowing)
- [ ] Task plan emits `builder.build` when builder present in squad profile
- [ ] Task plan emits `development.build` when builder absent (unchanged)
- [ ] `routing_reason` metadata present on build step envelopes with enum-like constants
- [ ] `qa_handoff` artifact emitted with all 3 required sections
- [ ] Missing required section in `qa_handoff` → validation failure reported
- [ ] `python_cli_builder` profile loads via `get_profile()`
- [ ] All Phase 1 unit tests pass
- [ ] Full regression suite passes (`run_new_arch_tests.sh`)
- [ ] Feature branch pushed, PR opened

---

## Phase 2: Task Plan Generator + Profiles + Tags

### 2.1 Squad profile with builder

**Modified file:** `config/squad-profiles.yaml`

Add new profile:

```yaml
  - profile_id: full-squad-with-builder
    name: "Full Squad with Builder"
    description: "6 agents including dedicated builder"
    version: 1
    agents:
      - { agent_id: max, role: lead, model: "llama3.1:8b", enabled: true }
      - { agent_id: neo, role: dev, model: "qwen2.5:7b", enabled: true }
      - { agent_id: nat, role: strat, model: "qwen2.5:7b", enabled: true }
      - { agent_id: bob, role: builder, model: "qwen2.5:7b", enabled: true }
      - { agent_id: eve, role: qa, model: "qwen2.5:3b-instruct", enabled: true }
      - { agent_id: data, role: data, model: "qwen2.5:3b-instruct", enabled: true }
```

### 2.2 Cycle request profiles

**New file:** `src/squadops/contracts/cycle_request_profiles/profiles/builder-build.yaml`

```yaml
name: builder-build
description: Plan-then-build cycle using dedicated builder agent.
defaults:
  build_strategy: fresh
  build_profile: python_cli_builder
  task_flow_policy:
    mode: sequential
    gates:
      - name: plan-review
        description: Review planning artifacts before build begins.
        after_task_types:
          - governance.review
  expected_artifact_types:
    - document
    - source
    - test
    - config
    - qa_handoff
  build_tasks:
    - builder.build
    - qa.build_validate
  experiment_context: {}
  notes: "Plan-then-build with dedicated builder agent (SIP-0071)"
```

### 2.3 Additional build profiles

**Modified file:** `src/squadops/capabilities/handlers/build_profiles.py`

Add `static_web_builder` and `web_app_builder` (stretch) profiles to `BUILD_PROFILES` registry.

### 2.4 Task tag interpolation

**Modified file:** `src/squadops/capabilities/handlers/cycle_tasks.py` (in `BuilderBuildHandler`)

V1 uses `experiment_context` from `resolved_config` as the transport for builder tags. This is a transitional transport — tags are the subset of `experiment_context` keys consumed by the builder's prompt template. Precedence: build profile `required_files` and `validation_rules` are authoritative; tags from `experiment_context` refine prompt guidance only. `BuildProfile.default_task_tags` are applied first, then overridden by `experiment_context` values.

### 2.5 Tests

- Profile resolution for `static_web_builder`
- Tag interpolation in prompts
- Tags cannot remove required_files
- Unknown tags ignored with warning
- `experiment_context` tags override `default_task_tags`
- Cycle request profile `builder-build.yaml` loads and validates
- Squad profile `full-squad-with-builder` resolves builder agent

### Phase 2 Exit Criteria

- [ ] `builder-build` cycle request profile validates via schema
- [ ] `full-squad-with-builder` squad profile resolves all 6 agents
- [ ] `static_web_builder` profile loads with correct `required_files`
- [ ] Tag interpolation produces expected prompt content
- [ ] Tags cannot weaken profile `required_files` or `validation_rules`
- [ ] Unknown tags produce warning log (non-fatal)
- [ ] All Phase 2 unit tests pass
- [ ] Full regression suite passes
- [ ] PR merged or updated

---

## Phase 3: Docker Wiring + Reference Deployment

### 3.1 Builder agent container

**Modified file:** `docker-compose.yml`

Add builder container following existing pattern:

```yaml
bob:
  build:
    context: .
    dockerfile: agents/Dockerfile
    args:
      AGENT_ROLE: builder
  container_name: squadops-bob
  environment:
    SQUADOPS__AGENT__NAME: bob
    SQUADOPS__AGENT__ROLE: builder
    # ... standard agent env vars (same as neo/eve/etc.)
```

### 3.2 Build agent package

Validate `build_agent.py builder` succeeds:
- `src/squadops/agents/roles/builder.py` exists
- `src/squadops/agents/skills/builder/` exists (create `__init__.py` with skill exports)

### 3.3 Cycle request profile updates

Update existing `play_game`, `hello_squad`, `group_run` reference apps with builder-aware variants or document how to use `builder-build` profile.

### 3.4 Local bootstrap verification (before Docker)

- Local bootstrap registry test with builder role enabled (no Docker required)
- Dry-run cycle plan generation using `full-squad-with-builder` profile locally

### Phase 3 Exit Criteria

- [ ] `build_agent.py builder` succeeds
- [ ] Local bootstrap with builder role produces no errors
- [ ] Dry-run plan generation emits `builder.build` tasks
- [ ] `docker-compose build bob` succeeds
- [ ] Builder container starts and connects to RabbitMQ
- [ ] Full regression suite passes
- [ ] PR merged or updated

---

## Phase 4: Validation + Documentation

### 4.1 E2E validation

- `play_game` with `builder-build` profile + `full-squad-with-builder` → runnable CLI
- `hello_squad` with `static_web_builder` profile → browser-openable HTML
- `group_run` with `python_cli_builder` or `web_app_builder` profile
- QA handoff artifact present and consumed by `QABuildValidateHandler`
- Routing diagnostics visible in task metadata

### 4.2 Legacy parity

- No config changes required for 5-agent mode
- `development.build` remains the planned and executed build task when builder role absent
- Legacy build path passes existing validation checks and emits expected artifact set (allowing additive diagnostics metadata)
- `play_game` with existing `build` profile + `full-squad` → same behavior as current

### 4.3 Documentation

- Update SIP-0068 docs to reference builder role
- Update CLAUDE.md Agent Squad section (6 agents when builder present)
- Regression suite passes (all existing tests green + new tests)

### 4.4 Version bump

Bump framework version to `0.9.11` to mark the builder role addition:

```bash
python scripts/maintainer/version_cli.py 0.9.11
```

Update `CLAUDE.md` version line (`**Framework Version**: 0.9.11`).

### 4.5 SIP promotion

After all E2E validation passes:
```bash
SQUADOPS_MAINTAINER=1 python scripts/maintainer/update_sip_status.py \
    sips/accepted/SIP-0071-Builder-Role-Dedicated-Product.md implemented
```

### Phase 4 Exit Criteria

- [ ] At least one E2E cycle completes with `builder.build` producing runnable artifacts
- [ ] QA handoff consumed by `QABuildValidateHandler` without reverse-engineering
- [ ] Legacy 5-agent cycle passes with zero config changes
- [ ] Routing diagnostics visible in Prefect/task metadata
- [ ] CLAUDE.md and SIP-0068 docs updated
- [ ] Framework version bumped to 0.9.11
- [ ] Full regression suite passes
- [ ] SIP-0071 promoted to implemented
- [ ] Final PR merged to main

---

## Files Summary

### New Files

| File | Purpose |
|------|---------|
| `src/squadops/agents/roles/builder.py` | BuilderAgent class |
| `src/squadops/capabilities/handlers/build_profiles.py` | BuildProfile dataclass + registry + QA handoff constants + routing constants |
| `src/squadops/agents/skills/builder/__init__.py` | Builder skill exports |
| `src/squadops/contracts/cycle_request_profiles/profiles/builder-build.yaml` | Cycle request profile |
| `tests/unit/capabilities/test_builder_build_handler.py` | Handler tests (positive + negative) |
| `tests/unit/capabilities/test_build_profiles.py` | Profile registry tests |
| `tests/unit/agents/roles/test_builder_agent.py` | Agent class tests |

### Modified Files

| File | Change | 5-agent behavior preserved? |
|------|--------|-----------------------------|
| `src/squadops/agents/models.py` | Add `BUILDER_ROLE` + `DEFAULT_ROLES` entry | Yes — additive |
| `src/squadops/agents/roles/__init__.py` | Import + export `BuilderAgent` | Yes — additive |
| `src/squadops/capabilities/handlers/cycle_tasks.py` | Add `BuilderBuildHandler` class | Yes — new class, no existing code changed |
| `src/squadops/cycles/models.py` | Add `ArtifactType.QA_HANDOFF` | Yes — additive constant |
| `src/squadops/cycles/task_plan.py` | Builder-aware routing + `BUILDER_BUILD_TASK_STEPS` | Yes — fallback path is existing `BUILD_TASK_STEPS` |
| `src/squadops/bootstrap/handlers.py` | Register `BuilderBuildHandler`, add builder to warmboot | Yes — additive registration |
| `src/squadops/contracts/cycle_request_profiles/schema.py` | Add `"build_profile"` to extra keys | Yes — additive key |
| `adapters/cycles/distributed_flow_executor.py` | Add `"builder.build"` to `_BUILD_ARTIFACT_FILTER` | Yes — new entry, existing entries unchanged |
| `config/squad-profiles.yaml` | Add `full-squad-with-builder` profile | Yes — existing `full-squad` unchanged |
| `docker-compose.yml` | Add `bob` container (Phase 3) | Yes — additive service |
| `tests/unit/cycles/test_task_plan.py` | Builder routing tests | Yes — existing tests unchanged |
| `tests/unit/bootstrap/test_handler_bootstrap.py` | Builder handler + legacy handler parity | Yes — existing tests unchanged |
| `tests/unit/agents/test_agent_models.py` | Builder role in DEFAULT_ROLES | Yes — existing tests unchanged |

### Non-Goals (V1)

- External profile authoring UX (YAML/JSON profile loading from user-supplied files)
- Multi-builder load balancing or selection policy
- Profile versioning or migration tooling

### Unchanged

- `Cycle`, `Run`, `Gate` domain models — no schema changes
- `CycleCreateRequest` DTO — `build_profile` flows through `applied_defaults`
- Existing `DevelopmentBuildHandler` — untouched, used as fallback
- Existing `full-squad` profile — unchanged
- Existing cycle request profiles (`selftest`, `build`, `build-only`) — unchanged

---

## Verification

```bash
# 1. Unit tests pass
pytest tests/unit/capabilities/test_builder_build_handler.py -v
pytest tests/unit/capabilities/test_build_profiles.py -v
pytest tests/unit/agents/roles/test_builder_agent.py -v
pytest tests/unit/cycles/test_task_plan.py -v

# 2. Full regression suite
./scripts/dev/run_new_arch_tests.sh -v

# 3. Builder role registered
python -c "from squadops.agents.models import DEFAULT_ROLES; assert 'builder' in DEFAULT_ROLES"

# 4. Handler registered (builder + legacy parity)
python -c "
from squadops.bootstrap.handlers import create_handler_registry
r = create_handler_registry()
caps = r.list_capabilities()
assert 'builder.build' in caps, 'builder.build not registered'
assert 'development.build' in caps, 'development.build lost (regression!)'
"

# 5. Build profile loads
python -c "from squadops.capabilities.handlers.build_profiles import get_profile; p = get_profile('python_cli_builder'); assert 'main.py' in p.required_files"

# 6. Plan-generation routing — assert actual emitted task types (D5 verification)
python -c "
from squadops.cycles.task_plan import generate_task_plan, _has_builder_role
from squadops.cycles.models import Cycle, Run, SquadProfile, SquadAgent
# With builder
profile_with = SquadProfile(profile_id='test', agents=[
    SquadAgent(agent_id='bob', role='builder', enabled=True),
    SquadAgent(agent_id='neo', role='dev', enabled=True),
], name='test', version=1)
# Without builder
profile_without = SquadProfile(profile_id='test', agents=[
    SquadAgent(agent_id='neo', role='dev', enabled=True),
], name='test', version=1)
assert _has_builder_role(profile_with), 'builder should be detected'
assert not _has_builder_role(profile_without), 'no builder should mean fallback'
# Assert actual emitted task types in plan
plan_with = generate_task_plan(profile=profile_with, include_build=True)
task_types_with = [step[0] for step in plan_with]
assert 'builder.build' in task_types_with, 'builder.build must appear in plan'
assert 'development.build' not in task_types_with, 'development.build must NOT appear when builder present'
plan_without = generate_task_plan(profile=profile_without, include_build=True)
task_types_without = [step[0] for step in plan_without]
assert 'development.build' in task_types_without, 'development.build must appear in fallback plan'
assert 'builder.build' not in task_types_without, 'builder.build must NOT appear without builder'
print('D5 routing verified — emitted task types match')
"
# NOTE: Adjust field access (step[0] vs step.task_type) for actual
# generate_task_plan() return shape while preserving the same assertions.
```
