<svelte:options customElement="squadops-home-summary" />

<script>
  import { onMount, onDestroy } from 'svelte';

  let projects = $state([]);
  let allCycles = $state([]);
  let recentRuns = $state([]);
  let loading = $state(true);
  let error = $state(null);
  let pollTimer = $state(null);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) {
      return window.squadops.apiFetch(url, opts);
    }
    return fetch(url, opts);
  }

  function executeCommand(commandId, params) {
    if (window.squadops?.executeCommand) {
      window.squadops.executeCommand(commandId, params);
    }
  }

  async function fetchData() {
    // Fetch projects + cycles (degrade gracefully on failure)
    try {
      const projResp = await apiFetch(`${apiBase}/api/v1/projects`);
      if (projResp.ok) {
        const allProjects = await projResp.json();
        projects = allProjects;

        const projectSlice = allProjects.slice(0, 10);
        const runs = [];
        for (const proj of projectSlice) {
          try {
            const cyclesResp = await apiFetch(
              `${apiBase}/api/v1/projects/${proj.project_id}/cycles`
            );
            if (cyclesResp.ok) {
              const cycles = await cyclesResp.json();
              for (const cycle of cycles.slice(0, 5)) {
                const hasPausedRun = (cycle.runs || []).some(r => r.status === 'paused');
                runs.push({
                  project_id: proj.project_id,
                  cycle_id: cycle.cycle_id,
                  status: cycle.status || 'unknown',
                  has_paused_run: hasPausedRun,
                  created_at: cycle.created_at,
                });
              }
            }
          } catch {
            // Skip failed project fetches
          }
        }
        runs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        allCycles = runs;
        recentRuns = runs.slice(0, 5);
      }
    } catch {
      // Projects API unavailable — show dashboard with agent data only
    }

    loading = false;
    error = null;
  }

  onMount(() => {
    fetchData();
    pollTimer = setInterval(fetchData, 30000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  function statusColor(status) {
    const colors = {
      completed: 'var(--continuum-accent-success, #22c55e)',
      active: 'var(--continuum-accent-primary, #6366f1)',
      failed: 'var(--continuum-accent-danger, #ef4444)',
      created: 'var(--continuum-text-muted, #94a3b8)',
      cancelled: 'var(--continuum-text-muted, #94a3b8)',
    };
    return colors[status] || colors.created;
  }

  let activeCycleCount = $derived(
    allCycles.filter(r => r.status === 'active').length
  );
  let pendingGateCount = $derived(
    allCycles.filter(r => r.has_paused_run).length
  );
</script>

<div class="home-summary">
  <h2 class="title">SquadOps Dashboard</h2>

  {#if loading}
    <div class="loading">Loading...</div>
  {:else if error}
    <div class="error">Error: {error}</div>
  {:else}
    <div class="cards">
      <!-- Active Cycles -->
      <div class="card">
        <div class="card-header">Active Cycles</div>
        <div class="card-value">{activeCycleCount}</div>
        <div class="card-label">across {projects.length} projects</div>
      </div>

      <!-- Pending Gates -->
      <div class="card" class:card-highlight={pendingGateCount > 0}>
        <div class="card-header">
          Pending Gates
          {#if pendingGateCount > 0}
            <span class="gate-badge">{pendingGateCount}</span>
          {/if}
        </div>
        <div class="card-value">{pendingGateCount}</div>
        <div class="card-label">awaiting decision</div>
      </div>

      <!-- Create Cycle quick action -->
      <div
        class="card card-action"
        role="button"
        tabindex="0"
        onclick={() => executeCommand('squadops.open_create_cycle')}
        onkeydown={(e) => { if (e.key === 'Enter') executeCommand('squadops.open_create_cycle'); }}
      >
        <div class="card-header">Quick Action</div>
        <div class="card-action-label">+ Create Cycle</div>
        <div class="card-label">Start a new development cycle</div>
      </div>
    </div>

    <!-- Recent Runs -->
    <div class="section">
      <h3 class="section-title">Recent Runs</h3>
      {#if recentRuns.length === 0}
        <div class="empty">No recent runs</div>
      {:else}
        <div class="run-list">
          {#each recentRuns as run}
            <div class="run-item">
              <span class="run-badge" style="background: {statusColor(run.status)}">{run.status}</span>
              <span class="run-project">{run.project_id}</span>
              <span class="run-id">{run.cycle_id?.slice(0, 12)}</span>
            </div>
          {/each}
        </div>
      {/if}
      {#if projects.length > 10}
        <div class="more">+{projects.length - 10} more projects</div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .home-summary {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .title {
    font-size: var(--continuum-font-size-lg, 1.25rem);
    font-weight: 600;
    margin: 0 0 var(--continuum-space-lg, 24px) 0;
  }

  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: var(--continuum-space-md, 16px);
    margin-bottom: var(--continuum-space-lg, 24px);
  }

  .card {
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-md, 8px);
    padding: var(--continuum-space-md, 16px);
  }

  .card-highlight {
    border-color: var(--continuum-accent-warning, #f59e0b);
  }

  .card-action {
    cursor: pointer;
    border-style: dashed;
    transition: border-color 0.15s, background 0.15s;
  }

  .card-action:hover {
    border-color: var(--continuum-accent-primary, #6366f1);
    background: rgba(99, 102, 241, 0.05);
  }

  .card-action-label {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--continuum-accent-primary, #6366f1);
    margin: var(--continuum-space-xs, 4px) 0;
  }

  .card-header {
    font-size: var(--continuum-font-size-sm, 0.875rem);
    color: var(--continuum-text-muted, #94a3b8);
    margin-bottom: var(--continuum-space-xs, 4px);
    display: flex;
    align-items: center;
    gap: var(--continuum-space-xs, 4px);
  }

  .gate-badge {
    font-size: 0.65rem;
    background: var(--continuum-accent-warning, #f59e0b);
    color: #000;
    padding: 1px 5px;
    border-radius: 9999px;
    font-weight: 700;
    line-height: 1.2;
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

  .section { margin-top: var(--continuum-space-lg, 24px); }

  .section-title {
    font-size: var(--continuum-font-size-md, 1rem);
    font-weight: 600;
    margin: 0 0 var(--continuum-space-sm, 8px) 0;
  }

  .run-list { display: flex; flex-direction: column; gap: var(--continuum-space-xs, 4px); }

  .run-item {
    display: flex;
    align-items: center;
    gap: var(--continuum-space-sm, 8px);
    padding: var(--continuum-space-sm, 8px);
    background: var(--continuum-bg-secondary, #1e293b);
    border-radius: var(--continuum-radius-sm, 4px);
  }

  .run-badge {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 2px 8px;
    border-radius: var(--continuum-radius-sm, 4px);
    color: #fff;
    font-weight: 600;
    text-transform: uppercase;
  }

  .run-project { font-weight: 500; }

  .run-id {
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
  }

  .loading, .error, .empty {
    padding: var(--continuum-space-lg, 24px);
    text-align: center;
    color: var(--continuum-text-muted, #94a3b8);
  }

  .error { color: var(--continuum-accent-danger, #ef4444); }

  .more {
    margin-top: var(--continuum-space-sm, 8px);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    color: var(--continuum-text-muted, #94a3b8);
    text-align: center;
  }
</style>
