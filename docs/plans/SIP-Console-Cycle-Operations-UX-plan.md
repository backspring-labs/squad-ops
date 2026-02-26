# SIP: Console Cycle Operations UX — Implementation Plan

## Context

The console's Cycles perspective currently lists cycles and shows run detail via three stacked panels, but creating a cycle requires the CLI. Gate decisions exist as command IDs (`squadops.gate_approve`, `squadops.gate_reject`) but have no form-driven UI. The SIP at `sips/proposed/SIP-Console-Cycle-Operations-UX.md` defines the full solution: cycle creation modal, master-detail layout, inline gate decisions, squad profile viewer enhancements, and CLI parity for new endpoints.

### Current State

- **Console BFF** (`console/app/main.py`): FastAPI wrapper around ContinuumRuntime. 11 registered command handlers. Reverse-proxies `/api/v1/*` reads to runtime-api. All writes go through command bus → `_api_request()`.
- **Cycles plugin** (`console/continuum-plugins/squadops.cycles/`): 3 separate panels (`CyclesList`, `CyclesRunTimeline`, `CyclesRunDetail`) stacked vertically in `ui.slot.main`. Components communicate via `window.dispatchEvent(CustomEvent('squadops:select-*'))`.
- **Projects plugin** (`console/continuum-plugins/squadops.projects/`): 2 panels (`ProjectsList`, `ProjectsProfiles`). Read-only profile viewer with `set_active_profile` command.
- **API**: 5 routers (projects, cycles, runs, squad-profiles, artifacts). No endpoint for cycle request profiles or model registry.
- **CLI**: `squadops cycles create` loads cycle request profiles internally via `load_profile()`. `squadops squad-profiles list/show` exists. No `request-profiles` (cycle request profiles) command group. No `models` command group.
- **Cycle request profile schema**: `PromptMeta` has `label`, `help_text`, `choices`. No `type` or `required` fields.

---

## Binding Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Phase 1 is API + CLI only — no console UI changes | Establishes testable endpoints before building UI consumers |
| D2 | New CLI command group `request-profiles` for cycle request profiles | Cleanly distinct from existing `squad-profiles` group. No ambiguity. |
| D3 | `GET /api/v1/cycle-request-profiles` uses the CRP loader (`load_profile()`), not a port | Cycle request profiles are config-file-based value objects, not domain entities. No new port needed. |
| D4 | `GET /api/v1/models` reads directly from `MODEL_SPECS` dict in `model_registry.py` | Same reasoning — code-defined registry, no port or persistence layer. |
| D5 | `CyclesPerspective.svelte` replaces 3 separate panel contributions with 1 composite panel | SIP §8: parent component owns layout (CSS grid) and selection state (props, not CustomEvent). |
| D6 | `CycleCreateModal.svelte` submits via `executeCommand('squadops.create_cycle', ...)` | SIP §5.1: all console writes go through command bus. Existing handler in `main.py` already maps to `POST /api/v1/projects/{project_id}/cycles`. |
| D7 | Gate decision UI reuses existing `executeCommand()` pattern from `CyclesRunDetail.svelte` | Handler already exists (`squadops.gate_approve`, `squadops.gate_reject`). Add safety semantics (disabled states, in-flight, no optimistic update). |
| D8 | `PromptMeta` schema extension is backward-compatible — `type` and `required` are optional with defaults | SIP §5.8: existing profiles continue to work via type inference rules. |
| D9 | Cycle request profile YAML files get a `description` field added | Currently only `name`, `defaults`, `prompts`. The API response needs it for the console dropdown. |

---

## Phase 1: API + CLI Foundation

### 1.1 Extend PromptMeta Schema

**Modified file:** `src/squadops/contracts/cycle_request_profiles/schema.py`

Add optional `type` and `required` fields to `PromptMeta`:

```python
class PromptMeta(BaseModel):
    """CLI/console prompt metadata for interactive mode."""
    label: str
    help_text: str = ""
    choices: list[str] = Field(default_factory=list)
    type: str | None = None        # "choice" | "text" | "bool" — inferred if not set
    required: bool = False          # Whether the field must be filled
```

Type inference rules (§5.8) are applied by consumers (console UI, CLI), not by the schema validator. The schema accepts any `type` string — unknown types are the consumer's problem (console renders as read-only text with warning icon).

### 1.2 Cycle Request Profiles API Endpoint

**New file:** `src/squadops/api/routes/cycles/cycle_request_profiles.py`

```python
router = APIRouter(prefix="/api/v1/cycle-request-profiles", tags=["cycle-request-profiles"])

@router.get("")
async def list_cycle_request_profiles():
    """Return all registered cycle request profiles with prompts metadata."""
    from squadops.contracts.cycle_request_profiles import list_profiles, load_profile
    names = list_profiles()
    return [_profile_to_response(load_profile(name)) for name in names]

@router.get("/{profile_name}")
async def get_cycle_request_profile(profile_name: str):
    """Return a single cycle request profile by name."""
    from squadops.contracts.cycle_request_profiles import load_profile
    try:
        return _profile_to_response(load_profile(profile_name))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
```

**Response DTO** (add to `dtos.py`):

```python
class PromptMetaResponse(BaseModel):
    label: str
    help_text: str = ""
    choices: list[str] = Field(default_factory=list)
    type: str | None = None
    required: bool = False

class CycleRequestProfileResponse(BaseModel):
    name: str
    description: str = ""
    defaults: dict = Field(default_factory=dict)
    prompts: dict[str, PromptMetaResponse] = Field(default_factory=dict)
```

**Wire into service:** Register the new router in `src/squadops/api/service.py` alongside the existing routers.

**Cache headers:** Both `/api/v1/cycle-request-profiles` and `/api/v1/models` are backed by code-defined value objects that only change on redeploy. Add `Cache-Control: public, max-age=300` response headers. In the console, memoize both lists for the session (one fetch per page load, shared across modal opens).

### 1.3 Model Registry API Endpoint

**New file:** `src/squadops/api/routes/cycles/models.py`

```python
router = APIRouter(prefix="/api/v1/models", tags=["models"])

@router.get("")
async def list_models():
    """Return all model registry entries."""
    from squadops.llm.model_registry import MODEL_SPECS
    return [
        ModelSpecResponse(
            name=spec.name,
            context_window=spec.context_window,
            default_max_completion=spec.default_max_completion,
        )
        for spec in MODEL_SPECS.values()
    ]
```

**Response DTO** (add to `dtos.py`):

```python
class ModelSpecResponse(BaseModel):
    name: str
    context_window: int
    default_max_completion: int
```

### 1.4 CLI: `profiles` Command Group (Cycle Request Profiles)

**New file:** `src/squadops/cli/commands/crp.py`

Note: file named `crp.py` internally but registered as `request-profiles` command group in `main.py`. The acronym is acceptable for internal filenames — only user-facing text avoids acronyms.

```python
app = typer.Typer(name="request-profiles", help="Manage cycle request profiles")

@app.command("list")
def list_crp(ctx: typer.Context):
    """List all cycle request profiles."""
    # GET /api/v1/cycle-request-profiles
    # Table: Name | Description | # Prompts | # Defaults

@app.command("show")
def show_crp(ctx: typer.Context, profile_name: str = typer.Argument(...)):
    """Show cycle request profile defaults and prompt metadata."""
    # GET /api/v1/cycle-request-profiles/{profile_name}
    # Output: name, description, defaults (formatted), prompts (formatted)
```

**Register in CLI main:** `src/squadops/cli/main.py`

```python
from squadops.cli.commands.crp import app as crp_app
app.add_typer(crp_app, name="request-profiles")
```

### 1.5 CLI: `models` Command Group

**New file:** `src/squadops/cli/commands/models.py`

```python
app = typer.Typer(name="models", help="View model registry information")

@app.command("list")
def list_models(ctx: typer.Context):
    """List known models with context windows."""
    # GET /api/v1/models
    # Table: Model | Context Window | Max Completion
```

**Register in CLI main:**

```python
from squadops.cli.commands.models import app as models_app
app.add_typer(models_app, name="models")
```

### 1.6 Phase 1 Tests

**New tests:**
- `tests/unit/api/test_cycle_request_profiles_api.py` — endpoint returns all profiles, 404 for unknown, prompts metadata serialized correctly, PromptMeta with/without `type`/`required`
- `tests/unit/api/test_models_api.py` — endpoint returns all model specs, response matches registry
- `tests/unit/cli/test_commands_crp.py` — `request-profiles list` and `request-profiles show` output, error handling
- `tests/unit/cli/test_commands_models.py` — `models list` output, error handling
- `tests/unit/contracts/test_crp_schema_dev_capability.py` — extend existing: PromptMeta `type` and `required` fields are optional, backward-compatible

**Modified tests:**
- `tests/unit/api/test_service.py` — new routers registered (route presence assertion)

### 1.7 Phase 1 Files Summary

| File | Change |
|------|--------|
| `src/squadops/contracts/cycle_request_profiles/schema.py` | `PromptMeta` gets `type`, `required` fields |
| `src/squadops/api/routes/cycles/cycle_request_profiles.py` | **New** — `GET /api/v1/cycle-request-profiles`, `GET /api/v1/cycle-request-profiles/{name}` |
| `src/squadops/api/routes/cycles/models.py` | **New** — `GET /api/v1/models` |
| `src/squadops/api/routes/cycles/dtos.py` | Add `CycleRequestProfileResponse`, `PromptMetaResponse`, `ModelSpecResponse` |
| `src/squadops/api/service.py` | Register new routers |
| `src/squadops/cli/commands/crp.py` | **New** — `request-profiles list/show` |
| `src/squadops/cli/commands/models.py` | **New** — `models list` |
| `src/squadops/cli/main.py` | Register `request-profiles` and `models` command groups |
| Tests (5 new + 1 modified) | See §1.6 |

---

## Phase 2: Master-Detail Layout + Gate Decisions

### 2.1 CyclesPerspective Wrapper Component

**New file:** `console/continuum-plugins/squadops.cycles/ui/src/CyclesPerspective.svelte`

This component replaces the three separate panel contributions with a single composite layout. It owns the selection state and passes it down as props.

```svelte
<svelte:options customElement="squadops-cycles-perspective" />

<script>
  import CyclesList from './CyclesList.svelte';
  import CyclesRunTimeline from './CyclesRunTimeline.svelte';
  import CyclesRunDetail from './CyclesRunDetail.svelte';

  // Selection state (§5.2)
  let selection = $state({
    project_id: null,
    cycle_id: null,
    active_run_id: null,
  });

  let modalOpen = $state(false);
</script>

<div class="cycles-perspective">
  <div class="left-pane">
    <CyclesList
      onSelectCycle={(projectId, cycleId) => { ... }}
      onNewCycle={() => modalOpen = true}
    />
    {#if selection.cycle_id}
      <CyclesRunTimeline
        projectId={selection.project_id}
        cycleId={selection.cycle_id}
        onSelectRun={(runId) => { selection.active_run_id = runId; }}
      />
    {/if}
  </div>
  <div class="right-pane">
    {#if selection.active_run_id}
      <CyclesRunDetail
        projectId={selection.project_id}
        cycleId={selection.cycle_id}
        runId={selection.active_run_id}
      />
    {:else}
      <div class="empty-state">Select a cycle to view details.</div>
    {/if}
  </div>
</div>

<style>
  .cycles-perspective {
    display: grid;
    grid-template-columns: 2fr 3fr;
    gap: 1rem;
    height: 100%;
  }
</style>
```

**Key architecture change:** The existing three components (`CyclesList`, `CyclesRunTimeline`, `CyclesRunDetail`) are converted from standalone custom elements to regular Svelte components imported by the parent. They lose their `<svelte:options customElement="..." />` declarations and instead receive props from the parent. This eliminates `window.dispatchEvent(CustomEvent(...))` for inter-component communication.

**Migration path for existing components:**
1. Remove `<svelte:options customElement="..." />` from each
2. Replace `window.addEventListener('squadops:select-*', ...)` with exported props (`projectId`, `cycleId`, `runId`)
3. Replace `window.dispatchEvent(new CustomEvent('squadops:select-*', ...))` with callback props (`onSelectCycle`, `onSelectRun`)
4. Data fetching stays in each component (not lifted to parent) — only selection state is coordinated

### 2.2 Plugin.toml Update

**Modified file:** `console/continuum-plugins/squadops.cycles/plugin.toml`

Replace three panel contributions with one composite panel + one overlay (for the modal in Phase 3):

```toml
# Before: 3 separate panels
# [[contributions.panel]]
# component = "squadops-cycles-list"          # main slot, priority 800
# [[contributions.panel]]
# component = "squadops-cycles-run-timeline"  # main slot, priority 700
# [[contributions.panel]]
# component = "squadops-cycles-run-detail"    # main slot, priority 600

# After: 1 composite panel
[[contributions.panel]]
slot = "ui.slot.main"
perspective = "cycles"
component = "squadops-cycles-perspective"
priority = 800
```

The `index.js` entry point is updated to export `CyclesPerspective` as the custom element instead of the three separate ones.

### 2.3 Selection State Model

Implementation of SIP §5.2 in `CyclesPerspective.svelte`:

```javascript
// Selection rules:
// 1. Click cycle → set project_id + cycle_id, auto-set active_run_id to latest run
//    "Latest run" = highest run_number. The API returns runs sorted descending
//    by run_number (contract: GET /runs always returns newest first). UI takes first.
// 2. Click run in timeline → set active_run_id
// 3. No runs → active_run_id = null, right pane shows "No runs yet"
// 4. Deselect → all null, right pane shows empty state
// 5. After creating cycle → set to new cycle_id + run_id from response
```

The parent `CyclesPerspective` manages all selection state. Children receive it as props and call callbacks to update it.

### 2.4 Inline Gate Decisions (GateDecisionCard)

**New file:** `console/continuum-plugins/squadops.cycles/ui/src/GateDecisionCard.svelte`

Extracts the gate decision UI from the existing `CyclesRunDetail.svelte` into a dedicated component with safety semantics per SIP §5.5:

```svelte
<script>
  let { gate, projectId, cycleId, runId, runStatus, onDecisionRecorded } = $props();

  let inFlight = $state(false);
  let error = $state(null);

  // Gate is decidable only when run is "waiting" AND gate has no decision
  let decidable = $derived(
    runStatus === 'waiting' && !gate.decision && !inFlight
  );

  async function decide(decision) {
    if (decision === 'rejected') {
      const confirmed = confirm(`Reject gate "${gate.gate_name}"? This will stop the run.`);
      if (!confirmed) return;
    }
    inFlight = true;
    error = null;
    try {
      const commandId = decision === 'approved'
        ? 'squadops.gate_approve'
        : 'squadops.gate_reject';
      await executeCommand(commandId, {
        project_id: projectId,
        cycle_id: cycleId,
        run_id: runId,
        gate_name: gate.gate_name,
      });
      // NO optimistic update — parent re-fetches run detail
      onDecisionRecorded?.();
    } catch (err) {
      // Already-decided (conflict/idempotent) → info toast, not error
      if (err.message?.includes('already') || err.status === 409) {
        info = 'Gate already decided';
      } else {
        error = err.message;
      }
      // Always re-fetch to get server-confirmed state
      onDecisionRecorded?.();
    } finally {
      inFlight = false;
    }
  }
</script>
```

**Safety semantics per SIP §5.5:**
- Approve: single click, no confirmation (`danger_level: "safe"`)
- Reject: `confirm()` dialog before submission (`danger_level: "confirm"`)
- In-flight: both buttons disabled with spinner
- After decision: buttons replaced with read-only decision badge
- Failure: error toast, buttons re-enabled, NO optimistic update, parent re-fetches
- Already decided (conflict/race): non-error info toast ("Gate already decided"), re-fetch and render read-only badge

### 2.5 Artifact List with Type Filter

**New file:** `console/continuum-plugins/squadops.cycles/ui/src/ArtifactTypeFilter.svelte`

Filter chips for the artifact list: `All | Docs | Code | Tests | Config`. Currently `CyclesRunDetail` shows `artifact_refs` as a simple list. This adds type-based filtering.

```svelte
<script>
  let { artifacts, onFilter } = $props();
  let activeType = $state('all');

  const types = ['all', 'documentation', 'source_code', 'test_report', 'configuration'];
  const labels = { all: 'All', documentation: 'Docs', source_code: 'Code', test_report: 'Tests', configuration: 'Config' };

  function setFilter(type) {
    activeType = type;
    onFilter?.(type === 'all' ? artifacts : artifacts.filter(a => a.artifact_type === type));
  }
</script>
```

Note: `artifact_refs` in the current `RunResponse` are just strings (artifact IDs), not full objects. To show artifact type, we need either:
- **Option A**: Enrich `RunResponse.artifact_refs` to include type metadata (API change)
- **Option B**: Fetch full artifact list via `GET /api/v1/projects/{project_id}/artifacts?run_id={run_id}`

**Decision**: Option B — use the existing artifacts endpoint. No API change needed. The right pane fetches artifacts separately when a run is selected.

### 2.6 Modify CyclesRunDetail

**Modified file:** `console/continuum-plugins/squadops.cycles/ui/src/CyclesRunDetail.svelte`

- Remove `<svelte:options customElement="..." />` (now a regular child of `CyclesPerspective`)
- Receive `projectId`, `cycleId`, `runId` as props instead of listening for `squadops:select-run` events
- Embed `GateDecisionCard` for each gate in `runDetail.gate_decisions` (or undecided gates from `task_flow_policy.gates`)
- Fetch artifacts via `GET /api/v1/projects/{projectId}/artifacts?run_id={runId}` instead of using `runDetail.artifact_refs`
- Embed `ArtifactTypeFilter` above the artifact list
- After gate decision callback: re-fetch run detail from API (server-confirmed, no optimistic update)

### 2.7 Modify CyclesList

**Modified file:** `console/continuum-plugins/squadops.cycles/ui/src/CyclesList.svelte`

- Remove `<svelte:options customElement="..." />` (now a regular child)
- Add "New Cycle" button in header
- Replace `window.dispatchEvent(CustomEvent('squadops:select-cycle'))` with callback prop `onSelectCycle(projectId, cycleId)`
- Add callback prop `onNewCycle()` for the button

### 2.8 Modify CyclesRunTimeline

**Modified file:** `console/continuum-plugins/squadops.cycles/ui/src/CyclesRunTimeline.svelte`

- Remove `<svelte:options customElement="..." />` (now a regular child)
- Receive `projectId`, `cycleId` as props instead of listening for `squadops:select-cycle`
- Replace `window.dispatchEvent(CustomEvent('squadops:select-run'))` with callback prop `onSelectRun(runId)`

### 2.9 Update index.js

**Modified file:** `console/continuum-plugins/squadops.cycles/ui/src/index.js`

Export only `CyclesPerspective` as the custom element. The other three components are internal imports.

```javascript
export { default as CyclesPerspective } from './CyclesPerspective.svelte';
```

### 2.10 Phase 2 Tests

**New tests:**
- `tests/unit/console/test_cycles_perspective.py` — selection state transitions (cycle click, run click, deselect, empty state)
- `tests/unit/console/test_gate_decision_card.py` — button states (decidable, in-flight, decided), confirm dialog for reject, error recovery

**Existing tests to update:**
- `tests/unit/console/test_console_main.py` — verify plugin.toml changes don't break boot

**Manual verification (no automated test):**
- Build cycles plugin: `cd console/continuum-plugins/squadops.cycles/ui && npm run build`
- Rebuild console: `./scripts/dev/ops/rebuild_and_deploy.sh console`
- Visual check: master-detail layout, gate buttons, artifact filter chips

### 2.11 Phase 2 Files Summary

| File | Change |
|------|--------|
| `console/continuum-plugins/squadops.cycles/ui/src/CyclesPerspective.svelte` | **New** — composite wrapper with grid layout + selection state |
| `console/continuum-plugins/squadops.cycles/ui/src/GateDecisionCard.svelte` | **New** — inline gate approve/reject with safety semantics |
| `console/continuum-plugins/squadops.cycles/ui/src/ArtifactTypeFilter.svelte` | **New** — type filter chips |
| `console/continuum-plugins/squadops.cycles/ui/src/CyclesList.svelte` | Remove custom element, use props/callbacks |
| `console/continuum-plugins/squadops.cycles/ui/src/CyclesRunTimeline.svelte` | Remove custom element, use props/callbacks |
| `console/continuum-plugins/squadops.cycles/ui/src/CyclesRunDetail.svelte` | Remove custom element, embed gate card + artifact filter, props |
| `console/continuum-plugins/squadops.cycles/ui/src/index.js` | Export only `CyclesPerspective` |
| `console/continuum-plugins/squadops.cycles/plugin.toml` | Replace 3 panels with 1 composite panel |
| Tests (2 new + 1 modified) | See §2.10 |

---

## Phase 3: Cycle Creation Modal

### 3.1 CycleCreateModal Component

**New file:** `console/continuum-plugins/squadops.cycles/ui/src/CycleCreateModal.svelte`

Multi-section modal form per SIP §5.3. Opened by "New Cycle" button in `CyclesPerspective`, closed on success or explicit dismiss.

**Section 1: Project & Squad**
- Project dropdown: fetches `GET /api/v1/projects` on mount
- Squad profile dropdown: fetches `GET /api/v1/squad-profiles` on mount, defaults to active profile
- Agent summary row: shows agents for selected profile (read-only)

**Section 2: PRD**
- Mode toggle: "Write PRD" | "Use project PRD"
- Textarea (monospace, resizable, 20-line height)
- "Use project PRD" fetches content from `project.prd_path` via a new console BFF endpoint or direct fetch, then pre-populates textarea
- Size constraint: character count display, warn at 50KB (yellow), block at 200KB (red, submit disabled)
- Missing `prd_path`: toggle disabled with tooltip
- Unreadable `prd_path`: inline error, textarea left empty for manual entry

**PRD resolution approach:** The console BFF already proxies `/api/v1/*`. The project's `prd_path` is a filesystem path on the server. Two options:
- **Option A**: New API endpoint `GET /api/v1/projects/{id}/prd-content` that reads `prd_path` server-side and returns content
- **Option B**: The CLI reads files locally via `Path(prd).is_file()`. The console can't do this since it runs in a browser.

**Decision**: Option A — add a thin **best-effort** read-only endpoint. The project registry already knows the `prd_path`. This endpoint reads the file and returns its content as text. Returns 404 if `prd_path` is missing, unreadable, or unmounted (containerized deployments where the PRD file lives on the host). The UI handles 404 gracefully: shows inline message "PRD file not available in this deployment; paste PRD text instead" and keeps the textarea editable for manual entry. This makes the feature robust across laptop, Spark, and container setups without blocking the plan.

**New endpoint** (add to `projects.py`):
```
GET /api/v1/projects/{project_id}/prd-content → text/plain (best-effort, 404 if unavailable)
```

### 3.2 ProfileParamRenderer Component

**New file:** `console/continuum-plugins/squadops.cycles/ui/src/ProfileParamRenderer.svelte`

Renders dynamic form fields from a cycle request profile's `prompts` metadata using the §5.8 type inference rules:

```svelte
<script>
  let { prompts, defaults, values, onChange } = $props();

  function inferType(key, meta) {
    if (meta.type) return meta.type;
    if (meta.choices?.length > 0) return 'choice';
    if (typeof defaults[key] === 'boolean') return 'bool';
    return 'text';
  }
</script>

{#each Object.entries(prompts) as [key, meta]}
  {#if inferType(key, meta) === 'choice'}
    <select ...>
  {:else if inferType(key, meta) === 'bool'}
    <input type="checkbox" ...>
  {:else if inferType(key, meta) === 'text'}
    <input type="text" ...>
  {:else}
    <!-- Unknown type: read-only display with warning icon.
         If meta.required, this blocks submit (see validation below). -->
    <span class="readonly-field">⚠ {values[key]}</span>
  {/if}
{/each}
```

### 3.3 Applied Defaults Preview

In `CycleCreateModal.svelte`, a collapsible section showing the resolved `applied_defaults` dict. Computed client-side with the merge order from §5.7:

```javascript
// Layer 1: profile defaults
// Layer 2: user overrides (from ProfileParamRenderer)
// Layer 3: system-required (project_id, squad_profile_id)
let appliedDefaults = $derived({
  ...selectedProfile?.defaults,
  ...userOverrides,
  project_id: selectedProjectId,
  squad_profile_id: selectedSquadProfileId,
});
```

Fields not in `prompts` are carried from profile defaults without UI exposure. They appear in the preview but are not editable.

### 3.4 Submit Flow

1. Validate required fields (project, squad profile, PRD text). Additionally:
   - If any prompt field has `required: true` and `inferType()` returns an unknown type → block submit with inline error: "Unsupported prompt type for required field: {key}". This prevents misconfigured profile YAML from silently producing cycles with missing inputs.
2. Build `CycleCreateRequest` payload:
   ```javascript
   const body = {
     project_id: selectedProjectId,
     squad_profile_id: selectedSquadProfileId,
     prd_ref: null,  // PRD is sent as text — see below
     applied_defaults: appliedDefaults,
     execution_overrides: computeOverrides(selectedProfile.defaults, userOverrides),
     notes: notes || undefined,
     // Top-level DTO fields extracted from merged config:
     build_strategy: merged.build_strategy,
     task_flow_policy: merged.task_flow_policy,
     expected_artifact_types: merged.expected_artifact_types,
   };
   ```
3. **PRD handling**: The console needs to send PRD content to the API. The current `CycleCreateRequest` only has `prd_ref` (an artifact ID or null). The CLI auto-ingests the file via `POST /api/v1/projects/{id}/artifacts/ingest` and passes the `artifact_id` as `prd_ref`. The console must do the same:
   - Before cycle creation, ingest PRD text via `squadops.ingest_artifact` command (already exists in BFF)
   - Use returned `artifact_id` as `prd_ref` in the cycle creation request
4. Submit via `executeCommand('squadops.create_cycle', { project_id, ...body })`
5. On success: close modal, set selection to `{ project_id, cycle_id, active_run_id: run_id }` from response
6. On failure: show error inline, form stays open with inputs preserved

### 3.5 PRD Content Endpoint

**Modified file:** `src/squadops/api/routes/cycles/projects.py`

Add endpoint:
```python
@router.get("/{project_id}/prd-content")
async def get_project_prd_content(project_id: str):
    """Read the PRD file content for a project.

    Returns the raw text content of the project's configured prd_path.
    404 if no prd_path configured or file not readable.
    """
    from squadops.api.runtime.deps import get_project_registry
    port = get_project_registry()
    project = await port.get_project(project_id)
    if not project.prd_path:
        raise HTTPException(404, detail="No PRD file configured for this project")
    prd_path = Path(project.prd_path)
    if not prd_path.is_file():
        raise HTTPException(404, detail=f"PRD file not found: {project.prd_path}")
    return PlainTextResponse(prd_path.read_text())
```

### 3.6 Modal Rendering

The Continuum shell defines `ui.slot.modal` in its schema but the V1 frontend doesn't render it yet. The modal is rendered inline in `CyclesPerspective.svelte` as a child component controlled by `modalOpen` state — no plugin.toml overlay registration needed. `CycleCreateModal.svelte` is a regular Svelte import, not a custom element.

### 3.7 Phase 3 Tests

**New tests:**
- `tests/unit/console/test_cycle_create_modal.py` — form validation (required fields block submit), PRD size constraints, applied defaults merge order
- `tests/unit/api/test_project_prd_content.py` — endpoint returns content, 404 for missing prd_path, 404 for unreadable file

**Manual verification:**
- Build and deploy console
- Create cycle from modal: select project, profile, write PRD, submit
- Verify cycle appears in list and is auto-selected
- Verify gate buttons work on the new cycle's run
- Error cases: missing project, oversized PRD, API failure

### 3.8 Phase 3 Files Summary

| File | Change |
|------|--------|
| `console/continuum-plugins/squadops.cycles/ui/src/CycleCreateModal.svelte` | **New** — multi-section cycle creation form |
| `console/continuum-plugins/squadops.cycles/ui/src/ProfileParamRenderer.svelte` | **New** — dynamic form fields from prompts metadata |
| `src/squadops/api/routes/cycles/projects.py` | Add `GET /{project_id}/prd-content` endpoint |
| Tests (2 new) | See §3.7 |

---

## Phase 4: Projects & Dashboard Polish

### 4.1 Squad Profile Detail Card

**New file:** `console/continuum-plugins/squadops.projects/ui/src/SquadProfileDetail.svelte`

Expandable card shown when clicking a profile in `ProjectsProfiles`. Displays:
- Profile name, description, version
- Agent table: agent_id, role, model, enabled status
- Model metadata from `GET /api/v1/models`: context window, default max completion tokens

The model metadata fetch is a one-time load on mount (the model registry is static). The agent table joins profile agents with model specs client-side.

### 4.2 Project Detail Card

**Modified file:** `console/continuum-plugins/squadops.projects/ui/src/ProjectsList.svelte`

When clicking a project row:
- Expand to show description, tags, creation date
- Show `prd_path` if configured, with a "View PRD" button that opens a read-only modal showing PRD content (fetched via `GET /api/v1/projects/{id}/prd-content`)
- Recent cycles (last 5) for this project, fetched via `GET /api/v1/projects/{id}/cycles?limit=5`

### 4.3 Dashboard Quick Actions

**Modified file:** `console/continuum-plugins/squadops.home/ui/src/HomeSignal.svelte` (or equivalent dashboard component)

- **"Create Cycle" quick action card**: navigates to Cycles perspective, then opens modal after mount (§5.12 two-step navigation)
- **Pending gates badge**: counts runs in `waiting` status across all projects, shows count + "Review" link that navigates to Cycles perspective with the first waiting cycle pre-selected

**Navigation via Continuum commands:**

Register a new command `squadops.open_create_cycle` in the cycles plugin. The command handler navigates to the Cycles perspective and sets `modalOpen = true`. The dashboard's "Create Cycle" button fires this command via the command bus — same pattern as every other write operation.

```toml
# plugin.toml — new command
[[contributions.command]]
id = "squadops.open_create_cycle"
label = "New Cycle"
description = "Open the cycle creation modal"
```

The command handler in `CyclesPerspective.svelte` (or the plugin's `__init__.py`) handles perspective activation + modal state. No custom events, no query params — just the command bus.

### 4.4 Phase 4 Tests

**New tests:**
- `tests/unit/console/test_squad_profile_detail.py` — model metadata joined with agents, empty model spec handling

**Manual verification:**
- Squad profile detail card shows agents + model context windows
- Project detail shows PRD preview, recent cycles
- Dashboard "Create Cycle" navigates and opens modal
- Pending gates badge shows correct count

### 4.5 Phase 4 Files Summary

| File | Change |
|------|--------|
| `console/continuum-plugins/squadops.projects/ui/src/SquadProfileDetail.svelte` | **New** — agent table with model metadata |
| `console/continuum-plugins/squadops.projects/ui/src/ProjectsList.svelte` | Add project detail expansion with PRD preview + recent cycles |
| `console/continuum-plugins/squadops.home/ui/src/HomeSignal.svelte` | Add "Create Cycle" quick action + pending gates badge |
| Tests (1 new) | See §4.4 |

---

## Phase 5: Version Bump + SIP Promotion

### 5.1 Version Bump

Bump `0.9.13 → 0.9.14` in:
- `pyproject.toml`
- `src/squadops/__init__.py` (both `__version__` and docstring)
- `CLAUDE.md`

### 5.2 SIP Promotion

After all phases are merged and verified:
```bash
export SQUADOPS_MAINTAINER=1
python scripts/maintainer/update_sip_status.py \
  sips/accepted/SIP-NNNN-Console-Cycle-Operations-UX.md implemented
```

---

## Files Modified (Complete Summary)

### Python (API + CLI)
| File | Change |
|------|--------|
| `src/squadops/contracts/cycle_request_profiles/schema.py` | `PromptMeta` gets `type`, `required` |
| `src/squadops/api/routes/cycles/cycle_request_profiles.py` | **New** — cycle request profiles endpoint |
| `src/squadops/api/routes/cycles/models.py` | **New** — model registry endpoint |
| `src/squadops/api/routes/cycles/projects.py` | Add PRD content endpoint |
| `src/squadops/api/routes/cycles/dtos.py` | Add 3 response DTOs |
| `src/squadops/api/service.py` | Register 2 new routers |
| `src/squadops/cli/commands/crp.py` | **New** — `request-profiles list/show` |
| `src/squadops/cli/commands/models.py` | **New** — `models list` |
| `src/squadops/cli/main.py` | Register 2 new command groups |

### Console (Svelte + Plugin Config)
| File | Change |
|------|--------|
| `console/continuum-plugins/squadops.cycles/plugin.toml` | 3 panels → 1 composite panel |
| `console/continuum-plugins/squadops.cycles/ui/src/CyclesPerspective.svelte` | **New** — grid layout + selection state |
| `console/continuum-plugins/squadops.cycles/ui/src/CycleCreateModal.svelte` | **New** — cycle creation form |
| `console/continuum-plugins/squadops.cycles/ui/src/ProfileParamRenderer.svelte` | **New** — dynamic prompt fields |
| `console/continuum-plugins/squadops.cycles/ui/src/GateDecisionCard.svelte` | **New** — inline gate buttons |
| `console/continuum-plugins/squadops.cycles/ui/src/ArtifactTypeFilter.svelte` | **New** — type filter chips |
| `console/continuum-plugins/squadops.cycles/ui/src/CyclesList.svelte` | Remove custom element, use props |
| `console/continuum-plugins/squadops.cycles/ui/src/CyclesRunTimeline.svelte` | Remove custom element, use props |
| `console/continuum-plugins/squadops.cycles/ui/src/CyclesRunDetail.svelte` | Remove custom element, embed gate card + filter |
| `console/continuum-plugins/squadops.cycles/ui/src/index.js` | Export only perspective |
| `console/continuum-plugins/squadops.projects/ui/src/SquadProfileDetail.svelte` | **New** |
| `console/continuum-plugins/squadops.projects/ui/src/ProjectsList.svelte` | Add detail expansion |
| `console/continuum-plugins/squadops.home/ui/src/HomeSignal.svelte` | Quick actions + gates badge |

### Tests
| File | Change |
|------|--------|
| `tests/unit/api/test_cycle_request_profiles_api.py` | **New** |
| `tests/unit/api/test_models_api.py` | **New** |
| `tests/unit/api/test_project_prd_content.py` | **New** |
| `tests/unit/cli/test_commands_crp.py` | **New** |
| `tests/unit/cli/test_commands_models.py` | **New** |
| `tests/unit/console/test_cycles_perspective.py` | **New** |
| `tests/unit/console/test_gate_decision_card.py` | **New** |
| `tests/unit/console/test_cycle_create_modal.py` | **New** |
| `tests/unit/console/test_squad_profile_detail.py` | **New** |
| `tests/unit/contracts/test_crp_schema_dev_capability.py` | Extend with PromptMeta type/required |
| `tests/unit/api/test_service.py` | New router assertions |
| `tests/unit/console/test_console_main.py` | Plugin.toml changes |

---

## Verification

```bash
# Phase 1: All new + existing tests pass
./scripts/dev/run_new_arch_tests.sh -v

# Phase 1: CLI commands work
squadops request-profiles list
squadops request-profiles show default
squadops models list

# Phase 2-4: Rebuild and deploy console
./scripts/dev/ops/rebuild_and_deploy.sh runtime-api console

# E2E: Create a cycle from the console
# 1. Open http://localhost:4040
# 2. Navigate to Cycles perspective
# 3. Click "New Cycle"
# 4. Fill form: project=play_game, profile=default, squad=full-squad, PRD text
# 5. Submit → verify cycle appears in list, auto-selected
# 6. Monitor in Prefect UI (http://localhost:4200)
# 7. When run hits gate → approve from console inline buttons
# 8. Verify run completes

# Regression: CLI cycle creation still works
squadops cycles create play_game \
  --squad-profile full-squad-with-builder \
  --profile pcr-scaffold \
  --prd examples/group_run/prd-scaffold.md
```

---

## Resolved Questions

1. **Continuum modal slot**: Continuum defines `ui.slot.modal` (not `ui.slot.overlay`) in `regions.py` and `manifest.py`. However, the V1 frontend doesn't render it yet — `Shell.svelte` only renders `ui.slot.main`, `ui.slot.left_nav`, and `ui.slot.right_rail`. **Decision**: render the modal inline in `CyclesPerspective.svelte` as a child component controlled by `modalOpen` state. No dependency on unimplemented shell slot. Update the SIP and plugin.toml to remove the `ui.slot.overlay` reference.

2. **Cross-perspective navigation**: Continuum provides `setPerspective(perspectiveId)` in `registry.ts` (Svelte store function). Not exposed on `window`, but accessible from command handlers within the shell. The `squadops.open_create_cycle` command handler calls `setPerspective('cycles')` + sets modal state. This confirms the command bus approach from §4.3.

3. **PRD content endpoint in containers**: `GET /api/v1/projects/{id}/prd-content` is best-effort — returns 404 if `prd_path` is missing, unreadable, or unmounted. UI shows "PRD file not available in this deployment; paste PRD text instead" and keeps textarea editable. Robust across laptop/Spark/container setups.

