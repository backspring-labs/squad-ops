<svelte:options customElement="squadops-obs-llm-traces" />

<script>
  import { onMount, onDestroy } from 'svelte';

  let traces = $state([]);
  let loading = $state(true);
  let error = $state(null);
  let pollTimer = $state(null);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const langfuseBase = config.langfuseBaseUrl || '';

  async function fetchTraces() {
    if (!langfuseBase) { loading = false; error = 'LangFuse URL not configured'; return; }
    try {
      const resp = await fetch(`${langfuseBase}/api/public/traces?limit=20`);
      if (resp.ok) {
        const data = await resp.json();
        traces = data.data || data;
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
    fetchTraces();
    pollTimer = setInterval(fetchTraces, 60000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  function totalGenerations() {
    return traces.reduce((sum, t) => sum + (t.observations?.length || 0), 0);
  }
</script>

<div class="llm-traces">
  <h3 class="title">LLM Traces (LangFuse)</h3>

  {#if loading}
    <div class="loading">Loading traces...</div>
  {:else if error}
    <div class="error">{error}</div>
  {:else}
    <div class="stats">
      <div class="stat"><span class="stat-val">{traces.length}</span><span class="stat-label">traces</span></div>
      <div class="stat"><span class="stat-val">{totalGenerations()}</span><span class="stat-label">generations</span></div>
    </div>

    <div class="trace-list">
      {#each traces.slice(0, 10) as trace}
        <div class="trace-item">
          <span class="trace-name">{trace.name || trace.id?.slice(0, 16)}</span>
          <span class="trace-meta">{trace.observations?.length || 0} gen</span>
          {#if trace.latency}
            <span class="trace-latency">{(trace.latency / 1000).toFixed(1)}s</span>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .llm-traces {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }
  .title { font-size: var(--continuum-font-size-md, 1rem); font-weight: 600; margin: 0 0 var(--continuum-space-md, 16px) 0; }
  .stats { display: flex; gap: var(--continuum-space-lg, 24px); margin-bottom: var(--continuum-space-md, 16px); }
  .stat { display: flex; flex-direction: column; }
  .stat-val { font-size: 1.5rem; font-weight: 700; font-family: var(--continuum-font-mono, monospace); }
  .stat-label { font-size: var(--continuum-font-size-xs, 0.75rem); color: var(--continuum-text-muted, #94a3b8); }
  .trace-list { display: flex; flex-direction: column; gap: 2px; }
  .trace-item {
    display: flex; gap: var(--continuum-space-sm, 8px); align-items: center;
    padding: var(--continuum-space-sm, 8px);
    background: var(--continuum-bg-secondary, #1e293b); border-radius: var(--continuum-radius-sm, 4px);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }
  .trace-name { font-family: var(--continuum-font-mono, monospace); font-size: var(--continuum-font-size-xs, 0.75rem); flex: 1; }
  .trace-meta { font-size: var(--continuum-font-size-xs, 0.75rem); color: var(--continuum-text-muted, #94a3b8); }
  .trace-latency { font-size: var(--continuum-font-size-xs, 0.75rem); color: var(--continuum-accent-primary, #6366f1); font-family: var(--continuum-font-mono, monospace); }
  .loading, .error { color: var(--continuum-text-muted, #94a3b8); padding: var(--continuum-space-md, 16px); }
  .error { color: var(--continuum-accent-warning, #f59e0b); }
</style>
