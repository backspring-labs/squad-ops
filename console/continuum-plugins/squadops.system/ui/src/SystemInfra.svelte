<svelte:options customElement="squadops-system-infra" />

<script>
  import { onMount, onDestroy } from 'svelte';

  let infra = $state(null);
  let loading = $state(true);
  let pollTimer = $state(null);

  async function fetchInfra() {
    try {
      const resp = await fetch('/api/health/infra');
      if (resp.ok) infra = await resp.json();
    } catch {
      // Best-effort
    }
    loading = false;
  }

  onMount(() => {
    fetchInfra();
    pollTimer = setInterval(fetchInfra, 30000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });
</script>

<div class="system-infra">
  <h3 class="title">Infrastructure</h3>

  {#if loading}
    <div class="loading">Checking infrastructure...</div>
  {:else if !infra}
    <div class="empty">Infrastructure data unavailable</div>
  {:else}
    <div class="infra-grid">
      {#each infra as svc}
        <div class="infra-card">
          <div class="infra-header">
            <span class="infra-name">{svc.component}</span>
            <span class="infra-status {svc.status === 'online' ? 'healthy' : 'unhealthy'}">
              {svc.status}
            </span>
          </div>
          <div class="infra-details">
            <div class="detail-row">
              <span class="detail-key">type:</span>
              <span class="detail-val">{svc.type}</span>
            </div>
            {#if svc.version}
              <div class="detail-row">
                <span class="detail-key">version:</span>
                <span class="detail-val">{svc.version}</span>
              </div>
            {/if}
            {#if svc.notes}
              <div class="detail-row">
                <span class="detail-key">notes:</span>
                <span class="detail-val">{svc.notes}</span>
              </div>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .system-infra {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .title {
    font-size: var(--continuum-font-size-md, 1rem);
    font-weight: 600;
    margin: 0 0 var(--continuum-space-md, 16px) 0;
  }

  .infra-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: var(--continuum-space-md, 16px);
  }

  .infra-card {
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-md, 8px);
    padding: var(--continuum-space-md, 16px);
  }

  .infra-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--continuum-space-sm, 8px);
  }

  .infra-name {
    font-weight: 600;
    text-transform: capitalize;
  }

  .infra-status {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 2px 8px;
    border-radius: var(--continuum-radius-sm, 4px);
    font-weight: 500;
  }

  .healthy {
    background: rgba(34, 197, 94, 0.15);
    color: var(--continuum-accent-success, #22c55e);
  }

  .unhealthy {
    background: rgba(239, 68, 68, 0.15);
    color: var(--continuum-accent-danger, #ef4444);
  }

  .infra-details { margin-top: var(--continuum-space-sm, 8px); }

  .detail-row {
    display: flex;
    gap: var(--continuum-space-sm, 8px);
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 2px 0;
  }

  .detail-key {
    color: var(--continuum-text-muted, #94a3b8);
    min-width: 80px;
  }

  .detail-val {
    font-family: var(--continuum-font-mono, monospace);
    word-break: break-all;
  }

  .loading, .empty {
    color: var(--continuum-text-muted, #94a3b8);
    padding: var(--continuum-space-md, 16px);
  }
</style>
