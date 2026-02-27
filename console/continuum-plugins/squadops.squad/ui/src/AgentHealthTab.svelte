<script>
  import { onMount, onDestroy } from 'svelte';

  const apiBase = '';
  let agents = $state([]);
  let loading = $state(true);
  let error = $state(null);
  let pollTimer = $state(null);

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  async function fetchAgents() {
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/squad-profiles/active`);
      if (!resp.ok) {
        error = `Failed to load active profile (${resp.status})`;
        loading = false;
        return;
      }
      const profile = await resp.json();
      agents = (profile.agents || []).map((a) => ({
        agent_id: a.agent_id,
        role: a.role,
        model: a.model || '—',
        enabled: a.enabled,
        config_overrides: a.config_overrides || {},
      }));
      error = null;
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    fetchAgents();
    pollTimer = setInterval(fetchAgents, 30000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });
</script>

<div class="agent-health">
  <h3 class="section-title">Agent Health</h3>

  {#if loading}
    <div class="loading">Loading agent status...</div>
  {:else if error}
    <div class="error">Error: {error}</div>
  {:else if agents.length === 0}
    <div class="empty">No agents reporting</div>
  {:else}
    <table class="agents-table">
      <thead>
        <tr>
          <th>Agent</th>
          <th>Role</th>
          <th>Configured Model</th>
          <th>Enabled</th>
          <th>Overrides</th>
        </tr>
      </thead>
      <tbody>
        {#each agents as agent}
          <tr class="agent-row" class:disabled={!agent.enabled}>
            <td class="cell-id">{agent.agent_id}</td>
            <td>
              <span class="role-badge">{agent.role}</span>
            </td>
            <td class="cell-model">{agent.model}</td>
            <td>
              <span class="status-dot" class:status-on={agent.enabled} class:status-off={!agent.enabled}></span>
              {agent.enabled ? 'Yes' : 'No'}
            </td>
            <td class="cell-overrides">
              {#if Object.keys(agent.config_overrides).length > 0}
                {Object.entries(agent.config_overrides).map(([k, v]) => `${k}=${v}`).join(', ')}
              {:else}
                <span class="text-muted">—</span>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<style>
  .agent-health {
    padding: var(--continuum-space-lg, 24px);
  }

  .section-title {
    font-size: var(--continuum-font-size-lg, 1.25rem);
    font-weight: 600;
    margin: 0 0 var(--continuum-space-md, 16px);
  }

  .loading, .error, .empty {
    padding: var(--continuum-space-lg, 24px);
    text-align: center;
    color: var(--continuum-text-muted, #94a3b8);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  .error {
    color: var(--continuum-accent-danger, #ef4444);
  }

  .agents-table {
    width: 100%;
    border-collapse: collapse;
  }

  th, td {
    text-align: left;
    padding: var(--continuum-space-sm, 8px);
    border-bottom: 1px solid var(--continuum-border, #334155);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  th {
    color: var(--continuum-text-muted, #94a3b8);
    font-weight: 600;
    text-transform: uppercase;
    font-size: var(--continuum-font-size-xs, 0.75rem);
    letter-spacing: 0.05em;
  }

  .agent-row.disabled {
    opacity: 0.5;
  }

  .role-badge {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 2px 8px;
    border-radius: var(--continuum-radius-sm, 4px);
    background: var(--continuum-bg-tertiary, #273549);
    color: var(--continuum-accent-primary, #6366f1);
    font-weight: 600;
  }

  .cell-model {
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }

  .cell-overrides {
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
  }

  .status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 4px;
  }

  .status-on {
    background: var(--continuum-accent-success, #22c55e);
  }

  .status-off {
    background: var(--continuum-text-muted, #94a3b8);
  }

  .text-muted {
    color: var(--continuum-text-muted, #94a3b8);
  }
</style>
