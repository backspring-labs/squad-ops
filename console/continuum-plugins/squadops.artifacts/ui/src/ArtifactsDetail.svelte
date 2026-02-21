<svelte:options customElement="squadops-artifacts-detail" />

<script>
  import { onMount, onDestroy } from 'svelte';

  let artifact = $state(null);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  function onSelect(e) {
    artifact = e.detail;
  }

  onMount(() => {
    window.addEventListener('squadops:select-artifact', onSelect);
  });

  onDestroy(() => {
    window.removeEventListener('squadops:select-artifact', onSelect);
  });

  async function download() {
    if (!artifact) return;
    const resp = await apiFetch(`${apiBase}/api/v1/artifacts/${artifact.artifact_id}/download`);
    if (resp.ok) {
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = artifact.filename;
      a.click();
      URL.revokeObjectURL(url);
    }
  }

  function view() {
    if (!artifact) return;
    window.dispatchEvent(new CustomEvent('squadops:view-artifact', { detail: artifact }));
  }
</script>

<div class="artifacts-detail">
  {#if artifact}
    <h4 class="title">{artifact.filename}</h4>
    <div class="meta">
      <div class="row"><span class="key">Type:</span><span class="val">{artifact.artifact_type}</span></div>
      <div class="row"><span class="key">Media:</span><span class="val">{artifact.media_type || '--'}</span></div>
      <div class="row"><span class="key">Size:</span><span class="val">{artifact.size_bytes ? `${(artifact.size_bytes / 1024).toFixed(1)}KB` : '--'}</span></div>
      <div class="row"><span class="key">Hash:</span><span class="val mono">{artifact.content_hash?.slice(0, 16) || '--'}</span></div>
      <div class="row"><span class="key">ID:</span><span class="val mono">{artifact.artifact_id}</span></div>
    </div>
    <div class="actions">
      <button class="view-btn" onclick={view}>View</button>
      <button class="download-btn" onclick={download}>Download</button>
    </div>
  {:else}
    <div class="empty">Select an artifact to view details</div>
  {/if}
</div>

<style>
  .artifacts-detail {
    padding: var(--continuum-space-md, 16px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }
  .title { font-size: var(--continuum-font-size-md, 1rem); font-weight: 600; margin: 0 0 var(--continuum-space-md, 16px) 0; word-break: break-all; }
  .meta { display: flex; flex-direction: column; gap: 4px; }
  .row { display: flex; gap: var(--continuum-space-sm, 8px); font-size: var(--continuum-font-size-sm, 0.875rem); }
  .key { color: var(--continuum-text-muted, #94a3b8); min-width: 60px; }
  .mono { font-family: var(--continuum-font-mono, monospace); }
  .actions {
    display: flex;
    gap: var(--continuum-space-sm, 8px);
    margin-top: var(--continuum-space-md, 16px);
  }
  .view-btn, .download-btn {
    background: var(--continuum-accent-primary, #6366f1);
    color: #fff; border: none; padding: 8px 16px;
    border-radius: var(--continuum-radius-sm, 4px); cursor: pointer;
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }
  .download-btn {
    background: var(--continuum-bg-tertiary, #334155);
  }
  .view-btn:hover, .download-btn:hover { opacity: 0.9; }
  .empty { color: var(--continuum-text-muted, #94a3b8); font-size: var(--continuum-font-size-sm, 0.875rem); }
</style>
