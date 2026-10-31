<!--
  CycleCreateModal — multi-section cycle creation form (SIP-0074 §3.1).

  Sections:
  1. Project & Squad — project dropdown, squad profile dropdown, agent summary
  2. PRD — mode toggle (write / use project PRD), monospace textarea, size constraints
  3. Profile params — dynamic fields from selected cycle request profile, and its stack choice
  4. Request preview — the cycle-create body the server resolves from the profile's name
  5. Submit — resolve the request, ingest PRD artifact, resolve it with the PRD, then create cycle
     via command bus

  The body is never built here (#2520): the runtime API resolves it with the one builder the CLI and
  a campaign's launches share, so a profile run on a stack gets that stack's request defaults here
  too. The preview is that resolution; the submit resolves it once more with the PRD and notes.

  PRD size constraints:
  - Warn at 50 KB (yellow)
  - Block at 200 KB (red, submit disabled)
-->
<script>
  import { onMount } from 'svelte';
  import ProfileParamRenderer from './ProfileParamRenderer.svelte';

  let { onCreated = null, onClose = null } = $props();

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  async function executeCommand(commandId, params) {
    const resp = await apiFetch(`${apiBase}/api/commands/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command_id: commandId, params }),
    });
    if (!resp.ok) {
      const body = await resp.text();
      const err = new Error(body || `Command failed: ${resp.status}`);
      err.status = resp.status;
      throw err;
    }
    return resp.json();
  }

  // ── Data loading state ──────────────────────────────────────────────
  let projects = $state([]);
  let squadProfiles = $state([]);
  let requestProfiles = $state([]);
  let loadingData = $state(true);
  let loadError = $state(null);

  // ── Form state ──────────────────────────────────────────────────────
  let selectedProjectId = $state('');
  let selectedSquadProfileId = $state('');
  // #316: the operator's profiles, as the CLI's default; the listing no longer carries `default`.
  let selectedRequestProfileName = $state('smoke');
  let prdMode = $state('write');
  let prdText = $state('');
  let prdLoading = $state(false);
  let prdError = $state(null);
  let userOverrides = $state({});
  // #2520: the stack an operator profile runs on, the CLI's `--set build_profile`. Empty is none.
  let selectedStack = $state('');
  let notes = $state('');
  let showDefaults = $state(false);

  // ── Submit state ────────────────────────────────────────────────────
  let submitting = $state(false);
  let submitError = $state(null);

  // ── PRD size constraints ────────────────────────────────────────────
  const PRD_WARN_BYTES = 50 * 1024;
  const PRD_BLOCK_BYTES = 200 * 1024;

  let prdSize = $derived(new Blob([prdText]).size);
  let prdSizeKb = $derived((prdSize / 1024).toFixed(1));
  let prdWarn = $derived(prdSize >= PRD_WARN_BYTES && prdSize < PRD_BLOCK_BYTES);
  let prdBlocked = $derived(prdSize >= PRD_BLOCK_BYTES);

  // ── Derived data ────────────────────────────────────────────────────
  let selectedProject = $derived(
    projects.find((p) => p.project_id === selectedProjectId) || null
  );
  let selectedRequestProfile = $derived(
    requestProfiles.find((p) => p.name === selectedRequestProfileName) || null
  );
  let selectedSquadProfile = $derived(
    squadProfiles.find((p) => p.profile_id === selectedSquadProfileId) || null
  );

  // ── The request, resolved by the server (#2520) ─────────────────────
  let resolved = $state(null);
  let resolveError = $state(null);

  // The caller's values: the profile's prompts, and the stack when one is chosen.
  function requestValues() {
    const values = $state.snapshot(userOverrides);
    return selectedStack ? { ...values, build_profile: selectedStack } : values;
  }

  async function resolveRequest(profileName, squadProfileId, values, extra = {}) {
    const resp = await apiFetch(
      `${apiBase}/api/v1/cycle-request-profiles/${encodeURIComponent(profileName)}/resolve`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ squad_profile_id: squadProfileId, values, ...extra }),
      },
    );
    if (!resp.ok) {
      const text = await resp.text();
      let message = text;
      try {
        message = JSON.parse(text)?.detail?.error?.message || JSON.parse(text)?.error?.message || text;
      } catch {
        // not the error envelope: show it as it came
      }
      throw new Error(message || `Resolving the request failed: ${resp.status}`);
    }
    return resp.json();
  }

  // Resolved again whenever the profile, the squad or a value changes; a stale answer is dropped.
  $effect(() => {
    const profileName = selectedRequestProfile?.name;
    const squadProfileId = selectedSquadProfileId;
    const values = requestValues();
    // Nothing is submittable until this resolution answers: a refused change never submits the
    // body resolved before it.
    resolved = null;
    resolveError = null;
    if (!profileName || !squadProfileId) {
      return;
    }
    let current = true;
    resolveRequest(profileName, squadProfileId, values)
      .then((body) => {
        if (current) {
          resolved = body;
          resolveError = null;
        }
      })
      .catch((err) => {
        if (current) {
          resolved = null;
          resolveError = err.message;
        }
      });
    return () => {
      current = false;
    };
  });

  let offeredStacks = $derived(selectedRequestProfile?.stacks || []);
  $effect(() => {
    if (selectedStack && !offeredStacks.includes(selectedStack)) {
      selectedStack = '';
    }
  });

  // Check for required fields with unknown type (blocks submit)
  let unsupportedRequiredFields = $derived.by(() => {
    if (!selectedRequestProfile?.prompts) return [];
    const bad = [];
    for (const [key, meta] of Object.entries(selectedRequestProfile.prompts)) {
      if (!meta.required) continue;
      const inferredType = meta.type
        || (meta.choices?.length > 0 ? 'choice'
          : typeof (selectedRequestProfile.defaults?.[key]) === 'boolean' ? 'bool'
            : 'text');
      if (!['choice', 'text', 'bool'].includes(inferredType)) {
        bad.push(key);
      }
    }
    return bad;
  });

  let canSubmit = $derived(
    selectedProjectId &&
    selectedSquadProfileId &&
    prdText.trim().length > 0 &&
    !prdBlocked &&
    !submitting &&
    resolved !== null &&
    unsupportedRequiredFields.length === 0
  );

  // ── Load initial data ───────────────────────────────────────────────
  async function loadData() {
    loadingData = true;
    loadError = null;
    try {
      const [projResp, squadResp, profileResp] = await Promise.all([
        apiFetch(`${apiBase}/api/v1/projects`),
        apiFetch(`${apiBase}/api/v1/squad-profiles`),
        apiFetch(`${apiBase}/api/v1/cycle-request-profiles`),
      ]);

      if (!projResp.ok) throw new Error(`Projects: ${projResp.status}`);
      if (!squadResp.ok) throw new Error(`Squad profiles: ${squadResp.status}`);
      if (!profileResp.ok) throw new Error(`Request profiles: ${profileResp.status}`);

      projects = await projResp.json();
      squadProfiles = await squadResp.json();
      requestProfiles = await profileResp.json();
      // A choice the listing doesn't carry would send a cycle with no profile's defaults at all.
      if (requestProfiles.length > 0 && !requestProfiles.some((p) => p.name === selectedRequestProfileName)) {
        selectedRequestProfileName = requestProfiles[0].name;
      }

      // Auto-select first project and active squad profile
      if (projects.length > 0) {
        selectedProjectId = projects[0].project_id;
      }
      const active = squadProfiles.find((p) => p.is_active);
      if (active) {
        selectedSquadProfileId = active.profile_id;
      } else if (squadProfiles.length > 0) {
        selectedSquadProfileId = squadProfiles[0].profile_id;
      }
    } catch (err) {
      loadError = err.message;
    } finally {
      loadingData = false;
    }
  }

  onMount(() => {
    loadData();
  });

  // ── PRD loading from project ────────────────────────────────────────
  async function loadProjectPrd() {
    if (!selectedProjectId) return;
    prdLoading = true;
    prdError = null;
    try {
      const resp = await apiFetch(
        `${apiBase}/api/v1/projects/${selectedProjectId}/prd-content`
      );
      if (!resp.ok) {
        if (resp.status === 404) {
          prdError = 'PRD file not available in this deployment; paste PRD text instead.';
        } else {
          prdError = `Failed to load PRD: ${resp.status}`;
        }
        return;
      }
      prdText = await resp.text();
    } catch {
      prdError = 'Failed to load PRD file.';
    } finally {
      prdLoading = false;
    }
  }

  // When mode switches to "project", auto-load the PRD
  $effect(() => {
    if (prdMode === 'project' && selectedProjectId) {
      loadProjectPrd();
    }
  });

  // ── Submit flow ─────────────────────────────────────────────────────
  async function handleSubmit() {
    if (!canSubmit) return;

    if (!selectedRequestProfile) {
      submitError = 'Choose a request profile';
      return;
    }
    submitting = true;
    submitError = null;

    try {
      // Step 0: the request must resolve before anything is stored
      const values = requestValues();
      await resolveRequest(selectedRequestProfile.name, selectedSquadProfileId, values);

      // Step 1: Ingest PRD text as artifact
      const ingestResult = await executeCommand('squadops.ingest_artifact', {
        project_id: selectedProjectId,
        filename: 'prd.md',
        artifact_type: 'documentation',
        media_type: 'text/markdown',
        content: prdText,
      });

      if (ingestResult.error) {
        throw new Error(ingestResult.error);
      }

      const prdRef = ingestResult.artifact_id;

      // Step 2: Resolve the request with its PRD and notes, as the CLI's would be built
      const body = await resolveRequest(
        selectedRequestProfile.name,
        selectedSquadProfileId,
        values,
        { prd_ref: prdRef, ...(notes.trim() ? { notes: notes.trim() } : {}) },
      );

      // Step 3: Create cycle via command bus
      const result = await executeCommand('squadops.create_cycle', {
        project_id: selectedProjectId,
        ...body,
      });

      if (result.error) {
        throw new Error(result.error);
      }

      // Step 4: Notify parent with new selection
      onCreated?.({
        project_id: selectedProjectId,
        cycle_id: result.cycle_id,
        run_id: result.run_id,
      });
    } catch (err) {
      submitError = err.message;
    } finally {
      submitting = false;
    }
  }

  function handleParamChange(newValues) {
    userOverrides = newValues;
  }

  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) {
      onClose?.();
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="modal-backdrop" onclick={handleBackdropClick}>
  <div class="modal-content">
    <div class="modal-header">
      <h2 class="modal-title">New Cycle</h2>
      <button class="modal-close" onclick={() => onClose?.()}>X</button>
    </div>

    {#if loadingData}
      <div class="modal-loading">Loading...</div>
    {:else if loadError}
      <div class="modal-error">Error: {loadError}</div>
    {:else}
      <div class="modal-body">
        <!-- Section 1: Project & Squad Profile -->
        <div class="section">
          <h3 class="section-title">Project & Squad</h3>
          <div class="field-row">
            <div class="field-group">
              <label class="field-label" for="project-select">Project</label>
              <select id="project-select" class="field-select" bind:value={selectedProjectId}>
                {#each projects as proj}
                  <option value={proj.project_id}>{proj.name} ({proj.project_id})</option>
                {/each}
              </select>
            </div>
            <div class="field-group">
              <label class="field-label" for="squad-select">Squad Profile</label>
              <select id="squad-select" class="field-select" bind:value={selectedSquadProfileId}>
                {#each squadProfiles as sp}
                  <option value={sp.profile_id}>
                    {sp.name}{sp.is_active ? ' (active)' : ''}
                  </option>
                {/each}
              </select>
            </div>
          </div>
          {#if selectedSquadProfile?.agents}
            <div class="agent-summary">
              {#each selectedSquadProfile.agents as agent}
                <span class="agent-chip">{agent.display_name || agent.agent_id} ({agent.role_label || agent.role})</span>
              {/each}
            </div>
          {/if}
        </div>

        <!-- Section 2: PRD -->
        <div class="section">
          <h3 class="section-title">PRD</h3>
          <div class="prd-mode-toggle">
            <label class="toggle-label">
              <input type="radio" bind:group={prdMode} value="write" />
              Write PRD
            </label>
            <label
              class="toggle-label"
              title={!selectedProject?.has_prd ? 'No PRD file configured for this project' : ''}
            >
              <input
                type="radio"
                bind:group={prdMode}
                value="project"
                disabled={!selectedProject?.has_prd}
              />
              Use project PRD
            </label>
          </div>

          {#if prdLoading}
            <div class="prd-loading">Loading PRD...</div>
          {/if}

          {#if prdError}
            <div class="prd-error">{prdError}</div>
          {/if}

          <textarea
            class="prd-textarea"
            class:prd-warn={prdWarn}
            class:prd-blocked={prdBlocked}
            bind:value={prdText}
            rows="20"
            placeholder="Paste or write your PRD here..."
          ></textarea>

          <div class="prd-size" class:size-warn={prdWarn} class:size-blocked={prdBlocked}>
            {prdSizeKb} KB
            {#if prdWarn}
              — large PRD, consider trimming
            {/if}
            {#if prdBlocked}
              — exceeds 200 KB limit
            {/if}
          </div>
        </div>

        <!-- Section 3: Cycle Request Profile & Params -->
        <div class="section">
          <h3 class="section-title">Cycle Request Profile</h3>
          <div class="field-group">
            <label class="field-label" for="profile-select">Profile</label>
            <select
              id="profile-select"
              class="field-select"
              bind:value={selectedRequestProfileName}
            >
              {#each requestProfiles as rp}
                <option value={rp.name}>{rp.name}{rp.description ? ` — ${rp.description}` : ''}</option>
              {/each}
            </select>
          </div>

          {#if selectedRequestProfile?.prompts && Object.keys(selectedRequestProfile.prompts).length > 0}
            <div class="profile-params">
              <ProfileParamRenderer
                prompts={selectedRequestProfile.prompts}
                defaults={selectedRequestProfile.defaults}
                values={userOverrides}
                onChange={handleParamChange}
              />
            </div>
          {/if}
          {#if offeredStacks.length > 0}
            <div class="field-group">
              <label class="field-label" for="cycle-stack">Stack</label>
              <select id="cycle-stack" class="field-select" bind:value={selectedStack}>
                <option value="">none</option>
                {#each offeredStacks as stack}
                  <option value={stack}>{stack}</option>
                {/each}
              </select>
              <span class="field-help">A squad with a builder needs one. Its request defaults sit beneath the profile's.</span>
            </div>
          {/if}
        </div>

        <!-- Section 4: Notes -->
        <div class="section">
          <h3 class="section-title">Notes</h3>
          <input
            type="text"
            class="field-input"
            bind:value={notes}
            placeholder="Optional: describe the experiment intent..."
          />
        </div>

        <!-- Section 5: The request the server resolved (#2520) -->
        <div class="section">
          <button class="defaults-toggle" onclick={() => showDefaults = !showDefaults}>
            {showDefaults ? 'Hide' : 'Show'} the request
          </button>
          {#if showDefaults && resolved}
            <pre class="defaults-preview">{JSON.stringify(resolved, null, 2)}</pre>
          {/if}
        </div>

        {#if resolveError}
          <div class="submit-error">The request can't be resolved: {resolveError}</div>
        {/if}

        <!-- Unsupported required field errors -->
        {#if unsupportedRequiredFields.length > 0}
          <div class="submit-error">
            Unsupported prompt type for required field(s): {unsupportedRequiredFields.join(', ')}
          </div>
        {/if}

        <!-- Submit error -->
        {#if submitError}
          <div class="submit-error">{submitError}</div>
        {/if}
      </div>

      <div class="modal-footer">
        <button class="btn btn-cancel" onclick={() => onClose?.()} disabled={submitting}>
          Cancel
        </button>
        <button class="btn btn-submit" onclick={handleSubmit} disabled={!canSubmit}>
          {submitting ? 'Creating...' : 'Create Cycle'}
        </button>
      </div>
    {/if}
  </div>
</div>

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .modal-content {
    background: var(--continuum-bg-primary, #0f172a);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-lg, 12px);
    width: 90%;
    max-width: 720px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--continuum-space-lg, 24px);
    border-bottom: 1px solid var(--continuum-border, #334155);
  }

  .modal-title {
    font-size: var(--continuum-font-size-lg, 1.25rem);
    font-weight: 600;
    margin: 0;
  }

  .modal-close {
    background: none;
    border: none;
    color: var(--continuum-text-muted, #94a3b8);
    font-size: var(--continuum-font-size-md, 1rem);
    cursor: pointer;
    padding: var(--continuum-space-xs, 4px) var(--continuum-space-sm, 8px);
  }

  .modal-close:hover {
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .modal-body {
    padding: var(--continuum-space-lg, 24px);
    overflow-y: auto;
    flex: 1;
  }

  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: var(--continuum-space-sm, 8px);
    padding: var(--continuum-space-lg, 24px);
    border-top: 1px solid var(--continuum-border, #334155);
  }

  .modal-loading,
  .modal-error {
    padding: var(--continuum-space-lg, 24px);
    text-align: center;
    color: var(--continuum-text-muted, #94a3b8);
  }

  .modal-error {
    color: var(--continuum-accent-danger, #ef4444);
  }

  .section {
    margin-bottom: var(--continuum-space-lg, 24px);
  }

  .section-title {
    font-size: var(--continuum-font-size-sm, 0.875rem);
    font-weight: 600;
    color: var(--continuum-text-muted, #94a3b8);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0 0 var(--continuum-space-sm, 8px) 0;
  }

  .field-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--continuum-space-md, 16px);
  }

  .field-group {
    display: flex;
    flex-direction: column;
    gap: var(--continuum-space-xs, 4px);
  }

  .field-label {
    font-size: var(--continuum-font-size-sm, 0.875rem);
    font-weight: 600;
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .field-help {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
  }

  .field-select,
  .field-input {
    padding: var(--continuum-space-sm, 8px);
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    color: var(--continuum-text-primary, #e2e8f0);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    outline: none;
  }

  .field-select:focus,
  .field-input:focus {
    border-color: var(--continuum-accent-primary, #6366f1);
  }

  .agent-summary {
    display: flex;
    flex-wrap: wrap;
    gap: var(--continuum-space-xs, 4px);
    margin-top: var(--continuum-space-sm, 8px);
  }

  .agent-chip {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 2px 8px;
    background: rgba(99, 102, 241, 0.15);
    border-radius: var(--continuum-radius-sm, 4px);
    color: var(--continuum-accent-primary, #6366f1);
    font-weight: 500;
  }

  /* PRD section */
  .prd-mode-toggle {
    display: flex;
    gap: var(--continuum-space-md, 16px);
    margin-bottom: var(--continuum-space-sm, 8px);
  }

  .toggle-label {
    display: flex;
    align-items: center;
    gap: var(--continuum-space-xs, 4px);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    cursor: pointer;
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .prd-textarea {
    width: 100%;
    min-height: 200px;
    padding: var(--continuum-space-sm, 8px);
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    color: var(--continuum-text-primary, #e2e8f0);
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    resize: vertical;
    outline: none;
    box-sizing: border-box;
  }

  .prd-textarea:focus {
    border-color: var(--continuum-accent-primary, #6366f1);
  }

  .prd-textarea.prd-warn {
    border-color: var(--continuum-accent-warning, #f59e0b);
  }

  .prd-textarea.prd-blocked {
    border-color: var(--continuum-accent-danger, #ef4444);
  }

  .prd-size {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
    margin-top: var(--continuum-space-xs, 4px);
    text-align: right;
  }

  .prd-size.size-warn {
    color: var(--continuum-accent-warning, #f59e0b);
  }

  .prd-size.size-blocked {
    color: var(--continuum-accent-danger, #ef4444);
    font-weight: 600;
  }

  .prd-loading {
    font-size: var(--continuum-font-size-sm, 0.875rem);
    color: var(--continuum-text-muted, #94a3b8);
    margin-bottom: var(--continuum-space-sm, 8px);
  }

  .prd-error {
    font-size: var(--continuum-font-size-sm, 0.875rem);
    color: var(--continuum-accent-warning, #f59e0b);
    margin-bottom: var(--continuum-space-sm, 8px);
  }

  .profile-params {
    margin-top: var(--continuum-space-md, 16px);
  }

  /* Applied defaults */
  .defaults-toggle {
    background: none;
    border: none;
    color: var(--continuum-accent-primary, #6366f1);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    cursor: pointer;
    padding: 0;
    text-decoration: underline;
  }

  .defaults-preview {
    margin-top: var(--continuum-space-sm, 8px);
    padding: var(--continuum-space-sm, 8px);
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
    overflow-x: auto;
    white-space: pre-wrap;
  }

  .submit-error {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: var(--continuum-radius-sm, 4px);
    padding: var(--continuum-space-sm, 8px);
    color: var(--continuum-accent-danger, #ef4444);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    margin-top: var(--continuum-space-sm, 8px);
  }

  .btn {
    padding: var(--continuum-space-sm, 8px) var(--continuum-space-lg, 24px);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    font-size: var(--continuum-font-size-sm, 0.875rem);
    font-weight: 500;
    cursor: pointer;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-cancel {
    background: transparent;
    color: var(--continuum-text-muted, #94a3b8);
  }

  .btn-cancel:hover:not(:disabled) {
    color: var(--continuum-text-primary, #e2e8f0);
  }

  .btn-submit {
    background: var(--continuum-accent-primary, #6366f1);
    color: #fff;
    border-color: var(--continuum-accent-primary, #6366f1);
  }

  .btn-submit:hover:not(:disabled) {
    background: var(--continuum-accent-primary-hover, #4f46e5);
  }
</style>
