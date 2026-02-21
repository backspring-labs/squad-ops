<svelte:options customElement="squadops-obs-artifacts" />

<script>
  import { onMount, onDestroy } from 'svelte';

  let artifacts = $state([]);
  let typeCounts = $state({});
  let loading = $state(true);
  let pollTimer = $state(null);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  function timeAgo(iso) {
    if (!iso) return '';
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  function formatSize(bytes) {
    if (!bytes) return '--';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function typeColor(type) {
    const colors = {
      prd: '#6366f1',
      code: '#22c55e',
      test_report: '#f59e0b',
      qa_report: '#f59e0b',
      build_output: '#06b6d4',
    };
    return colors[type] || '#94a3b8';
  }

  async function fetchData() {
    try {
      const projResp = await apiFetch(`${apiBase}/api/v1/projects`);
      if (!projResp.ok) { loading = false; return; }
      const projects = await projResp.json();

      const allArtifacts = [];
      for (const proj of projects.slice(0, 10)) {
        try {
          const resp = await apiFetch(`${apiBase}/api/v1/projects/${proj.project_id}/artifacts`);
          if (!resp.ok) continue;
          const arts = await resp.json();
          allArtifacts.push(...arts);
        } catch { /* skip */ }
      }

      // Compute type counts
      const counts = {};
      for (const a of allArtifacts) {
        const t = a.artifact_type || 'unknown';
        counts[t] = (counts[t] || 0) + 1;
      }
      typeCounts = counts;

      // Sort by created_at desc, take top 10
      allArtifacts.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
      artifacts = allArtifacts.slice(0, 10);
    } catch { /* API unavailable */ }
    loading = false;
  }

  onMount(() => {
    fetchData();
    pollTimer = setInterval(fetchData, 30000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });
</script>

<div class="build-artifacts">
  <h3 class="title">Build Artifacts</h3>

  {#if loading}
    <div class="loading">Loading artifacts...</div>
  {:else if artifacts.length === 0}
    <div class="empty">No artifacts yet</div>
  {:else}
    <div class="type-summary">
      {#each Object.entries(typeCounts) as [type, count]}
        <span class="type-chip" style="border-color: {typeColor(type)}">
          <span class="type-name">{type.replace('_', ' ')}</span>
          <span class="type-count">{count}</span>
        </span>
      {/each}
    </div>

    <div class="artifact-list">
      {#each artifacts as art}
        <div class="artifact-item">
          <span class="art-badge" style="background: {typeColor(art.artifact_type)}">{art.artifact_type?.replace('_', ' ') || '?'}</span>
          <div class="art-info">
            <span class="art-filename">{art.filename}</span>
            <span class="art-meta">{formatSize(art.size_bytes)}</span>
          </div>
          <span class="art-age">{timeAgo(art.created_at)}</span>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .build-artifacts {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }
  .title { font-size: var(--continuum-font-size-md, 1rem); font-weight: 600; margin: 0 0 var(--continuum-space-md, 16px) 0; }
  .type-summary { display: flex; flex-wrap: wrap; gap: var(--continuum-space-sm, 8px); margin-bottom: var(--continuum-space-md, 16px); }
  .type-chip {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 2px 10px; border-radius: var(--continuum-radius-sm, 4px);
    border: 1px solid; font-size: var(--continuum-font-size-xs, 0.75rem);
    background: var(--continuum-bg-secondary, #1e293b);
  }
  .type-name { text-transform: capitalize; }
  .type-count { font-weight: 700; font-family: var(--continuum-font-mono, monospace); }
  .artifact-list { display: flex; flex-direction: column; gap: 2px; }
  .artifact-item {
    display: flex; align-items: center; gap: var(--continuum-space-sm, 8px);
    padding: var(--continuum-space-sm, 8px) var(--continuum-space-md, 16px);
    background: var(--continuum-bg-secondary, #1e293b); border-radius: var(--continuum-radius-sm, 4px);
  }
  .art-badge {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 2px 8px; border-radius: var(--continuum-radius-sm, 4px);
    color: #fff; font-weight: 600; text-transform: uppercase; white-space: nowrap; flex-shrink: 0;
  }
  .art-info { flex: 1; min-width: 0; }
  .art-filename {
    display: block; font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-xs, 0.75rem); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .art-meta { display: block; font-size: var(--continuum-font-size-xs, 0.75rem); color: var(--continuum-text-muted, #94a3b8); }
  .art-age { font-size: var(--continuum-font-size-xs, 0.75rem); color: var(--continuum-text-muted, #94a3b8); flex-shrink: 0; }
  .loading, .empty { color: var(--continuum-text-muted, #94a3b8); font-size: var(--continuum-font-size-sm, 0.875rem); padding: var(--continuum-space-md, 16px); }
</style>
