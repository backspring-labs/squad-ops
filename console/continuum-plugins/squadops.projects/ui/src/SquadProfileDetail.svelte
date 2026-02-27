<!--
  SquadProfileDetail — expandable agent table with model metadata (SIP-0074 §4.1).

  Fetches model specs once on mount (static registry). Joins agents with model
  specs client-side to show context window and max completion tokens.
-->
<script>
  import { onMount } from 'svelte';

  let { profile = null } = $props();

  let modelSpecs = $state({});
  let modelsLoaded = $state(false);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  onMount(async () => {
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/models`);
      if (resp.ok) {
        const models = await resp.json();
        for (const m of models) {
          modelSpecs[m.name] = m;
        }
      }
    } catch {
      // Non-critical — table renders without model metadata
    }
    modelsLoaded = true;
  });

  function formatNumber(n) {
    if (n == null) return '--';
    return n.toLocaleString();
  }
</script>

{#if profile}
  <div class="profile-detail">
    {#if profile.description}
      <div class="detail-desc">{profile.description}</div>
    {/if}
    {#if profile.version}
      <div class="detail-meta">Version: {profile.version}</div>
    {/if}

    {#if profile.agents}
      <table class="agent-table">
        <thead>
          <tr>
            <th>Agent</th>
            <th>Model</th>
            <th>Context Window</th>
            <th>Max Completion</th>
            <th>Enabled</th>
          </tr>
        </thead>
        <tbody>
          {#each profile.agents as agent}
            {@const spec = modelSpecs[agent.model] || null}
            <tr>
              <td class="cell-role">{agent.display_name || agent.agent_id} ({agent.role_label || agent.role})</td>
              <td class="cell-model">{agent.model || '--'}</td>
              <td class="cell-num">{spec ? formatNumber(spec.context_window) : '--'}</td>
              <td class="cell-num">{spec ? formatNumber(spec.default_max_completion) : '--'}</td>
              <td class="cell-enabled">{agent.enabled !== false ? 'on' : 'off'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {:else}
      <div class="no-agents">No agents configured</div>
    {/if}
  </div>
{/if}

<style>
  .profile-detail {
    margin-top: var(--continuum-space-sm, 8px);
    padding-top: var(--continuum-space-sm, 8px);
    border-top: 1px solid var(--continuum-border, #334155);
  }

  .detail-desc {
    font-size: var(--continuum-font-size-sm, 0.875rem);
    color: var(--continuum-text-muted, #94a3b8);
    margin-bottom: var(--continuum-space-sm, 8px);
  }

  .detail-meta {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
    margin-bottom: var(--continuum-space-sm, 8px);
  }

  .agent-table {
    width: 100%;
    border-collapse: collapse;
  }

  .agent-table th,
  .agent-table td {
    text-align: left;
    padding: var(--continuum-space-xs, 4px) var(--continuum-space-sm, 8px);
    font-size: var(--continuum-font-size-xs, 0.75rem);
    border-bottom: 1px solid var(--continuum-border, #334155);
  }

  .agent-table th {
    color: var(--continuum-text-muted, #94a3b8);
    font-weight: 500;
  }

  .cell-role {
    font-weight: 500;
    text-transform: capitalize;
  }

  .cell-model {
    font-family: var(--continuum-font-mono, monospace);
    color: var(--continuum-text-muted, #94a3b8);
  }

  .cell-num {
    font-family: var(--continuum-font-mono, monospace);
    text-align: right;
  }

  .cell-enabled {
    color: var(--continuum-text-muted, #94a3b8);
  }

  .no-agents {
    font-size: var(--continuum-font-size-sm, 0.875rem);
    color: var(--continuum-text-muted, #94a3b8);
  }
</style>
