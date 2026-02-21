<svelte:options customElement="squadops-cycles-run-detail" />

<script>
  import { onMount, onDestroy } from 'svelte';

  let selectedRun = $state(null);
  let runDetail = $state(null);
  let artifacts = $state([]);
  let loading = $state(false);
  let error = $state(null);
  let gateLoading = $state(null);
  let gateError = $state(null);
  let pollTimer = $state(null);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  function handleSelectRun(event) {
    const { project_id, cycle_id, run_id, run_number } = event.detail;
    selectedRun = { project_id, cycle_id, run_id, run_number };
    gateError = null;
    fetchRunDetail();
  }

  async function fetchRunDetail() {
    if (!selectedRun) return;
    loading = true;
    error = null;
    try {
      const { project_id, cycle_id, run_id } = selectedRun;
      const runResp = await apiFetch(
        `${apiBase}/api/v1/projects/${project_id}/cycles/${cycle_id}/runs/${run_id}`
      );
      if (!runResp.ok) throw new Error(`Run detail: ${runResp.status}`);
      runDetail = await runResp.json();

      // Extract artifact refs from run detail response (no separate endpoint)
      artifacts = runDetail.artifact_refs || [];

      loading = false;
    } catch (err) {
      error = err.message;
      loading = false;
    }
  }

  async function executeCommand(commandId, params) {
    const resp = await apiFetch('/api/commands/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command_id: commandId, params }),
    });
    if (!resp.ok) {
      const body = await resp.text();
      throw new Error(body || `Command failed: ${resp.status}`);
    }
    return resp.json();
  }

  async function handleGateDecision(gateName, decision) {
    if (!selectedRun) return;
    gateLoading = gateName;
    gateError = null;
    try {
      const commandId =
        decision === 'approved'
          ? 'squadops.gate_approve'
          : 'squadops.gate_reject';
      await executeCommand(commandId, {
        project_id: selectedRun.project_id,
        cycle_id: selectedRun.cycle_id,
        run_id: selectedRun.run_id,
        gate_name: gateName,
        decision,
      });
      // Refresh after gate decision
      await fetchRunDetail();
    } catch (err) {
      gateError = `Gate ${decision} failed: ${err.message}`;
    }
    gateLoading = null;
  }

  onMount(() => {
    window.addEventListener('squadops:select-run', handleSelectRun);
    pollTimer = setInterval(() => {
      if (selectedRun) fetchRunDetail();
    }, 15000);
  });

  onDestroy(() => {
    window.removeEventListener('squadops:select-run', handleSelectRun);
    if (pollTimer) clearInterval(pollTimer);
  });

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

<div class="run-detail">
  {#if !selectedRun}
    <div class="empty">Select a run to view details</div>
  {:else if loading}
    <div class="loading">Loading run details...</div>
  {:else if error}
    <div class="error">Error: {error}</div>
  {:else if runDetail}
    <h3 class="title">
      Run #{selectedRun.run_number ?? '--'}
      <span
        class="title-status"
        style="color: {statusColor(runDetail.status || 'queued')}"
      >
        {runDetail.status || 'queued'}
      </span>
    </h3>

    <!-- Overview -->
    <div class="detail-section">
      <h4 class="section-title">Overview</h4>
      <div class="detail-grid">
        <div class="detail-row">
          <span class="detail-key">Run ID</span>
          <span class="detail-val mono">{runDetail.run_id}</span>
        </div>
        <div class="detail-row">
          <span class="detail-key">Cycle ID</span>
          <span class="detail-val mono">{selectedRun.cycle_id}</span>
        </div>
        <div class="detail-row">
          <span class="detail-key">Project</span>
          <span class="detail-val">{selectedRun.project_id}</span>
        </div>
        <div class="detail-row">
          <span class="detail-key">Status</span>
          <span class="detail-val" style="color: {statusColor(runDetail.status || 'queued')}">
            {runDetail.status || 'queued'}
          </span>
        </div>
        {#if runDetail.started_at}
          <div class="detail-row">
            <span class="detail-key">Started</span>
            <span class="detail-val">{formatTimestamp(runDetail.started_at)}</span>
          </div>
        {/if}
        {#if runDetail.finished_at}
          <div class="detail-row">
            <span class="detail-key">Finished</span>
            <span class="detail-val">{formatTimestamp(runDetail.finished_at)}</span>
          </div>
        {/if}
        {#if runDetail.config_hash}
          <div class="detail-row">
            <span class="detail-key">Config Hash</span>
            <span class="detail-val mono">{runDetail.config_hash}</span>
          </div>
        {/if}
      </div>
    </div>

    <!-- Gates -->
    {#if runDetail.gates && runDetail.gates.length > 0}
      <div class="detail-section">
        <h4 class="section-title">Gate Decisions</h4>

        {#if gateError}
          <div class="gate-error">{gateError}</div>
        {/if}

        <div class="gates-list">
          {#each runDetail.gates as gate}
            <div class="gate-card">
              <div class="gate-header">
                <span class="gate-name">{gate.gate_name}</span>
                <span
                  class="gate-decision"
                  class:gate-pending={!gate.decision}
                  class:gate-approved={gate.decision === 'approved'}
                  class:gate-rejected={gate.decision === 'rejected'}
                >
                  {gate.decision || 'pending'}
                </span>
              </div>

              {#if gate.decided_by}
                <div class="gate-meta">
                  Decided by: {gate.decided_by}
                  {#if gate.decided_at}
                    at {formatTimestamp(gate.decided_at)}
                  {/if}
                </div>
              {/if}

              {#if gate.reason}
                <div class="gate-meta">Reason: {gate.reason}</div>
              {/if}

              {#if !gate.decision}
                <div class="gate-actions">
                  <button
                    class="btn btn-approve"
                    disabled={gateLoading === gate.gate_name}
                    onclick={() => handleGateDecision(gate.gate_name, 'approved')}
                  >
                    {gateLoading === gate.gate_name ? 'Processing...' : 'Approve'}
                  </button>
                  <button
                    class="btn btn-reject"
                    disabled={gateLoading === gate.gate_name}
                    onclick={() => handleGateDecision(gate.gate_name, 'rejected')}
                  >
                    {gateLoading === gate.gate_name ? 'Processing...' : 'Reject'}
                  </button>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Artifacts -->
    {#if artifacts.length > 0}
      <div class="detail-section">
        <h4 class="section-title">Artifacts</h4>
        <div class="artifacts-list">
          {#each artifacts as artifact}
            <div class="artifact-row">
              <span class="artifact-name">{artifact.filename || artifact.artifact_id}</span>
              <span class="artifact-type">{artifact.content_type || '--'}</span>
              <span class="artifact-agent">{artifact.agent_role || '--'}</span>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  {/if}
</div>

<style>
  .run-detail {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .title {
    font-size: var(--continuum-font-size-md, 1rem);
    font-weight: 600;
    margin: 0 0 var(--continuum-space-md, 16px) 0;
    display: flex;
    align-items: center;
    gap: var(--continuum-space-sm, 8px);
  }

  .title-status {
    font-size: var(--continuum-font-size-sm, 0.875rem);
    text-transform: uppercase;
    font-weight: 600;
  }

  .detail-section {
    margin-bottom: var(--continuum-space-lg, 24px);
  }

  .section-title {
    font-size: var(--continuum-font-size-sm, 0.875rem);
    font-weight: 600;
    color: var(--continuum-text-muted, #94a3b8);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0 0 var(--continuum-space-sm, 8px) 0;
  }

  .detail-grid {
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-md, 8px);
    padding: var(--continuum-space-md, 16px);
  }

  .detail-row {
    display: flex;
    gap: var(--continuum-space-md, 16px);
    padding: var(--continuum-space-xs, 4px) 0;
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  .detail-key {
    color: var(--continuum-text-muted, #94a3b8);
    min-width: 100px;
    flex-shrink: 0;
  }

  .detail-val {
    word-break: break-all;
  }

  .mono {
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }

  /* Gates */
  .gates-list {
    display: flex;
    flex-direction: column;
    gap: var(--continuum-space-sm, 8px);
  }

  .gate-card {
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-md, 8px);
    padding: var(--continuum-space-md, 16px);
  }

  .gate-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--continuum-space-xs, 4px);
  }

  .gate-name {
    font-weight: 600;
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  .gate-decision {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 2px 8px;
    border-radius: var(--continuum-radius-sm, 4px);
    font-weight: 600;
    text-transform: uppercase;
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

  .gate-meta {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
    margin-top: 2px;
  }

  .gate-actions {
    display: flex;
    gap: var(--continuum-space-sm, 8px);
    margin-top: var(--continuum-space-sm, 8px);
  }

  .gate-error {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: var(--continuum-radius-sm, 4px);
    padding: var(--continuum-space-sm, 8px);
    color: var(--continuum-accent-danger, #ef4444);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    margin-bottom: var(--continuum-space-sm, 8px);
  }

  .btn {
    padding: var(--continuum-space-xs, 4px) var(--continuum-space-md, 16px);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-approve {
    background: rgba(34, 197, 94, 0.15);
    color: var(--continuum-accent-success, #22c55e);
    border-color: rgba(34, 197, 94, 0.3);
  }

  .btn-approve:hover:not(:disabled) {
    background: rgba(34, 197, 94, 0.25);
  }

  .btn-reject {
    background: rgba(239, 68, 68, 0.15);
    color: var(--continuum-accent-danger, #ef4444);
    border-color: rgba(239, 68, 68, 0.3);
  }

  .btn-reject:hover:not(:disabled) {
    background: rgba(239, 68, 68, 0.25);
  }

  /* Artifacts */
  .artifacts-list {
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-md, 8px);
    overflow: hidden;
  }

  .artifact-row {
    display: flex;
    gap: var(--continuum-space-md, 16px);
    padding: var(--continuum-space-sm, 8px) var(--continuum-space-md, 16px);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    border-bottom: 1px solid var(--continuum-border, #334155);
  }

  .artifact-row:last-child {
    border-bottom: none;
  }

  .artifact-name {
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-xs, 0.75rem);
    flex: 1;
  }

  .artifact-type {
    color: var(--continuum-text-muted, #94a3b8);
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }

  .artifact-agent {
    color: var(--continuum-text-muted, #94a3b8);
    font-size: var(--continuum-font-size-xs, 0.75rem);
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
