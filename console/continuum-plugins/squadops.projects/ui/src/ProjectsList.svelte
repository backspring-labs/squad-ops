<svelte:options customElement="squadops-projects-list" />

<script>
  import { onMount, onDestroy } from 'svelte';

  let projects = $state([]);
  let filterText = $state('');
  let loading = $state(true);
  let error = $state(null);
  let pollTimer = $state(null);

  let expandedId = $state(null);
  let prdContent = $state(null);
  let prdLoading = $state(false);
  let prdError = $state(null);
  let recentCycles = $state([]);
  let cyclesLoading = $state(false);

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

  function toggleExpand(project) {
    if (expandedId === project.project_id) {
      expandedId = null;
      prdContent = null;
      prdError = null;
      recentCycles = [];
      return;
    }
    expandedId = project.project_id;
    prdContent = null;
    prdError = null;
    recentCycles = [];
    fetchProjectDetail(project);
  }

  async function fetchProjectDetail(project) {
    // Fetch PRD content (best-effort)
    if (project.has_prd) {
      prdLoading = true;
      try {
        const resp = await apiFetch(`${apiBase}/api/v1/projects/${project.project_id}/prd-content`);
        if (resp.ok) {
          prdContent = await resp.text();
        } else {
          prdError = 'PRD not available';
        }
      } catch {
        prdError = 'Failed to load PRD';
      }
      prdLoading = false;
    }

    // Fetch recent cycles
    cyclesLoading = true;
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/projects/${project.project_id}/cycles?limit=5`);
      if (resp.ok) {
        recentCycles = await resp.json();
      }
    } catch {
      // Non-critical — detail renders without cycles
    }
    cyclesLoading = false;
  }

  function statusColor(status) {
    const colors = {
      completed: 'var(--continuum-accent-success, #22c55e)',
      active: 'var(--continuum-accent-primary, #6366f1)',
      failed: 'var(--continuum-accent-danger, #ef4444)',
      created: 'var(--continuum-text-muted, #94a3b8)',
      cancelled: 'var(--continuum-text-muted, #94a3b8)',
    };
    return colors[status] || colors.created;
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
            class:expanded={expandedId === project.project_id}
            onclick={() => selectProject(project)}
          >
            <td class="cell-id">
              <button
                class="expand-btn"
                title={expandedId === project.project_id ? 'Collapse' : 'Expand'}
                onclick={(e) => { e.stopPropagation(); toggleExpand(project); }}
              >{expandedId === project.project_id ? '\u25BC' : '\u25B6'}</button>
              {project.project_id}
            </td>
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
          {#if expandedId === project.project_id}
            <tr class="detail-row">
              <td colspan="4">
                <div class="project-detail">
                  {#if project.description}
                    <div class="detail-section">
                      <span class="detail-label">Description:</span>
                      <span class="detail-value">{project.description}</span>
                    </div>
                  {/if}
                  {#if project.created_at}
                    <div class="detail-section">
                      <span class="detail-label">Created:</span>
                      <span class="detail-value">{new Date(project.created_at).toLocaleString()}</span>
                    </div>
                  {/if}

                  <!-- PRD Preview -->
                  {#if project.has_prd}
                    <div class="detail-section">
                      <span class="detail-label">PRD:</span>
                      {#if prdLoading}
                        <span class="detail-value muted">Loading...</span>
                      {:else if prdError}
                        <span class="detail-value muted">{prdError}</span>
                      {:else if prdContent}
                        <pre class="prd-preview">{prdContent.slice(0, 2000)}{prdContent.length > 2000 ? '\n\n... (truncated)' : ''}</pre>
                      {/if}
                    </div>
                  {/if}

                  <!-- Recent Cycles -->
                  <div class="detail-section">
                    <span class="detail-label">Recent Cycles:</span>
                    {#if cyclesLoading}
                      <span class="detail-value muted">Loading...</span>
                    {:else if recentCycles.length === 0}
                      <span class="detail-value muted">No cycles yet</span>
                    {:else}
                      <div class="cycle-list">
                        {#each recentCycles as cycle}
                          <div class="cycle-item">
                            <span class="cycle-badge" style="background: {statusColor(cycle.status)}">{cycle.status}</span>
                            <span class="cycle-id">{cycle.cycle_id?.slice(0, 12)}</span>
                            <span class="cycle-date">{new Date(cycle.created_at).toLocaleDateString()}</span>
                          </div>
                        {/each}
                      </div>
                    {/if}
                  </div>
                </div>
              </td>
            </tr>
          {/if}
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

  .project-row.expanded {
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

  .expand-btn {
    background: none;
    border: none;
    color: var(--continuum-text-muted, #94a3b8);
    cursor: pointer;
    font-size: 0.6rem;
    padding: 0 4px 0 0;
    line-height: 1;
  }

  .detail-row td {
    padding: 0;
    border-bottom: 1px solid var(--continuum-border, #334155);
  }

  .project-detail {
    padding: var(--continuum-space-sm, 8px) var(--continuum-space-md, 16px) var(--continuum-space-md, 16px);
    background: var(--continuum-bg-secondary, #1e293b);
    display: flex;
    flex-direction: column;
    gap: var(--continuum-space-sm, 8px);
  }

  .detail-section {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .detail-label {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
    font-weight: 500;
  }

  .detail-value {
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  .detail-value.muted {
    color: var(--continuum-text-muted, #94a3b8);
    font-style: italic;
  }

  .prd-preview {
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-xs, 0.75rem);
    background: var(--continuum-bg-primary, #0f172a);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    padding: var(--continuum-space-sm, 8px);
    max-height: 200px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-wrap: break-word;
    margin: 0;
  }

  .cycle-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .cycle-item {
    display: flex;
    align-items: center;
    gap: var(--continuum-space-sm, 8px);
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 2px 0;
  }

  .cycle-badge {
    font-size: 0.65rem;
    padding: 1px 6px;
    border-radius: var(--continuum-radius-sm, 4px);
    color: #fff;
    font-weight: 600;
    text-transform: uppercase;
  }

  .cycle-id {
    font-family: var(--continuum-font-mono, monospace);
    color: var(--continuum-text-muted, #94a3b8);
  }

  .cycle-date {
    color: var(--continuum-text-muted, #94a3b8);
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
