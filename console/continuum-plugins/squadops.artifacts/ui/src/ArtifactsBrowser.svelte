<svelte:options customElement="squadops-artifacts-browser" />

<script>
  import { onMount } from 'svelte';

  let projects = $state([]);
  let selectedProject = $state('');
  let baselines = $state({});
  let loading = $state(true);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  async function fetchProjects() {
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/projects`);
      if (resp.ok) projects = await resp.json();
    } catch { /* best-effort */ }
    loading = false;
  }

  async function fetchBaselines(projectId) {
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/projects/${projectId}/baseline`);
      if (resp.ok) baselines = await resp.json();
      else baselines = {};
    } catch { baselines = {}; }
  }

  onMount(fetchProjects);

  function onSelectProject(projectId) {
    selectedProject = projectId;
    if (projectId) fetchBaselines(projectId);
  }
</script>

<div class="artifacts-browser">
  <h3 class="title">Artifact Browser</h3>

  <div class="project-select">
    <select onchange={(e) => onSelectProject(e.target.value)}>
      <option value="">Select project...</option>
      {#each projects as proj}
        <option value={proj.project_id}>{proj.project_id}</option>
      {/each}
    </select>
  </div>

  {#if loading}
    <div class="loading">Loading...</div>
  {:else if selectedProject}
    <div class="section">
      <h4 class="section-title">Baselines — {selectedProject}</h4>
      {#if Object.keys(baselines).length === 0}
        <div class="empty">No baselines set</div>
      {:else}
        <div class="baseline-list">
          {#each Object.entries(baselines) as [type, artifact]}
            <div class="baseline-item">
              <span class="baseline-type">{type}</span>
              <span class="baseline-file">{artifact.filename}</span>
              <span class="baseline-id">{artifact.artifact_id?.slice(0, 12)}</span>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {:else}
    <div class="empty">Select a project to browse artifacts and baselines</div>
  {/if}
</div>

<style>
  .artifacts-browser {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }
  .title { font-size: var(--continuum-font-size-md, 1rem); font-weight: 600; margin: 0 0 var(--continuum-space-md, 16px) 0; }
  .section-title { font-size: var(--continuum-font-size-sm, 0.875rem); font-weight: 600; margin: var(--continuum-space-md, 16px) 0 var(--continuum-space-sm, 8px) 0; }
  .project-select { margin-bottom: var(--continuum-space-md, 16px); }
  select {
    background: var(--continuum-bg-secondary, #1e293b);
    color: var(--continuum-text-primary, #e2e8f0);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    padding: 6px 12px;
  }
  .baseline-list { display: flex; flex-direction: column; gap: var(--continuum-space-xs, 4px); }
  .baseline-item {
    display: flex; gap: var(--continuum-space-sm, 8px); align-items: center;
    padding: var(--continuum-space-sm, 8px);
    background: var(--continuum-bg-secondary, #1e293b);
    border-radius: var(--continuum-radius-sm, 4px);
  }
  .baseline-type { font-weight: 600; min-width: 100px; }
  .baseline-file { font-family: var(--continuum-font-mono, monospace); font-size: var(--continuum-font-size-sm, 0.875rem); }
  .baseline-id { font-family: var(--continuum-font-mono, monospace); font-size: var(--continuum-font-size-xs, 0.75rem); color: var(--continuum-text-muted, #94a3b8); }
  .loading, .empty { color: var(--continuum-text-muted, #94a3b8); padding: var(--continuum-space-md, 16px); }
</style>
