<script>
  import { onMount, onDestroy } from 'svelte';
  import ProfileEditForm from './ProfileEditForm.svelte';

  const apiBase = '';
  let profiles = $state([]);
  let activeProfileId = $state(null);
  let loading = $state(true);
  let error = $state(null);
  let pollTimer = $state(null);
  let editingProfile = $state(null);
  let creating = $state(false);

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  async function fetchProfiles() {
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/squad-profiles`);
      if (!resp.ok) {
        error = `Failed to load profiles (${resp.status})`;
        loading = false;
        return;
      }
      profiles = await resp.json();

      const activeResp = await apiFetch(`${apiBase}/api/v1/squad-profiles/active`);
      if (activeResp.ok) {
        const active = await activeResp.json();
        activeProfileId = active.profile_id;
      }

      error = null;
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  }

  async function setActive(profileId) {
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/squad-profiles/active`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_id: profileId }),
      });
      if (resp.ok) {
        activeProfileId = profileId;
      }
    } catch (err) {
      error = err.message;
    }
  }

  async function deleteProfile(profileId) {
    if (!confirm(`Delete profile "${profileId}"? This cannot be undone.`)) return;
    try {
      const resp = await apiFetch(`${apiBase}/api/v1/squad-profiles/${profileId}`, {
        method: 'DELETE',
      });
      if (resp.ok) {
        await fetchProfiles();
      }
    } catch (err) {
      error = err.message;
    }
  }

  function handleSaved() {
    editingProfile = null;
    creating = false;
    fetchProfiles();
  }

  onMount(() => {
    fetchProfiles();
    pollTimer = setInterval(fetchProfiles, 30000);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });
</script>

<div class="profiles-tab">
  {#if editingProfile || creating}
    <ProfileEditForm
      profile={editingProfile}
      onSave={handleSaved}
      onCancel={() => { editingProfile = null; creating = false; }}
    />
  {:else}
    <div class="header">
      <h3 class="section-title">Squad Profiles</h3>
      <button class="btn btn-new" onclick={() => (creating = true)}>+ New Profile</button>
    </div>

    {#if loading}
      <div class="loading">Loading profiles...</div>
    {:else if error}
      <div class="error">Error: {error}</div>
    {:else if profiles.length === 0}
      <div class="empty">
        <p>No squad profiles yet.</p>
        <button class="btn btn-new" onclick={() => (creating = true)}>Create your first squad profile</button>
      </div>
    {:else}
      <table class="profiles-table">
        <thead>
          <tr>
            <th></th>
            <th>Profile ID</th>
            <th>Name</th>
            <th>Agents</th>
            <th>Version</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each profiles as profile}
            <tr class="profile-row">
              <td>
                {#if profile.profile_id === activeProfileId}
                  <span class="active-marker" title="Active profile">*</span>
                {/if}
              </td>
              <td class="cell-id">{profile.profile_id}</td>
              <td>{profile.name}</td>
              <td>{profile.agents?.length || 0}</td>
              <td>v{profile.version}</td>
              <td class="cell-actions">
                <button class="btn btn-sm" onclick={() => (editingProfile = profile)}>Edit</button>
                {#if profile.profile_id !== activeProfileId}
                  <button class="btn btn-sm btn-accent" onclick={() => setActive(profile.profile_id)}>
                    Set Active
                  </button>
                  <button class="btn btn-sm btn-danger" onclick={() => deleteProfile(profile.profile_id)}>
                    Delete
                  </button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  {/if}
</div>

<style>
  .profiles-tab {
    padding: var(--continuum-space-lg, 24px);
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--continuum-space-md, 16px);
  }

  .section-title {
    font-size: var(--continuum-font-size-lg, 1.25rem);
    font-weight: 600;
    margin: 0;
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

  .profiles-table {
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

  .profile-row:hover {
    background: var(--continuum-bg-tertiary, #273549);
  }

  .active-marker {
    color: var(--continuum-accent-success, #22c55e);
    font-weight: 700;
    font-size: var(--continuum-font-size-lg, 1.25rem);
  }

  .cell-id {
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }

  .cell-actions {
    display: flex;
    gap: var(--continuum-space-xs, 4px);
  }

  .btn {
    padding: var(--continuum-space-xs, 4px) var(--continuum-space-sm, 8px);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    background: var(--continuum-bg-secondary, #1e293b);
    color: var(--continuum-text-primary, #e2e8f0);
    cursor: pointer;
    font-size: var(--continuum-font-size-xs, 0.75rem);
    transition: background 0.15s;
  }

  .btn:hover {
    background: var(--continuum-bg-tertiary, #273549);
  }

  .btn-new {
    background: var(--continuum-accent-primary, #6366f1);
    border-color: var(--continuum-accent-primary, #6366f1);
    color: #fff;
    font-size: var(--continuum-font-size-sm, 0.875rem);
    padding: var(--continuum-space-sm, 8px) var(--continuum-space-md, 16px);
  }

  .btn-new:hover {
    background: var(--continuum-accent-primary-hover, #4f46e5);
  }

  .btn-accent {
    color: var(--continuum-accent-primary, #6366f1);
    border-color: var(--continuum-accent-primary, #6366f1);
  }

  .btn-danger {
    color: var(--continuum-accent-danger, #ef4444);
    border-color: var(--continuum-accent-danger, #ef4444);
  }

  .btn-sm {
    padding: 2px 6px;
  }
</style>
