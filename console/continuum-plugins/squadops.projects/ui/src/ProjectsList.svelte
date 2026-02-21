<svelte:options customElement="squadops-projects-list" />

<script>
  import { onMount, onDestroy } from 'svelte';

  let projects = $state([]);
  let filterText = $state('');
  let loading = $state(true);
  let error = $state(null);
  let pollTimer = $state(null);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  async function fetchProjects() {
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/projects`);
      if (!resp.ok) throw new Error(`Projects: ${resp.status}`);
      projects = await resp.json();
      loading = false;
      error = null;
    } catch (err) {
      error = err.message;
      loading = false;
    }
  }

  onMount(() => {
    fetchProjects();
    pollTimer = setInterval(fetchProjects, 30000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  function selectProject(project) {
    window.dispatchEvent(
      new CustomEvent('squadops:select-project', {
        detail: {
          project_id: project.project_id,
          name: project.name,
        },
      })
    );
  }

  let filteredProjects = $derived(
    projects.filter((p) => {
      if (!filterText) return true;
      const q = filterText.toLowerCase();
      return (
        (p.project_id || '').toLowerCase().includes(q) ||
        (p.name || '').toLowerCase().includes(q) ||
        (p.description || '').toLowerCase().includes(q) ||
        (p.tags || []).some((t) => t.toLowerCase().includes(q))
      );
    })
  );
</script>

<div class="projects-list">
  <h3 class="title">Projects</h3>

  <div class="filters">
    <input
      type="text"
      class="filter-input"
      placeholder="Filter by name, ID, or tag..."
      bind:value={filterText}
    />
  </div>

  {#if loading}
    <div class="loading">Loading projects...</div>
  {:else if error}
    <div class="error">Error: {error}</div>
  {:else if filteredProjects.length === 0}
    <div class="empty">No projects match the current filter</div>
  {:else}
    <table class="projects-table">
      <thead>
        <tr>
          <th>Project ID</th>
          <th>Name</th>
          <th>Description</th>
          <th>Tags</th>
        </tr>
      </thead>
      <tbody>
        {#each filteredProjects as project}
          <tr
            class="project-row"
            onclick={() => selectProject(project)}
          >
            <td class="cell-id">{project.project_id}</td>
            <td class="cell-name">{project.name || '--'}</td>
            <td class="cell-desc">{project.description || '--'}</td>
            <td class="cell-tags">
              {#if project.tags && project.tags.length > 0}
                {#each project.tags as tag}
                  <span class="tag">{tag}</span>
                {/each}
              {:else}
                <span class="no-tags">--</span>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<style>
  .projects-list {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .title {
    font-size: var(--continuum-font-size-md, 1rem);
    font-weight: 600;
    margin: 0 0 var(--continuum-space-md, 16px) 0;
  }

  .filters {
    margin-bottom: var(--continuum-space-md, 16px);
  }

  .filter-input {
    width: 100%;
    padding: var(--continuum-space-sm, 8px);
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    color: var(--continuum-text-primary, #e2e8f0);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    outline: none;
    box-sizing: border-box;
  }

  .filter-input:focus {
    border-color: var(--continuum-accent-primary, #6366f1);
  }

  .projects-table {
    width: 100%;
    border-collapse: collapse;
  }

  th,
  td {
    text-align: left;
    padding: var(--continuum-space-sm, 8px);
    border-bottom: 1px solid var(--continuum-border, #334155);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  th {
    color: var(--continuum-text-muted, #94a3b8);
    font-weight: 500;
  }

  .project-row {
    cursor: pointer;
    transition: background 0.15s;
  }

  .project-row:hover {
    background: var(--continuum-bg-tertiary, #273549);
  }

  .cell-id {
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-xs, 0.75rem);
    white-space: nowrap;
  }

  .cell-name {
    font-weight: 500;
  }

  .cell-desc {
    color: var(--continuum-text-muted, #94a3b8);
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .cell-tags {
    display: flex;
    flex-wrap: wrap;
    gap: var(--continuum-space-xs, 4px);
  }

  .tag {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 1px 6px;
    border-radius: var(--continuum-radius-sm, 4px);
    background: rgba(99, 102, 241, 0.15);
    color: var(--continuum-accent-primary, #6366f1);
    font-weight: 500;
  }

  .no-tags {
    color: var(--continuum-text-muted, #94a3b8);
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }

  .loading,
  .error,
  .empty {
    padding: var(--continuum-space-lg, 24px);
    text-align: center;
    color: var(--continuum-text-muted, #94a3b8);
  }

  .error {
    color: var(--continuum-accent-danger, #ef4444);
  }
</style>
