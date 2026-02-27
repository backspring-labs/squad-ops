<svelte:options customElement="squadops-squad-perspective" />

<script>
  import AgentHealthTab from './AgentHealthTab.svelte';
  import SquadProfilesTab from './SquadProfilesTab.svelte';
  import ModelsTab from './ModelsTab.svelte';
  import CompareTab from './CompareTab.svelte';

  const TABS = ['Health', 'Profiles', 'Models', 'Compare'];
  let activeTab = $state('Health');
</script>

<div class="squad-perspective">
  <div class="tab-bar">
    {#each TABS as tab}
      <button
        class="tab-btn"
        class:active={activeTab === tab}
        onclick={() => (activeTab = tab)}
      >
        {tab}
      </button>
    {/each}
  </div>

  <div class="tab-content">
    {#if activeTab === 'Health'}
      <AgentHealthTab />
    {:else if activeTab === 'Profiles'}
      <SquadProfilesTab />
    {:else if activeTab === 'Models'}
      <ModelsTab />
    {:else if activeTab === 'Compare'}
      <CompareTab />
    {/if}
  </div>
</div>

<style>
  .squad-perspective {
    display: flex;
    flex-direction: column;
    height: 100%;
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .tab-bar {
    display: flex;
    gap: 0;
    border-bottom: 1px solid var(--continuum-border, #334155);
    padding: 0 var(--continuum-space-lg, 24px);
    background: var(--continuum-bg-secondary, #1e293b);
    flex-shrink: 0;
  }

  .tab-btn {
    padding: var(--continuum-space-sm, 8px) var(--continuum-space-md, 16px);
    border: none;
    background: transparent;
    color: var(--continuum-text-muted, #94a3b8);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    font-weight: 500;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    transition: color 0.15s, border-color 0.15s;
  }

  .tab-btn:hover {
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .tab-btn.active {
    color: var(--continuum-accent-primary, #6366f1);
    border-bottom-color: var(--continuum-accent-primary, #6366f1);
  }

  .tab-content {
    flex: 1;
    overflow-y: auto;
  }
</style>
