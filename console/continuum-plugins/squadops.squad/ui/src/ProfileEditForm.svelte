<script>
  let { profile = null, onSave = null, onCancel = null } = $props();

  const apiBase = '';
  let profileId = $state(profile?.profile_id || '');
  let name = $state(profile?.name || '');
  let description = $state(profile?.description || '');
  let agents = $state(
    profile?.agents
      ? profile.agents.map((a) => ({ ...a, config_overrides: { ...(a.config_overrides || {}) } }))
      : [{ agent_id: '', role: '', model: '', enabled: true, config_overrides: {} }]
  );
  let pulledModels = $state([]);
  let submitting = $state(false);
  let error = $state(null);

  const isEditing = !!profile;

  const ROLES = ['strat', 'dev', 'qa', 'data', 'lead', 'builder'];

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  async function fetchModels() {
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/models/pulled`);
      if (resp.ok) {
        pulledModels = await resp.json();
      }
    } catch (_) {
      // Models list is best-effort
    }
  }

  function addAgent() {
    agents = [...agents, { agent_id: '', role: '', model: '', enabled: true, config_overrides: {} }];
  }

  function removeAgent(index) {
    agents = agents.filter((_, i) => i !== index);
  }

  function updateOverride(agentIndex, key, value) {
    const updated = [...agents];
    const overrides = { ...updated[agentIndex].config_overrides };
    if (value === '' || value === undefined) {
      delete overrides[key];
    } else {
      overrides[key] = isNaN(Number(value)) ? value : Number(value);
    }
    updated[agentIndex] = { ...updated[agentIndex], config_overrides: overrides };
    agents = updated;
  }

  let canSubmit = $derived(
    profileId.trim() &&
    name.trim() &&
    agents.length > 0 &&
    agents.every((a) => a.agent_id && a.role && a.model) &&
    !submitting
  );

  async function handleSubmit() {
    submitting = true;
    error = null;
    try {
      const body = {
        profile_id: profileId,
        name,
        description,
        agents: agents.map((a) => ({
          agent_id: a.agent_id,
          role: a.role,
          model: a.model,
          enabled: a.enabled,
          config_overrides: Object.keys(a.config_overrides).length > 0 ? a.config_overrides : undefined,
        })),
      };

      const url = isEditing
        ? `${apiBase}/api/v1/squad-profiles/${profile.profile_id}`
        : `${apiBase}/api/v1/squad-profiles`;
      const method = isEditing ? 'PUT' : 'POST';

      const resp = await apiFetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text || `Request failed (${resp.status})`);
      }

      onSave?.();
    } catch (err) {
      error = err.message;
    } finally {
      submitting = false;
    }
  }

  import { onMount } from 'svelte';
  onMount(fetchModels);
</script>

<div class="profile-form">
  <div class="form-header">
    <h3 class="form-title">{isEditing ? 'Edit Profile' : 'Create Profile'}</h3>
  </div>

  {#if error}
    <div class="form-error">{error}</div>
  {/if}

  <div class="form-body">
    <div class="field-row">
      <div class="field-group">
        <label for="profile-id">Profile ID</label>
        <input
          id="profile-id"
          type="text"
          class="field-input"
          bind:value={profileId}
          disabled={isEditing}
          placeholder="e.g. full-squad"
        />
      </div>
      <div class="field-group">
        <label for="profile-name">Name</label>
        <input
          id="profile-name"
          type="text"
          class="field-input"
          bind:value={name}
          placeholder="e.g. Full Squad"
        />
      </div>
    </div>

    <div class="field-group">
      <label for="profile-desc">Description</label>
      <input
        id="profile-desc"
        type="text"
        class="field-input"
        bind:value={description}
        placeholder="Optional description"
      />
    </div>

    <div class="agents-section">
      <div class="agents-header">
        <h4>Agents</h4>
        <button class="btn btn-sm" onclick={addAgent}>+ Add Agent</button>
      </div>

      {#each agents as agent, i}
        <div class="agent-card">
          <div class="agent-fields">
            <div class="field-group field-narrow">
              <label>Agent ID</label>
              <input type="text" class="field-input" bind:value={agent.agent_id} placeholder="e.g. neo" />
            </div>
            <div class="field-group field-narrow">
              <label>Role</label>
              <select class="field-select" bind:value={agent.role}>
                <option value="">Select...</option>
                {#each ROLES as role}
                  <option value={role}>{role}</option>
                {/each}
              </select>
            </div>
            <div class="field-group field-wide">
              <label>Model</label>
              {#if pulledModels.length > 0}
                <select class="field-select" bind:value={agent.model}>
                  <option value="">Select model...</option>
                  {#each pulledModels as m}
                    <option value={m.name}>{m.name}</option>
                  {/each}
                </select>
              {:else}
                <input type="text" class="field-input" bind:value={agent.model} placeholder="e.g. qwen2.5:7b" />
              {/if}
            </div>
            <div class="field-group field-check">
              <label>
                <input type="checkbox" bind:checked={agent.enabled} />
                Enabled
              </label>
            </div>
            <button class="btn btn-sm btn-danger" onclick={() => removeAgent(i)}>X</button>
          </div>

          <div class="overrides-row">
            <span class="overrides-label">Overrides:</span>
            <input
              type="number"
              class="field-input field-xs"
              placeholder="temperature"
              step="0.1"
              value={agent.config_overrides.temperature ?? ''}
              oninput={(e) => updateOverride(i, 'temperature', e.target.value)}
            />
            <input
              type="number"
              class="field-input field-xs"
              placeholder="max_completion_tokens"
              value={agent.config_overrides.max_completion_tokens ?? ''}
              oninput={(e) => updateOverride(i, 'max_completion_tokens', e.target.value)}
            />
            <input
              type="number"
              class="field-input field-xs"
              placeholder="timeout_seconds"
              value={agent.config_overrides.timeout_seconds ?? ''}
              oninput={(e) => updateOverride(i, 'timeout_seconds', e.target.value)}
            />
          </div>
        </div>
      {/each}
    </div>
  </div>

  <div class="form-footer">
    <button class="btn btn-cancel" onclick={() => onCancel?.()} disabled={submitting}>Cancel</button>
    <button class="btn btn-submit" onclick={handleSubmit} disabled={!canSubmit}>
      {submitting ? 'Saving...' : isEditing ? 'Update' : 'Create'}
    </button>
  </div>
</div>

<style>
  .profile-form {
    max-width: 800px;
  }

  .form-header {
    margin-bottom: var(--continuum-space-md, 16px);
  }

  .form-title {
    font-size: var(--continuum-font-size-lg, 1.25rem);
    font-weight: 600;
    margin: 0;
  }

  .form-error {
    padding: var(--continuum-space-sm, 8px);
    margin-bottom: var(--continuum-space-md, 16px);
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid var(--continuum-accent-danger, #ef4444);
    border-radius: var(--continuum-radius-sm, 4px);
    color: var(--continuum-accent-danger, #ef4444);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  .form-body {
    display: flex;
    flex-direction: column;
    gap: var(--continuum-space-md, 16px);
  }

  .field-row {
    display: flex;
    gap: var(--continuum-space-md, 16px);
  }

  .field-group {
    display: flex;
    flex-direction: column;
    gap: var(--continuum-space-xs, 4px);
    flex: 1;
  }

  .field-group label {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .field-input, .field-select {
    padding: var(--continuum-space-sm, 8px);
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    color: var(--continuum-text-primary, #e2e8f0);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  .agents-section {
    margin-top: var(--continuum-space-sm, 8px);
  }

  .agents-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--continuum-space-sm, 8px);
  }

  .agents-header h4 {
    margin: 0;
    font-size: var(--continuum-font-size-md, 1rem);
  }

  .agent-card {
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-md, 8px);
    padding: var(--continuum-space-sm, 8px);
    margin-bottom: var(--continuum-space-sm, 8px);
    background: var(--continuum-bg-secondary, #1e293b);
  }

  .agent-fields {
    display: flex;
    gap: var(--continuum-space-sm, 8px);
    align-items: flex-end;
  }

  .field-narrow {
    flex: 0 0 120px;
  }

  .field-wide {
    flex: 1;
  }

  .field-check {
    flex: 0 0 80px;
    justify-content: flex-end;
  }

  .overrides-row {
    display: flex;
    gap: var(--continuum-space-sm, 8px);
    align-items: center;
    margin-top: var(--continuum-space-xs, 4px);
    padding-top: var(--continuum-space-xs, 4px);
    border-top: 1px solid var(--continuum-border, #334155);
  }

  .overrides-label {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
    white-space: nowrap;
  }

  .field-xs {
    width: 140px;
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 4px 6px;
  }

  .form-footer {
    display: flex;
    justify-content: flex-end;
    gap: var(--continuum-space-sm, 8px);
    margin-top: var(--continuum-space-lg, 24px);
    padding-top: var(--continuum-space-md, 16px);
    border-top: 1px solid var(--continuum-border, #334155);
  }

  .btn {
    padding: var(--continuum-space-sm, 8px) var(--continuum-space-md, 16px);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    background: var(--continuum-bg-secondary, #1e293b);
    color: var(--continuum-text-primary, #e2e8f0);
    cursor: pointer;
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }

  .btn:hover {
    background: var(--continuum-bg-tertiary, #273549);
  }

  .btn-submit {
    background: var(--continuum-accent-primary, #6366f1);
    border-color: var(--continuum-accent-primary, #6366f1);
    color: #fff;
  }

  .btn-submit:hover {
    background: var(--continuum-accent-primary-hover, #4f46e5);
  }

  .btn-submit:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-sm {
    padding: 2px 8px;
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }

  .btn-danger {
    color: var(--continuum-accent-danger, #ef4444);
    border-color: var(--continuum-accent-danger, #ef4444);
  }

  .btn-cancel {
    background: transparent;
  }
</style>
