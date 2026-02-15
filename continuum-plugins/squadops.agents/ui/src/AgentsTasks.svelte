<svelte:options customElement="squadops-agents-tasks" />

<script>
  import { onMount } from 'svelte';

  const AGENTS = ['max', 'neo', 'nat', 'eve', 'data'];
  let tasksByAgent = $state({});
  let loading = $state(true);
  let unavailable = $state({});

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  async function fetchTasks() {
    const results = {};
    const unavailableMap = {};
    for (const agent of AGENTS) {
      try {
        const resp = await apiFetch(`${apiBase}/api/v1/tasks/agent/${agent}`);
        if (resp.ok) {
          results[agent] = await resp.json();
          unavailableMap[agent] = false;
        } else {
          results[agent] = [];
          unavailableMap[agent] = true;
        }
      } catch {
        results[agent] = [];
        unavailableMap[agent] = true;
      }
    }
    tasksByAgent = results;
    unavailable = unavailableMap;
    loading = false;
  }

  onMount(fetchTasks);
</script>

<div class="agents-tasks">
  <h3 class="title">Agent Task History</h3>

  {#if loading}
    <div class="loading">Loading task history...</div>
  {:else}
    {#each AGENTS as agent}
      <div class="agent-section">
        <h4 class="agent-name">{agent}</h4>
        {#if unavailable[agent]}
          <div class="unavailable">Endpoint unavailable</div>
        {:else if (tasksByAgent[agent] || []).length === 0}
          <div class="empty">No recent tasks</div>
        {:else}
          <div class="task-list">
            {#each (tasksByAgent[agent] || []).slice(0, 10) as task}
              <div class="task-item">
                <span class="task-type">{task.task_type || task.type || '--'}</span>
                <span class="task-status">{task.status || '--'}</span>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/each}
  {/if}
</div>

<style>
  .agents-tasks {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }
  .title { font-size: var(--continuum-font-size-md, 1rem); font-weight: 600; margin: 0 0 var(--continuum-space-md, 16px) 0; }
  .agent-section { margin-bottom: var(--continuum-space-md, 16px); }
  .agent-name { font-size: var(--continuum-font-size-sm, 0.875rem); font-weight: 600; text-transform: capitalize; margin: 0 0 var(--continuum-space-xs, 4px) 0; }
  .task-list { display: flex; flex-direction: column; gap: 2px; }
  .task-item {
    display: flex; justify-content: space-between; padding: 4px var(--continuum-space-sm, 8px);
    background: var(--continuum-bg-secondary, #1e293b); border-radius: var(--continuum-radius-sm, 4px);
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }
  .task-type { font-family: var(--continuum-font-mono, monospace); }
  .task-status { color: var(--continuum-text-muted, #94a3b8); }
  .loading, .empty { color: var(--continuum-text-muted, #94a3b8); font-size: var(--continuum-font-size-sm, 0.875rem); }
  .unavailable { color: var(--continuum-accent-warning, #f59e0b); font-size: var(--continuum-font-size-sm, 0.875rem); font-style: italic; }
</style>
