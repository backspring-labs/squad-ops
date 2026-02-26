<!--
  GateDecisionCard — inline gate approve/reject with safety semantics (SIP-0074 §5.5).

  Safety rules:
  - Approve: single click, no confirmation (danger_level: "safe")
  - Reject: confirm() dialog before submission (danger_level: "confirm")
  - In-flight: both buttons disabled with spinner text
  - After decision: buttons replaced with read-only decision badge
  - Failure: error message, buttons re-enabled, NO optimistic update
  - Already decided (conflict/race): non-error info toast, re-fetch
-->
<script>
  let { gate, projectId, cycleId, runId, runStatus, onDecisionRecorded = null } = $props();

  let inFlight = $state(false);
  let error = $state(null);
  let info = $state(null);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  async function executeCommand(commandId, params) {
    const resp = await apiFetch(`${apiBase}/api/commands/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command_id: commandId, params }),
    });
    if (!resp.ok) {
      const body = await resp.text();
      const err = new Error(body || `Command failed: ${resp.status}`);
      err.status = resp.status;
      throw err;
    }
    return resp.json();
  }

  // Gate is decidable only when run is "waiting" AND gate has no decision
  let decidable = $derived(
    runStatus === 'waiting' && !gate.decision && !inFlight
  );

  async function decide(decision) {
    if (decision === 'rejected') {
      const confirmed = confirm(`Reject gate "${gate.gate_name}"? This will stop the run.`);
      if (!confirmed) return;
    }
    inFlight = true;
    error = null;
    info = null;
    try {
      const commandId = decision === 'approved'
        ? 'squadops.gate_approve'
        : 'squadops.gate_reject';
      await executeCommand(commandId, {
        project_id: projectId,
        cycle_id: cycleId,
        run_id: runId,
        gate_name: gate.gate_name,
      });
      // NO optimistic update — parent re-fetches run detail
      onDecisionRecorded?.();
    } catch (err) {
      // Already-decided (conflict/idempotent) -> info toast, not error
      if (err.message?.includes('already') || err.status === 409) {
        info = 'Gate already decided';
      } else {
        error = err.message;
      }
      // Always re-fetch to get server-confirmed state
      onDecisionRecorded?.();
    } finally {
      inFlight = false;
    }
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

  {#if info}
    <div class="gate-info">{info}</div>
  {/if}

  {#if error}
    <div class="gate-error">{error}</div>
  {/if}

  {#if !gate.decision}
    <div class="gate-actions">
      <button
        class="btn btn-approve"
        disabled={!decidable}
        onclick={() => decide('approved')}
      >
        {inFlight ? 'Processing...' : 'Approve'}
      </button>
      <button
        class="btn btn-reject"
        disabled={!decidable}
        onclick={() => decide('rejected')}
      >
        {inFlight ? 'Processing...' : 'Reject'}
      </button>
    </div>
  {/if}
</div>

<style>
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

  .gate-info {
    background: rgba(99, 102, 241, 0.1);
    border: 1px solid rgba(99, 102, 241, 0.3);
    border-radius: var(--continuum-radius-sm, 4px);
    padding: var(--continuum-space-sm, 8px);
    color: var(--continuum-accent-primary, #6366f1);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    margin-top: var(--continuum-space-sm, 8px);
  }

  .gate-error {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: var(--continuum-radius-sm, 4px);
    padding: var(--continuum-space-sm, 8px);
    color: var(--continuum-accent-danger, #ef4444);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    margin-top: var(--continuum-space-sm, 8px);
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
</style>
