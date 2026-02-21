<svelte:options customElement="squadops-system-health" />

<script>
  import { onMount, onDestroy } from 'svelte';

  let consoleHealth = $state(null);
  let infraHealth = $state(null);
  let loading = $state(true);
  let pollTimer = $state(null);

  async function fetchHealth() {
    try {
      // Console self-health (local backend)
      const consoleResp = await fetch('/health');
      if (consoleResp.ok) consoleHealth = await consoleResp.json();

      // Runtime infrastructure health
      const infraResp = await fetch('/api/health/infra');
      if (infraResp.ok) infraHealth = await infraResp.json();
    } catch {
      // Best-effort
    }
    loading = false;
  }

  onMount(() => {
    fetchHealth();
    pollTimer = setInterval(fetchHealth, 30000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  function statusIcon(healthy) {
    return healthy ? '\u2713' : '\u2717';
  }

  function statusClass(healthy) {
    return healthy ? 'healthy' : 'unhealthy';
  }
</script>

<div class="system-health">
  <h3 class="title">Service Health</h3>

  {#if loading}
    <div class="loading">Checking services...</div>
  {:else}
    <div class="grid">
      <!-- Console lifecycle -->
      <div class="service-card">
        <div class="service-name">Console</div>
        <div class="service-status {consoleHealth ? 'healthy' : 'unhealthy'}">
          {consoleHealth?.lifecycle_state || 'unknown'}
        </div>
      </div>

      <!-- Infrastructure services from /health/infra -->
      {#if infraHealth && Array.isArray(infraHealth)}
        {#each infraHealth as svc}
          <div class="service-card">
            <div class="service-name">{svc.component}</div>
            <div class="service-status {statusClass(svc.status === 'online')}">
              {statusIcon(svc.status === 'online')} {svc.status}
            </div>
          </div>
        {/each}
      {:else}
        <div class="service-card">
          <div class="service-name">Infrastructure</div>
          <div class="service-status unhealthy">unavailable</div>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .system-health {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .title {
    font-size: var(--continuum-font-size-md, 1rem);
    font-weight: 600;
    margin: 0 0 var(--continuum-space-md, 16px) 0;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: var(--continuum-space-sm, 8px);
  }

  .service-card {
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    padding: var(--continuum-space-sm, 8px) var(--continuum-space-md, 16px);
  }

  .service-name {
    font-size: var(--continuum-font-size-sm, 0.875rem);
    color: var(--continuum-text-muted, #94a3b8);
    text-transform: capitalize;
  }

  .service-status {
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    margin-top: 2px;
  }

  .healthy { color: var(--continuum-accent-success, #22c55e); }
  .unhealthy { color: var(--continuum-accent-danger, #ef4444); }
  .loading {
    color: var(--continuum-text-muted, #94a3b8);
    padding: var(--continuum-space-md, 16px);
  }
</style>
