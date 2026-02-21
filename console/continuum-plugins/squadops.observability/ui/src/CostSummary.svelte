<svelte:options customElement="squadops-obs-cycle-stats" />

<script>
  import { onMount, onDestroy } from 'svelte';

  let stats = $state({ totalCycles: 0, completedPct: 0, activeRuns: 0, totalArtifacts: 0 });
  let loading = $state(true);
  let pollTimer = $state(null);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  async function fetchData() {
    try {
      const projResp = await apiFetch(`${apiBase}/api/v1/projects`);
      if (!projResp.ok) { loading = false; return; }
      const projects = await projResp.json();

      let totalCycles = 0;
      let completed = 0;
      let activeRuns = 0;
      let totalArtifacts = 0;

      for (const proj of projects.slice(0, 10)) {
        try {
          const cyclesResp = await apiFetch(`${apiBase}/api/v1/projects/${proj.project_id}/cycles`);
          if (!cyclesResp.ok) continue;
          const cycles = await cyclesResp.json();
          totalCycles += cycles.length;
          for (const cycle of cycles) {
            if (cycle.status === 'completed') completed++;
            for (const run of (cycle.runs || [])) {
              if (run.status === 'in_progress' || run.status === 'paused') activeRuns++;
              totalArtifacts += (run.artifact_refs || []).length;
            }
          }
        } catch { /* skip */ }
      }

      const completedPct = totalCycles > 0 ? Math.round((completed / totalCycles) * 100) : 0;
      stats = { totalCycles, completedPct, activeRuns, totalArtifacts };
    } catch { /* API unavailable */ }
    loading = false;
  }

  onMount(() => {
    fetchData();
    pollTimer = setInterval(fetchData, 30000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });
</script>

<div class="cycle-stats">
  <h4 class="title">Cycle Stats</h4>

  {#if loading}
    <div class="loading">Loading...</div>
  {:else}
    <div class="metrics">
      <div class="metric">
        <span class="metric-label">Total Cycles</span>
        <span class="metric-val">{stats.totalCycles}</span>
      </div>
      <div class="metric">
        <span class="metric-label">Completed</span>
        <span class="metric-val">{stats.completedPct}%</span>
      </div>
      <div class="metric">
        <span class="metric-label">Active Runs</span>
        <span class="metric-val">{stats.activeRuns}</span>
      </div>
      <div class="metric">
        <span class="metric-label">Artifacts</span>
        <span class="metric-val">{stats.totalArtifacts}</span>
      </div>
    </div>
  {/if}
</div>

<style>
  .cycle-stats {
    padding: var(--continuum-space-md, 16px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }
  .title { font-size: var(--continuum-font-size-md, 1rem); font-weight: 600; margin: 0 0 var(--continuum-space-md, 16px) 0; }
  .metrics { display: grid; grid-template-columns: 1fr 1fr; gap: var(--continuum-space-sm, 8px); }
  .metric {
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    padding: var(--continuum-space-sm, 8px) var(--continuum-space-md, 16px);
  }
  .metric-label { font-size: var(--continuum-font-size-xs, 0.75rem); color: var(--continuum-text-muted, #94a3b8); display: block; }
  .metric-val { font-size: 1.25rem; font-weight: 700; font-family: var(--continuum-font-mono, monospace); display: block; margin-top: 2px; }
  .loading { color: var(--continuum-text-muted, #94a3b8); font-size: var(--continuum-font-size-sm, 0.875rem); }
</style>
