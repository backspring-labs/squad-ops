<svelte:options customElement="squadops-obs-cost-summary" />

<script>
  import { onMount, onDestroy } from 'svelte';

  let metrics = $state(null);
  let loading = $state(true);
  let error = $state(null);
  let pollTimer = $state(null);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const langfuseBase = config.langfuseBaseUrl || '';

  async function fetchMetrics() {
    if (!langfuseBase) { loading = false; error = 'LangFuse URL not configured'; return; }
    try {
      const resp = await fetch(`${langfuseBase}/api/public/metrics/daily`);
      if (resp.ok) {
        metrics = await resp.json();
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
    fetchMetrics();
    pollTimer = setInterval(fetchMetrics, 60000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  function totalTokens() {
    if (!metrics?.data) return '—';
    return metrics.data.reduce((sum, d) => sum + (d.inputTokens || 0) + (d.outputTokens || 0), 0).toLocaleString();
  }

  function totalCost() {
    if (!metrics?.data) return '—';
    const cost = metrics.data.reduce((sum, d) => sum + (d.totalCost || 0), 0);
    return cost > 0 ? `$${cost.toFixed(4)}` : '$0.00';
  }
</script>

<div class="cost-summary">
  <h4 class="title">Cost Summary</h4>

  {#if loading}
    <div class="loading">Loading...</div>
  {:else if error}
    <div class="error">{error}</div>
  {:else}
    <div class="metrics">
      <div class="metric">
        <span class="metric-label">Total Tokens</span>
        <span class="metric-val">{totalTokens()}</span>
      </div>
      <div class="metric">
        <span class="metric-label">Estimated Cost</span>
        <span class="metric-val">{totalCost()}</span>
      </div>
    </div>
  {/if}
</div>

<style>
  .cost-summary {
    padding: var(--continuum-space-md, 16px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }
  .title { font-size: var(--continuum-font-size-md, 1rem); font-weight: 600; margin: 0 0 var(--continuum-space-md, 16px) 0; }
  .metrics { display: flex; flex-direction: column; gap: var(--continuum-space-md, 16px); }
  .metric {
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    padding: var(--continuum-space-sm, 8px) var(--continuum-space-md, 16px);
  }
  .metric-label { font-size: var(--continuum-font-size-xs, 0.75rem); color: var(--continuum-text-muted, #94a3b8); display: block; }
  .metric-val { font-size: 1.25rem; font-weight: 700; font-family: var(--continuum-font-mono, monospace); display: block; margin-top: 2px; }
  .loading, .error { color: var(--continuum-text-muted, #94a3b8); font-size: var(--continuum-font-size-sm, 0.875rem); }
  .error { color: var(--continuum-accent-warning, #f59e0b); }
</style>
