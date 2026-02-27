<svelte:options customElement="squadops-agents-status" />

<script>
  import { onMount, onDestroy } from 'svelte';

  let agents = $state([]);
  let loading = $state(true);
  let pollTimer = $state(null);

  function mapAgent(a) {
    return {
      name: a.agent_name || a.agent_id || a.name,
      status: a.network_status || a.lifecycle_state || a.status || 'unknown',
      role: a.role_label || a.role || '',
      current_task: a.current_task_id || a.current_task || null,
    };
  }

  async function fetchStatus() {
    try {
      const resp = await fetch('/api/health/agents');
      if (resp.ok) {
        agents = (await resp.json()).map(mapAgent);
      } else {
        agents = [];
      }
    } catch {
      agents = [];
    }
    loading = false;
  }

  onMount(() => {
    fetchStatus();
    pollTimer = setInterval(fetchStatus, 10000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  function statusClass(status) {
    const s = (status || '').toLowerCase();
    if (s === 'healthy' || s === 'idle' || s === 'online' || s === 'ready') return 'healthy';
    if (s === 'busy') return 'busy';
    return 'unhealthy';
  }
</script>

<div class="agents-status">
  <h4 class="title">Agent Squad</h4>

  {#if loading}
    <div class="loading">Checking agents...</div>
  {:else if agents.length === 0}
    <div class="no-agents">No agents reporting</div>
  {:else}
    <div class="agent-list">
      {#each agents as agent}
        <div class="agent-card">
          <div class="agent-name">{agent.name}</div>
          <div class="agent-role">{agent.role}</div>
          <div class="agent-status {statusClass(agent.status)}">{agent.status}</div>
          {#if agent.current_task}
            <div class="agent-task">{agent.current_task}</div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .agents-status {
    padding: var(--continuum-space-md, 16px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }
  .title { font-size: var(--continuum-font-size-md, 1rem); font-weight: 600; margin: 0 0 var(--continuum-space-sm, 8px) 0; }
  .agent-list { display: flex; flex-direction: column; gap: var(--continuum-space-xs, 4px); }
  .agent-card {
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    padding: var(--continuum-space-sm, 8px) var(--continuum-space-md, 16px);
    display: flex; align-items: center; gap: var(--continuum-space-sm, 8px);
  }
  .agent-name { font-weight: 600; min-width: 40px; text-transform: capitalize; }
  .agent-role { font-size: var(--continuum-font-size-xs, 0.75rem); color: var(--continuum-text-muted, #94a3b8); min-width: 70px; }
  .agent-status {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 2px 8px; border-radius: var(--continuum-radius-sm, 4px);
    font-weight: 500; text-transform: uppercase;
  }
  .healthy { background: rgba(34, 197, 94, 0.15); color: var(--continuum-accent-success, #22c55e); }
  .busy { background: rgba(99, 102, 241, 0.15); color: var(--continuum-accent-primary, #6366f1); }
  .unhealthy { background: rgba(148, 163, 184, 0.15); color: var(--continuum-text-muted, #94a3b8); }
  .agent-task { font-size: var(--continuum-font-size-xs, 0.75rem); color: var(--continuum-text-secondary, #cbd5e1); flex: 1; text-align: right; }
  .loading, .no-agents { color: var(--continuum-text-muted, #94a3b8); }
</style>
