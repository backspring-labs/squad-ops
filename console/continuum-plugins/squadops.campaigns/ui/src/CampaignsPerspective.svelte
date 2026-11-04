<svelte:options customElement="squadops-campaigns-perspective" />

<!--
  The Campaigns perspective (the 2.6 plan's Track G, D13; #2834): every Project's Campaigns, and one
  Campaign's state, current increment, ledger, digest, open escalations, proposals waiting for a
  ruling and recent control-log rows. Read-only in 2.6: no launch, rule, pause, resume or abort
  here; those stay with the crew's broker and the CLI (SIP-0069 §14). What it reads is
  `campaigns.js`; this file renders it.

  How it fits the pinned shell (docs/architecture/console-fit-check-2-6.md, view 2): one
  master–detail element in its own perspective, as the Memory plugin's is. It polls, as every live
  view does (30 s, as the goals panel), only while mounted and while the page is visible. A
  Campaign naming a goal set links to the goals panel in the Projects perspective
  (`squadops:select-campaign`, kept until that panel mounts: shared/selection.js).
-->

<script module>
  // Kept across mounts: a closed Campaign's increment is read once per page, not once per visit.
  const incrementCache = new Map();
</script>

<script>
  import { onDestroy, onMount } from 'svelte';
  import {
    acceptedCount,
    currentIncrement,
    goalsSelection,
    incrementShort,
    incrementText,
    isClosed,
    ledgerRows,
    loadCampaignView,
    loadCampaigns,
    loadIncrements,
    logOutcome,
    openEscalations,
    openGoals,
    recentLog,
    waitingProposals,
  } from './campaigns.js';

  const POLL_MS = 30000;
  const LOG_ROWS = 15;
  const config = window.__SQUADOPS_CONFIG__ || {};
  const apiBase = config.apiBaseUrl || '';

  async function apiFetch(url, opts) {
    if (window.squadops?.apiFetch) return window.squadops.apiFetch(url, opts);
    return fetch(url, opts);
  }

  // the list
  let campaigns = $state([]);
  let refused = $state([]);
  let increments = $state({});
  let listError = $state(null);
  let listLoading = $state(true);
  let projectFilter = $state('');

  // one Campaign
  let selectedId = $state(null);
  let view = $state(null);
  let viewError = $state(null);
  let viewLoading = $state(false);
  let goalsNotice = $state(null);

  let pollTimer = null;

  async function refreshList() {
    try {
      const got = await loadCampaigns(apiFetch, apiBase);
      campaigns = got.campaigns;
      refused = got.refused;
      listError = null;
      increments = await loadIncrements(apiFetch, apiBase, got.campaigns, incrementCache);
    } catch (err) {
      listError = err.message;
    }
    listLoading = false;
  }

  async function refreshView() {
    if (!selectedId) return;
    const forId = selectedId;
    try {
      const got = await loadCampaignView(apiFetch, apiBase, forId);
      if (forId !== selectedId) return;
      view = got;
      viewError = null;
    } catch (err) {
      if (forId === selectedId) viewError = err.message;
    }
    if (forId === selectedId) viewLoading = false;
  }

  function poll() {
    if (document.hidden) return;
    refreshList();
    refreshView();
  }

  function select(id) {
    if (id === selectedId) return;
    selectedId = id;
    view = null;
    viewError = null;
    goalsNotice = null;
    viewLoading = true;
    refreshView();
  }

  function toGoals() {
    const opened = openGoals(view.campaign);
    goalsNotice = opened
      ? null
      : 'Open Projects in the left nav: its goals panel opens on this Campaign.';
  }

  onMount(() => {
    refreshList();
    pollTimer = setInterval(poll, POLL_MS);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  const fmtDate = (iso) => (iso ? new Date(iso).toLocaleString() : '--');
  const fmtShort = (iso) =>
    iso
      ? new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
      : '--';

  let projects = $derived([...new Set(campaigns.map((c) => c.project_id))].sort());
  let shown = $derived(projectFilter ? campaigns.filter((c) => c.project_id === projectFilter) : campaigns);

  let campaign = $derived(view?.state === 'ok' ? view.campaign : null);
  let ledger = $derived(view?.ledger?.value ?? null);
  let log = $derived(view?.log?.value ?? null);
  let increment = $derived(log ? currentIncrement(log) : null);
  let rows = $derived(ledgerRows(ledger));
  let waiting = $derived(campaign && ledger ? waitingProposals(ledger, campaign) : []);
  let openEsc = $derived(openEscalations(view?.escalations?.value));
  let closedEscCount = $derived((view?.escalations?.value?.length ?? 0) - openEsc.length);
  let recent = $derived(recentLog(log, LOG_ROWS));
  let goals = $derived(goalsSelection(campaign));
</script>

<div class="campaigns">
  <div class="head">
    <h3 class="title">Campaigns</h3>
    <span class="muted small">Read-only: the crew and the CLI run the controls.</span>
    <label class="filter">
      <span class="muted small">Project</span>
      <select bind:value={projectFilter}>
        <option value="">all</option>
        {#each projects as p}<option value={p}>{p}</option>{/each}
      </select>
    </label>
  </div>

  <div class="panes">
    <!-- ── The list ─────────────────────────────────────────────── -->
    <div class="list">
      {#if listError}
        <div class="error">{listError}</div>
      {/if}
      {#each refused as r}
        <div class="error small">{r.project_id}'s Campaigns: the API answered {r.status}</div>
      {/each}
      {#if listLoading && campaigns.length === 0}
        <div class="empty">Loading Campaigns...</div>
      {:else if shown.length === 0}
        <div class="empty">No Campaigns{projectFilter ? ` in ${projectFilter}` : ''}.</div>
      {:else}
        <table>
          <thead>
            <tr><th>Campaign</th><th>Project</th><th>State</th><th>Outcome</th><th>Started</th><th>Increment</th></tr>
          </thead>
          <tbody>
            {#each shown as c (c.campaign_id)}
              <tr class:active={c.campaign_id === selectedId} onclick={() => select(c.campaign_id)}>
                <td class="mono">{c.campaign_id}</td>
                <td>{c.project_id}</td>
                <td><span class="state state-{c.state}">{c.state}</span></td>
                <td>{#if c.outcome}<span class="outcome outcome-{c.outcome}">{c.outcome}</span>{/if}</td>
                <td class="small" title={fmtDate(c.created_at)}>{fmtShort(c.created_at)}</td>
                <td class="small mono" title={incrementText(increments[c.campaign_id])}>{incrementShort(increments[c.campaign_id])}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </div>

    <!-- ── One Campaign ─────────────────────────────────────────── -->
    <div class="detail">
      {#if !selectedId}
        <div class="empty">Select a Campaign to read its state, ledger and digest.</div>
      {:else if viewLoading && !view}
        <div class="empty">Loading {selectedId}...</div>
      {:else if viewError}
        <div class="error">{viewError}</div>
      {:else if view?.state === 'not-found'}
        <div class="empty">{view.message}</div>
      {:else if campaign}
        <div class="detail-head">
          <span class="mono strong">{campaign.campaign_id}</span>
          <span class="state state-{campaign.state}">{campaign.state}</span>
          {#if campaign.outcome}<span class="outcome outcome-{campaign.outcome}">{campaign.outcome}</span>{/if}
          {#if goals}
            <button class="btn" onclick={toGoals}>Open its goal set</button>
          {/if}
        </div>
        {#if goalsNotice}<div class="muted small">{goalsNotice}</div>{/if}

        <dl class="facts">
          <dt>Project</dt><dd>{campaign.project_id}</dd>
          <dt>Objective</dt><dd>{campaign.objective.statement}</dd>
          <dt>Works from</dt>
          <dd>
            {#if campaign.objective.goals}
              goal set {campaign.objective.goals.goal_set}, revision {campaign.objective.goals.revision}
            {:else if campaign.objective.requirements}
              {campaign.objective.requirements}
            {:else}
              <span class="muted">its Project's PRD</span>
            {/if}
          </dd>
          <dt>Accepted</dt>
          <dd>
            {ledger ? acceptedCount(ledger) : '--'} of {campaign.objective.target_accepted_increments ?? '--'}
            {#if campaign.accepted?.commit}<span class="muted small">· head {campaign.accepted.commit.slice(0, 12)}</span>{/if}
          </dd>
          <dt>Increment</dt>
          <dd class="mono">{increment ? incrementText(increment) : (view.log.error ?? '--')}</dd>
          <dt>Cycle</dt>
          <dd class="mono">{increment?.cycle_id ?? '--'}{increment?.cycle_kind ? ` (${increment.cycle_kind})` : ''}</dd>
          <dt>Started</dt><dd>{fmtDate(campaign.created_at)} <span class="muted small">by {campaign.created_by}</span></dd>
          <dt>Last moved</dt><dd>{fmtDate(campaign.updated_at)}</dd>
        </dl>

        <!-- ── Waiting on someone ─────────────────────────────────── -->
        <section>
          <div class="section-label">Open escalations ({openEsc.length})</div>
          {#if view.escalations.error}
            <div class="error">{view.escalations.error}</div>
          {:else if openEsc.length === 0}
            <div class="muted small">None open{closedEscCount > 0 ? ` (${closedEscCount} closed)` : ''}.</div>
          {:else}
            {#each openEsc as e (e.escalation_id)}
              <div class="card">
                <div>
                  <span class="mono">{e.escalation_id}</span>
                  <span class="muted small">{e.kind}{e.hold_class ? ` (${e.hold_class})` : ''} · run {e.run_id} · {e.gate_name} · opened {fmtDate(e.opened_at)}</span>
                </div>
                {#if e.failed.length > 0}
                  <div class="small"><span class="muted">could not establish:</span> {e.failed.map((f) => f.condition).join(', ')}</div>
                {/if}
                {#each e.questions as q}<div class="small">? {q}</div>{/each}
              </div>
            {/each}
          {/if}

          <div class="section-label">Waiting for a ruling ({waiting.length})</div>
          {#if view.ledger.error}
            <div class="error">{view.ledger.error}</div>
          {:else if waiting.length === 0}
            <div class="muted small">No proposal is waiting.</div>
          {:else}
            <ul class="plain">
              {#each waiting as w}
                <li><span class="mono">{w.proposal_id} v{w.version}</span> <span class="muted small">submitted {fmtDate(w.submitted_at)} · cycle {w.cycle_id}</span></li>
              {/each}
            </ul>
          {/if}
        </section>

        <!-- ── The ledger ─────────────────────────────────────────── -->
        <section>
          <div class="section-label">Ledger</div>
          {#if view.ledger.error}
            <div class="error">{view.ledger.error}</div>
          {:else if rows.length === 0}
            <div class="muted small">No proposal submitted yet.</div>
          {:else}
            <table>
              <thead>
                <tr><th>Proposal</th><th>Ruling</th><th>Verdict</th><th>Decided (row)</th><th>Cycles</th><th>Classified</th></tr>
              </thead>
              <tbody>
                {#each rows as r (r.key)}
                  <tr>
                    <td class="mono">{r.proposal}</td>
                    <td title={r.ruling_reason ?? ''}>
                      {r.ruling ?? 'waiting'}{#if r.ruled_by}<div class="muted small">{r.ruled_by}</div>{/if}
                    </td>
                    <td>{#if r.verdict}<span class="verdict verdict-{r.verdict}">{r.verdict}</span>{:else}--{/if}</td>
                    <td class="small">{r.ending ?? '--'}{r.decided_row != null ? ` (${r.decided_row})` : ''}</td>
                    <td class="small mono">{#each r.cycles as c}<div>{c}</div>{:else}--{/each}</td>
                    <td class="small">{r.classification ?? '--'}</td>
                  </tr>
                  {#if r.unbuilt}
                    <tr class="note"><td></td><td colspan="5" class="small muted">{r.unbuilt}</td></tr>
                  {/if}
                {/each}
              </tbody>
            </table>
          {/if}
        </section>

        {#if campaign.objective.goals}
          <!-- SIP-0115 slice 5 (#2888) has no route yet: this is where its reads will go. -->
          <section>
            <div class="section-label">The crew's assessment of each expected result</div>
            <div class="placeholder small">
              Not available yet: the crew's assessments are SIP-0115 slice 5 (#2888), which has no
              API route on this deploy.
            </div>
          </section>
        {/if}

        <!-- ── The digest ─────────────────────────────────────────── -->
        <section>
          <div class="section-label">Digest</div>
          {#if view.digest.error}
            <div class="error">{view.digest.error}</div>
          {:else if view.digest.none}
            <div class="muted small">{view.digest.none}.</div>
          {:else}
            <div class="muted small">package {view.digest.value.identity?.slice(0, 16) ?? '--'} · {view.digest.value.digest_artifact_id}</div>
            <pre class="digest">{view.digest.value.digest}</pre>
          {/if}
        </section>

        <!-- ── The control log ────────────────────────────────────── -->
        <section>
          <div class="section-label">Control log (latest {Math.min(LOG_ROWS, log?.length ?? 0)} of {log?.length ?? 0})</div>
          {#if view.log.error}
            <div class="error">{view.log.error}</div>
          {:else}
            <table>
              <thead>
                <tr><th>#</th><th>At</th><th>Operation</th><th>Outcome</th><th>State</th><th>Actor</th><th>Reason</th></tr>
              </thead>
              <tbody>
                {#each recent as e (e.entry_id)}
                  <tr class:refused={e.outcome !== 'applied'}>
                    <td>{e.seq}</td>
                    <td class="small">{fmtDate(e.committed_at)}</td>
                    <td class="mono small">{e.operation}</td>
                    <td class="small">{logOutcome(e)}</td>
                    <td class="small">{e.prior_state ?? '--'} → {e.next_state}</td>
                    <td class="small">{e.actor_role}</td>
                    <td class="small reason">{e.reason}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}
        </section>
      {/if}
    </div>
  </div>
</div>

<style>
  .campaigns {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px 16px;
    height: 100%;
    box-sizing: border-box;
    font-family: var(--continuum-font-sans, system-ui, sans-serif);
    color: var(--continuum-text-primary, #e2e8f0);
    font-size: var(--continuum-font-size-sm, 0.875rem);
  }
  .head {
    display: flex;
    align-items: baseline;
    gap: 12px;
    flex-wrap: wrap;
  }
  .title {
    font-size: var(--continuum-font-size-md, 1rem);
    font-weight: 600;
    margin: 0;
  }
  .filter {
    margin-left: auto;
    display: flex;
    gap: 6px;
    align-items: center;
  }
  /* As the Memory perspective (#2692): the panes don't stretch to the tallest; each scrolls. */
  .panes {
    display: flex;
    gap: 16px;
    min-height: 0;
    flex: 1;
    align-items: flex-start;
    overflow: hidden;
    /* The shell gives a panel no fixed height, so each pane is bounded by the viewport. */
    max-height: calc(100vh - 110px);
  }
  .list {
    flex: 0 1 auto;
    align-self: stretch;
    max-height: 100%;
    overflow-y: auto;
  }
  .list tbody tr {
    cursor: pointer;
  }
  .list td {
    white-space: nowrap;
  }
  .list tr.active {
    background: var(--continuum-bg-secondary, #1e293b);
  }
  .detail {
    flex: 1 1 0;
    min-width: 0;
    align-self: stretch;
    max-height: 100%;
    overflow-y: auto;
  }
  .detail-head {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
  }
  .strong {
    font-weight: 600;
  }
  .facts {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 2px 12px;
    margin: 8px 0;
  }
  dt {
    color: var(--continuum-text-muted, #94a3b8);
  }
  dd {
    margin: 0;
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
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }
  th,
  td {
    text-align: left;
    padding: 4px 6px;
    border-bottom: 1px solid var(--continuum-border, #334155);
    vertical-align: top;
  }
  th {
    color: var(--continuum-text-muted, #94a3b8);
    font-weight: 500;
  }
  tr.note td {
    border-bottom: none;
    padding-top: 0;
  }
  tr.refused td {
    color: var(--continuum-accent-warning, #f59e0b);
  }
  .reason {
    max-width: 28em;
  }
  .mono {
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }
  .muted {
    color: var(--continuum-text-muted, #94a3b8);
  }
  .small {
    font-size: var(--continuum-font-size-xs, 0.75rem);
  }
  ul.plain {
    margin: 0;
    padding-left: 18px;
  }
  .state,
  .outcome,
  .verdict {
    font-size: var(--continuum-font-size-xs, 0.75rem);
    padding: 1px 6px;
    border-radius: var(--continuum-radius-sm, 4px);
    background: var(--continuum-bg-tertiary, #273549);
    white-space: nowrap;
  }
  .state-building,
  .state-evaluating,
  .state-repairing,
  .state-retrying,
  .state-promoting,
  .state-calibrating,
  .state-at_proposal {
    background: rgba(99, 102, 241, 0.2);
    color: var(--continuum-accent-primary, #6366f1);
  }
  .state-awaiting_ruling,
  .state-escalated,
  .state-paused,
  .state-launch_blocked {
    background: rgba(245, 158, 11, 0.2);
    color: var(--continuum-accent-warning, #f59e0b);
  }
  .outcome-success,
  .verdict-accepted {
    background: rgba(34, 197, 94, 0.2);
    color: var(--continuum-accent-success, #22c55e);
  }
  .outcome-failure,
  .outcome-exhausted,
  .verdict-rejected {
    background: rgba(239, 68, 68, 0.2);
    color: var(--continuum-accent-danger, #ef4444);
  }
  .card {
    border: 1px solid var(--continuum-accent-warning, #f59e0b);
    border-radius: var(--continuum-radius-sm, 4px);
    padding: 6px 10px;
    margin-bottom: 6px;
  }
  .placeholder {
    border: 1px dashed var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    padding: 6px 10px;
    color: var(--continuum-text-muted, #94a3b8);
  }
  .digest {
    white-space: pre-wrap;
    word-break: break-word;
    font-family: var(--continuum-font-mono, monospace);
    font-size: var(--continuum-font-size-xs, 0.75rem);
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    padding: 8px 10px;
    margin: 4px 0 0;
    max-height: 32em;
    overflow-y: auto;
  }
  select {
    background: var(--continuum-bg-secondary, #1e293b);
    border: 1px solid var(--continuum-border, #334155);
    border-radius: var(--continuum-radius-sm, 4px);
    color: var(--continuum-text-primary, #e2e8f0);
    font: inherit;
    padding: 2px 6px;
  }
  .btn {
    font: inherit;
    cursor: pointer;
    color: var(--continuum-text-primary, #e2e8f0);
    padding: 2px 10px;
    border-radius: var(--continuum-radius-sm, 4px);
    border: 1px solid var(--continuum-accent-primary, #6366f1);
    background: var(--continuum-bg-tertiary, #273549);
    margin-left: auto;
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
