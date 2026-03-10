<!--
  ArtifactTypeFilter — filter chips for artifact list (SIP-0074 §2.5).
  Uses Option B: existing artifacts endpoint provides artifact_type field.
-->
<script>
  let { artifacts = [], onFilter = null } = $props();

  let activeType = $state('all');

  const types = [
    { key: 'all', label: 'All' },
    { key: 'source', label: 'Code' },
    { key: 'document', label: 'Docs' },
    { key: 'config', label: 'Config' },
    { key: 'test', label: 'Tests' },
  ];

  function setFilter(type) {
    activeType = type;
    if (type === 'all') {
      onFilter?.(artifacts);
    } else {
      onFilter?.(artifacts.filter(a => a.artifact_type === type));
    }
  }
</script>

<div class="filter-chips">
  {#each types as t}
    <button
      class="chip"
      class:active={activeType === t.key}
      onclick={() => setFilter(t.key)}
    >
      {t.label}
    </button>
  {/each}
</div>

<style>
  .filter-chips {
    display: flex;
    gap: var(--continuum-space-xs, 4px);
    margin-bottom: var(--continuum-space-sm, 8px);
  }

  .chip {
    padding: 2px 10px;
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    background: transparent;
    color: var(--continuum-text-muted, #94a3b8);
    font-size: var(--continuum-font-size-xs, 0.75rem);
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }

  .chip:hover {
    background: var(--continuum-bg-tertiary, #273549);
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .chip.active {
    background: var(--continuum-accent-primary, #6366f1);
    color: #fff;
    border-color: var(--continuum-accent-primary, #6366f1);
  }
</style>
