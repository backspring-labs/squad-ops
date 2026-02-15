<svelte:options customElement="squadops-system-plugins" />

<script>
  import { onMount } from 'svelte';

  let plugins = $state([]);
  let loading = $state(true);

  async function fetchRegistry() {
    try {
      const resp = await fetch('/api/registry');
      if (resp.ok) {
        const data = await resp.json();
        plugins = data.plugins || [];
      }
    } catch {
      // Best-effort
    }
    loading = false;
  }

  onMount(fetchRegistry);

  function statusClass(status) {
    return status === 'LOADED' ? 'loaded' : 'error';
  }
</script>

<div class="system-plugins">
  <h3 class="title">Plugins</h3>

  {#if loading}
    <div class="loading">Loading plugin registry...</div>
  {:else if plugins.length === 0}
    <div class="empty">No plugins registered</div>
  {:else}
    <table class="plugin-table">
      <thead>
        <tr>
          <th>Plugin ID</th>
          <th>Status</th>
          <th>Contributions</th>
        </tr>
      </thead>
      <tbody>
        {#each plugins as plugin}
          <tr>
            <td class="plugin-id">{plugin.id}</td>
            <td class={statusClass(plugin.status)}>{plugin.status}</td>
            <td>{plugin.contribution_count ?? '—'}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<style>
  .system-plugins {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .title {
    font-size: var(--continuum-font-size-md, 1rem);
    font-weight: 600;
    margin: 0 0 var(--continuum-space-md, 16px) 0;
  }

  .plugin-table {
    width: 100%;
    border-collapse: collapse;
  }

  th, td {
    text-align: left;
    padding: var(--continuum-space-sm, 8px);
    border-bottom: 1px solid var(--continuum-border, #334155);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  th { color: var(--continuum-text-muted, #94a3b8); font-weight: 500; }

  .plugin-id { font-family: var(--continuum-font-mono, monospace); }
  .loaded { color: var(--continuum-accent-success, #22c55e); }
  .error { color: var(--continuum-accent-danger, #ef4444); }
  .loading, .empty {
    color: var(--continuum-text-muted, #94a3b8);
    padding: var(--continuum-space-md, 16px);
  }
</style>
