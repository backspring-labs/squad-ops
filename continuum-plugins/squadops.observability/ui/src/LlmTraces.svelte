<svelte:options customElement="squadops-obs-gate-decisions" />

<script>
  import { onMount, onDestroy } from 'svelte';

  let pendingRuns = $state([]);
  let recentDecisions = $state([]);
  let loading = $state(true);
  let pollTimer = $state(null);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  function timeAgo(iso) {
    if (!iso) return '';
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  function decisionColor(decision) {
    if (decision === 'approved') return 'var(--continuum-accent-success, #22c55e)';
    if (decision === 'rejected') return 'var(--continuum-accent-danger, #ef4444)';
    return 'var(--continuum-text-muted, #94a3b8)';
  }

  async function fetchData() {
    try {
      const projResp = await apiFetch(`${apiBase}/api/v1/projects`);
      if (!projResp.ok) { loading = false; return; }
      const projects = await projResp.json();

      const paused = [];
      const decisions = [];

      for (const proj of projects.slice(0, 10)) {
        try {
          const cyclesResp = await apiFetch(`${apiBase}/api/v1/projects/${proj.project_id}/cycles`);
          if (!cyclesResp.ok) continue;
          const cycles = await cyclesResp.json();
          for (const cycle of cycles) {
            for (const run of (cycle.runs || [])) {
              if (run.status === 'paused') {
                paused.push({
                  run_id: run.run_id,
                  run_number: run.run_number,
                  cycle_id_short: cycle.cycle_id?.slice(0, 12),
                  project_name: proj.name || proj.project_id,
                });
              }
              for (const gd of (run.gate_decisions || [])) {
                decisions.push({
                  ...gd,
                  run_number: run.run_number,
                  cycle_id_short: cycle.cycle_id?.slice(0, 12),
                  project_name: proj.name || proj.project_id,
                });
              }
            }
          }
        } catch { /* skip */ }
      }

      pendingRuns = paused;
      decisions.sort((a, b) => (b.decided_at || '').localeCompare(a.decided_at || ''));
      recentDecisions = decisions.slice(0, 10);
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

<div class="gate-decisions">
  <h3 class="title">Gate Decisions</h3>

  {#if loading}
    <div class="loading">Loading gate activity...</div>
  {:else if pendingRuns.length === 0 && recentDecisions.length === 0}
    <div class="empty">No gate activity</div>
  {:else}
    {#if pendingRuns.length > 0}
      <div class="section">
        <h4 class="section-title awaiting">Awaiting Decision ({pendingRuns.length})</h4>
        <div class="item-list">
          {#each pendingRuns as run}
            <div class="item pending-item">
              <span class="pending-badge">PAUSED</span>
              <div class="item-info">
                <span class="item-project">{run.project_name}</span>
                <span class="item-meta">{run.cycle_id_short} &middot; run #{run.run_number}</span>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if recentDecisions.length > 0}
      <div class="section">
        <h4 class="section-title">Recent Decisions</h4>
        <div class="item-list">
          {#each recentDecisions as gd}
            <div class="item">
              <span class="decision-badge" style="background: {decisionColor(gd.decision)}">{gd.decision}</span>
              <div class="item-info">
                <span class="item-gate">{gd.gate_name}</span>
                <span class="item-meta">{gd.project_name} &middot; run #{gd.run_number} &middot; {gd.decided_by}</span>
              </div>
              <span class="item-age">{timeAgo(gd.decided_at)}</span>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  {/if}
</div>

<style>
  .gate-decisions {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }
  .title { font-size: var(--continuum-font-size-md, 1rem); font-weight: 600; margin: 0 0 var(--continuum-space-md, 16px) 0; }
  .section { margin-bottom: var(--continuum-space-md, 16px); }
  .section-title { font-size: var(--continuum-font-size-sm, 0.875rem); font-weight: 600; margin: 0 0 var(--continuum-space-xs, 4px) 0; }
  .section-title.awaiting { color: var(--continuum-accent-warning, #f59e0b); }
  .item-list { display: flex; flex-direction: column; gap: 2px; }
  .item {
    display: flex; align-items: center; gap: var(--continuum-space-sm, 8px);
    padding: var(--continuum-space-sm, 8px) var(--continuum-space-md, 16px);
    background: var(--continuum-bg-secondary, #1e293b); border-radius: var(--continuum-radius-sm, 4px);
  }
  .pending-item { border-left: 3px solid var(--continuum-accent-warning, #f59e0b); }
  .pending-badge {
    font-size: var(--continuum-font-size-xs, 0.75rem); padding: 2px 8px;
    border-radius: var(--continuum-radius-sm, 4px); background: var(--continuum-accent-warning, #f59e0b);
    color: #000; font-weight: 700; text-transform: uppercase; flex-shrink: 0;
  }
  .decision-badge {
    font-size: var(--continuum-font-size-xs, 0.75rem); padding: 2px 8px;
    border-radius: var(--continuum-radius-sm, 4px); color: #fff; font-weight: 600;
    text-transform: uppercase; flex-shrink: 0;
  }
  .item-info { flex: 1; min-width: 0; }
  .item-project, .item-gate { display: block; font-weight: 500; font-size: var(--continuum-font-size-sm, 0.875rem); }
  .item-meta {
    display: block; font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8); font-family: var(--continuum-font-mono, monospace);
  }
  .item-age { font-size: var(--continuum-font-size-xs, 0.75rem); color: var(--continuum-text-muted, #94a3b8); flex-shrink: 0; }
  .loading, .empty { color: var(--continuum-text-muted, #94a3b8); font-size: var(--continuum-font-size-sm, 0.875rem); padding: var(--continuum-space-md, 16px); }
</style>
