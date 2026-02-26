<svelte:options customElement="squadops-cycles-perspective" />

<!--
  CyclesPerspective — composite wrapper with master-detail layout (SIP-0074 §5.2).

  Layout:
  - Left pane (75%): CyclesList (filterable table)
  - Right pane (25%, stacked):
    1. Cycle Stats — 2x2 card grid matching dashboard card style
    2. Active Cycle — placeholder table for running cycle
    3. Hint to select a cycle, then run timeline + run detail

  Selection rules:
  1. Click cycle -> set project_id + cycle_id, auto-set active_run_id to latest run
  2. Click run in timeline -> set active_run_id
  3. No runs -> active_run_id = null, shows empty state
  4. Deselect -> all null, shows empty state
  5. After creating cycle -> set to new cycle_id + run_id from response
-->
<script>
  import { onMount, onDestroy } from 'svelte';
  import CyclesList from './CyclesList.svelte';
  import CyclesRunTimeline from './CyclesRunTimeline.svelte';
  import CyclesRunDetail from './CyclesRunDetail.svelte';
  import CycleCreateModal from './CycleCreateModal.svelte';

  let selection = $state({
    project_id: null,
    cycle_id: null,
    active_run_id: null,
  });

  let modalOpen = $state(false);

  // Cycle stats — fetched independently, always visible
  let stats = $state({ total: 0, completed_pct: 0, active_runs: 0, artifacts: 0 });
  let activeCycle = $state(null);
  let statsPollTimer = $state(null);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  async function fetchStats() {
    try {
      const projResp = await apiFetch(`${apiBase}/api/v1/projects`);
      if (!projResp.ok) return;
      const projects = await projResp.json();

      let total = 0;
      let completed = 0;
      let activeRuns = 0;
      let artifactCount = 0;
      let firstRunning = null;

      for (const proj of projects.slice(0, 20)) {
        try {
          const resp = await apiFetch(`${apiBase}/api/v1/projects/${proj.project_id}/cycles`);
          if (!resp.ok) continue;
          const cycles = await resp.json();
          total += cycles.length;
          for (const c of cycles) {
            if (c.status === 'completed') completed++;
            // Cycle status is 'active' (not 'running') when runs are in progress
            if (c.status === 'active') {
              activeRuns++;
              if (!firstRunning) {
                firstRunning = { project_id: proj.project_id, ...c };
              }
            }
            if (c.runs) {
              for (const r of c.runs) {
                artifactCount += (r.artifact_refs || []).length;
              }
            }
          }
        } catch {
          // Skip failed project
        }
      }

      const completedPct = total > 0 ? Math.round((completed / total) * 100) : 0;
      stats = { total, completed_pct: completedPct, active_runs: activeRuns, artifacts: artifactCount };
      activeCycle = firstRunning;
    } catch {
      // Stats are best-effort
    }
  }

  onMount(() => {
    fetchStats();
    statsPollTimer = setInterval(fetchStats, 20000);
  });

  onDestroy(() => {
    if (statsPollTimer) clearInterval(statsPollTimer);
  });

  async function handleSelectCycle(projectId, cycleId) {
    selection.project_id = projectId;
    selection.cycle_id = cycleId;
    selection.active_run_id = null;

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
      // Non-critical
    }
  }

  function handleSelectRun(runId) {
    selection.active_run_id = runId;
  }

  function handleNewCycle() {
    modalOpen = true;
  }

  function handleModalClose() {
    modalOpen = false;
  }

  function handleCycleCreated({ project_id, cycle_id, run_id }) {
    modalOpen = false;
    selection.project_id = project_id;
    selection.cycle_id = cycle_id;
    selection.active_run_id = run_id || null;
    fetchStats();
  }
</script>

<div class="cycles-perspective">
  <div class="left-pane">
    <CyclesList
      onSelectCycle={handleSelectCycle}
      onNewCycle={handleNewCycle}
    />
  </div>

  <div class="right-pane">
    <!-- Cycle Stats -->
    <div class="section">
      <h3 class="section-title">Cycle Stats</h3>
      <div class="cards">
        <div class="card">
          <div class="card-header">Total Cycles</div>
          <div class="card-value">{stats.total}</div>
          <div class="card-label">all time</div>
        </div>
        <div class="card">
          <div class="card-header">Completed</div>
          <div class="card-value">{stats.completed_pct}%</div>
          <div class="card-label">success rate</div>
        </div>
        <div class="card">
          <div class="card-header">Active Runs</div>
          <div class="card-value">{stats.active_runs}</div>
          <div class="card-label">in progress</div>
        </div>
        <div class="card">
          <div class="card-header">Artifacts</div>
          <div class="card-value">{stats.artifacts}</div>
          <div class="card-label">generated</div>
        </div>
      </div>
    </div>

    <!-- Active Cycle -->
    <div class="section">
      <h3 class="section-title">Active Cycle</h3>
      {#if activeCycle}
        <table class="active-table">
          <thead>
            <tr>
              <th>Project</th>
              <th>Cycle</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr
              class="active-row"
              onclick={() => handleSelectCycle(activeCycle.project_id, activeCycle.cycle_id)}
            >
              <td>{activeCycle.project_id}</td>
              <td class="mono">{activeCycle.cycle_id?.slice(0, 12)}</td>
              <td><span class="status-dot active"></span> Active</td>
            </tr>
          </tbody>
        </table>
      {:else}
        <table class="active-table">
          <thead>
            <tr>
              <th>Project</th>
              <th>Cycle</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr class="placeholder-row">
              <td colspan="3">No active cycles</td>
            </tr>
          </tbody>
        </table>
      {/if}
    </div>

    <!-- Selected cycle detail -->
    <div class="section">
      <h3 class="section-title">Run Detail</h3>
      {#if selection.cycle_id}
        <CyclesRunTimeline
          projectId={selection.project_id}
          cycleId={selection.cycle_id}
          onSelectRun={handleSelectRun}
        />
        {#if selection.active_run_id}
          <CyclesRunDetail
            projectId={selection.project_id}
            cycleId={selection.cycle_id}
            runId={selection.active_run_id}
          />
        {/if}
      {:else}
        <div class="hint">Select a cycle from the list to view its runs.</div>
      {/if}
    </div>
  </div>
</div>

{#if modalOpen}
  <CycleCreateModal
    onCreated={handleCycleCreated}
    onClose={handleModalClose}
  />
{/if}

<style>
  .cycles-perspective {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 1px;
    height: 100%;
    overflow: hidden;
    background: var(--continuum-border, #334155);
  }

  .left-pane {
    overflow-y: auto;
    background: var(--continuum-bg-primary, #0f172a);
  }

  .right-pane {
    overflow-y: auto;
    background: var(--continuum-bg-primary, #0f172a);
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }

  /* ── Sections ─────────────────────────────── */
  .section {
    margin-bottom: var(--continuum-space-lg, 24px);
  }

  .section-title {
    font-size: var(--continuum-font-size-md, 1rem);
    font-weight: 600;
    margin: 0 0 var(--continuum-space-sm, 8px) 0;
  }

  /* ── Cards (identical to HomeSummary dashboard) ── */
  .cards {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--continuum-space-md, 16px);
    margin-bottom: var(--continuum-space-lg, 24px);
  }

  .card {
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-md, 8px);
    padding: var(--continuum-space-md, 16px);
  }

  .card-header {
    font-size: var(--continuum-font-size-sm, 0.875rem);
    color: var(--continuum-text-muted, #94a3b8);
    margin-bottom: var(--continuum-space-xs, 4px);
    display: flex;
    align-items: center;
    gap: var(--continuum-space-xs, 4px);
  }

  .card-value {
    font-size: 2rem;
    font-weight: 700;
    font-family: var(--continuum-font-mono, monospace);
  }

  .card-label {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
  }

  /* ── Active cycle table ───────────────────── */
  .active-table {
    width: 100%;
    border-collapse: collapse;
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-md, 8px);
    overflow: hidden;
  }

  .active-table th,
  .active-table td {
    text-align: left;
    padding: var(--continuum-space-sm, 8px);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    border-bottom: 1px solid var(--continuum-border, #334155);
  }

  .active-table th {
    color: var(--continuum-text-muted, #94a3b8);
    font-weight: 500;
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }

  .active-table tbody tr:last-child td {
    border-bottom: none;
  }

  .active-row {
    cursor: pointer;
    transition: background 0.15s;
  }

  .active-row:hover {
    background: var(--continuum-bg-tertiary, #273549);
  }

  .placeholder-row td {
    color: var(--continuum-text-muted, #94a3b8);
    text-align: center;
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: var(--continuum-space-md, 16px);
  }

  .mono {
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }

  .status-dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    margin-right: 4px;
    vertical-align: middle;
  }

  .status-dot.active {
    background: var(--continuum-accent-primary, #6366f1);
    animation: pulse 2s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }

  /* ── Hint ─────────────────────────────────── */
  .hint {
    color: var(--continuum-text-muted, #94a3b8);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    padding: var(--continuum-space-sm, 8px) 0;
  }
</style>
