# Implementation Plan: SIP — Prompt Registry Integration Using Langfuse

## Overview

Extend the SIP-0057 prompt system with Langfuse-backed governed prompt asset storage, adding request template externalization and multi-stage provenance tracking.

**Extends**: SIP-0057 (Hexagonal Layered Prompt System)
**Target**: v1.0.1

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

32 handlers build requests inline via `_build_user_prompt()` methods:

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

### Phase 1: PromptAssetSourcePort and LangfusePromptAssetAdapter

**Goal**: Introduce the new port and adapter without changing any existing behavior. System prompt fragment retrieval continues via `PromptRepository` unchanged.

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
    """Pluggable backend for retrieving governed prompt assets."""

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
- This adapter is the default and the fallback

#### Tests (~25)

- `tests/unit/prompts/test_asset_source_port.py` — port contract tests
- `tests/unit/prompts/test_filesystem_asset_adapter.py` — filesystem adapter with temp dirs
- `tests/unit/prompts/test_langfuse_asset_adapter.py` — mock SDK, lazy import pattern (follows telemetry adapter test style)
- `tests/unit/prompts/test_asset_factory.py` — factory selection by config

---

### Phase 2: Request Template Extraction and Rendering

**Goal**: Extract inline request templates from handlers into governed template files. Introduce a `RequestTemplateRenderer` that resolves templates through the port and injects runtime variables.

#### Step 2a: Template inventory and extraction

Catalog every handler's request construction, identify the template skeleton vs. runtime payload, and extract templates as `.md` files with `{{placeholder}}` variables.

**Base class templates** (3 templates, high reuse):

| Template ID | Source | Placeholders |
|---|---|---|
| `request.cycle_task_base` | `_CycleTaskHandler._build_user_prompt` | `{{prd}}`, `{{prior_outputs}}`, `{{role}}` |
| `request.planning_task_base` | `_PlanningTaskHandler._build_user_prompt` | `{{prd}}`, `{{prior_outputs}}`, `{{role}}`, `{{time_budget_section}}` |
| `request.repair_task_base` | `_RepairTaskHandler._build_user_prompt` | `{{prd}}`, `{{prior_outputs}}`, `{{role}}`, `{{verification_context}}` |

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

#### Step 2b: RequestTemplateRenderer

```python
class RequestTemplateRenderer:
    """Resolves governed request templates and renders with runtime variables."""

    def __init__(self, asset_source: PromptAssetSourcePort):
        self._source = asset_source
        self._cache: dict[str, ResolvedAsset] = {}

    async def render(
        self,
        template_id: str,
        variables: dict[str, str],
        environment: str = "production",
    ) -> RenderedRequest:
        """Resolve template and inject runtime variables."""
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
- Missing required variables raise `TemplateMissingVariableError`
- Extra variables are silently ignored
- Prior analysis section must be LAST (enforced by template structure, validated by tests)

#### Step 2c: Add to PortsBundle and ExecutionContext

Add `request_renderer: RequestTemplateRenderer` to `PortsBundle`. Wire in `BaseAgent.__init__`.

#### Tests (~35)

- `tests/unit/prompts/test_request_template_renderer.py` — rendering, variable injection, missing var errors
- `tests/unit/prompts/test_request_templates/` — one test per extracted template verifying structure, required variables, prior-analysis-last constraint
- Template extraction parity tests: render each template with known inputs and compare output against current handler `_build_user_prompt()` output (regression guard)

---

### Phase 3: Handler Refactoring

**Goal**: Refactor handlers to resolve request templates through the renderer instead of constructing requests inline. Zero behavioral change — rendered output must match current output exactly.

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

#### Refactoring order (by risk, low to high)

1. **5 basic `_CycleTaskHandler` subclasses** — use base template, simplest change
2. **14 `_PlanningTaskHandler` subclasses** (including 5 wrapup) — base template + time budget
3. **4 `_RepairTaskHandler` subclasses** — base template + verification context
4. **`GovernanceIncorporateFeedbackHandler`** — custom template
5. **`DevelopmentDevelopHandler`** — custom template + capability supplement
6. **`QATestHandler`** — custom template + capability supplement
7. **SIP-0079 inline handlers** (`analyze_failure`, `correction_decision`, `establish_contract`) — custom templates
8. **`BuilderAssembleHandler`** — fully inline, most complex extraction

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

### Phase 4: Prompt Asset Caching and Cycle Immutability

**Goal**: Add per-cycle caching and the cycle immutability rule.

#### CyclePromptCache

```python
class CyclePromptCache:
    """Per-cycle cache for resolved prompt assets. Immutable once populated."""

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

- Langfuse unavailable at startup → cycle fails with `PromptRegistryUnavailableError`
- Langfuse unavailable mid-cycle → cached assets serve; log warning
- Asset not found → `PromptAssetNotFoundError` with asset identity in message
- Timeout: configurable via `SQUADOPS__PROMPTS__RESOLVE_TIMEOUT_SECONDS` (default: 10)

#### Tests (~15)

- Cache seal behavior (resolve before seal, reject after seal)
- Startup failure propagation
- Mid-cycle resilience (mock Langfuse going down after cache populated)
- Timeout behavior

---

### Phase 5: Provenance Integration

**Goal**: Add multi-stage provenance fields to `ArtifactRef` and record provenance in handlers.

#### ArtifactRef changes

Add optional fields to `ArtifactRef` (`src/squadops/cycles/models.py`):

```python
# Stage 1: System Prompt Assembly
system_prompt_bundle_hash: str | None = None
system_fragment_ids: tuple[str, ...] | None = None
system_fragment_versions: tuple[str, ...] | None = None

# Stage 2: Request Template Rendering
request_template_id: str | None = None
request_template_version: str | None = None
request_render_hash: str | None = None

# Stage 3: Invocation Composition (optional)
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
    system_prompt_bundle_hash=assembled.assembly_hash,
    system_fragment_ids=tuple(f.fragment_id for f in ...),
    request_template_id=rendered.template_id,
    request_template_version=rendered.template_version,
    request_render_hash=rendered.render_hash,
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
- Reports upload summary

#### E2E validation

- Run a full `play_game` cycle with `--request-profile selftest` using Langfuse-backed prompt resolution
- Verify artifacts contain provenance fields
- Verify cached assets survive simulated Langfuse downtime mid-cycle
- Compare cycle output against a baseline cycle run with filesystem-backed prompts (regression check)

#### Tests (~5)

- Upload script dry-run test
- Round-trip: upload → resolve → compare content

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
| `src/squadops/prompts/request_templates/*.md` | 2 | ~15–20 template files |
| `src/squadops/prompts/renderer.py` | 2 | `RequestTemplateRenderer` |
| `src/squadops/prompts/cache.py` | 4 | `CyclePromptCache` |
| `infra/migrations/NNNN_add_prompt_provenance.sql` | 5 | DDL for provenance columns |
| `scripts/maintainer/upload_prompts_to_langfuse.py` | 6 | Upload script |

### Modified files

| File | Phase | Change |
|---|---|---|
| `src/squadops/agents/base.py` | 2 | Add `request_renderer` to `PortsBundle` |
| `src/squadops/capabilities/handlers/cycle_tasks.py` | 3 | Refactor `_build_user_prompt` → template resolution |
| `src/squadops/capabilities/handlers/planning_tasks.py` | 3 | Refactor `_build_user_prompt` → template resolution |
| `src/squadops/capabilities/handlers/repair_tasks.py` | 3 | Refactor `_build_user_prompt` → template resolution |
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
| `tests/unit/prompts/test_asset_factory.py` | 1 | 3 |
| `tests/unit/prompts/test_request_template_renderer.py` | 2 | 12 |
| `tests/unit/prompts/test_request_templates.py` | 2 | 20 |
| `tests/unit/prompts/test_handler_parity.py` | 3 | 20 |
| `tests/unit/prompts/test_cycle_prompt_cache.py` | 4 | 10 |
| `tests/unit/prompts/test_cache_resilience.py` | 4 | 5 |
| `tests/unit/cycles/test_artifact_provenance.py` | 5 | 15 |
| `tests/unit/prompts/test_upload_script.py` | 6 | 5 |
| **Total** | | **~112** |

---

## Verification

After each phase:
- Regression suite passes (3032+ tests)
- `ruff check .` clean
- No behavioral change to LLM outputs until Phase 3 handler refactoring (which must be parity-tested)

After Phase 6:
- Full `play_game` cycle succeeds with Langfuse-backed prompts
- Artifacts contain provenance metadata
- Prompt update in Langfuse → new cycle picks up new version without redeployment
- `docker compose config | grep SQUADOPS__PROMPTS` shows provider config

---

## Key Design Decisions

| ID | Decision | Rationale |
|---|---|---|
| D1 | `PromptAssetSourcePort` serves both fragments and templates | Single retrieval abstraction matching SIP's two governed asset types |
| D2 | `PromptRepository` (SIP-0057) is NOT replaced | `FilesystemPromptAssetAdapter` wraps it; existing `PromptAssembler` unchanged |
| D3 | Simple `{{variable}}` substitution, no template logic | Request templates define structure, not behavior; keeps templates declarative |
| D4 | Capability supplements stay handler-owned | Not governed assets per SIP Section 1.3; avoids registry scope creep |
| D5 | Cache sealed after cycle startup | Cycle immutability rule from SIP Section 8 |
| D6 | Fail-at-start, not silent fallback | Missing assets = broken cycle; never mask with stale data |
| D7 | Provenance fields optional on ArtifactRef | Backward compat with pre-1.0.1 artifacts (D19 pattern from SIP-0076) |
| D8 | Phase 3 requires parity tests | Handler refactoring must produce identical LLM messages; regression guard |
| D9 | Filesystem adapter is default, Langfuse opt-in | Safe rollout; existing deployments unaffected until explicitly switched |
| D10 | Request templates stored alongside fragments | `src/squadops/prompts/request_templates/` — colocated, same package |
