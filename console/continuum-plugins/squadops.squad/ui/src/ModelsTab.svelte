<script>
  import { onMount, onDestroy } from 'svelte';

  const apiBase = '';
  let models = $state([]);
  let loading = $state(true);
  let error = $state(null);
  let pollTimer = $state(null);
  let pullName = $state('');
  let pulling = $state(false);
  let pullStatus = $state(null);
  let pullError = $state(null);

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  function formatSize(bytes) {
    if (!bytes) return '—';
    if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
    if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
    return `${(bytes / 1_000).toFixed(1)} KB`;
  }

  function formatDate(iso) {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleDateString();
    } catch (_) {
      return iso;
    }
  }

  async function fetchModels() {
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/models/pulled`);
      if (!resp.ok) {
        error = `Failed to load models (${resp.status})`;
        loading = false;
        return;
      }
      models = await resp.json();
      error = null;
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  }

  async function pullModel() {
    if (!pullName.trim()) return;
    pulling = true;
    pullError = null;
    pullStatus = 'pulling';
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/models/pull`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: pullName }),
      });
      if (!resp.ok) {
        throw new Error(`Pull failed (${resp.status})`);
      }
      const data = await resp.json();
      const pullId = data.pull_id;

      // Poll for completion
      let done = false;
      while (!done) {
        await new Promise((r) => setTimeout(r, 2000));
        const statusResp = await apiFetch(`${apiBase}/api/v1/models/pull/${pullId}/status`);
        if (!statusResp.ok) break;
        const statusData = await statusResp.json();
        pullStatus = statusData.status;
        if (statusData.status === 'complete') {
          done = true;
          pullName = '';
          await fetchModels();
        } else if (statusData.status === 'failed') {
          done = true;
          pullError = statusData.error || 'Pull failed';
        }
      }
    } catch (err) {
      pullError = err.message;
    } finally {
      pulling = false;
      pullStatus = null;
    }
  }

  async function deleteModel(modelName) {
    if (!confirm(`Remove "${modelName}"? This will delete the model from Ollama.`)) return;
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/models/${modelName}`, {
        method: 'DELETE',
      });
      if (resp.ok) {
        await fetchModels();
      }
    } catch (err) {
      error = err.message;
    }
  }

  onMount(() => {
    fetchModels();
    pollTimer = setInterval(fetchModels, 30000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });
</script>

<div class="models-tab">
  <h3 class="section-title">Pulled Models</h3>

  <div class="pull-form">
    <input
      type="text"
      class="field-input"
      bind:value={pullName}
      placeholder="Model name (e.g. qwen2.5:7b)"
      disabled={pulling}
    />
    <button class="btn btn-pull" onclick={pullModel} disabled={pulling || !pullName.trim()}>
      {#if pulling}
        Pulling{pullStatus === 'pulling' ? '...' : ` (${pullStatus})`}
      {:else}
        Pull Model
      {/if}
    </button>
  </div>

  {#if pullError}
    <div class="pull-error">{pullError}</div>
  {/if}

  {#if loading}
    <div class="loading">Loading models...</div>
  {:else if error}
    <div class="error">Error: {error}</div>
  {:else if models.length === 0}
    <div class="empty">
      <p>No models pulled yet.</p>
      <p class="hint">Pull a model to get started. Model selection may be limited until models are available.</p>
    </div>
  {:else}
    <table class="models-table">
      <thead>
        <tr>
          <th></th>
          <th>Model</th>
          <th>Size</th>
          <th>Modified</th>
          <th>Used By</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {#each models as model}
          <tr class="model-row">
            <td>
              {#if model.in_active_profile}
                <span class="active-marker" title="Used in active profile">*</span>
              {/if}
            </td>
            <td class="cell-model">{model.name}</td>
            <td>{formatSize(model.size_bytes)}</td>
            <td class="cell-date">{formatDate(model.modified_at)}</td>
            <td>
              {#if model.used_by_active_profile?.length > 0}
                {model.used_by_active_profile.join(', ')}
              {:else}
                <span class="text-muted">—</span>
              {/if}
            </td>
            <td>
              <button class="btn btn-sm btn-danger" onclick={() => deleteModel(model.name)}>Remove</button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<style>
  .models-tab {
    padding: var(--continuum-space-lg, 24px);
  }

  .section-title {
    font-size: var(--continuum-font-size-lg, 1.25rem);
    font-weight: 600;
    margin: 0 0 var(--continuum-space-md, 16px);
  }

  .pull-form {
    display: flex;
    gap: var(--continuum-space-sm, 8px);
    margin-bottom: var(--continuum-space-md, 16px);
  }

  .field-input {
    flex: 1;
    padding: var(--continuum-space-sm, 8px);
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    color: var(--continuum-text-primary, #e2e8f0);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  .btn-pull {
    padding: var(--continuum-space-sm, 8px) var(--continuum-space-md, 16px);
    background: var(--continuum-accent-primary, #6366f1);
    border: 1px solid var(--continuum-accent-primary, #6366f1);
    border-radius: var(--continuum-radius-sm, 4px);
    color: #fff;
    cursor: pointer;
    font-size: var(--continuum-font-size-sm, 0.875rem);
    white-space: nowrap;
  }

  .btn-pull:hover {
    background: var(--continuum-accent-primary-hover, #4f46e5);
  }

  .btn-pull:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .pull-error {
    padding: var(--continuum-space-sm, 8px);
    margin-bottom: var(--continuum-space-md, 16px);
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid var(--continuum-accent-danger, #ef4444);
    border-radius: var(--continuum-radius-sm, 4px);
    color: var(--continuum-accent-danger, #ef4444);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  .loading, .error, .empty {
    padding: var(--continuum-space-lg, 24px);
    text-align: center;
    color: var(--continuum-text-muted, #94a3b8);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  .error {
    color: var(--continuum-accent-danger, #ef4444);
  }

  .hint {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    margin-top: var(--continuum-space-xs, 4px);
  }

  .models-table {
    width: 100%;
    border-collapse: collapse;
  }

  th, td {
    text-align: left;
    padding: var(--continuum-space-sm, 8px);
    border-bottom: 1px solid var(--continuum-border, #334155);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  th {
    color: var(--continuum-text-muted, #94a3b8);
    font-weight: 600;
    text-transform: uppercase;
    font-size: var(--continuum-font-size-xs, 0.75rem);
    letter-spacing: 0.05em;
  }

  .model-row:hover {
    background: var(--continuum-bg-tertiary, #273549);
  }

  .active-marker {
    color: var(--continuum-accent-success, #22c55e);
    font-weight: 700;
    font-size: var(--continuum-font-size-lg, 1.25rem);
  }

  .cell-model {
    font-family: var(--continuum-font-mono, monospace);
    font-weight: 600;
  }

  .cell-date {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
  }

  .text-muted {
    color: var(--continuum-text-muted, #94a3b8);
  }

  .btn {
    padding: var(--continuum-space-xs, 4px) var(--continuum-space-sm, 8px);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    background: var(--continuum-bg-secondary, #1e293b);
    color: var(--continuum-text-primary, #e2e8f0);
    cursor: pointer;
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }

  .btn:hover {
    background: var(--continuum-bg-tertiary, #273549);
  }

  .btn-sm {
    padding: 2px 6px;
  }

  .btn-danger {
    color: var(--continuum-accent-danger, #ef4444);
    border-color: var(--continuum-accent-danger, #ef4444);
  }
</style>
