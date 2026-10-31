<svelte:options customElement="squadops-memory-perspective" />

<script>
  // SIP-0110 Appendix A §3.11 (#2182): a project's memory records, and one page per record. What used a
  // record and what it did are kept apart: "used" and "improved the outcome" never share a column.
  import { onMount } from 'svelte';

  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  let projects = $state([]);
  let projectId = $state(''); // '' = your own private records only (an unbound query, T4)
  let kind = $state('');
  let scope = $state('');
  let status = $state('active');
  let records = $state([]);
  let error = $state(null);

  let selected = $state(null); // the record, every revision and status change
  let uses = $state(null);
  let turn = $state(null); // a chat source turn, opened by its owner
  let detailError = $state(null);

  async function errorOf(resp) {
    const body = await resp.json().catch(() => ({}));
    return body?.detail?.error?.message || `${resp.status}`;
  }

  async function loadProjects() {
    const resp = await apiFetch(`${apiBase}/api/v1/projects`);
    if (resp.ok) projects = await resp.json();
  }

  async function loadRecords() {
    error = null;
    const params = new URLSearchParams({ status });
    if (projectId) params.set('project_id', projectId);
    if (kind) params.set('kind', kind);
    if (scope) params.set('scope', scope);
    const resp = await apiFetch(`${apiBase}/api/v1/memory-records?${params}`);
    if (!resp.ok) {
      error = `Could not read the records (${await errorOf(resp)})`;
      records = [];
      return;
    }
    records = await resp.json();
  }

  async function open(recordId) {
    detailError = null;
    turn = null;
    uses = null;
    const [recordResp, usesResp] = await Promise.all([
      apiFetch(`${apiBase}/api/v1/memory-records/${recordId}`),
      apiFetch(`${apiBase}/api/v1/memory-records/${recordId}/uses`),
    ]);
    if (!recordResp.ok) {
      detailError = `Could not read the record (${await errorOf(recordResp)})`;
      return;
    }
    selected = await recordResp.json();
    if (usesResp.ok) uses = await usesResp.json();
    else detailError = `Could not read what used it (${await errorOf(usesResp)})`;
  }

  // §3.4: the link opens the one turn, and only the session's owner sees it (others get a summary).
  async function openTurn(revision) {
    const resp = await apiFetch(
      `${apiBase}/api/v1/memory-records/${selected.record_id}/revisions/${revision.number}/source`
    );
    if (!resp.ok) {
      detailError = `Could not open the chat turn (${await errorOf(resp)})`;
      return;
    }
    turn = await resp.json();
  }

  function excerpt(text) {
    return text.length > 90 ? `${text.slice(0, 90)}…` : text;
  }

  function when(iso) {
    return iso ? new Date(iso).toLocaleString() : '';
  }

  $effect(() => {
    // Re-read whenever a filter changes.
    projectId; kind; scope; status;
    loadRecords();
  });

  onMount(loadProjects);
</script>

<div class="memory">
  <div class="filters">
    <select bind:value={projectId} title="An unbound view lists only your own private records">
      <option value="">Your private records</option>
      {#each projects as p}<option value={p.project_id}>{p.project_id}</option>{/each}
    </select>
    <select bind:value={kind}>
      <option value="">Every kind</option>
      <option value="note">Notes</option>
      <option value="preference">Preferences</option>
      <option value="instruction">Instructions</option>
    </select>
    <select bind:value={scope}>
      <option value="">Every scope</option>
      <option value="user">Yours</option>
      <option value="project">Project</option>
      <option value="task">Task</option>
    </select>
    <select bind:value={status}>
      <option value="active">Active</option>
      <option value="withdrawn">Withdrawn</option>
      <option value="all">All</option>
    </select>
  </div>

  {#if error}<div class="error">{error}</div>{/if}

  <div class="panes">
    <table class="list">
      <thead><tr><th>kind</th><th>scope</th><th>status</th><th>rev</th><th>text</th></tr></thead>
      <tbody>
        {#each records as r}
          <tr class:active={selected?.record_id === r.record_id} onclick={() => open(r.record_id)}>
            <td>{r.kind}</td><td>{r.scope}</td><td>{r.status}</td><td>{r.current.number}</td>
            <td>{excerpt(r.current.body)}</td>
          </tr>
        {:else}
          <tr><td colspan="5" class="muted">No records.</td></tr>
        {/each}
      </tbody>
    </table>

    {#if selected}
      <div class="record">
        {#if detailError}<div class="error">{detailError}</div>{/if}
        <h3>{selected.record_id}</h3>
        <dl class="header">
          <dt>kind</dt><dd>{selected.kind}</dd>
          <dt>scope</dt><dd>{selected.scope}</dd>
          <dt>project</dt><dd>{selected.project_id || '—'}</dd>
          <dt>status</dt><dd>{selected.status}</dd>
          <dt>current revision</dt><dd>{selected.current.number}</dd>
        </dl>

        <h4>Source</h4>
        {#each [selected.current] as rev}
          <p>
            {rev.source.kind}{#if rev.source.summary}: {rev.source.summary}{/if}
            {#if rev.source.session_deleted}<span class="muted"> (its session was deleted)</span>{/if}
            — by {rev.author}{#if rev.confirmed_by}, confirmed by {rev.confirmed_by}{/if}
          </p>
          {#if rev.source.kind === 'chat_message' && rev.source.ids && !rev.source.session_deleted}
            <button class="link" onclick={() => openTurn(rev)}>Open the chat turn</button>
          {/if}
        {/each}
        {#if turn}<blockquote>{turn.role}, {when(turn.created_at)}: {turn.content}</blockquote>{/if}

        <h4>Revisions</h4>
        <ol>
          {#each selected.revisions as rev}
            <li>
              <div>{rev.body}</div>
              <div class="muted">
                {rev.author}, {when(rev.created_at)}{#if rev.confirmed_by}; confirmed by {rev.confirmed_by}{/if}{#if rev.supersedes}; supersedes {rev.supersedes}{/if}
              </div>
            </li>
          {/each}
        </ol>
        {#each selected.status_changes as c}
          <p class="muted">{c.status} by {c.by}, {when(c.at)}: {c.why}</p>
        {/each}

        <h4>References</h4>
        {#each selected.current.references as ref}
          <p>{ref.ref}{ref.required ? ' (required)' : ' (optional)'}</p>
        {:else}<p class="muted">None.</p>{/each}

        <h4>Used by</h4>
        {#if uses}
          <table>
            <thead><tr><th>cycle</th><th>run</th><th>task</th><th>attempt</th><th>section</th><th>revision</th><th>disposition</th></tr></thead>
            <tbody>
              {#each uses.tasks as t}
                <tr>
                  <td>{t.cycle_id}</td><td>{t.run_id}</td><td>{t.task_id}</td><td>{t.attempt}</td>
                  <td>{t.section}</td><td>{t.revision}</td>
                  <td>{t.disposition}{#if t.held}: held, {t.held}{/if}</td>
                </tr>
              {:else}<tr><td colspan="7" class="muted">No dispatch was handed it.</td></tr>{/each}
            </tbody>
          </table>
          {#each uses.chats as c}
            <p>Your chat turn {c.message_id} ({when(c.assembled_at)}), revision {c.revision}</p>
          {/each}
          {#if uses.others_chat_turns}<p class="muted">Other people's chat turns: {uses.others_chat_turns}</p>{/if}

          <h4>Builds those dispatches fed</h4>
          <table>
            <thead><tr><th>run</th><th>verdict</th><th>failed rounds</th><th>rounds to green</th><th>increment</th><th>dispatches</th></tr></thead>
            <tbody>
              {#each uses.builds as b}
                <tr>
                  <td>{b.run_id}</td><td>{b.verdict ?? 'evidence missing'}</td><td>{b.failed_rounds ?? '—'}</td>
                  <td>{b.rounds_to_green ?? 'never'}</td>
                  <td>{b.accepted === null || b.accepted === undefined ? '—' : b.accepted ? 'promoted' : 'not promoted'}</td>
                  <td>{b.exposures.length}</td>
                </tr>
              {:else}<tr><td colspan="6" class="muted">No build to report.</td></tr>{/each}
            </tbody>
          </table>
          {#each Object.entries(uses.unbuilt) as [state, ids]}
            <p class="muted">{state.replaceAll('_', ' ')}: {ids.length} (none of them a build failure)</p>
          {/each}

          <h4>Effect</h4>
          <p class="effect">{uses.effect}</p>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .memory { display: flex; flex-direction: column; gap: 8px; padding: 12px 16px; height: 100%; color: var(--continuum-text-primary, #e0e0e8); }
  .filters { display: flex; gap: 8px; flex-wrap: wrap; }
  select { background: var(--continuum-bg-secondary, #252540); color: inherit; border: 1px solid var(--continuum-border, #2d2d44); border-radius: 4px; padding: 4px 6px; }
  /* #2692: the panes don't stretch their children to the tallest. A stretched table shares the
     record's height out among its rows, so a long record left the list showing one row. Each pane
     scrolls on its own instead. */
  .panes { display: flex; gap: 16px; min-height: 0; flex: 1; align-items: flex-start; overflow: hidden; }
  table { border-collapse: collapse; font-size: var(--continuum-font-size-xs, 12px); width: 100%; }
  th, td { text-align: left; padding: 4px 6px; border-bottom: 1px solid var(--continuum-border, #2d2d44); vertical-align: top; }
  .list { flex: 1; cursor: pointer; display: block; align-self: stretch; max-height: 100%; overflow-y: auto; }
  .list tr.active { background: var(--continuum-bg-secondary, #252540); }
  .record { flex: 1.4; align-self: stretch; overflow-y: auto; font-size: var(--continuum-font-size-sm, 13px); }
  .header { display: grid; grid-template-columns: max-content 1fr; gap: 2px 12px; }
  dt { color: var(--continuum-text-secondary, #a0a0b8); }
  .muted { color: var(--continuum-text-secondary, #a0a0b8); }
  .error { color: #f87171; }
  .effect { border-left: 3px solid var(--continuum-accent-primary, #6366f1); padding-left: 8px; }
  .link { background: none; border: none; color: var(--continuum-accent-primary, #6366f1); cursor: pointer; padding: 0; }
  blockquote { margin: 4px 0; padding-left: 8px; border-left: 2px solid var(--continuum-border, #2d2d44); }
</style>
