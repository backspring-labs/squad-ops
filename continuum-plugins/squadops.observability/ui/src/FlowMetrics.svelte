<svelte:options customElement="squadops-obs-flow-metrics" />

<script>
  import { onMount, onDestroy } from 'svelte';

  let flowRuns = $state([]);
  let loading = $state(true);
  let error = $state(null);
  let pollTimer = $state(null);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const prefectBase = config.prefectBaseUrl || '';

  async function fetchFlowRuns() {
    if (!prefectBase) { loading = false; error = 'Prefect URL not configured'; return; }
    try {
      const resp = await fetch(`${prefectBase}/api/flow_runs/filter`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sort: 'START_TIME_DESC',
          limit: 20,
        }),
      });
      if (resp.ok) {
        flowRuns = await resp.json();
        error = null;
      } else {
        error = 'Service unavailable';
      }
    } catch {
      error = 'Service unavailable';
    }
    loading = false;
  }

  onMount(() => {
    fetchFlowRuns();
    pollTimer = setInterval(fetchFlowRuns, 60000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  function completedCount() { return flowRuns.filter(r => r.state_type === 'COMPLETED').length; }
  function failedCount() { return flowRuns.filter(r => r.state_type === 'FAILED').length; }
  function avgDuration() {
    const finished = flowRuns.filter(r => r.total_run_time);
    if (finished.length === 0) return '—';
    const avg = finished.reduce((sum, r) => sum + (r.total_run_time || 0), 0) / finished.length;
    return `${avg.toFixed(1)}s`;
  }
</script>

<div class="flow-metrics">
  <h3 class="title">Prefect Flow Runs</h3>

  {#if loading}
    <div class="loading">Loading flow metrics...</div>
  {:else if error}
    <div class="error">{error}</div>
  {:else}
    <div class="stats">
      <div class="stat"><span class="stat-val">{completedCount()}</span><span class="stat-label">completed</span></div>
      <div class="stat"><span class="stat-val failed">{failedCount()}</span><span class="stat-label">failed</span></div>
      <div class="stat"><span class="stat-val">{avgDuration()}</span><span class="stat-label">avg duration</span></div>
    </div>

    <div class="run-list">
      {#each flowRuns.slice(0, 10) as run}
        <div class="run-item">
          <span class="run-name">{run.name || run.id?.slice(0, 12)}</span>
          <span class="run-state {run.state_type?.toLowerCase()}">{run.state_type || '—'}</span>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .flow-metrics {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }
  .title { font-size: var(--continuum-font-size-md, 1rem); font-weight: 600; margin: 0 0 var(--continuum-space-md, 16px) 0; }
  .stats { display: flex; gap: var(--continuum-space-lg, 24px); margin-bottom: var(--continuum-space-md, 16px); }
  .stat { display: flex; flex-direction: column; }
  .stat-val { font-size: 1.5rem; font-weight: 700; font-family: var(--continuum-font-mono, monospace); }
  .stat-val.failed { color: var(--continuum-accent-danger, #ef4444); }
  .stat-label { font-size: var(--continuum-font-size-xs, 0.75rem); color: var(--continuum-text-muted, #94a3b8); }
  .run-list { display: flex; flex-direction: column; gap: 2px; }
  .run-item {
    display: flex; justify-content: space-between; padding: var(--continuum-space-sm, 8px);
    background: var(--continuum-bg-secondary, #1e293b); border-radius: var(--continuum-radius-sm, 4px);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }
  .run-name { font-family: var(--continuum-font-mono, monospace); font-size: var(--continuum-font-size-xs, 0.75rem); }
  .run-state { font-size: var(--continuum-font-size-xs, 0.75rem); padding: 2px 6px; border-radius: var(--continuum-radius-sm, 4px); text-transform: uppercase; font-weight: 500; }
  .completed { color: var(--continuum-accent-success, #22c55e); }
  .failed { color: var(--continuum-accent-danger, #ef4444); }
  .running { color: var(--continuum-accent-primary, #6366f1); }
  .loading, .error { color: var(--continuum-text-muted, #94a3b8); padding: var(--continuum-space-md, 16px); }
  .error { color: var(--continuum-accent-warning, #f59e0b); }
</style>
