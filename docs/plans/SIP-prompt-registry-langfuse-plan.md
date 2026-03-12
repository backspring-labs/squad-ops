# Implementation Plan: SIP — Prompt Registry Integration Using Langfuse

## Overview

Extend the SIP-0057 prompt system with Langfuse-backed governed prompt asset storage, adding request template externalization and multi-stage provenance tracking.

**Extends**: SIP-0057 (Hexagonal Layered Prompt System)
**Target**: v1.0.1

## Not In Scope

The following are explicitly excluded from this implementation:

- No A/B prompt experimentation or evaluation pipelines
- No mid-cycle asset refresh
- No registry-driven execution semantics
- No handler logic encoded in prompt assets
- No workload routing, retry policy, or task sequencing in templates
- No governed capability supplement management (future extension)

---

## Architecture Context

### Existing Prompt System (SIP-0057)

The current system has a clean three-layer architecture:

1. **Port**: `PromptRepository` (`src/squadops/ports/prompts/repository.py`) — abstract contract for fragment storage with `get_fragment()`, `fragment_exists()`, `get_manifest()`, `list_fragments()`, `validate_integrity()`
2. **Domain**: `PromptAssembler` (`src/squadops/prompts/assembler.py`) — deterministic 5-layer assembly (identity → constraints → lifecycle → task_type → recovery), implements `PromptService` port
3. **Adapter**: `FilesystemPromptRepository` — reads `.md` fragments from `src/squadops/prompts/fragments/`

**Key types**:
- `PromptFragment` — frozen dataclass with `fragment_id`, `content`, `sha256_hash`, `layer`, `role`
- `AssembledPrompt` — frozen dataclass with `content`, `fragment_hashes`, `assembly_hash`, `role`, `hook`, `version`
- `PromptManifest` — version + fragment metadata index

**Current fragment inventory**: 21 `.md` files (5 role-specific identity, 1 shared identity, 1 constraints, 2 lifecycle, 12 task_type)

### Current Request Construction

32 handlers build requests inline via handler methods:

| Base Class | Location | Signature | Handlers |
|---|---|---|---|
| `_CycleTaskHandler` | `cycle_tasks.py:72` | `(prd, prior_outputs)` | 5 |
| `_PlanningTaskHandler` | `planning_tasks.py:103` | `(prd, prior_outputs, time_budget_seconds)` | 14 |
| `_RepairTaskHandler` | `repair_tasks.py:20` | `(prd, prior_outputs)` | 4 |
| Custom inline | various | handler-specific | 9 |

Notable custom handlers:
- `DevelopmentDevelopHandler` (cycle_tasks.py:383) — adds `impl_plan`, `strategy`, capability file structure
- `QATestHandler` (cycle_tasks.py:739) — adds validation plan, source files, test supplement
- `BuilderAssembleHandler` (cycle_tasks.py:1243) — fully inline in `handle()`, no method override
- `GovernanceIncorporateFeedbackHandler` (planning_tasks.py:409) — adds original artifact + refinement instructions
- SIP-0079 handlers (`impl/analyze_failure.py`, `impl/correction_decision.py`, `impl/establish_contract.py`) — inline construction

### Handler DI Wiring

Handlers receive `ExecutionContext` which carries `ports: PortsBundle`. `PortsBundle` (defined in `src/squadops/agents/base.py`) includes `prompt_service: PromptService`. The `PromptAssetSourcePort` will be added to `PortsBundle` so handlers can resolve request templates.

### ArtifactRef (provenance target)

`ArtifactRef` (`src/squadops/cycles/models.py:306`) — frozen dataclass with 13 fields. New provenance fields will be added as optional with `None` defaults.

---

## Phased Implementation

### Phase 1: PromptAssetSourcePort and Adapters

**Goal**: Introduce the new port and adapters without changing any existing behavior. The port serves two distinct retrieval paths — system fragment retrieval for deterministic assembly, and request template retrieval for handler-side rendering — through a unified interface. These are separate operations with different semantics: system fragments feed into SIP-0057's deterministic layer assembly; request templates are resolved independently by handlers for Stage 2 rendering. They must not be treated as interchangeable.

#### Files to create

| File | Purpose |
|---|---|
| `src/squadops/ports/prompts/asset_source.py` | `PromptAssetSourcePort` ABC |
| `adapters/prompts/__init__.py` | Adapter package |
| `adapters/prompts/langfuse_asset_adapter.py` | `LangfusePromptAssetAdapter` |
| `adapters/prompts/filesystem_asset_adapter.py` | `FilesystemPromptAssetAdapter` (wraps existing `PromptRepository`) |
| `adapters/prompts/factory.py` | Factory for selecting adapter by config |

#### PromptAssetSourcePort design

```python
class PromptAssetSourcePort(ABC):
    """Pluggable backend for retrieving governed prompt assets.

    Serves two distinct retrieval paths:
    - System fragment retrieval: feeds SIP-0057 deterministic layered assembly
    - Request template retrieval: feeds handler-side rendering (Stage 2)

    These are separate operations. System fragments are composed deterministically
    by the PromptAssembler. Request templates are resolved and rendered by handlers.
    """

    @abstractmethod
    async def resolve_system_fragment(
        self, fragment_id: str, role: str | None = None, environment: str = "production"
    ) -> ResolvedAsset: ...

    @abstractmethod
    async def resolve_request_template(
        self, template_id: str, environment: str = "production"
    ) -> ResolvedAsset: ...

    @abstractmethod
    async def get_asset_version(self, asset_id: str) -> AssetVersionInfo | None: ...
```

```python
@dataclass(frozen=True)
class ResolvedAsset:
    """A governed prompt asset resolved from the registry."""
    asset_id: str
    content: str
    version: str
    environment: str
    content_hash: str  # SHA256

@dataclass(frozen=True)
class AssetVersionInfo:
    asset_id: str
    version: str
    environment: str
    updated_at: datetime | None = None
```

#### LangfusePromptAssetAdapter design

- Lazy-import `langfuse` SDK in `__init__` (matches existing adapter pattern)
- Use Langfuse prompt management API: `langfuse.get_prompt(name, label=environment)`
- Return normalized `ResolvedAsset` with computed SHA256 hash
- Config via `SQUADOPS__PROMPTS__PROVIDER` (values: `filesystem`, `langfuse`)
- LangFuse connection config reuses existing `SQUADOPS__LANGFUSE__*` env vars

#### FilesystemPromptAssetAdapter design

- Wraps the existing `PromptRepository` for system fragment retrieval
- For request templates: reads from a new `src/squadops/prompts/request_templates/` directory
- Template files follow naming convention: `request.{handler_class}.{task_type}.md`
- This adapter is the **default** — all deployments use it unless explicitly switched to Langfuse

#### Fallback behavior

Three distinct modes must be clearly separated:

| Mode | When | Behavior |
|---|---|---|
| Default adapter | Migration period, or no Langfuse configured | Filesystem adapter serves all assets; Langfuse not involved |
| Explicit disaster recovery | Operator sets `SQUADOPS__PROMPTS__PROVIDER=filesystem` after prior Langfuse use | Filesystem adapter serves from last-known-good local copies; logged as recovery mode |
| Silent operational fallback | **NOT ALLOWED** | If Langfuse is configured as provider and unavailable at startup, the cycle fails. No silent downgrade to filesystem. |

#### Tests (~25)

- `tests/unit/prompts/test_asset_source_port.py` — port contract tests
- `tests/unit/prompts/test_filesystem_asset_adapter.py` — filesystem adapter with temp dirs
- `tests/unit/prompts/test_langfuse_asset_adapter.py` — mock SDK, lazy import pattern (follows telemetry adapter test style)
- `tests/unit/prompts/test_asset_factory.py` — factory selection by config, no-silent-fallback test

---

### Phase 2: Request Template Extraction, Rendering, and Contract Validation

**Goal**: Extract inline request templates from handlers into governed template files. Introduce a `RequestTemplateRenderer` that resolves templates through the port and injects runtime variables. Establish template-contract validation as a first-class correctness mechanism.

#### Step 2a: Template inventory and extraction

Catalog every handler's request construction, identify the template skeleton vs. runtime payload, and extract templates as `.md` files with `{{placeholder}}` variables.

**Base class templates** (3 templates, high reuse):

| Template ID | Source | Placeholders |
|---|---|---|
| `request.cycle_task_base` | `_CycleTaskHandler` handler method | `{{prd}}`, `{{prior_outputs}}`, `{{role}}` |
| `request.planning_task_base` | `_PlanningTaskHandler` handler method | `{{prd}}`, `{{prior_outputs}}`, `{{role}}`, `{{time_budget_section}}` |
| `request.repair_task_base` | `_RepairTaskHandler` handler method | `{{prd}}`, `{{prior_outputs}}`, `{{role}}`, `{{verification_context}}` |

**Custom handler templates** (~12 templates):

| Template ID | Source | Additional Placeholders |
|---|---|---|
| `request.development_develop.code_generate` | `DevelopmentDevelopHandler` | `{{impl_plan}}`, `{{strategy}}`, `{{file_structure_guidance}}`, `{{example_structure}}` |
| `request.qa_test.test_validate` | `QATestHandler` | `{{validation_plan}}`, `{{source_files}}`, `{{test_supplement}}` |
| `request.builder_assemble.build_assemble` | `BuilderAssembleHandler` | `{{source_files}}`, `{{task_tags}}`, `{{assembly_instructions}}` |
| `request.governance_incorporate_feedback` | `GovernanceIncorporateFeedbackHandler` | `{{original_artifact}}`, `{{refinement_notes}}` |
| `request.data_analyze_failure` | `DataAnalyzeFailureHandler` | `{{failure_evidence}}` |
| `request.governance_correction_decision` | `GovernanceCorrectionDecisionHandler` | `{{failure_analysis}}` |
| `request.governance_establish_contract` | `GovernanceEstablishContractHandler` | (uses base template) |
| (+ remaining wrapup/repair handlers that use base templates) | | |

**Estimated total**: ~15–20 request template files.

Template files stored at: `src/squadops/prompts/request_templates/{template_id}.md`

#### Step 2b: Template Contract Validation

Each request template declares its required and optional placeholders via a frontmatter block:

```yaml
---
template_id: request.development_develop.code_generate
required_variables:
  - prd
  - prior_outputs
  - role
  - impl_plan
  - file_structure_guidance
  - example_structure
optional_variables:
  - strategy
---
```

The `RequestTemplateRenderer` enforces these contracts at render time:

- **Missing required variable** → raise `TemplateMissingVariableError` with the variable name and template identity
- **Unknown variable** (not declared in required or optional) → log a warning, do not inject (detect handler drift)
- **Unused optional variable** → silently skip (no error)

Contract validation is tested per-template in the unit test suite.

#### Step 2c: RequestTemplateRenderer

```python
class RequestTemplateRenderer:
    """Resolves governed request templates and renders with runtime variables.

    This component handles Stage 2 of the prompt pipeline: request template
    rendering. It does NOT participate in Stage 1 (system prompt assembly),
    which remains owned by the PromptAssembler.
    """

    def __init__(self, asset_source: PromptAssetSourcePort):
        self._source = asset_source
        self._cache: dict[str, ResolvedAsset] = {}

    async def render(
        self,
        template_id: str,
        variables: dict[str, str],
        environment: str = "production",
    ) -> RenderedRequest:
        """Resolve template, validate contract, inject runtime variables."""
        ...
```

```python
@dataclass(frozen=True)
class RenderedRequest:
    """A fully rendered request with provenance."""
    content: str
    template_id: str
    template_version: str
    render_hash: str  # SHA256 of final rendered content
```

**Rendering rules**:
- Simple `{{variable}}` substitution (no logic, no conditionals)
- Contract validation enforced before rendering (required/optional/unknown)
- Prior analysis section must be LAST (enforced by template structure, validated by tests)

#### Step 2d: Add to PortsBundle and ExecutionContext

Add `request_renderer: RequestTemplateRenderer` to `PortsBundle`. Wire in `BaseAgent.__init__`.

#### Tests (~40)

- `tests/unit/prompts/test_request_template_renderer.py` — rendering, variable injection, contract validation (missing required, unknown variable warning, optional skip)
- `tests/unit/prompts/test_request_template_contracts.py` — one test per extracted template verifying declared variables match handler usage, prior-analysis-last constraint
- Template extraction parity tests: render each template with known inputs and compare output against current handler output (regression guard)

---

### Phase 3: Handler Refactoring

**Goal**: Refactor handlers to resolve request templates through the renderer instead of constructing requests inline. Zero behavioral change — rendered output must match current output exactly.

#### Migration sequence (controlled blast radius)

Migration proceeds in 3 waves, not a single sweep:

**Wave 1 — Prove the pattern (1 base class + 1 custom handler)**

1. Migrate `_CycleTaskHandler` base class (5 handlers) to use `request.cycle_task_base` template
2. Migrate `DevelopmentDevelopHandler` (custom template + capability supplement) to prove custom handler pattern
3. Run full parity tests for Wave 1 handlers
4. Run regression suite — must pass before proceeding

**Wave 2 — Extend to remaining base classes**

5. Migrate `_PlanningTaskHandler` base class (14 handlers including wrapup) to use `request.planning_task_base` template
6. Migrate `_RepairTaskHandler` base class (4 handlers) to use `request.repair_task_base` template
7. Run parity tests for Wave 2 handlers
8. Run regression suite

**Wave 3 — Custom handlers**

9. Migrate remaining custom handlers in order:
   - `QATestHandler`
   - `GovernanceIncorporateFeedbackHandler`
   - SIP-0079 inline handlers (`analyze_failure`, `correction_decision`, `establish_contract`)
   - `BuilderAssembleHandler` (most complex, last)
10. Run parity tests for Wave 3 handlers
11. Run regression suite

#### Refactoring pattern

**Before** (current):
```python
def _build_user_prompt(self, prd, prior_outputs):
    parts = [f"## Product Requirements Document\n\n{prd}"]
    if prior_outputs:
        parts.append("\n\n## Prior Analysis from Upstream Roles\n")
        for role, summary in prior_outputs.items():
            parts.append(f"### {role}\n{summary}\n")
    parts.append(f"\nPlease provide your {self._role} analysis and deliverables.")
    return "\n".join(parts)
```

**After**:
```python
async def _build_request(self, prd, prior_outputs):
    prior_section = ""
    if prior_outputs:
        prior_section = "\n\n## Prior Analysis from Upstream Roles\n"
        for role, summary in prior_outputs.items():
            prior_section += f"### {role}\n{summary}\n"
    rendered = await context.ports.request_renderer.render(
        template_id="request.cycle_task_base",
        variables={"prd": prd, "prior_outputs": prior_section, "role": self._role},
    )
    return rendered.content
```

#### Capability supplement handling

Capability supplements (`capability.system_prompt_supplement`, `capability.test_prompt_supplement`, `profile.system_prompt_template`) remain handler-attached runtime content. They are NOT moved to the registry. Handlers continue to append them to the system prompt at call time:

```python
system_prompt = assembled.content + "\n\n" + capability.system_prompt_supplement
```

No change to this pattern.

#### Tests (~20)

- Parity tests per handler: call `handle()` with identical inputs before and after refactoring, assert identical LLM messages
- Verify prompt guard truncation still works on rendered output
- Verify capability supplements are still appended correctly

---

### Phase 3.5: Request Template Migration Validation Gate

**Goal**: Dedicated validation checkpoint after handler refactoring and before provenance work. Phase 3 is the most behaviorally sensitive step — it deserves its own gate.

#### Validation checklist

| Check | Method | Pass Criteria |
|---|---|---|
| Placeholder completeness | Contract validation tests from Phase 2 | All required variables declared and populated by handler |
| Render snapshot parity | Side-by-side comparison of pre/post refactoring output | Byte-identical rendered requests for identical inputs |
| Prior-analysis ordering | Template structure tests | `## Prior Analysis` heading is always the last section |
| Prompt guard preservation | Truncation tests on rendered output | Guard truncates from prior analysis heading, same as before |
| Capability supplement attachment | Handler-level tests | Supplements still appended to system prompt, not injected into templates |
| Unknown variable detection | Renderer warning tests | Warning logged if handler passes variable not in contract |
| Base class coverage | Parity tests across all 3 base hierarchies | All 23 base-class handlers produce identical output |
| Custom handler coverage | Parity tests for all 9 custom handlers | All custom handlers produce identical output |
| Regression suite | `run_regression_tests.sh` | 3032+ tests pass, 0 failures |

**Gate rule**: Do not proceed to Phase 4 until all checks pass. If any handler produces different output after refactoring, fix the template or the handler — do not proceed with a behavioral delta.

#### Tests (~10, in addition to Phase 3 tests)

- `tests/unit/prompts/test_migration_validation.py` — comprehensive snapshot tests for representative handlers from each wave
- Template contract coverage test: verify every template has a contract, every contract lists all required variables

---

### Phase 4: Prompt Asset Caching and Cycle Immutability

**Goal**: Add per-cycle caching and the cycle immutability rule.

#### Cycle Immutability Rule

- Once a cycle starts, the resolved governed asset versions for that cycle are fixed
- Later label promotions or asset changes in Langfuse only affect subsequent cycles
- The platform must not re-resolve assets mid-cycle even if environment labels change in the registry
- If mid-cycle refresh is needed in the future, it must be introduced by explicit design with its own governance model (see SIP Section 17)

#### CyclePromptCache

```python
class CyclePromptCache:
    """Per-cycle cache for resolved prompt assets. Immutable once sealed.

    Enforces cycle-level asset immutability: all governed assets are resolved
    eagerly at cycle startup, then the cache is sealed. No further resolution
    occurs for the remainder of the cycle.
    """

    def __init__(self):
        self._fragments: dict[str, ResolvedAsset] = {}
        self._templates: dict[str, ResolvedAsset] = {}
        self._sealed: bool = False

    def seal(self) -> None:
        """Seal the cache — no further resolution after this point."""
        self._sealed = True

    def get_or_resolve(self, asset_id: str, resolver: Callable) -> ResolvedAsset:
        """Return cached asset or resolve and cache. Raises if sealed and missing."""
        ...
```

#### Integration points

- `DistributedFlowExecutor.execute_cycle()` creates a `CyclePromptCache` at cycle start
- All required assets are resolved eagerly during cycle startup (fail-fast)
- Cache is sealed after startup resolution
- Cache is passed through `ExecutionContext` to handlers
- Cache is discarded at cycle end

#### Resilience

- Langfuse configured but unavailable at startup → cycle fails with `PromptRegistryUnavailableError`. No silent downgrade to filesystem.
- Langfuse becomes unavailable mid-cycle → cached assets serve; log warning (assets already resolved and sealed)
- Asset not found in registry → `PromptAssetNotFoundError` with asset identity in message
- Timeout: configurable via `SQUADOPS__PROMPTS__RESOLVE_TIMEOUT_SECONDS` (default: 10)

#### Tests (~15)

- Cache seal behavior (resolve before seal, reject after seal)
- Startup failure propagation (Langfuse configured but down → cycle fails, not silent fallback)
- Mid-cycle resilience (mock Langfuse going down after cache populated and sealed)
- Timeout behavior
- Cycle immutability: verify same asset version served throughout cycle even if registry changes

---

### Phase 5: Provenance Integration

**Goal**: Add provenance fields to `ArtifactRef`, tracked as two distinct concerns: system prompt assembly provenance and request template render provenance.

#### Two Provenance Concerns

Provenance is captured and stored as two separate records, not a single "prompt bundle":

1. **System prompt assembly provenance** — which fragments were assembled, in what versions, producing what hash. This is the SIP-0057 deterministic assembly lineage.
2. **Request template render provenance** — which template was resolved, in what version, producing what rendered hash. This is the Stage 2 rendering lineage.

These are independent and must be analyzable independently for RCA, replay, and experiment comparison. When investigating a cycle outcome, the asset identifier plus version plus rendered hash gives a complete picture.

#### ArtifactRef changes

Add optional fields to `ArtifactRef` (`src/squadops/cycles/models.py`):

```python
# System prompt assembly provenance (Stage 1)
system_prompt_bundle_hash: str | None = None
system_fragment_ids: tuple[str, ...] | None = None
system_fragment_versions: tuple[str, ...] | None = None

# Request template render provenance (Stage 2)
request_template_id: str | None = None
request_template_version: str | None = None
request_render_hash: str | None = None

# Invocation composition (Stage 3 — runtime, not governed)
capability_supplement_ids: tuple[str, ...] | None = None
full_invocation_bundle_hash: str | None = None

# Environment
prompt_environment: str | None = None
```

All default to `None` for backward compatibility.

#### Handler provenance recording

After LLM invocation, handlers record provenance on the produced artifact:

```python
artifact = dataclasses.replace(
    artifact,
    # Stage 1: system prompt assembly
    system_prompt_bundle_hash=assembled.assembly_hash,
    system_fragment_ids=tuple(f.fragment_id for f in ...),
    system_fragment_versions=tuple(f.version for f in ...),
    # Stage 2: request template rendering
    request_template_id=rendered.template_id,
    request_template_version=rendered.template_version,
    request_render_hash=rendered.render_hash,
    # Environment
    prompt_environment=environment,
)
```

#### Downstream changes

- `FilesystemArtifactVault` — serialize/deserialize new fields in metadata.json
- `PostgresCycleRegistry` — DDL migration adding nullable columns to `artifacts` table
- API DTOs — include provenance fields in artifact response DTOs
- CLI `artifacts list` — no change needed (fields are metadata, not display columns)

#### Tests (~20)

- ArtifactRef round-trip with provenance fields
- Vault store/retrieve with provenance
- Postgres migration test
- API DTO mapping with provenance fields
- Handler provenance recording (at least one handler end-to-end)
- Verify Stage 1 and Stage 2 provenance are independently queryable

---

### Phase 6: Langfuse Prompt Upload and Validation

**Goal**: Upload all governed assets to Langfuse, validate round-trip, run E2E cycles.

#### Upload script

Create `scripts/maintainer/upload_prompts_to_langfuse.py`:

- Reads all system fragments from `src/squadops/prompts/fragments/`
- Reads all request templates from `src/squadops/prompts/request_templates/`
- Uploads each to Langfuse via prompt management API
- Applies naming convention from SIP Section 9
- Sets initial environment label to `production`
- Reports upload summary with asset count, version, and content hash

#### E2E validation

- Run a full `play_game` cycle with `--request-profile selftest` using Langfuse-backed prompt resolution
- Verify artifacts contain both Stage 1 and Stage 2 provenance fields
- Verify cached assets survive simulated Langfuse downtime mid-cycle
- Compare cycle output against a baseline cycle run with filesystem-backed prompts (regression check)
- Verify cycle immutability: change a prompt in Langfuse mid-cycle, confirm running cycle still uses original version

#### Tests (~5)

- Upload script dry-run test
- Round-trip: upload → resolve → compare content hash

---

## File Inventory

### New files

| File | Phase | Purpose |
|---|---|---|
| `src/squadops/ports/prompts/asset_source.py` | 1 | `PromptAssetSourcePort` ABC |
| `src/squadops/prompts/models.py` (extend) | 1 | `ResolvedAsset`, `AssetVersionInfo`, `RenderedRequest` |
| `adapters/prompts/__init__.py` | 1 | Package init |
| `adapters/prompts/langfuse_asset_adapter.py` | 1 | LangFuse adapter |
| `adapters/prompts/filesystem_asset_adapter.py` | 1 | Filesystem adapter |
| `adapters/prompts/factory.py` | 1 | Provider factory |
| `src/squadops/prompts/request_templates/*.md` | 2 | ~15–20 template files with frontmatter contracts |
| `src/squadops/prompts/renderer.py` | 2 | `RequestTemplateRenderer` with contract validation |
| `src/squadops/prompts/cache.py` | 4 | `CyclePromptCache` with seal/immutability |
| `infra/migrations/NNNN_add_prompt_provenance.sql` | 5 | DDL for provenance columns |
| `scripts/maintainer/upload_prompts_to_langfuse.py` | 6 | Upload script |

### Modified files

| File | Phase | Change |
|---|---|---|
| `src/squadops/agents/base.py` | 2 | Add `request_renderer` to `PortsBundle` |
| `src/squadops/capabilities/handlers/cycle_tasks.py` | 3 | Refactor handler methods → template resolution |
| `src/squadops/capabilities/handlers/planning_tasks.py` | 3 | Refactor handler methods → template resolution |
| `src/squadops/capabilities/handlers/repair_tasks.py` | 3 | Refactor handler methods → template resolution |
| `src/squadops/capabilities/handlers/impl/*.py` | 3 | Refactor inline construction → template resolution |
| `src/squadops/capabilities/handlers/wrapup_tasks.py` | 3 | Inherits planning base refactor |
| `src/squadops/cycles/models.py` | 5 | Add provenance fields to `ArtifactRef` |
| `adapters/cycles/filesystem_artifact_vault.py` | 5 | Serialize/deserialize provenance |
| `adapters/cycles/postgres_cycle_registry.py` | 5 | Query/persist provenance columns |
| `src/squadops/api/dtos/cycles.py` | 5 | Add provenance to artifact DTOs |
| `adapters/cycles/distributed_flow_executor.py` | 4 | Create cache at cycle start, pass via context |

### Test files

| File | Phase | Est. Tests |
|---|---|---|
| `tests/unit/prompts/test_asset_source_port.py` | 1 | 8 |
| `tests/unit/prompts/test_filesystem_asset_adapter.py` | 1 | 8 |
| `tests/unit/prompts/test_langfuse_asset_adapter.py` | 1 | 6 |
| `tests/unit/prompts/test_asset_factory.py` | 1 | 4 |
| `tests/unit/prompts/test_request_template_renderer.py` | 2 | 15 |
| `tests/unit/prompts/test_request_template_contracts.py` | 2 | 20 |
| `tests/unit/prompts/test_handler_parity.py` | 3 | 20 |
| `tests/unit/prompts/test_migration_validation.py` | 3.5 | 10 |
| `tests/unit/prompts/test_cycle_prompt_cache.py` | 4 | 12 |
| `tests/unit/prompts/test_cache_resilience.py` | 4 | 5 |
| `tests/unit/cycles/test_artifact_provenance.py` | 5 | 20 |
| `tests/unit/prompts/test_upload_script.py` | 6 | 5 |
| **Total** | | **~133** |

---

## Verification

After each phase:
- Regression suite passes (3032+ tests)
- `ruff check .` clean
- No behavioral change to LLM outputs until Phase 3 handler refactoring (which must be parity-tested)

After Phase 3.5 (migration validation gate):
- All parity tests pass across all 3 waves
- Template contract validation passes for all templates
- Prompt guard behavior verified
- Prior-analysis ordering verified

After Phase 6:
- Full `play_game` cycle succeeds with Langfuse-backed prompts
- Artifacts contain both Stage 1 and Stage 2 provenance metadata
- Prompt update in Langfuse → new cycle picks up new version without redeployment
- Mid-cycle Langfuse change does NOT affect running cycle (immutability verified)
- `docker compose config | grep SQUADOPS__PROMPTS` shows provider config

---

## Key Design Decisions

| ID | Decision | Rationale |
|---|---|---|
| D1 | `PromptAssetSourcePort` serves both fragments and templates via separate methods | Single retrieval abstraction; separate methods preserve semantic distinction |
| D2 | `PromptRepository` (SIP-0057) is NOT replaced | `FilesystemPromptAssetAdapter` wraps it; existing `PromptAssembler` unchanged |
| D3 | Simple `{{variable}}` substitution, no template logic | Request templates define structure, not behavior; keeps templates declarative |
| D4 | Capability supplements stay handler-owned | Not governed assets per SIP Section 1.3; avoids registry scope creep |
| D5 | Cache sealed after cycle startup | Cycle immutability rule from SIP Section 8 |
| D6 | Fail-at-start, not silent fallback | Missing assets = broken cycle; never mask with stale data; never silently downgrade to filesystem |
| D7 | Provenance fields optional on ArtifactRef | Backward compat with pre-1.0.1 artifacts (D19 pattern from SIP-0076) |
| D8 | Phase 3 uses 3-wave migration | Controlled blast radius; prove pattern on 1 base + 1 custom before wider rollout |
| D9 | Filesystem adapter is default, Langfuse opt-in | Safe rollout; existing deployments unaffected until explicitly switched |
| D10 | Request templates stored alongside fragments | `src/squadops/prompts/request_templates/` — colocated, same package |
| D11 | Template contracts declared in frontmatter | Required/optional variables validated at render time; catches handler drift |
| D12 | Provenance tracked as two distinct concerns | System assembly and request rendering are independently analyzable for RCA/replay |
| D13 | Phase 3.5 validation gate before provenance work | Most behaviorally sensitive phase gets its own checkpoint |
