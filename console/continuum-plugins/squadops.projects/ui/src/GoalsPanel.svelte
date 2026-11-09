<svelte:options customElement="squadops-projects-goals" />

<!--
  The goals panel (SIP-0115 §8.3, slice 4, #2887): the selected Project's goal set and expected
  results with the operator's latest assessment of each (slice 5, #2888), its backlog with each item's
  status and increment as a chosen Campaign stands on it,
  the candidates waiting (read-only: slice 3's actions are not here) and the revision history.
  Editing writes the next revision through the command bus. What it reads and how it writes is
  `goals.js`; this file renders it.

  How it fits the pinned shell (docs/architecture/console-fit-check-2-6.md, view 1): a panel in
  the `discovery` perspective, following `squadops:select-project` from the Projects list, and
  `squadops:select-campaign` from any view that names a Campaign (the link from a Campaign); it
  polls, as every live view does, and stops while an edit is open so a refresh never replaces it.
-->

<script>
  import { onDestroy, onMount } from 'svelte';
  import {
    backlogRows,
    canWriteGoalSet,
    documentFrom,
    draftFrom,
    incrementOf,
    loadAssessments,
    loadBacklog,
    loadGoalSet,
    loadGoalSetCampaigns,
    moved,
    newIdempotencyKey,
    revisionArgs,
    submitRevision,
  } from './goals.js';
  import { standingOf } from '../../../shared/assessments.js';
  import { takeAnnounced } from '../../../shared/selection.js';

  const SELECT_CAMPAIGN = 'squadops:select-campaign';

  const POLL_MS = 30000;
  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  let projectId = $state(null);
  let projectName = $state(null);
  let loading = $state(false);
  let error = $state(null);
  let goals = $state(null); // {state: 'none'|'ok', current, revisions, message}
  let campaigns = $state([]);
  let campaignId = $state('');
  let backlog = $state(null); // {state: 'ok'|'no-goal-set', backlog, message}
  let backlogError = $state(null);
  let assessments = $state(null); // CampaignAssessmentsResponse, for the chosen Campaign
  let assessmentsError = $state(null);
  let campaignsError = $state(null);
  let canWrite = $state(false);
  let openRevision = $state(null);

  // the edit
  let draft = $state(null);
  let editFrom = $state(null);
  let editKey = $state(null);
  let reason = $state('');
  let saving = $state(false);
  let outcome = $state(null); // submitRevision's answer
  let newItem = $state({ id: '', title: '', serves: [] });

  let pollTimer = null;

  async function refreshGoals() {
    if (!projectId) return;
    const forProject = projectId;
    try {
      const got = await loadGoalSet(apiFetch, apiBase, forProject);
      if (forProject !== projectId) return;
      goals = got;
      error = null;
    } catch (err) {
      if (forProject === projectId) error = err.message;
    }
    loading = false;
  }

  async function refreshCampaigns() {
    if (!projectId) return;
    const forProject = projectId;
    try {
      const found = await loadGoalSetCampaigns(apiFetch, apiBase, forProject);
      if (forProject !== projectId) return;
      campaigns = found;
      campaignsError = null;
      if (!campaignId && found.length > 0) campaignId = found[0].campaign_id;
    } catch (err) {
      if (forProject === projectId) campaignsError = err.message;
    }
  }

  async function refreshBacklog() {
    if (!campaignId) {
      backlog = null;
      backlogError = null;
      assessments = null;
      assessmentsError = null;
      return;
    }
    const forCampaign = campaignId;
    try {
      const got = await loadBacklog(apiFetch, apiBase, forCampaign);
      if (forCampaign !== campaignId) return;
      backlog = got;
      backlogError = null;
    } catch (err) {
      if (forCampaign === campaignId) backlogError = err.message;
    }
    try {
      const got = await loadAssessments(apiFetch, apiBase, forCampaign);
      if (forCampaign !== campaignId) return;
      assessments = got;
      assessmentsError = null;
    } catch (err) {
      if (forCampaign === campaignId) assessmentsError = err.message;
    }
  }

  async function refreshAll() {
    if (draft) return; // an open edit is never replaced under the editor
    await refreshGoals();
    await refreshCampaigns();
    await refreshBacklog();
  }

  function selectProject(id, name = null, campaign = '') {
    if (id === projectId && !campaign) return;
    if (id !== projectId) {
      goals = null;
      campaigns = [];
      backlog = null;
      backlogError = null;
      assessments = null;
      assessmentsError = null;
      campaignsError = null;
      error = null;
      draft = null;
      outcome = null;
      openRevision = null;
      loading = true;
    }
    projectId = id;
    projectName = name;
    campaignId = campaign;
    refreshAll();
  }

  function onSelectProject(e) {
    if (e.detail?.project_id) selectProject(e.detail.project_id, e.detail.name ?? null);
  }

  // A Campaign's link to its goal set: the Project it belongs to, with that Campaign chosen.
  // Taken here too, so the record `announce` left for a panel not yet mounted isn't applied again.
  function onSelectCampaign(e) {
    takeAnnounced(SELECT_CAMPAIGN);
    const d = e.detail ?? {};
    if (d.project_id && d.campaign_id) selectProject(d.project_id, null, d.campaign_id);
  }

  onMount(async () => {
    window.addEventListener('squadops:select-project', onSelectProject);
    window.addEventListener(SELECT_CAMPAIGN, onSelectCampaign);
    // The Campaigns view's link opens this perspective after announcing its Campaign, so the
    // event fired before this panel was mounted: take what it left (shared/selection.js).
    const held = takeAnnounced(SELECT_CAMPAIGN);
    if (held) onSelectCampaign({ detail: held });
    pollTimer = setInterval(refreshAll, POLL_MS);
    canWrite = await canWriteGoalSet(apiFetch, apiBase);
  });

  onDestroy(() => {
    window.removeEventListener('squadops:select-project', onSelectProject);
    window.removeEventListener(SELECT_CAMPAIGN, onSelectCampaign);
    if (pollTimer) clearInterval(pollTimer);
  });

  function chooseCampaign(e) {
    campaignId = e.target.value;
    backlog = null;
    assessments = null;
    assessmentsError = null;
    refreshBacklog();
  }

  // --- editing ---

  function startEdit() {
    draft = draftFrom($state.snapshot(goals.current.goal_set));
    editFrom = goals.current.revision;
    editKey = newIdempotencyKey();
    reason = '';
    outcome = null;
    newItem = { id: '', title: '', serves: [] };
  }

  function cancelEdit() {
    draft = null;
    outcome = null;
    refreshAll();
  }

  // After a conflict: the latest revision, edits discarded, so the owner makes them again on it.
  async function reloadLatest() {
    draft = null;
    outcome = null;
    await refreshAll();
  }

  function moveItem(index, delta) {
    draft.doc.backlog = moved(draft.doc.backlog, index, delta);
  }

  function removeItem(index) {
    draft.doc.backlog = draft.doc.backlog.filter((_, i) => i !== index);
  }

  function addItem() {
    const id = newItem.id.trim();
    const title = newItem.title.trim();
    if (!id || !title) return;
    if (draft.doc.backlog.some((b) => b.id === id)) {
      outcome = { state: 'refused', message: `The backlog already holds an item ${id}: an id names one item.` };
      return;
    }
    draft.doc.backlog = [
      ...draft.doc.backlog,
      { id, title, description: '', serves: [...newItem.serves] },
    ];
    newItem = { id: '', title: '', serves: [] };
  }

  function toggleServes(item, resultId) {
    item.serves = item.serves.includes(resultId)
      ? item.serves.filter((s) => s !== resultId)
      : [...item.serves, resultId];
  }

  async function save() {
    if (!reason.trim()) {
      outcome = { state: 'refused', message: 'Say why this revision is written: the reason is required.' };
      return;
    }
    saving = true;
    outcome = null;
    const args = revisionArgs(projectId, {
      expectedRevision: editFrom,
      reason: reason.trim(),
      goalSet: documentFrom($state.snapshot(draft)),
      idempotencyKey: editKey,
    });
    const got = await submitRevision(apiFetch, args, {
      confirm: (answer) =>
        window.confirm(
          `Write revision ${editFrom + 1} of ${projectId}'s goal set?\n\n` +
            `${answer.command_id} is a ${answer.danger_level}-level command.`,
        ),
    }).catch((err) => ({ state: 'refused', message: err.message }));
    saving = false;
    if (got.state === 'declined') return;
    if (got.state === 'written') {
      draft = null;
      outcome = got;
      await refreshAll();
      return;
    }
    outcome = got;
  }

  const fmtDate = (iso) => (iso ? new Date(iso).toLocaleString() : '--');

  function surfaceText(surface) {
    if (!surface) return '';
    return surface.kind === 'none' ? `no surface: ${surface.reason}` : `${surface.kind} ${surface.ref}`;
  }

  let goalSet = $derived(goals?.state === 'ok' ? goals.current.goal_set : null);
  let rows = $derived(goalSet ? backlogRows(goalSet, backlog?.state === 'ok' ? backlog.backlog : null) : []);
  let readsOther = $derived(
    backlog?.state === 'ok' && goals?.state === 'ok' && backlog.backlog.revision !== goals.current.revision,
  );
</script>

<div class="goals">
  <h3 class="title">
    Goals{#if projectId}<span class="for">&nbsp;· {projectName || projectId}</span>{/if}
  </h3>

  {#if !projectId}
    <div class="empty">Select a Project to read its goal set.</div>
  {:else if loading && !goals}
    <div class="empty">Loading the goal set...</div>
  {:else if error}
    <div class="error">{error}</div>
  {:else if goals?.state === 'none'}
    <div class="empty">No goal set is written for {projectId} yet.</div>
  {:else if goals?.state === 'ok'}
    {#if outcome?.state === 'written'}
      <div class="notice">
        Revision {outcome.revision.revision} written{outcome.replayed ? ' (a retry, replayed)' : ''}.
      </div>
    {/if}

    <div class="revision-line">
      <span class="badge">revision {goals.current.revision}</span>
      <span class="muted">by {goals.current.author} · {fmtDate(goals.current.created_at)} · {goals.current.reason}</span>
      {#if canWrite && !draft}
        <button class="btn" onclick={startEdit}>Edit</button>
      {/if}
    </div>

    {#if draft}
      <!-- ── The edit: the next revision ───────────────────────────── -->
      <section class="editor">
        <div class="section-label">Editing from revision {editFrom}</div>

        <label class="field">
          <span>Goal</span>
          <textarea rows="2" bind:value={draft.doc.goal}></textarea>
        </label>

        <div class="field">
          <span>Expected results</span>
          {#each draft.doc.expected_results as result}
            <div class="er-edit">
              <code>{result.id}</code>
              <input type="text" bind:value={result.statement} />
              <span class="muted small">{surfaceText(result.surface)}</span>
            </div>
          {/each}
        </div>

        <label class="field">
          <span>Constraints, one per line</span>
          <textarea rows="2" bind:value={draft.constraintsText}></textarea>
        </label>
        <label class="field">
          <span>Out of scope, one per line</span>
          <textarea rows="2" bind:value={draft.outOfScopeText}></textarea>
        </label>

        <div class="field">
          <span>Backlog, in order</span>
          {#each draft.doc.backlog as item, i (item.id)}
            <div class="item-edit">
              <span class="pos">{i + 1}</span>
              <code>{item.id}</code>
              <input type="text" bind:value={item.title} />
              <span class="serves">
                {#each draft.doc.expected_results as result}
                  <label class="chk">
                    <input
                      type="checkbox"
                      checked={item.serves.includes(result.id)}
                      onchange={() => toggleServes(item, result.id)}
                    />{result.id}
                  </label>
                {/each}
              </span>
              <button class="icon" title="Move up" disabled={i === 0} onclick={() => moveItem(i, -1)}>&#9650;</button>
              <button class="icon" title="Move down" disabled={i === draft.doc.backlog.length - 1} onclick={() => moveItem(i, 1)}>&#9660;</button>
              <button class="icon danger" title="Remove from the backlog" onclick={() => removeItem(i)}>&#10005;</button>
            </div>
          {/each}
          <div class="item-edit add">
            <span class="pos">+</span>
            <input type="text" class="id-input" placeholder="id" bind:value={newItem.id} />
            <input type="text" placeholder="title of a new item" bind:value={newItem.title} />
            <span class="serves">
              {#each draft.doc.expected_results as result}
                <label class="chk">
                  <input
                    type="checkbox"
                    checked={newItem.serves.includes(result.id)}
                    onchange={() => toggleServes(newItem, result.id)}
                  />{result.id}
                </label>
              {/each}
            </span>
            <button class="btn" onclick={addItem}>Add</button>
          </div>
        </div>

        <label class="field">
          <span>Why this revision (required)</span>
          <input type="text" bind:value={reason} placeholder="the reason recorded with the revision" />
        </label>

        {#if outcome?.state === 'conflict'}
          <div class="conflict">
            <strong>Not saved: someone else wrote a revision first.</strong>
            <p>{outcome.message}</p>
            <button class="btn" onclick={reloadLatest}>Discard my edits and load the latest</button>
          </div>
        {:else if outcome?.state === 'refused'}
          <div class="error">
            Not saved{outcome.status ? ` (${outcome.status}${outcome.code ? ` ${outcome.code}` : ''})` : ''}:
            {outcome.message}
          </div>
        {/if}

        <div class="actions">
          <button class="btn primary" disabled={saving} onclick={save}>
            {saving ? 'Writing...' : `Write revision ${editFrom + 1}`}
          </button>
          <button class="btn" disabled={saving} onclick={cancelEdit}>Cancel</button>
        </div>
      </section>
    {:else}
      <!-- ── The goal and its expected results ─────────────────────── -->
      <section>
        <div class="section-label">Goal</div>
        <p class="goal">{goalSet.goal}</p>

        <div class="section-label">Expected results</div>
        <ul class="results">
          {#each goalSet.expected_results as result}
            <li>
              <code>{result.id}</code>
              <span>{result.statement}</span>
              <span class="muted small">{surfaceText(result.surface)}</span>
              {#if standingOf(assessments, result)}
                {@const row = standingOf(assessments, result)}
                {#if row.readAs}
                  <div class="read-as small">
                    This Campaign reads r{row.readAs.revision}, and its standing is of that text:
                    <span>{row.readAs.statement}</span>
                    <span class="muted">{surfaceText(row.readAs.surface)}</span>
                  </div>
                {/if}
                <div class="assessment small">
                  <span class="standing standing-{row.standing}">{row.label}</span>
                  {#each row.entries as e (e.sequence)}
                    <span class="reading">
                      {e.readingText}{e.causeText ? `: ${e.causeText}` : ''}
                      {#if e.issueUrl}<a href={e.issueUrl} target="_blank" rel="noreferrer">#{e.issue}</a>{/if}
                      <span class="muted" title={e.sourceRef ?? ''}>{e.author}, r{e.revision}</span>
                    </span>
                  {/each}
                </div>
              {/if}
            </li>
          {/each}
        </ul>
        {#if assessmentsError}
          <div class="error small">{assessmentsError}</div>
        {/if}

        {#if goalSet.constraints.length > 0}
          <div class="section-label">Constraints</div>
          <ul class="plain">{#each goalSet.constraints as c}<li>{c}</li>{/each}</ul>
        {/if}
        {#if goalSet.out_of_scope.length > 0}
          <div class="section-label">Out of scope</div>
          <ul class="plain">{#each goalSet.out_of_scope as c}<li>{c}</li>{/each}</ul>
        {/if}
      </section>
    {/if}

    <!-- ── The backlog, as a chosen Campaign stands on it ──────────── -->
    <section>
      <div class="section-head">
        <div class="section-label">Backlog</div>
        <label class="campaign-pick">
          <span class="muted small">status in</span>
          <select value={campaignId} onchange={chooseCampaign}>
            <option value="">no Campaign</option>
            {#each campaigns as c}
              <option value={c.campaign_id}>{c.campaign_id} ({c.state})</option>
            {/each}
            {#if campaignId && !campaigns.some((c) => c.campaign_id === campaignId)}
              <option value={campaignId}>{campaignId}</option>
            {/if}
          </select>
        </label>
      </div>

      {#if campaignsError}
        <div class="error">{campaignsError}</div>
      {/if}
      {#if backlogError}
        <div class="error">{backlogError}</div>
      {:else if backlog?.state === 'no-goal-set'}
        <div class="empty small">{backlog.message}</div>
      {:else if campaigns.length === 0 && !campaignId}
        <div class="muted small">No Campaign of this Project works through its goal set yet.</div>
      {/if}
      {#if backlog?.state === 'ok'}
        <div class="muted small">
          {backlog.backlog.campaign_id} reads revision {backlog.backlog.revision} ({backlog.backlog.reads}){readsOther
            ? `, not the latest (${goals.current.revision})`
            : ''}. Next: {backlog.backlog.next_item ?? 'none'}{backlog.backlog.done ? ' · backlog done' : ''}.
        </div>
      {/if}

      {#if rows.length === 0}
        <div class="empty small">The backlog is empty.</div>
      {:else}
        <table>
          <thead>
            <tr><th>#</th><th>Item</th><th>Serves</th><th>Status</th><th>Increment</th></tr>
          </thead>
          <tbody>
            {#each rows as row (row.item_id)}
              <tr class:gone={row.position === null}>
                <td class="pos">{row.position ?? '--'}</td>
                <td><code>{row.item_id}</code> {row.title}</td>
                <td class="small">{row.serves.join(', ')}</td>
                <td>
                  {#if row.derived}
                    <span class="status status-{row.derived.status}">{row.derived.label}</span>
                  {:else}
                    <span class="muted small">{backlog?.state === 'ok' ? 'not in this Campaign\'s revision' : '--'}</span>
                  {/if}
                </td>
                <td class="small mono">{incrementOf(row.derived) ?? ''}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </section>

    <!-- ── Candidates waiting (read-only) ───────────────────────────── -->
    <section>
      <div class="section-label">Candidates waiting ({goalSet.candidates.length})</div>
      {#if goalSet.candidates.length === 0}
        <div class="muted small">None.</div>
      {:else}
        <ul class="candidates">
          {#each goalSet.candidates as c}
            <li>
              <code>{c.id}</code> {c.title}
              <span class="muted small">found by {c.found_by} · {fmtDate(c.found_at)}</span>
              {#if c.description}<div class="muted small">{c.description}</div>{/if}
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    <!-- ── The revision history ─────────────────────────────────────── -->
    <section>
      <div class="section-label">History</div>
      <ul class="history">
        {#each goals.revisions as r (r.revision)}
          <li>
            <button class="link" onclick={() => (openRevision = openRevision === r.revision ? null : r.revision)}>
              r{r.revision}
            </button>
            <span class="muted small">{fmtDate(r.created_at)} · {r.author}</span>
            <span>{r.reason}</span>
            {#if r.source_ref}<span class="muted small">from {r.source_ref}</span>{/if}
            {#if openRevision === r.revision}
              <div class="revision-body">
                <div><span class="muted small">goal</span> {r.goal_set.goal}</div>
                <div>
                  <span class="muted small">backlog</span>
                  {r.goal_set.backlog.map((b) => b.id).join(' → ') || 'empty'}
                </div>
                <div><span class="muted small">candidates</span> {r.goal_set.candidates.length}</div>
              </div>
            {/if}
          </li>
        {/each}
      </ul>
    </section>
  {/if}
</div>

<style>
  .goals {
    padding: var(--continuum-space-lg, 24px);
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }
  .title {
    font-size: var(--continuum-font-size-md, 1rem);
    font-weight: 600;
    margin: 0 0 var(--continuum-space-md, 16px) 0;
  }
  .for {
    font-weight: 400;
    color: var(--continuum-text-muted, #94a3b8);
  }
  section {
    margin-top: var(--continuum-space-md, 16px);
  }
  .section-label {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin: var(--continuum-space-sm, 8px) 0 4px;
  }
  .section-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--continuum-space-sm, 8px);
  }
  .goal {
    margin: 0 0 var(--continuum-space-sm, 8px);
    font-size: var(--continuum-font-size-md, 1rem);
  }
  ul {
    margin: 0;
    padding-left: 0;
    list-style: none;
  }
  ul.plain {
    padding-left: 18px;
    list-style: disc;
  }
  .results li,
  .candidates li,
  .history li {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: baseline;
    padding: 3px 0;
    border-bottom: 1px solid var(--continuum-border, #334155);
  }
  code,
  .mono {
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }
  code {
    color: var(--continuum-accent-primary, #6366f1);
  }
  .muted {
    color: var(--continuum-text-muted, #94a3b8);
  }
  .small {
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }
  .revision-line {
    display: flex;
    align-items: center;
    gap: var(--continuum-space-sm, 8px);
    flex-wrap: wrap;
  }
  .badge {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 1px 8px;
    border-radius: var(--continuum-radius-sm, 4px);
    background: rgba(99, 102, 241, 0.15);
    color: var(--continuum-accent-primary, #6366f1);
    font-weight: 600;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 4px;
  }
  th,
  td {
    text-align: left;
    padding: 4px var(--continuum-space-sm, 8px);
    border-bottom: 1px solid var(--continuum-border, #334155);
    vertical-align: top;
  }
  th {
    color: var(--continuum-text-muted, #94a3b8);
    font-weight: 500;
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }
  tr.gone td {
    opacity: 0.6;
  }
  .pos {
    width: 2em;
    color: var(--continuum-text-muted, #94a3b8);
  }
  .status {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 1px 6px;
    border-radius: var(--continuum-radius-sm, 4px);
    background: var(--continuum-bg-tertiary, #273549);
    white-space: nowrap;
  }
  .status-accepted {
    background: rgba(34, 197, 94, 0.2);
    color: var(--continuum-accent-success, #22c55e);
  }
  .status-in_increment,
  .status-proposed {
    background: rgba(99, 102, 241, 0.2);
    color: var(--continuum-accent-primary, #6366f1);
  }
  .status-abandoned,
  .status-removed {
    color: var(--continuum-text-muted, #94a3b8);
  }
  .assessment {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 12px;
    margin-top: 2px;
  }
  .read-as {
    margin-top: 2px;
    color: var(--continuum-accent-warning, #f59e0b);
  }
  .read-as span {
    color: var(--continuum-text-primary, #e2e8f0);
  }
  .read-as .muted {
    color: var(--continuum-text-muted, #94a3b8);
  }
  .standing-stale,
  .standing-unassessed {
    color: var(--continuum-text-muted, #94a3b8);
  }
  .standing-conflicting {
    color: var(--continuum-accent-warning, #f59e0b);
  }
  select,
  input[type='text'],
  textarea {
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    color: var(--continuum-text-primary, #e2e8f0);
    font: inherit;
    padding: 4px 6px;
    box-sizing: border-box;
  }
  textarea,
  .field input[type='text'] {
    width: 100%;
  }
  .campaign-pick {
    display: flex;
    gap: 6px;
    align-items: center;
  }
  .editor {
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    padding: var(--continuum-space-md, 16px);
    background: var(--continuum-bg-secondary, #1e293b);
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: var(--continuum-space-sm, 8px);
  }
  .field > span {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    color: var(--continuum-text-muted, #94a3b8);
  }
  .er-edit,
  .item-edit {
    display: flex;
    gap: 6px;
    align-items: center;
    flex-wrap: wrap;
  }
  .item-edit input[type='text'] {
    flex: 1 1 200px;
    width: auto;
  }
  .item-edit .id-input {
    flex: 0 0 120px;
  }
  .er-edit input[type='text'] {
    flex: 1 1 260px;
    width: auto;
  }
  .serves {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .chk {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    display: flex;
    gap: 2px;
    align-items: center;
  }
  .btn,
  .icon,
  .link {
    font: inherit;
    cursor: pointer;
    color: var(--continuum-text-primary, #e2e8f0);
  }
  .btn {
    padding: 3px 10px;
    border-radius: var(--continuum-radius-sm, 4px);
    border: 1px solid var(--continuum-border, #334155);
    background: var(--continuum-bg-tertiary, #273549);
  }
  .btn.primary {
    background: var(--continuum-accent-primary, #6366f1);
    border-color: var(--continuum-accent-primary, #6366f1);
    color: #fff;
  }
  .btn:disabled,
  .icon:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .icon {
    background: none;
    border: none;
    padding: 0 4px;
    font-size: 0.7rem;
  }
  .icon.danger {
    color: var(--continuum-accent-danger, #ef4444);
  }
  .link {
    background: none;
    border: none;
    padding: 0;
    color: var(--continuum-accent-primary, #6366f1);
    font-family: var(--continuum-font-mono, monospace);
  }
  .revision-body {
    flex-basis: 100%;
    padding: 4px 0 4px 16px;
  }
  .actions {
    display: flex;
    gap: var(--continuum-space-sm, 8px);
    margin-top: var(--continuum-space-sm, 8px);
  }
  .notice {
    padding: 6px 10px;
    margin-bottom: var(--continuum-space-sm, 8px);
    border-radius: var(--continuum-radius-sm, 4px);
    background: rgba(34, 197, 94, 0.15);
    color: var(--continuum-accent-success, #22c55e);
  }
  .conflict {
    padding: 8px 12px;
    margin: var(--continuum-space-sm, 8px) 0;
    border: 1px solid var(--continuum-accent-warning, #f59e0b);
    border-radius: var(--continuum-radius-sm, 4px);
  }
  .conflict p {
    margin: 4px 0 8px;
  }
  .empty {
    padding: var(--continuum-space-md, 16px) 0;
    color: var(--continuum-text-muted, #94a3b8);
  }
  .error {
    color: var(--continuum-accent-danger, #ef4444);
    padding: 4px 0;
  }
</style>
