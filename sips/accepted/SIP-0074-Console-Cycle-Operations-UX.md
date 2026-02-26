---
title: Console Cycle Operations UX
status: accepted
author: SquadOps Core
created_at: '2026-02-25'
sip_number: 74
updated_at: '2026-02-25T21:56:56.693150Z'
---
# SIP: Console Cycle Operations UX

**Status:** Proposed \
**Created:** 2026-02-25 \
**Owner:** SquadOps Core \
**Target Release:** v0.9.14 \
**Related:** SIP-0069 (Console Control-Plane UI), SIP-0065 (CLI for Cycle Execution), SIP-0064 (Project Cycle Request API), SIP-0073 (LLM Budget and Timeout Controls)

### Revision History

| Rev | Date       | Changes |
|-----|------------|---------|
| 1   | 2026-02-25 | Initial proposal |
| 2   | 2026-02-25 | Tightenings: command/HTTP boundary, selection state model, gate safety semantics, PRD source behavior, prompts schema contract, applied defaults merge order, endpoint naming, CLI parity specifics, overlay routing, artifact filtering, negative-path ACs |

---

## 1. Abstract

The console's Cycles perspective currently lists cycles and shows run detail, but creating a cycle requires the CLI. This SIP adds a cycle creation form, a master-detail layout for cycle/run inspection, inline gate approval, and supporting enhancements to the Projects perspective for squad profile management. It also ensures CLI parity for any new API surface introduced.

---

## 2. Problem Statement

Operators today must switch between the console (monitoring) and the CLI (creation, gate decisions) to manage a cycle's full lifecycle. The console has the plumbing (`squadops.create_cycle` command, `squadops.gate_approve`/`squadops.gate_reject` commands) but exposes them only as raw command IDs — there is no form-driven UI for cycle creation and no inline gate decision workflow. Specific gaps:

1. **No cycle creation form.** The `squadops.create_cycle` command exists but the Cycles perspective offers no UI to compose a request — no project selector, no squad profile picker, no PRD editor, no cycle request profile parameter controls. Operators must use `squadops cycles create` from the CLI.

2. **Flat cycle list.** Clicking a cycle dispatches `squadops:select-cycle` event, which the run-timeline and run-detail panels consume. But all three panels stack vertically in `ui.slot.main`, forcing the operator to scroll between the cycle list and run detail. There is no master-detail split pane.

3. **Gate decisions require context switching.** The run-detail panel shows gate state but the approve/reject action requires invoking a command. The operator must know the run ID and gate name — there is no inline approve/reject button on the waiting gate.

4. **Squad profile management is view-only.** The Projects perspective shows profiles and supports `set_active_profile`, but there is no way to create or edit a squad profile (assign different agents, change models) from the console.

5. **Cycle request profile parameters are opaque.** The CLI reads cycle request profile YAML and prompts interactively for overridable fields. The console has no equivalent — operators can't see what a profile's defaults are or override them before submission.

6. **No PRD authoring.** The CLI accepts `--prd <file>` but the console has no way to write or paste a PRD before creating a cycle.

---

## 3. Goals

1. **Cycle creation modal** — a multi-step form in the Cycles perspective that collects project, squad profile, PRD (text input or file reference), cycle request profile selection, and overridable parameters. Submits via the Continuum command bus.

2. **Master-detail layout** — split the Cycles perspective into a left pane (cycle list + run timeline) and a right pane (run detail, gate decisions, artifacts). Clicking a cycle populates the right pane.

3. **Inline gate decisions** — when a run is in `waiting` status, the right pane shows the pending gate with Approve / Reject buttons with explicit safety semantics (disabled states, in-flight handling, server-confirmed updates).

4. **Squad profile viewer enhancements** — show agent roles, assigned models, and capability details in the Projects perspective. Surface the model registry (SIP-0073) so operators can see context window / completion limits per model.

5. **CLI parity** — any new API endpoint introduced for the console must also be accessible from the CLI with consistent naming.

6. **PRD input** — the cycle creation form supports pasting PRD text directly (textarea) or loading content from a project's configured PRD path. The API always receives PRD as raw text (not a file reference).

---

## 4. Non-Goals

- **Squad profile CRUD via the console.** V1 is read-only for profiles; creating/editing profiles remains YAML + restart. A future SIP may add dynamic profile management with API persistence.
- **Real-time WebSocket updates.** The existing 15-second polling is retained. WebSocket upgrade is a separate concern.
- **Drag-and-drop workflow builder.** The console monitors and creates cycles; it doesn't design task flow policies visually.
- **Mobile-responsive layout.** The console is a desktop operator tool.
- **PRD version history or diffing.** The textarea captures the current PRD text; versioning is out of scope.
- **Artifact grouping or advanced filtering.** V1 shows a flat artifact list with type filter chips. Hierarchical grouping by role or phase is deferred to a future SIP.

---

## 5. Design

### 5.1 Command vs HTTP Boundary

All console write operations flow through the Continuum command bus. The command bus is the source of truth for operator actions in the console; direct HTTP calls from the browser are not permitted for mutations.

**Console (write path):**
```
UI component → command bus → console BFF command handler → Runtime API (HTTP)
```
The command handler (`console/app/main.py`) adds the service token (or proxied user token) and calls the Runtime API. This is the only write path for the console.

**Console (read path):**
```
UI component → fetch(/api/v1/...) → console BFF proxy → Runtime API (HTTP)
```
Read-only data fetching (projects, cycles, profiles, models) goes through the BFF reverse proxy at `/api/v1/{path:path}`. No command bus involvement for reads.

**CLI (both paths):**
```
CLI command → httpx.Client → Runtime API (HTTP)
```
The CLI talks directly to the Runtime API. It does not use the command bus.

This means: the command bus is console-specific plumbing. The Runtime API is the shared source of truth. Both CLI and console ultimately call the same API endpoints; they differ only in how the call is authenticated and dispatched.

### 5.2 Selection State Model

The Cycles perspective maintains a single reactive selection state:

```typescript
type CycleSelection = {
  project_id: string;
  cycle_id: string;
  active_run_id: string | null;
};
```

**Selection rules:**
1. Clicking a cycle in the list sets `project_id` and `cycle_id`. `active_run_id` is auto-set to the **latest run** (highest `run_number`).
2. Clicking a specific run in the timeline sets `active_run_id` explicitly.
3. When `active_run_id` is `null` (cycle exists but has no runs), the right pane shows "No runs yet" with cycle metadata only.
4. Deselection (clicking outside or clearing filter) resets all three fields to `null`. Right pane shows empty state: "Select a cycle to view details."
5. After creating a new cycle, selection is set to the new `cycle_id` + `run_id` from the API response.

The selection state lives in `CyclesPerspective.svelte` and is passed as props to child components. No `CustomEvent` dispatching between siblings — the parent owns the state.

### 5.3 Cycle Creation Modal

A modal dialog opened by a "New Cycle" button in the Cycles perspective header. The form has three sections:

**Section 1: Project & Squad**
- **Project** — dropdown populated from `GET /api/v1/projects`. Required.
- **Squad Profile** — dropdown populated from `GET /api/v1/squad-profiles`. Shows profile name + agent count. Defaults to active profile. Required.
- Agent summary row below the dropdown: shows agent names, roles, and models for the selected profile (read-only).

**Section 2: PRD**
- **Mode toggle**: "Write PRD" (textarea) | "Use project PRD" (loads content from project's `prd_path`).
- **Textarea**: monospace, resizable, 20-line default height. Always visible regardless of mode — "Use project PRD" pre-populates the textarea with the file content.
- **PRD size constraint**: warn at 50KB, hard block at 200KB. Display character count.
- **Missing `prd_path`**: if the selected project has no `prd_path` configured, the "Use project PRD" toggle is disabled with tooltip "No PRD file configured for this project."
- **Unreadable `prd_path`**: if fetch fails, show inline error "Could not load PRD from {path}" and leave textarea empty for manual entry.
- **API payload**: the PRD is always sent as raw text in the `CycleCreateRequest`. The console does not send file references — it resolves the content before submission, matching the CLI's `--prd <file>` semantics (which reads the file and sends content).

**Section 3: Cycle Request Profile & Parameters**
- **Profile** — dropdown populated from `GET /api/v1/cycle-request-profiles`. Shows profile name + description. Defaults to "default".
- **Overridable parameters** — rendered dynamically from the profile's `prompts` metadata using the canonical prompt field schema (see §5.8).
- **Applied defaults preview** — collapsible section showing the resolved `applied_defaults` dict. Computed client-side with explicit merge order (see §5.7).
- **Notes** — optional text input.

**Submit behavior:**
- Submit button disabled until all required fields are filled (project, squad profile, PRD text).
- On submit: button enters loading state ("Creating..."), form inputs disabled.
- On success: modal closes, new cycle auto-selected in the list.
- On failure: error message displayed inline at the bottom of the modal. Form remains open with inputs preserved. No phantom cycle created.

**Submit path:** calls `squadops.create_cycle` via the Continuum command bus with the composed `CycleCreateRequest` payload.

### 5.4 Master-Detail Layout

Replace the current vertical stack of three panels with a split-pane layout:

```
┌──────────────────────────┬──────────────────────────────┐
│  Cycle List (filterable) │  Run Detail                  │
│  ────────────────────    │  ──────────────────────────  │
│  [+ New Cycle]           │  Run ID: run_abc123...       │
│                          │  Status: ● waiting           │
│  ▸ play_game cyc_5b16... │  Started: Feb 25 14:32       │
│    ● running   Feb 25    │                              │
│                          │  Gates                       │
│  ▸ play_game cyc_a012... │  ┌─────────────────────────┐ │
│    ✓ completed Feb 24    │  │ plan-review   ⏳ pending │ │
│                          │  │ [Approve]  [Reject]     │ │
│  Run Timeline            │  └─────────────────────────┘ │
│  ──────────────────────  │                              │
│  run_1 ● → run_2 ✓      │  Artifacts (5)               │
│                          │  ├ 📄 strategy_analysis.md   │
│                          │  ├ 💻 build_output (source)  │
│                          │  └ [All] [Docs] [Code] [Test]│
└──────────────────────────┴──────────────────────────────┘
```

**Left pane** (40% width):
- Cycle list table (existing `CyclesList` component, enhanced with "New Cycle" button)
- Run timeline (existing `CyclesRunTimeline`, shown below the list for the selected cycle)

**Right pane** (60% width):
- Run detail (existing `CyclesRunDetail`, enhanced with inline gate buttons and artifact list)
- Visible only when a cycle + run is selected. Empty state: "Select a cycle to view details."
- **Artifact list** with type filter chips: `All | Docs | Code | Tests | Config`. V1 is a flat list filtered by `artifact_type`. Hierarchical grouping by producing role is deferred.

The split is implemented via CSS `display: grid; grid-template-columns: 2fr 3fr` in a new wrapper component `CyclesPerspective.svelte` that replaces the three separate panel contributions with a single panel.

### 5.5 Inline Gate Decisions

When the selected run has status `waiting` and has a gate without a decision:

1. Display the gate name, description, and a "Pending" badge.
2. Show **Approve** (green) and **Reject** (red) buttons.

**Safety semantics:**
- **Approve** does not require confirmation (`danger_level: "safe"` — already defined in plugin.toml). Single click submits.
- **Reject** requires confirmation dialog (`danger_level: "confirm"` — already defined). Dialog shows gate name and warns that rejection stops the run.
- **In-flight state**: both buttons disabled with spinner while the request is in flight. No double-submit possible.
- **After decision recorded**: buttons replaced with read-only decision badge (e.g., "Approved by squadops-admin at 14:32"). Gate card is idempotent — re-fetching a decided gate shows the decision, never re-shows buttons.
- **Failure behavior**: on API error, show error toast ("Gate decision failed: {error}"). Buttons re-enabled. Gate state is NOT optimistically updated — the UI re-fetches run detail from the API to confirm current state.

Already-decided gates show the decision, decided_by, and timestamp (read-only).

### 5.6 Projects Perspective Enhancements

**Squad profile detail card** — when clicking a profile in the profiles list, expand to show:
- Profile name, description, version
- Agent table: agent_id, role, model, enabled status
- Model metadata from the model registry (SIP-0073): context window size, default max completion tokens — fetched via `GET /api/v1/models`

**Project detail** — when clicking a project:
- Show description, tags, creation date
- Show `prd_path` if configured, with a "View PRD" link that opens the PRD content in a read-only modal
- Recent cycles for this project (last 5)

### 5.7 Applied Defaults Merge Order

The cycle creation modal computes `applied_defaults` client-side with a deterministic merge order:

```
Layer 1: cycle request profile defaults     (from GET /api/v1/cycle-request-profiles)
Layer 2: user overrides from form inputs    (operator-entered values)
Layer 3: system-required fields             (project_id, squad_profile_id — always set by form)
```

Later layers override earlier layers. The merge is a shallow `Object.assign()` — no deep merge. The "Applied defaults preview" section shows the final merged dict before submission so the operator can verify.

Fields not present in the profile's `prompts` metadata are carried from profile defaults without UI exposure (e.g., `task_flow_policy`, `build_tasks`). They appear in the preview but are not editable in the form.

### 5.8 Cycle Request Profile Prompt Schema

The `prompts` field in a cycle request profile defines the rendering contract between YAML profiles and the console UI. Each prompt field has a canonical shape:

```yaml
prompts:
  <field_key>:
    label: str           # Display label (required)
    help_text: str       # Tooltip or description (optional, default "")
    type: str            # "choice" | "text" | "bool" (optional, inferred — see below)
    choices: list[str]   # Available options for choice type (optional, default [])
    required: bool       # Whether the field must be filled (optional, default false)
```

**Type inference rules** (when `type` is not explicitly set):
- If `choices` is non-empty → `choice` (renders as dropdown)
- If the default value in `defaults` is a boolean → `bool` (renders as toggle)
- Otherwise → `text` (renders as text input)

**Unknown types**: if `type` is set to an unrecognized value, the field is rendered as a read-only text display with a warning icon. The value is included in `applied_defaults` unchanged.

**Schema extension**: the existing `PromptMeta` Pydantic model in `src/squadops/contracts/cycle_request_profiles/schema.py` is extended with `type` and `required` fields (both optional with backward-compatible defaults). Existing profiles without these fields continue to work via type inference.

### 5.9 New API Endpoints

Two new read-only endpoints support the console without touching the existing cycle execution path:

**Cycle request profiles listing:**
```
GET /api/v1/cycle-request-profiles → CycleRequestProfileResponse[]
```
Returns all registered cycle request profiles with their `name`, `description`, `defaults`, and `prompts` metadata. The CLI already loads these from YAML via the `CycleRequestProfileLoader`; this endpoint exposes the same data over HTTP.

**Model registry listing:**
```
GET /api/v1/models → ModelSpecResponse[]
```
Returns all entries from the model context registry (SIP-0073): `name`, `context_window`, `default_max_completion`. Read-only, no write operations.

### 5.10 CLI Parity

The new API endpoints are accessible from the CLI with naming that matches the API path:

**Existing commands (SIP-0065):**
```bash
squadops profiles list       # Already exists — lists cycle request profiles
```

**New commands introduced by this SIP:**
```bash
# Show a single cycle request profile's defaults and prompt metadata
squadops profiles show <profile-name>
# Output: profile name, description, defaults (YAML-formatted), prompts metadata

# List known models and their context windows
squadops models list
# Output: table with columns: Model, Context Window, Max Completion
```

Note: `squadops profiles list` uses the short name "profiles" (established in SIP-0065). The API endpoint uses the full path `/api/v1/cycle-request-profiles` to avoid ambiguity with squad profiles. The CLI retains the short name since the `squadops` command context makes it unambiguous.

### 5.11 Dashboard Enhancements

The Home (Signal) perspective gets minor updates to surface the new capabilities:

- **Quick action card** — "Create Cycle" button. Behavior: navigates to the Cycles perspective first (setting the active perspective in the shell), then opens the creation modal after the perspective is mounted. This two-step sequence avoids race conditions where the modal opens before the perspective's data is loaded.
- **Pending gates badge** — existing alert badge enhanced to show the count of runs in `waiting` status with a "Review" link that navigates to the Cycles perspective with the waiting cycle pre-selected in the selection state.

### 5.12 Overlay Modal Routing

The cycle creation modal is registered as an overlay panel tied to the `cycles` perspective:

```toml
[[contributions.panel]]
slot = "ui.slot.overlay"
perspective = "cycles"
component = "squadops-cycles-create-modal"
priority = 900
```

**Opening from the Cycles perspective**: "New Cycle" button sets `modalOpen = true` in the perspective state. The overlay component reads this prop.

**Opening from the Dashboard**: the "Create Cycle" quick action performs a two-step navigation:
1. Set active perspective to `cycles` (via Continuum shell navigation API).
2. After perspective mount (`onMount` callback), set `modalOpen = true`.

This guarantees the perspective's data (projects, profiles) is fetched before the modal opens.

**Close behavior**: closing the modal resets `modalOpen = false` and clears any partially-filled form state. The selection state is unchanged (unless a cycle was successfully created, in which case the new cycle is selected).

---

## 6. Phasing

### Phase 1: API + CLI Foundation
- Implement `GET /api/v1/cycle-request-profiles` endpoint (returns cycle request profiles as JSON)
- Implement `GET /api/v1/models` endpoint (returns model registry as JSON)
- Extend `PromptMeta` with optional `type` and `required` fields
- Add `squadops profiles show <profile-name>` CLI command
- Add `squadops models list` CLI command
- Tests for new endpoints, schema extension, and CLI commands

### Phase 2: Master-Detail Layout + Gate Decisions
- New `CyclesPerspective.svelte` wrapper component with grid split and selection state model
- Move cycle list to left pane, run detail to right pane
- Run timeline collapses under the selected cycle in the left pane
- Plugin.toml updated: single panel contribution replaces three separate ones
- Inline gate approve/reject buttons with safety semantics (disabled states, in-flight, error handling)
- Artifact list with type filter chips in the right pane

### Phase 3: Cycle Creation Modal
- "New Cycle" button in Cycles perspective header
- Modal with three sections: Project & Squad, PRD, Profile & Parameters
- Dynamic parameter rendering from profile `prompts` metadata (§5.8 schema)
- Applied defaults preview with client-side merge (§5.7)
- PRD size constraints (50KB warn, 200KB block)
- Submit via `squadops.create_cycle` command bus
- Post-creation: auto-select the new cycle in the list
- Validation and error handling (negative-path behaviors)

### Phase 4: Projects & Dashboard Polish
- Squad profile detail card with model metadata from `GET /api/v1/models`
- Project detail card with PRD preview and recent cycles
- Dashboard "Create Cycle" quick action with two-step navigation (§5.12)
- Pending gates badge with navigation link

---

## 7. Data Flow

### Command vs HTTP Boundary
```
┌─────────────────────────────────────────────────────┐
│                    Runtime API                       │
│              (source of truth for all state)         │
└────────┬────────────────────────────┬───────────────┘
         │                            │
    ┌────┴─────┐               ┌──────┴──────┐
    │ Console  │               │    CLI      │
    │ (BFF)    │               │ (httpx)     │
    └────┬─────┘               └─────────────┘
         │
    ┌────┴──────────────────────────────┐
    │ Reads:  fetch(/api/v1/...) proxy  │
    │ Writes: command bus → BFF handler │
    └───────────────────────────────────┘
```

### Cycle Creation Flow
```
Console Modal                Console BFF              Runtime API
     │                           │                        │
     │ 1. GET /api/v1/projects ──┼──── proxy ────────────▶│
     │ 2. GET /api/v1/squad-profiles ┼── proxy ──────────▶│
     │ 3. GET /api/v1/cycle-request-profiles ── proxy ───▶│
     │                           │                        │
     │ 4. Operator fills form    │                        │
     │ 5. Submit (command bus) ──▶ squadops.create_cycle  │
     │                           │── POST /cycles ───────▶│
     │                           │◀── {cycle_id, run_id} ─│
     │ 6. Auto-select new cycle ◀│                        │
```

### Gate Decision Flow
```
Right Pane                   Console BFF              Runtime API
     │                           │                        │
     │ Run status = "waiting"    │                        │
     │ Gate: plan-review ⏳      │                        │
     │                           │                        │
     │ [Approve] clicked ────────▶ squadops.gate_approve  │
     │ (buttons disabled)        │── POST /gates/... ────▶│
     │                           │◀── updated run ────────│
     │ Re-fetch run detail ──────┼── GET /runs/... ──────▶│
     │ Gate: plan-review ✓       │                        │
     │ (buttons replaced)        │                        │
```

---

## 8. Plugin Architecture Changes

### Current (SIP-0069)
```toml
# Three separate panels stacked vertically
[[contributions.panel]]
component = "squadops-cycles-list"          # main slot, priority 800
[[contributions.panel]]
component = "squadops-cycles-run-timeline"  # main slot, priority 700
[[contributions.panel]]
component = "squadops-cycles-run-detail"    # main slot, priority 600
```

### Proposed
```toml
# Single composite panel owns the perspective layout
[[contributions.panel]]
slot = "ui.slot.main"
perspective = "cycles"
component = "squadops-cycles-perspective"
priority = 800

# Modal registered as an overlay
[[contributions.panel]]
slot = "ui.slot.overlay"
perspective = "cycles"
component = "squadops-cycles-create-modal"
priority = 900
```

The three existing components (`CyclesList`, `CyclesRunTimeline`, `CyclesRunDetail`) become internal imports of `CyclesPerspective.svelte` rather than standalone custom elements. This gives the perspective component control over layout (grid split) and state coordination (selected cycle/run flows from parent to children via props, not CustomEvent dispatching).

---

## 9. Component Inventory

| Component | Status | Description |
|-----------|--------|-------------|
| `CyclesPerspective.svelte` | **New** | Grid wrapper: left pane (list + timeline) / right pane (detail). Owns selection state. |
| `CycleCreateModal.svelte` | **New** | Multi-section cycle creation form with validation |
| `ProfileParamRenderer.svelte` | **New** | Dynamic form fields from cycle request profile `prompts` metadata (§5.8 schema) |
| `GateDecisionCard.svelte` | **New** | Inline approve/reject buttons with safety semantics |
| `ArtifactTypeFilter.svelte` | **New** | Type filter chips for artifact list (All / Docs / Code / Tests / Config) |
| `SquadProfileDetail.svelte` | **New** | Agent table with model metadata |
| `CyclesList.svelte` | **Modified** | Add "New Cycle" button, emit selection to parent via props (not CustomEvent) |
| `CyclesRunDetail.svelte` | **Modified** | Embed `GateDecisionCard`, add artifact list with `ArtifactTypeFilter` |
| `CyclesRunTimeline.svelte` | **Modified** | Inline under selected cycle in left pane |
| `ProjectsList.svelte` | **Modified** | Clickable rows open project detail card |
| `ProjectsProfiles.svelte` | **Modified** | Clickable rows open `SquadProfileDetail` |

---

## 10. API Summary

| Method | Path | Source | Purpose |
|--------|------|--------|---------|
| GET | `/api/v1/cycle-request-profiles` | **New** | List cycle request profiles with prompts metadata |
| GET | `/api/v1/models` | **New** | List model registry entries |
| GET | `/api/v1/projects` | Existing | Project list for cycle creation |
| GET | `/api/v1/squad-profiles` | Existing | Squad profile list for cycle creation |
| POST | `/api/v1/projects/{id}/cycles` | Existing | Create cycle (via command bus) |
| POST | `/api/v1/.../gates/{gate_name}` | Existing | Gate decision (via command bus) |
| GET | `/api/v1/.../runs/{run_id}` | Existing | Run detail with gates |
| GET | `/api/v1/.../artifacts` | Existing | Artifact listing |

### CLI Command Summary

| Command | Status | Description |
|---------|--------|-------------|
| `squadops profiles list` | Existing (SIP-0065) | List cycle request profiles |
| `squadops profiles show <name>` | **New** | Show profile defaults + prompts metadata |
| `squadops models list` | **New** | List known models with context windows |

---

## 11. Acceptance Criteria

### Happy Path
- **AC-1**: Operator can create a cycle entirely from the console — project selection, squad profile, PRD text, profile parameters — without touching the CLI.
- **AC-2**: Cycles perspective uses a split-pane layout. Clicking a cycle shows run detail in the right pane without scrolling.
- **AC-3**: When a run is waiting at a gate, the right pane shows Approve and Reject buttons. Clicking Approve resumes the run. Reject requires confirmation.
- **AC-4**: Cycle request profile parameters render dynamically from the profile's `prompts` metadata (dropdowns for choices, text inputs for free text, toggles for booleans).
- **AC-5**: `squadops profiles show <name>` CLI command displays profile defaults and prompt metadata.
- **AC-6**: `squadops models list` CLI command displays known models with context windows.
- **AC-7**: `GET /api/v1/cycle-request-profiles` returns all registered cycle request profiles as JSON.
- **AC-8**: `GET /api/v1/models` returns model registry entries as JSON.
- **AC-9**: Projects perspective shows agent/model details when a squad profile is expanded.
- **AC-10**: Dashboard has a "Create Cycle" quick action that navigates to the Cycles perspective and opens the creation modal.

### Negative Path
- **AC-11**: Missing required fields (project, squad profile, PRD) block form submission with inline validation errors. Submit button remains disabled until all required fields are filled.
- **AC-12**: Cycle creation failure (API error) shows an error message inline in the modal. Form remains open with inputs preserved. No phantom cycle is created in the list.
- **AC-13**: Gate decision failure (API error) shows an error toast. Gate buttons re-enable. Gate state is not optimistically updated — the UI re-fetches from the API to confirm current state.
- **AC-14**: PRD exceeding 200KB is blocked with an inline warning. PRD between 50KB and 200KB shows a non-blocking size warning.

---

## 12. Migration & Backward Compatibility

- No breaking changes. Existing cycle creation via CLI is unaffected.
- The three existing Cycles plugin panels are refactored into a single composite component. The existing `squadops:select-cycle` CustomEvent is replaced by parent-child prop passing, but the command IDs (`squadops.create_cycle`, `squadops.gate_approve`, etc.) remain unchanged.
- New API endpoints are additive (GET only, no state mutation).
- `PromptMeta` schema extension adds optional fields (`type`, `required`) — existing profiles without these fields continue to work via type inference (§5.8).

---

## 13. Future Considerations

- **Squad profile CRUD API** — allow creating/editing profiles via the console instead of YAML files. Requires a persistence layer for profiles (currently config-file-based).
- **PRD template library** — pre-built PRD templates selectable from the creation modal.
- **WebSocket live updates** — replace 15s polling with push notifications for cycle status changes.
- **Cycle comparison view** — side-by-side comparison of two cycle runs (artifacts, metrics, duration).
- **Role-based form visibility** — viewers see read-only cycle detail; operators see creation + gate buttons (partially implemented via SIP-0069 AC-11).
- **Artifact grouping by role** — group artifacts by producing agent role (e.g., "Neo: source files", "Eve: test files") instead of flat list. Requires artifact metadata to include `producing_role`.
- **Backend-computed applied defaults preview** — a `POST /api/v1/cycle-request-profiles/{name}/resolve` endpoint that returns the merged defaults given a set of overrides, replacing client-side merge with server-authoritative resolution.
