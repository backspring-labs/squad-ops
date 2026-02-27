<script>
  import { onMount } from 'svelte';

  const apiBase = '';
  let projects = $state([]);
  let selectedProject = $state('');
  let cycles = $state([]);
  let leftCycleId = $state('');
  let rightCycleId = $state('');
  let leftData = $state(null);
  let rightData = $state(null);
  let loading = $state(false);
  let error = $state(null);

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  async function fetchProjects() {
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/projects`);
      if (resp.ok) {
        projects = await resp.json();
      }
    } catch (_) {}
  }

  async function fetchCycles() {
    if (!selectedProject) {
      cycles = [];
      return;
    }
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/projects/${selectedProject}/cycles`);
      if (resp.ok) {
        cycles = await resp.json();
      }
    } catch (_) {}
  }

  async function fetchCycleDetail(projectId, cycleId) {
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/projects/${projectId}/cycles/${cycleId}`);
      if (resp.ok) return resp.json();
    } catch (_) {}
    return null;
  }

  async function compare() {
    if (!leftCycleId || !rightCycleId) return;
    loading = true;
    error = null;
    try {
      const [left, right] = await Promise.all([
        fetchCycleDetail(selectedProject, leftCycleId),
        fetchCycleDetail(selectedProject, rightCycleId),
      ]);
      leftData = left;
      rightData = right;
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  }

  function formatValue(val) {
    if (val === null || val === undefined) return '—';
    if (typeof val === 'object') return JSON.stringify(val, null, 2);
    return String(val);
  }

  let comparisonFields = $derived(() => {
    if (!leftData || !rightData) return [];
    const keys = new Set([
      ...Object.keys(leftData.applied_defaults || {}),
      ...Object.keys(rightData.applied_defaults || {}),
    ]);
    return [...keys].sort().map((key) => ({
      key,
      left: formatValue(leftData.applied_defaults?.[key]),
      right: formatValue(rightData.applied_defaults?.[key]),
      differs: formatValue(leftData.applied_defaults?.[key]) !== formatValue(rightData.applied_defaults?.[key]),
    }));
  });

  $effect(() => {
    if (selectedProject) fetchCycles();
  });

  onMount(fetchProjects);
</script>

<div class="compare-tab">
  <h3 class="section-title">Compare Cycles</h3>

  {#if projects.length === 0}
    <div class="empty">
      <p>Run cycles with different profiles to compare results.</p>
    </div>
  {:else}
    <div class="compare-controls">
      <div class="field-group">
        <label>Project</label>
        <select class="field-select" bind:value={selectedProject}>
          <option value="">Select project...</option>
          {#each projects as proj}
            <option value={proj.project_id}>{proj.name || proj.project_id}</option>
          {/each}
        </select>
      </div>

      {#if cycles.length > 0}
        <div class="field-group">
          <label>Left Cycle</label>
          <select class="field-select" bind:value={leftCycleId}>
            <option value="">Select...</option>
            {#each cycles as c}
              <option value={c.cycle_id}>
                {c.cycle_id.slice(0, 12)} ({c.status}) — {c.squad_profile_id}
              </option>
            {/each}
          </select>
        </div>

        <div class="field-group">
          <label>Right Cycle</label>
          <select class="field-select" bind:value={rightCycleId}>
            <option value="">Select...</option>
            {#each cycles as c}
              <option value={c.cycle_id}>
                {c.cycle_id.slice(0, 12)} ({c.status}) — {c.squad_profile_id}
              </option>
            {/each}
          </select>
        </div>

        <button class="btn btn-compare" onclick={compare} disabled={!leftCycleId || !rightCycleId || loading}>
          {loading ? 'Loading...' : 'Compare'}
        </button>
      {:else if selectedProject}
        <div class="empty-inline">No cycles found for this project.</div>
      {/if}
    </div>

    {#if error}
      <div class="compare-error">{error}</div>
    {/if}

    {#if leftData && rightData}
      <div class="compare-grid">
        <div class="compare-header">
          <div class="compare-col-label"></div>
          <div class="compare-col">
            <strong>{leftData.cycle_id?.slice(0, 12)}</strong>
            <span class="text-muted">{leftData.squad_profile_id}</span>
          </div>
          <div class="compare-col">
            <strong>{rightData.cycle_id?.slice(0, 12)}</strong>
            <span class="text-muted">{rightData.squad_profile_id}</span>
          </div>
        </div>

        <div class="compare-row">
          <div class="compare-col-label">Status</div>
          <div class="compare-col">{leftData.status}</div>
          <div class="compare-col">{rightData.status}</div>
        </div>

        <div class="compare-row">
          <div class="compare-col-label">Squad Profile</div>
          <div class="compare-col">{leftData.squad_profile_id}</div>
          <div class="compare-col">{rightData.squad_profile_id}</div>
        </div>

        <div class="compare-row">
          <div class="compare-col-label">Build Strategy</div>
          <div class="compare-col">{leftData.build_strategy || '—'}</div>
          <div class="compare-col">{rightData.build_strategy || '—'}</div>
        </div>

        {#each comparisonFields() as field}
          <div class="compare-row" class:diff={field.differs}>
            <div class="compare-col-label">{field.key}</div>
            <div class="compare-col mono">{field.left}</div>
            <div class="compare-col mono">{field.right}</div>
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>

<style>
  .compare-tab {
    padding: var(--continuum-space-lg, 24px);
  }

  .section-title {
    font-size: var(--continuum-font-size-lg, 1.25rem);
    font-weight: 600;
    margin: 0 0 var(--continuum-space-md, 16px);
  }

  .compare-controls {
    display: flex;
    gap: var(--continuum-space-md, 16px);
    align-items: flex-end;
    margin-bottom: var(--continuum-space-lg, 24px);
    flex-wrap: wrap;
  }

  .field-group {
    display: flex;
    flex-direction: column;
    gap: var(--continuum-space-xs, 4px);
    min-width: 200px;
  }

  .field-group label {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .field-select {
    padding: var(--continuum-space-sm, 8px);
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    color: var(--continuum-text-primary, #e2e8f0);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  .btn-compare {
    padding: var(--continuum-space-sm, 8px) var(--continuum-space-md, 16px);
    background: var(--continuum-accent-primary, #6366f1);
    border: 1px solid var(--continuum-accent-primary, #6366f1);
    border-radius: var(--continuum-radius-sm, 4px);
    color: #fff;
    cursor: pointer;
    font-size: var(--continuum-font-size-sm, 0.875rem);
    align-self: flex-end;
  }

  .btn-compare:hover {
    background: var(--continuum-accent-primary-hover, #4f46e5);
  }

  .btn-compare:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .empty, .empty-inline {
    padding: var(--continuum-space-lg, 24px);
    text-align: center;
    color: var(--continuum-text-muted, #94a3b8);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  .empty-inline {
    padding: var(--continuum-space-sm, 8px) 0;
    text-align: left;
  }

  .compare-error {
    padding: var(--continuum-space-sm, 8px);
    margin-bottom: var(--continuum-space-md, 16px);
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid var(--continuum-accent-danger, #ef4444);
    border-radius: var(--continuum-radius-sm, 4px);
    color: var(--continuum-accent-danger, #ef4444);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  .compare-grid {
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-md, 8px);
    overflow: hidden;
  }

  .compare-header, .compare-row {
    display: grid;
    grid-template-columns: 200px 1fr 1fr;
    border-bottom: 1px solid var(--continuum-border, #334155);
  }

  .compare-header {
    background: var(--continuum-bg-secondary, #1e293b);
    font-weight: 600;
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  .compare-row:last-child {
    border-bottom: none;
  }

  .compare-row.diff {
    background: rgba(99, 102, 241, 0.08);
  }

  .compare-col-label {
    padding: var(--continuum-space-sm, 8px);
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
    font-weight: 600;
    border-right: 1px solid var(--continuum-border, #334155);
  }

  .compare-col {
    padding: var(--continuum-space-sm, 8px);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    border-right: 1px solid var(--continuum-border, #334155);
  }

  .compare-col:last-child {
    border-right: none;
  }

  .mono {
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-xs, 0.75rem);
    white-space: pre-wrap;
  }

  .text-muted {
    color: var(--continuum-text-muted, #94a3b8);
    font-size: var(--continuum-font-size-xs, 0.75rem);
    margin-left: var(--continuum-space-xs, 4px);
  }
</style>
