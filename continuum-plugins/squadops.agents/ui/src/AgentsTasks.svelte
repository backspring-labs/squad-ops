<svelte:options customElement="squadops-agents-run-activity" />

<script>
  import { onMount, onDestroy } from 'svelte';

  let runs = $state([]);
  let loading = $state(true);
  let pollTimer = $state(null);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  function statusColor(status) {
    const colors = {
      completed: 'var(--continuum-accent-success, #22c55e)',
      in_progress: 'var(--continuum-accent-primary, #6366f1)',
      failed: 'var(--continuum-accent-danger, #ef4444)',
      paused: 'var(--continuum-accent-warning, #f59e0b)',
      queued: 'var(--continuum-text-muted, #94a3b8)',
    };
    return colors[status] || colors.queued;
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

  function duration(start, end) {
    if (!start || !end) return null;
    const ms = new Date(end).getTime() - new Date(start).getTime();
    const secs = Math.floor(ms / 1000);
    if (secs < 60) return `${secs}s`;
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}m ${secs % 60}s`;
    return `${Math.floor(mins / 60)}h ${mins % 60}m`;
  }

  async function fetchData() {
    try {
      const projResp = await apiFetch(`${apiBase}/api/v1/projects`);
      if (!projResp.ok) { loading = false; return; }
      const projects = await projResp.json();

      const allRuns = [];
      for (const proj of projects.slice(0, 10)) {
        try {
          const cyclesResp = await apiFetch(`${apiBase}/api/v1/projects/${proj.project_id}/cycles`);
          if (!cyclesResp.ok) continue;
          const cycles = await cyclesResp.json();
          for (const cycle of cycles) {
            for (const run of (cycle.runs || [])) {
              allRuns.push({
                ...run,
                project_name: proj.name || proj.project_id,
                cycle_id_short: cycle.cycle_id?.slice(0, 12),
              });
            }
          }
        } catch { /* skip failed project */ }
      }

      allRuns.sort((a, b) => {
        const ta = a.started_at || a.created_at || '';
        const tb = b.started_at || b.created_at || '';
        return tb.localeCompare(ta);
      });

      runs = allRuns.slice(0, 10);
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

<div class="run-activity">
  <h3 class="title">Recent Run Activity</h3>

  {#if loading}
    <div class="loading">Loading runs...</div>
  {:else if runs.length === 0}
    <div class="empty">No recent runs</div>
  {:else}
    <div class="run-list">
      {#each runs as run}
        <div class="run-item">
          <span class="run-badge" style="background: {statusColor(run.status)}">{run.status?.replace('_', ' ') || '?'}</span>
          <div class="run-info">
            <span class="run-project">{run.project_name}</span>
            <span class="run-meta">
              {run.cycle_id_short} &middot; run #{run.run_number}
              {#if run.gate_decisions?.length}
                &middot; {run.gate_decisions.length} gate{run.gate_decisions.length > 1 ? 's' : ''}
              {/if}
              {#if run.artifact_refs?.length}
                &middot; {run.artifact_refs.length} artifact{run.artifact_refs.length > 1 ? 's' : ''}
              {/if}
            </span>
          </div>
          <div class="run-time">
            {#if duration(run.started_at, run.finished_at)}
              <span class="run-duration">{duration(run.started_at, run.finished_at)}</span>
            {/if}
            <span class="run-age">{timeAgo(run.started_at)}</span>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .run-activity {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }
  .title { font-size: var(--continuum-font-size-md, 1rem); font-weight: 600; margin: 0 0 var(--continuum-space-md, 16px) 0; }
  .run-list { display: flex; flex-direction: column; gap: var(--continuum-space-xs, 4px); }
  .run-item {
    display: flex; align-items: center; gap: var(--continuum-space-sm, 8px);
    padding: var(--continuum-space-sm, 8px) var(--continuum-space-md, 16px);
    background: var(--continuum-bg-secondary, #1e293b); border-radius: var(--continuum-radius-sm, 4px);
  }
  .run-badge {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 2px 8px; border-radius: var(--continuum-radius-sm, 4px);
    color: #fff; font-weight: 600; text-transform: uppercase; white-space: nowrap; flex-shrink: 0;
  }
  .run-info { flex: 1; min-width: 0; }
  .run-project { display: block; font-weight: 500; font-size: var(--continuum-font-size-sm, 0.875rem); }
  .run-meta {
    display: block; font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8); font-family: var(--continuum-font-mono, monospace);
  }
  .run-time { text-align: right; flex-shrink: 0; }
  .run-duration { display: block; font-size: var(--continuum-font-size-xs, 0.75rem); font-family: var(--continuum-font-mono, monospace); }
  .run-age { display: block; font-size: var(--continuum-font-size-xs, 0.75rem); color: var(--continuum-text-muted, #94a3b8); }
  .loading, .empty { color: var(--continuum-text-muted, #94a3b8); font-size: var(--continuum-font-size-sm, 0.875rem); padding: var(--continuum-space-md, 16px); }
</style>
