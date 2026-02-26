<svelte:options customElement="squadops-cycles-perspective" />

<!--
  CyclesPerspective — composite wrapper with master-detail grid layout (SIP-0074 §5.2).

  Owns all selection state and passes it to children as props.
  Selection rules:
  1. Click cycle -> set project_id + cycle_id, auto-set active_run_id to latest run
     "Latest run" = highest run_number (API returns runs sorted descending; UI takes first)
  2. Click run in timeline -> set active_run_id
  3. No runs -> active_run_id = null, right pane shows empty state
  4. Deselect -> all null, right pane shows empty state
  5. After creating cycle -> set to new cycle_id + run_id from response
-->
<script>
  import CyclesList from './CyclesList.svelte';
  import CyclesRunTimeline from './CyclesRunTimeline.svelte';
  import CyclesRunDetail from './CyclesRunDetail.svelte';

  let selection = $state({
    project_id: null,
    cycle_id: null,
    active_run_id: null,
  });

  let modalOpen = $state(false);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  async function handleSelectCycle(projectId, cycleId) {
    selection.project_id = projectId;
    selection.cycle_id = cycleId;
    selection.active_run_id = null;

    // Auto-select latest run (highest run_number = first in API response)
    try {
      const resp = await apiFetch(
        `${apiBase}/api/v1/projects/${projectId}/cycles/${cycleId}/runs`
      );
      if (resp.ok) {
        const runs = await resp.json();
        if (runs.length > 0) {
          selection.active_run_id = runs[0].run_id;
        }
      }
    } catch {
      // Non-critical — user can click a run manually
    }
  }

  function handleSelectRun(runId) {
    selection.active_run_id = runId;
  }

  function handleNewCycle() {
    modalOpen = true;
  }
</script>

<div class="cycles-perspective">
  <div class="left-pane">
    <CyclesList
      onSelectCycle={handleSelectCycle}
      onNewCycle={handleNewCycle}
    />
    {#if selection.cycle_id}
      <CyclesRunTimeline
        projectId={selection.project_id}
        cycleId={selection.cycle_id}
        onSelectRun={handleSelectRun}
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
    {:else if selection.cycle_id}
      <div class="empty-state">No runs yet. Waiting for execution to start.</div>
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
    overflow: hidden;
  }

  .left-pane {
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }

  .right-pane {
    overflow-y: auto;
  }

  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--continuum-text-muted, #94a3b8);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }
</style>
