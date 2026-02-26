<script>
  import { onMount, onDestroy } from 'svelte';

  let { onSelectCycle = null, onNewCycle = null } = $props();

  let projects = $state([]);
  let cycles = $state([]);
  let filterText = $state('');
  let filterStatus = $state('all');
  let loading = $state(true);
  let error = $state(null);
  let pollTimer = $state(null);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  async function fetchCycles() {
    try {
      const projResp = await apiFetch(`${apiBase}/api/v1/projects`);
      if (!projResp.ok) throw new Error(`Projects: ${projResp.status}`);
      const allProjects = await projResp.json();
      projects = allProjects;

      const allCycles = [];
      for (const proj of allProjects) {
        try {
          const cyclesResp = await apiFetch(
            `${apiBase}/api/v1/projects/${proj.project_id}/cycles`
          );
          if (cyclesResp.ok) {
            const projCycles = await cyclesResp.json();
            for (const c of projCycles) {
              allCycles.push({
                project_id: proj.project_id,
                cycle_id: c.cycle_id,
                status: c.status || 'unknown',
                created_at: c.created_at,
              });
            }
          }
        } catch {
          // Skip failed project fetches
        }
      }

      // Sort newest first
      allCycles.sort((a, b) => {
        const da = a.created_at ? new Date(a.created_at) : 0;
        const db = b.created_at ? new Date(b.created_at) : 0;
        return db - da;
      });

      cycles = allCycles;
      loading = false;
      error = null;
    } catch (err) {
      error = err.message;
      loading = false;
    }
  }

  onMount(() => {
    fetchCycles();
    pollTimer = setInterval(fetchCycles, 15000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  function selectCycle(projectId, cycleId) {
    onSelectCycle?.(projectId, cycleId);
  }

  let filteredCycles = $derived(
    cycles.filter((c) => {
      const matchesText =
        !filterText ||
        c.project_id.toLowerCase().includes(filterText.toLowerCase()) ||
        c.cycle_id.toLowerCase().includes(filterText.toLowerCase());
      const matchesStatus =
        filterStatus === 'all' || c.status === filterStatus;
      return matchesText && matchesStatus;
    })
  );

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

  function formatDate(iso) {
    if (!iso) return '--';
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }
</script>

<div class="cycles-list">
  <div class="header">
    <h3 class="title">Cycles</h3>
    {#if onNewCycle}
      <button class="btn btn-new" onclick={() => onNewCycle()}>+ New Cycle</button>
    {/if}
  </div>

  <div class="filters">
    <input
      type="text"
      class="filter-input"
      placeholder="Filter by project or cycle ID..."
      bind:value={filterText}
    />
    <select class="filter-select" bind:value={filterStatus}>
      <option value="all">All statuses</option>
      <option value="created">Created</option>
      <option value="active">Active</option>
      <option value="completed">Completed</option>
      <option value="failed">Failed</option>
      <option value="cancelled">Cancelled</option>
    </select>
  </div>

  {#if loading}
    <div class="loading">Loading cycles...</div>
  {:else if error}
    <div class="error">Error: {error}</div>
  {:else if filteredCycles.length === 0}
    <div class="empty">No cycles match the current filter</div>
  {:else}
    <table class="cycles-table">
      <thead>
        <tr>
          <th>Project</th>
          <th>Cycle ID</th>
          <th>Status</th>
          <th>Created</th>
        </tr>
      </thead>
      <tbody>
        {#each filteredCycles as cycle}
          <tr
            class="cycle-row"
            onclick={() => selectCycle(cycle.project_id, cycle.cycle_id)}
          >
            <td class="cell-project">{cycle.project_id}</td>
            <td class="cell-id">{cycle.cycle_id.slice(0, 12)}</td>
            <td>
              <span
                class="status-badge"
                style="background: {statusColor(cycle.status)}"
              >
                {cycle.status}
              </span>
            </td>
            <td class="cell-date">{formatDate(cycle.created_at)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<style>
  .cycles-list {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--continuum-space-md, 16px);
  }

  .title {
    font-size: var(--continuum-font-size-md, 1rem);
    font-weight: 600;
    margin: 0;
  }

  .btn-new {
    padding: var(--continuum-space-xs, 4px) var(--continuum-space-md, 16px);
    background: var(--continuum-accent-primary, #6366f1);
    color: #fff;
    border: none;
    border-radius: var(--continuum-radius-sm, 4px);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s;
  }

  .btn-new:hover {
    background: var(--continuum-accent-primary-hover, #4f46e5);
  }

  .filters {
    display: flex;
    gap: var(--continuum-space-sm, 8px);
    margin-bottom: var(--continuum-space-md, 16px);
  }

  .filter-input {
    flex: 1;
    padding: var(--continuum-space-sm, 8px);
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    color: var(--continuum-text-primary, #e2e8f0);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    outline: none;
  }

  .filter-input:focus {
    border-color: var(--continuum-accent-primary, #6366f1);
  }

  .filter-select {
    padding: var(--continuum-space-sm, 8px);
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    color: var(--continuum-text-primary, #e2e8f0);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    cursor: pointer;
  }

  .cycles-table {
    width: 100%;
    border-collapse: collapse;
  }

  th,
  td {
    text-align: left;
    padding: var(--continuum-space-sm, 8px);
    border-bottom: 1px solid var(--continuum-border, #334155);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  th {
    color: var(--continuum-text-muted, #94a3b8);
    font-weight: 500;
  }

  .cycle-row {
    cursor: pointer;
    transition: background 0.15s;
  }

  .cycle-row:hover {
    background: var(--continuum-bg-tertiary, #273549);
  }

  .cell-project {
    font-weight: 500;
  }

  .cell-id {
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }

  .cell-date {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
  }

  .status-badge {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 2px 8px;
    border-radius: var(--continuum-radius-sm, 4px);
    color: #fff;
    font-weight: 600;
    text-transform: uppercase;
  }

  .loading,
  .error,
  .empty {
    padding: var(--continuum-space-lg, 24px);
    text-align: center;
    color: var(--continuum-text-muted, #94a3b8);
  }

  .error {
    color: var(--continuum-accent-danger, #ef4444);
  }
</style>
