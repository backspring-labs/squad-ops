<script>
  import { onMount, onDestroy } from 'svelte';

  let { projectId = null, cycleId = null, onSelectRun = null } = $props();

  let runs = $state([]);
  let loading = $state(false);
  let error = $state(null);
  let pollTimer = $state(null);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  async function fetchRuns() {
    if (!projectId || !cycleId) return;
    loading = true;
    error = null;
    try {
      const resp = await apiFetch(
        `${apiBase}/api/v1/projects/${projectId}/cycles/${cycleId}/runs`
      );
      if (!resp.ok) throw new Error(`Runs: ${resp.status}`);
      runs = await resp.json();
      loading = false;
    } catch (err) {
      error = err.message;
      loading = false;
    }
  }

  // Re-fetch when cycle selection changes
  $effect(() => {
    if (projectId && cycleId) {
      fetchRuns();
    } else {
      runs = [];
    }
  });

  onMount(() => {
    pollTimer = setInterval(() => {
      if (projectId && cycleId) fetchRuns();
    }, 15000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  function selectRun(run) {
    onSelectRun?.(run.run_id);
  }

  function statusColor(status) {
    const colors = {
      completed: 'var(--continuum-accent-success, #22c55e)',
      running: 'var(--continuum-accent-primary, #6366f1)',
      failed: 'var(--continuum-accent-danger, #ef4444)',
      paused: 'var(--continuum-accent-warning, #f59e0b)',
      queued: 'var(--continuum-text-muted, #94a3b8)',
      cancelled: 'var(--continuum-text-muted, #94a3b8)',
    };
    return colors[status] || colors.queued;
  }

  function statusBgColor(status) {
    const colors = {
      completed: 'rgba(34, 197, 94, 0.15)',
      running: 'rgba(99, 102, 241, 0.15)',
      failed: 'rgba(239, 68, 68, 0.15)',
      paused: 'rgba(245, 158, 11, 0.15)',
      queued: 'rgba(148, 163, 184, 0.10)',
      cancelled: 'rgba(148, 163, 184, 0.10)',
    };
    return colors[status] || colors.queued;
  }

  function capitalize(s) {
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  function formatTimestamp(iso) {
    if (!iso) return '--';
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }
</script>

<div class="run-timeline">
  {#if !projectId || !cycleId}
    <div class="empty">Select a cycle to view its runs</div>
  {:else}
    <h3 class="title">
      Runs for
      <span class="cycle-ref">{cycleId.slice(0, 12)}</span>
    </h3>

    {#if loading}
      <div class="loading">Loading runs...</div>
    {:else if error}
      <div class="error">Error: {error}</div>
    {:else if runs.length === 0}
      <div class="empty">No runs for this cycle</div>
    {:else}
      <div class="timeline">
        {#each runs as run, i}
          <div
            class="timeline-item"
            onclick={() => selectRun(run)}
          >
            <div class="timeline-marker">
              <div
                class="marker-dot"
                style="background: {statusColor(run.status || 'queued')}"
              ></div>
              {#if i < runs.length - 1}
                <div class="marker-line"></div>
              {/if}
            </div>

            <div
              class="timeline-card"
              style="border-left: 3px solid {statusColor(run.status || 'queued')}"
            >
              <div class="run-header">
                <span class="run-number">{run.workload_type ? capitalize(run.workload_type) : `Run #${run.run_number ?? i + 1}`}</span>
                <span
                  class="run-status"
                  style="background: {statusBgColor(run.status || 'queued')}; color: {statusColor(run.status || 'queued')}"
                >
                  {run.status || 'queued'}
                </span>
              </div>

              <div class="run-meta">
                <span class="run-id">{run.run_id?.slice(0, 12) || '--'}</span>
                {#if run.started_at}
                  <span class="run-time">Started: {formatTimestamp(run.started_at)}</span>
                {/if}
                {#if run.finished_at}
                  <span class="run-time">Finished: {formatTimestamp(run.finished_at)}</span>
                {/if}
              </div>

              {#if run.gates && run.gates.length > 0}
                <div class="run-gates">
                  {#each run.gates as gate}
                    <span
                      class="gate-badge"
                      class:gate-pending={!gate.decision}
                      class:gate-approved={gate.decision === 'approved'}
                      class:gate-rejected={gate.decision === 'rejected'}
                    >
                      {gate.gate_name}: {gate.decision || 'pending'}
                    </span>
                  {/each}
                </div>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>

<style>
  .run-timeline {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .title {
    font-size: var(--continuum-font-size-md, 1rem);
    font-weight: 600;
    margin: 0 0 var(--continuum-space-md, 16px) 0;
  }

  .cycle-ref {
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    color: var(--continuum-accent-primary, #6366f1);
  }

  .timeline {
    display: flex;
    flex-direction: column;
  }

  .timeline-item {
    display: flex;
    gap: var(--continuum-space-md, 16px);
    cursor: pointer;
  }

  .timeline-marker {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 20px;
    flex-shrink: 0;
  }

  .marker-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    flex-shrink: 0;
    margin-top: 6px;
  }

  .marker-line {
    width: 2px;
    flex: 1;
    background: var(--continuum-border, #334155);
    min-height: 20px;
  }

  .timeline-card {
    flex: 1;
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-md, 8px);
    padding: var(--continuum-space-md, 16px);
    margin-bottom: var(--continuum-space-sm, 8px);
    transition: background 0.15s;
  }

  .timeline-card:hover {
    background: var(--continuum-bg-tertiary, #273549);
  }

  .run-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--continuum-space-xs, 4px);
  }

  .run-number {
    font-weight: 600;
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  .run-status {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 2px 8px;
    border-radius: var(--continuum-radius-sm, 4px);
    font-weight: 600;
    text-transform: uppercase;
  }

  .run-meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--continuum-space-sm, 8px);
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
  }

  .run-id {
    font-family: var(--continuum-font-mono, monospace);
  }

  .run-gates {
    display: flex;
    flex-wrap: wrap;
    gap: var(--continuum-space-xs, 4px);
    margin-top: var(--continuum-space-sm, 8px);
  }

  .gate-badge {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 2px 6px;
    border-radius: var(--continuum-radius-sm, 4px);
    font-weight: 500;
  }

  .gate-pending {
    background: rgba(148, 163, 184, 0.15);
    color: var(--continuum-text-muted, #94a3b8);
  }

  .gate-approved {
    background: rgba(34, 197, 94, 0.15);
    color: var(--continuum-accent-success, #22c55e);
  }

  .gate-rejected {
    background: rgba(239, 68, 68, 0.15);
    color: var(--continuum-accent-danger, #ef4444);
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
