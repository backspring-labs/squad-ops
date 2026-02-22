# Artifact Document Viewer — Modal Overlay

## Context

The `squadops.artifacts` plugin currently supports browsing, metadata display, and download — but no inline content viewing. Cycle artifacts (PRDs, code, test reports, build plans) are detailed documents that users need to read without leaving the console. This plan adds a modal overlay viewer to the existing artifacts plugin with type-aware rendering (markdown, code, JSON/YAML, plain text).

## Architecture Decision

**Extend `squadops.artifacts`** (no new plugin). The viewer is tightly coupled to artifact selection and download — same data, same API, same event bus. A separate plugin would just duplicate the wiring.

**Self-managed modal** (no Continuum framework changes). Components registered in `ui.slot.modal` are always rendered. The viewer component starts hidden and shows itself when it receives a `squadops:view-artifact` window event. This avoids needing Shell.svelte changes or new Continuum primitives.

## Files to Modify

| File | Change |
|------|--------|
| `console/continuum-plugins/squadops.artifacts/ui/src/ArtifactsViewer.svelte` | **NEW** — modal overlay component |
| `console/continuum-plugins/squadops.artifacts/ui/src/index.js` | Add `ArtifactsViewer` import |
| `console/continuum-plugins/squadops.artifacts/ui/package.json` | Add `marked` + `highlight.js` deps |
| `console/continuum-plugins/squadops.artifacts/__init__.py` | Register modal panel contribution |
| `console/continuum-plugins/squadops.artifacts/plugin.toml` | Add modal panel entry |
| `console/continuum-plugins/squadops.artifacts/ui/src/ArtifactsDetail.svelte` | Add "View" button |
| `console/continuum-plugins/squadops.artifacts/ui/src/ArtifactsList.svelte` | Add double-click to view |
| `tests/unit/console/test_artifacts_plugin.py` | Update contribution count, add modal panel test |

## Phase 1: ArtifactsViewer Component

Create `ArtifactsViewer.svelte` as a self-managed modal overlay custom element.

### Behavior
- Registered in `ui.slot.modal` — always in DOM, starts hidden (`visible = false`)
- Listens on `window` for `squadops:view-artifact` custom event
- On event: sets `visible = true`, stores artifact metadata, fetches content from `/api/v1/artifacts/{id}/download`
- Renders full-screen modal overlay with:
  - **Header**: filename, artifact type badge, close button (X)
  - **Content area**: type-aware rendered content (scrollable)
  - **Footer**: download button, metadata summary (size, media type)
- Close via: X button, Escape key, or backdrop click

### Content Rendering by Media Type

| Media Type | Renderer |
|------------|----------|
| `text/markdown` | `marked` library → sanitized HTML |
| `application/json` | Pretty-print + `highlight.js` syntax highlighting |
| `application/yaml`, `text/yaml` | `highlight.js` syntax highlighting |
| `text/plain` | Monospace pre-formatted block |
| `text/html` | Sandboxed display (escaped, rendered in pre) |
| Code types (`text/x-python`, `application/javascript`, etc.) | `highlight.js` with language auto-detect |
| Unknown/binary | "Preview not available" message + download button |

### Component Structure
```svelte
<svelte:options customElement="squadops-artifacts-viewer" />

<!-- Self-managed modal: always rendered in DOM, toggles visibility -->
{#if visible}
  <div class="modal-backdrop" onclick={close} onkeydown={onKey}>
    <div class="modal-container" onclick|stopPropagation>
      <header> filename + type badge + close button </header>
      <div class="modal-body">
        {#if loading} spinner
        {:else if error} error message
        {:else if renderMode === 'markdown'} {@html renderedHtml}
        {:else if renderMode === 'highlighted'} {@html highlightedCode}
        {:else} <pre>{rawText}</pre>
        {/if}
      </div>
      <footer> download button + metadata </footer>
    </div>
  </div>
{/if}
```

### Styling
- Backdrop: semi-transparent dark overlay (`rgba(0,0,0,0.7)`)
- Container: 90vw x 90vh max, centered, dark background matching Continuum theme
- Uses `--continuum-*` CSS custom properties for consistency
- Content area: scrollable, padding for readability
- Markdown: styled headings, lists, code blocks, tables
- Code: `highlight.js` dark theme (e.g., `github-dark`)

## Phase 2: Plugin Registration & Wiring

### `__init__.py` — add modal panel
```python
ctx.register_contribution("panel", {
    "slot": "ui.slot.modal",
    "component": "squadops-artifacts-viewer",
    "priority": 100,
})
```

No perspective filter — modal is global (available from any perspective).

### `plugin.toml` — add modal panel entry
```toml
[[contributions.panel]]
slot = "ui.slot.modal"
component = "squadops-artifacts-viewer"
priority = 100
```

### `index.js` — add import
```javascript
import './ArtifactsViewer.svelte';
```

## Phase 3: Trigger Points

### ArtifactsDetail.svelte — add "View" button
Add a "View" button next to the existing "Download" button that dispatches:
```javascript
function view() {
  if (!artifact) return;
  window.dispatchEvent(new CustomEvent('squadops:view-artifact', { detail: artifact }));
}
```

### ArtifactsList.svelte — add double-click to view
Add `ondblclick` handler on table rows:
```javascript
function viewArtifact(artifact) {
  window.dispatchEvent(new CustomEvent('squadops:view-artifact', { detail: artifact }));
}
```
Single-click continues to select (populate right-rail detail), double-click opens viewer.

## Phase 4: Dependencies

### `package.json` additions
```json
{
  "dependencies": {
    "marked": "^15.0.0",
    "highlight.js": "^11.11.0"
  }
}
```

- **marked**: Markdown → HTML renderer (~40KB). Mature, fast, zero dependencies.
- **highlight.js**: Syntax highlighting (~100KB with selected languages). Import only needed languages (python, javascript, json, yaml, bash, html, css) to minimize bundle.

Both are tree-shakeable and work in browser without Node.js runtime.

## Phase 5: Tests

### Plugin registration test updates (`test_artifacts_plugin.py`)
- Update `test_total_contributions`: 6 → 7 (add modal panel)
- Add `test_panel_artifacts_viewer_in_modal`: verify component name, slot = `ui.slot.modal`
- Add `test_viewer_has_no_perspective`: verify no perspective key (global modal)

## Verification

```bash
# Build plugin UI
cd console/continuum-plugins/squadops.artifacts/ui && npm ci && npm run build

# Run plugin registration tests
pytest tests/unit/console/test_artifacts_plugin.py -v

# Run full regression suite
./scripts/dev/run_new_arch_tests.sh

# Manual: rebuild console container and test
docker compose build squadops-console && docker compose up -d squadops-console

# Manual verification in browser at http://localhost:4040:
# 1. Navigate to Signal perspective → Artifacts list
# 2. Click an artifact row → right-rail shows metadata + "View" button
# 3. Click "View" → modal overlay opens with rendered content
# 4. Double-click artifact row → modal opens directly
# 5. Press Escape / click backdrop / click X → modal closes
# 6. Test with different artifact types (markdown, JSON, code, plain text)
```
