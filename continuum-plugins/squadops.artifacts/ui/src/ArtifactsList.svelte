<svelte:options customElement="squadops-artifacts-list" />

<script>
  import { onMount } from 'svelte';

  let artifacts = $state([]);
  let loading = $state(true);
  let filterType = $state('');
  let filterProject = $state('');
  let projects = $state([]);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  async function fetchArtifacts() {
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/projects`);
      if (!resp.ok) return;
      const projList = await resp.json();
      projects = projList;

      const all = [];
      for (const proj of projList.slice(0, 10)) {
        try {
          const artResp = await apiFetch(`${apiBase}/api/v1/projects/${proj.project_id}/artifacts`);
          if (artResp.ok) {
            const arts = await artResp.json();
            all.push(...arts.map(a => ({ ...a, project_id: proj.project_id })));
          }
        } catch { /* skip */ }
      }
      artifacts = all;
    } catch { /* best-effort */ }
    loading = false;
  }

  onMount(fetchArtifacts);

  function filtered() {
    let result = artifacts;
    if (filterType) result = result.filter(a => a.artifact_type === filterType);
    if (filterProject) result = result.filter(a => a.project_id === filterProject);
    return result;
  }

  function selectArtifact(artifact) {
    window.dispatchEvent(new CustomEvent('squadops:select-artifact', { detail: artifact }));
  }

  function formatTimestamp(iso) {
    if (!iso) return '--';
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }
</script>

<div class="artifacts-list">
  <h3 class="title">Artifacts</h3>

  <div class="filters">
    <select bind:value={filterType}>
      <option value="">All types</option>
      <option value="source">Source</option>
      <option value="test">Test</option>
      <option value="config">Config</option>
      <option value="documentation">Documentation</option>
    </select>
    <select bind:value={filterProject}>
      <option value="">All projects</option>
      {#each projects as proj}
        <option value={proj.project_id}>{proj.project_id}</option>
      {/each}
    </select>
  </div>

  {#if loading}
    <div class="loading">Loading artifacts...</div>
  {:else if filtered().length === 0}
    <div class="empty">No artifacts found</div>
  {:else}
    <table class="table">
      <thead>
        <tr><th>Filename</th><th>Type</th><th>Media</th><th>Size</th><th>Project</th><th>Created</th></tr>
      </thead>
      <tbody>
        {#each filtered() as art}
          <tr class="clickable" onclick={() => selectArtifact(art)}>
            <td class="mono">{art.filename}</td>
            <td><span class="badge">{art.artifact_type}</span></td>
            <td class="muted">{art.media_type || '--'}</td>
            <td>{art.size_bytes ? `${(art.size_bytes / 1024).toFixed(1)}KB` : '--'}</td>
            <td>{art.project_id}</td>
            <td class="muted">{formatTimestamp(art.created_at)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<style>
  .artifacts-list {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }
  .title { font-size: var(--continuum-font-size-md, 1rem); font-weight: 600; margin: 0 0 var(--continuum-space-md, 16px) 0; }
  .filters { display: flex; gap: var(--continuum-space-sm, 8px); margin-bottom: var(--continuum-space-md, 16px); }
  select {
    background: var(--continuum-bg-secondary, #1e293b);
    color: var(--continuum-text-primary, #e2e8f0);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    padding: 4px 8px;
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }
  .table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: var(--continuum-space-sm, 8px); border-bottom: 1px solid var(--continuum-border, #334155); font-size: var(--continuum-font-size-sm, 0.875rem); }
  th { color: var(--continuum-text-muted, #94a3b8); font-weight: 500; }
  .clickable { cursor: pointer; }
  .clickable:hover { background: var(--continuum-bg-hover, #334155); }
  .mono { font-family: var(--continuum-font-mono, monospace); font-size: var(--continuum-font-size-xs, 0.75rem); }
  .muted { color: var(--continuum-text-muted, #94a3b8); font-size: var(--continuum-font-size-xs, 0.75rem); }
  .badge { background: var(--continuum-bg-tertiary, #334155); padding: 2px 6px; border-radius: var(--continuum-radius-sm, 4px); font-size: var(--continuum-font-size-xs, 0.75rem); }
  .loading, .empty { color: var(--continuum-text-muted, #94a3b8); padding: var(--continuum-space-md, 16px); }
</style>
