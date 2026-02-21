<svelte:options customElement="squadops-projects-profiles" />

<script>
  import { onMount } from 'svelte';

  let profiles = $state([]);
  let activeProfile = $state(null);
  let loading = $state(true);
  let error = $state(null);
  let setActiveError = $state(null);

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  async function fetchProfiles() {
    try {
      const [profilesResp, activeResp] = await Promise.all([
        apiFetch(`${apiBase}/api/v1/squad-profiles`),
        apiFetch(`${apiBase}/api/v1/squad-profiles/active`),
      ]);
      if (profilesResp.ok) profiles = await profilesResp.json();
      if (activeResp.ok) activeProfile = await activeResp.json();
      error = null;
    } catch (err) {
      error = err.message;
    }
    loading = false;
  }

  onMount(fetchProfiles);

  async function setActive(profileId) {
    setActiveError = null;
    try {
      await apiFetch('/api/commands/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command_id: 'squadops.set_active_profile',
          params: { profile_id: profileId },
        }),
      });
      await fetchProfiles();
    } catch (err) {
      setActiveError = `Failed to set active profile: ${err.message}`;
    }
  }
</script>

<div class="profiles">
  <h3 class="title">Squad Profiles</h3>

  {#if loading}
    <div class="loading">Loading profiles...</div>
  {:else if error}
    <div class="error">Error: {error}</div>
  {:else if profiles.length === 0}
    <div class="empty">No profiles configured</div>
  {:else}
    {#if setActiveError}
      <div class="error">{setActiveError}</div>
    {/if}
    <div class="profile-list">
      {#each profiles as profile}
        <div class="profile-card" class:active={activeProfile?.profile_id === profile.profile_id}>
          <div class="profile-header">
            <span class="profile-name">{profile.profile_id || profile.name}</span>
            {#if activeProfile?.profile_id === profile.profile_id}
              <span class="active-badge">ACTIVE</span>
            {:else}
              <button class="set-active-btn" onclick={() => setActive(profile.profile_id)}>
                Set Active
              </button>
            {/if}
          </div>
          {#if profile.agents}
            <div class="agent-config">
              {#each Object.entries(profile.agents) as [agent, config]}
                <div class="agent-row">
                  <span class="agent-name">{agent}</span>
                  <span class="agent-model">{config.model || '—'}</span>
                  <span class="agent-enabled">{config.enabled !== false ? 'on' : 'off'}</span>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .profiles {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }
  .title { font-size: var(--continuum-font-size-md, 1rem); font-weight: 600; margin: 0 0 var(--continuum-space-md, 16px) 0; }
  .profile-list { display: flex; flex-direction: column; gap: var(--continuum-space-md, 16px); }
  .profile-card {
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-md, 8px);
    padding: var(--continuum-space-md, 16px);
  }
  .profile-card.active { border-color: var(--continuum-accent-primary, #6366f1); }
  .profile-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--continuum-space-sm, 8px); }
  .profile-name { font-weight: 600; }
  .active-badge {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    background: var(--continuum-accent-primary, #6366f1);
    color: #fff; padding: 2px 8px; border-radius: var(--continuum-radius-sm, 4px);
    font-weight: 600;
  }
  .set-active-btn {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    background: transparent; color: var(--continuum-accent-primary, #6366f1);
    border: 1px solid var(--continuum-accent-primary, #6366f1);
    padding: 2px 8px; border-radius: var(--continuum-radius-sm, 4px); cursor: pointer;
  }
  .set-active-btn:hover { background: rgba(99, 102, 241, 0.1); }
  .agent-config { display: flex; flex-direction: column; gap: 2px; }
  .agent-row {
    display: flex; gap: var(--continuum-space-sm, 8px);
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 2px 0;
  }
  .agent-name { min-width: 50px; font-weight: 500; text-transform: capitalize; }
  .agent-model { font-family: var(--continuum-font-mono, monospace); color: var(--continuum-text-muted, #94a3b8); flex: 1; }
  .agent-enabled { color: var(--continuum-text-muted, #94a3b8); }
  .loading, .empty { color: var(--continuum-text-muted, #94a3b8); padding: var(--continuum-space-md, 16px); }
  .error { color: var(--continuum-accent-danger, #ef4444); padding: var(--continuum-space-sm, 8px) 0; font-size: var(--continuum-font-size-sm, 0.875rem); }
</style>
