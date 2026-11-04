// The Campaigns plugin's reads (the 2.6 plan's Track G, D13; #2834). Read-only: it writes nothing,
// registers no command, and the controls (launch, rule, pause, resume, abort) stay with the crew's
// broker and the CLI. Plain functions over the console's `apiFetch`, so node's own runner tests
// them (`npm test` here) without a browser; `CampaignsPerspective.svelte` renders what they answer.
//
// What it reads, every route `campaigns:read` (or `cycles:read` for the Projects), and the
// response models whose field names are used here (src/squadops/api/campaign_schemas.py):
//   - `GET /api/v1/projects`: the Projects (`ProjectResponse`), whose Campaigns are listed;
//   - `GET /api/v1/campaigns?project_id=`: a Project's Campaigns, paged (`fetchAllPages`), newest
//     first (`CampaignResponse`: campaign_id, project_id, objective, state, outcome, created_at,
//     updated_at, accepted);
//   - `GET /api/v1/campaigns/{id}`: one Campaign. An unknown one answers 404 `CAMPAIGN_NOT_FOUND`;
//   - `GET /api/v1/campaigns/{id}/control-log`: every row (`ControlLogEntryResponse`), as
//     `squadops campaigns log` reads it. The current increment is read from it;
//   - `GET /api/v1/campaigns/{id}/ledger`: each proposal version (`LedgerEntryResponse`), as
//     `squadops campaigns ledger` reads it;
//   - `GET /api/v1/campaigns/{id}/escalations`: each escalation in its state
//     (`EscalationResponse`), as `squadops campaigns escalations` reads it;
//   - `GET /api/v1/campaigns/{id}/package`: the latest evidence package's digest
//     (`PackageDigestResponse`), as `squadops campaigns digest` prints it. A Campaign with none
//     yet answers 404 `PACKAGE_NOT_FOUND`.
//
// Not read: the crew's assessment of each expected result. SIP-0115 slice 5 (#2888) has no route
// on main yet; the view names the gap where it will go.

import { errorFromText } from '../../../shared/errors.js';
import { fetchAllPages } from '../../../shared/paging.js';
import { announce, openNav } from '../../../shared/selection.js';

/** A read the API refused for a reason the view doesn't answer itself. */
export class CampaignsReadError extends Error {
  constructor(message, { status, code = null } = {}) {
    super(message);
    this.name = 'CampaignsReadError';
    this.status = status;
    this.code = code;
  }
}

async function refusal(resp, what) {
  const { code, message } = errorFromText(await resp.text(), resp.status);
  return new CampaignsReadError(`${what}: ${message}`, { status: resp.status, code });
}

const enc = encodeURIComponent;

/** A Campaign that has ended (SIP-0109 §17): nothing it shows moves on its own any more. */
export const isClosed = (campaign) => campaign?.state === 'completed';

// --- the list ---

/**
 * Every Project's Campaigns, newest first: `{campaigns, refused}`. A Project whose Campaigns the
 * API refused is named in `refused` (`{project_id, status}`) and the rest are still listed.
 */
export async function loadCampaigns(apiFetch, apiBase) {
  const resp = await apiFetch(`${apiBase}/api/v1/projects`);
  if (!resp.ok) throw await refusal(resp, 'The Projects');
  const projects = await resp.json();
  const reads = await Promise.all(
    projects.map(async (p) => ({
      project_id: p.project_id,
      ...(await fetchAllPages(apiFetch, `${apiBase}/api/v1/campaigns?project_id=${enc(p.project_id)}`)),
    })),
  );
  const campaigns = reads.flatMap((r) => r.items);
  campaigns.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
  return {
    campaigns,
    refused: reads.filter((r) => !r.ok).map((r) => ({ project_id: r.project_id, status: r.status })),
  };
}

/** One Campaign's control log, or a `CampaignsReadError`. */
export async function loadControlLog(apiFetch, apiBase, campaignId) {
  const resp = await apiFetch(`${apiBase}/api/v1/campaigns/${enc(campaignId)}/control-log`);
  if (!resp.ok) throw await refusal(resp, `${campaignId}'s control log`);
  return resp.json();
}

/**
 * Each listed Campaign's current increment, `{campaign_id: increment | {error}}`. A closed
 * Campaign's is read once and kept in `cache` while its `updated_at` stands; an open one's is
 * read on every call, which is what the list's poll is for. At most `concurrency` logs are read
 * at once: a deploy holds a hundred closed Campaigns and more, each read once on first open.
 */
export async function loadIncrements(apiFetch, apiBase, campaigns, cache = new Map(), { concurrency = 6 } = {}) {
  const out = {};
  const queue = [];
  for (const c of campaigns) {
    const kept = cache.get(c.campaign_id);
    if (isClosed(c) && kept && kept.updated_at === c.updated_at) out[c.campaign_id] = kept.increment;
    else queue.push(c);
  }
  async function worker() {
    for (let c = queue.shift(); c; c = queue.shift()) {
      try {
        const increment = currentIncrement(await loadControlLog(apiFetch, apiBase, c.campaign_id));
        out[c.campaign_id] = increment;
        if (isClosed(c)) cache.set(c.campaign_id, { updated_at: c.updated_at, increment });
      } catch (err) {
        out[c.campaign_id] = { error: err.message };
      }
    }
  }
  await Promise.all(Array.from({ length: Math.max(1, concurrency) }, worker));
  return out;
}

// --- the current increment, from the control log ---

// What a launch's deciding row asked for, and the cycle that launch is (SIP-0109 §10's actions;
// `squadops.campaigns.continuation.PendingAction`): a proposal opens a new increment, a repair or
// retry continues the one in hand. A `start` row's launch is the calibration.
const LAUNCH_KIND = {
  propose: 'proposal',
  abandon_and_propose: 'proposal',
  repair: 'repair',
  retry: 'retry',
};

/**
 * The increment the Campaign is on, read from its applied control-log rows:
 * `{number, proposal_id, version, cycle_id, cycle_kind}`.
 *   - `number`: the increments opened so far, each a proposal (`submit` rows, by proposal id),
 *     plus one when a proposal cycle has launched and not yet submitted; 0 before any;
 *   - `proposal_id`/`version`: the latest submitted, or null while the next one is drafted;
 *   - `cycle_id`: the latest launched cycle (`mark_launched`), or null before any;
 *   - `cycle_kind`: `calibration`, `proposal`, `repair` or `retry`, as its launch was decided.
 * The ledger is the record of each increment; this is only "where is it now".
 */
export function currentIncrement(log) {
  const applied = (log ?? []).filter((e) => e.outcome === 'applied');
  const bySeq = [...applied].sort((a, b) => a.seq - b.seq);
  const proposals = [];
  let lastSubmit = null;
  let lastLaunch = null;
  for (const e of bySeq) {
    if (e.operation === 'submit') {
      lastSubmit = e;
      if (!proposals.includes(e.binding?.proposal_id)) proposals.push(e.binding?.proposal_id);
    } else if (e.operation === 'mark_launched') {
      lastLaunch = e;
    }
  }
  let cycleKind = null;
  if (lastLaunch) {
    const decided = bySeq.find((e) => e.launch_id && e.launch_id === lastLaunch.target);
    cycleKind =
      decided?.operation === 'start' ? 'calibration' : (LAUNCH_KIND[decided?.binding?.action] ?? null);
  }
  const drafting =
    lastLaunch && cycleKind === 'proposal' && (!lastSubmit || lastLaunch.seq > lastSubmit.seq);
  return {
    number: proposals.length + (drafting ? 1 : 0),
    proposal_id: drafting ? null : (lastSubmit?.binding?.proposal_id ?? null),
    version: drafting ? null : (lastSubmit?.binding?.version ?? null),
    cycle_id: lastLaunch?.binding?.cycle_id ?? null,
    cycle_kind: cycleKind,
  };
}

/** The increment as one line: `#3 prop_x v1 · repair cyc_y`, `#2 proposing · cyc_z`, `none yet`. */
export function incrementText(increment) {
  if (!increment) return '';
  if (increment.error) return 'unreadable';
  if (increment.number === 0) {
    return increment.cycle_id ? `calibration · ${increment.cycle_id}` : 'none yet';
  }
  const what = increment.proposal_id
    ? `${increment.proposal_id} v${increment.version}`
    : 'proposing';
  const cycle = increment.cycle_id
    ? ` · ${increment.cycle_kind && increment.cycle_kind !== 'proposal' ? `${increment.cycle_kind} ` : ''}${increment.cycle_id}`
    : '';
  return `#${increment.number} ${what}${cycle}`;
}

/** The list's short form: `#3 · repair`, `#2 · proposing`, `calibration`, `none yet`. */
export function incrementShort(increment) {
  if (!increment) return '';
  if (increment.error) return 'unreadable';
  if (increment.number === 0) return increment.cycle_id ? 'calibration' : 'none yet';
  if (!increment.proposal_id) return `#${increment.number} · proposing`;
  const kind = increment.cycle_kind && increment.cycle_kind !== 'proposal' ? ` · ${increment.cycle_kind}` : '';
  return `#${increment.number}${kind}`;
}

// --- one Campaign ---

// A part of the view read apart from the Campaign itself: its value, or the refusal in the API's
// words, so one unreadable part never blanks the rest.
async function part(apiFetch, url, what) {
  try {
    const resp = await apiFetch(url);
    if (!resp.ok) return { error: (await refusal(resp, what)).message };
    return { value: await resp.json() };
  } catch (err) {
    return { error: `${what}: ${err.message}` };
  }
}

/**
 * One Campaign's view. Answers `{state: 'not-found', message}` for a Campaign the API doesn't hold,
 * else `{state: 'ok', campaign, log, ledger, escalations, digest}`, where each of the last four is
 * `{value}` or `{error}`, and `digest` is `{none: message}` when no evidence package is stored yet.
 */
export async function loadCampaignView(apiFetch, apiBase, campaignId) {
  const base = `${apiBase}/api/v1/campaigns/${enc(campaignId)}`;
  const resp = await apiFetch(base);
  if (resp.status === 404) {
    const { code, message } = errorFromText(await resp.text(), 404);
    if (code === 'CAMPAIGN_NOT_FOUND') return { state: 'not-found', message };
    throw new CampaignsReadError(`${campaignId}: ${message}`, { status: 404, code });
  }
  if (!resp.ok) throw await refusal(resp, campaignId);
  const campaign = await resp.json();
  const [log, ledger, escalations, digest] = await Promise.all([
    part(apiFetch, `${base}/control-log`, 'The control log'),
    part(apiFetch, `${base}/ledger`, 'The ledger'),
    part(apiFetch, `${base}/escalations`, 'The escalations'),
    loadDigest(apiFetch, base),
  ]);
  return { state: 'ok', campaign, log, ledger, escalations, digest };
}

async function loadDigest(apiFetch, base) {
  try {
    const resp = await apiFetch(`${base}/package`);
    if (resp.status === 404) {
      const { code, message } = errorFromText(await resp.text(), 404);
      if (code === 'PACKAGE_NOT_FOUND') return { none: message };
      return { error: `The digest: ${message}` };
    }
    if (!resp.ok) return { error: (await refusal(resp, 'The digest')).message };
    return { value: await resp.json() };
  } catch (err) {
    return { error: `The digest: ${err.message}` };
  }
}

// --- what the view derives ---

/** The escalations still open: `pending` ones (the others are resolved, expired, superseded or cancelled). */
export const openEscalations = (escalations) => (escalations ?? []).filter((e) => e.state === 'pending');

/**
 * The proposal versions waiting for a ruling: unruled, the latest version of their proposal (a
 * revised proposal's earlier version is never ruled), on a Campaign that hasn't ended.
 */
export function waitingProposals(ledger, campaign) {
  if (isClosed(campaign)) return [];
  const latest = new Map();
  for (const e of ledger ?? []) {
    if ((latest.get(e.proposal_id)?.version ?? -1) < e.version) latest.set(e.proposal_id, e);
  }
  return (ledger ?? []).filter((e) => !e.ruling && latest.get(e.proposal_id) === e);
}

/** The increments accepted: proposal versions whose last carrying cycle's verdict was `accepted`. */
export const acceptedCount = (ledger) =>
  (ledger ?? []).filter((e) => e.outcome?.verdict === 'accepted').length;

/** One row per ledger entry, as `squadops campaigns ledger` prints it. */
export function ledgerRows(ledger) {
  return (ledger ?? []).map((e) => ({
    key: `${e.proposal_id}:${e.version}`,
    proposal: `${e.proposal_id} v${e.version}`,
    ruling: e.ruling?.decision ?? null,
    ruled_by: e.ruling?.actor_role ?? null,
    ruling_reason: e.ruling?.reason ?? null,
    verdict: e.outcome?.verdict ?? null,
    decided_row: e.outcome?.row ?? null,
    ending: e.outcome?.outcome ?? e.outcome?.action ?? null,
    cycles: (e.cycles ?? []).map((c) => `${c.kind} ${c.cycle_id}${c.row != null ? ` (row ${c.row})` : ''}`),
    classification: e.classification?.classification ?? null,
    unbuilt: e.outcome?.unbuilt ?? null,
  }));
}

/** The control log's latest `n` rows, newest first. */
export const recentLog = (log, n = 15) => [...(log ?? [])].sort((a, b) => b.seq - a.seq).slice(0, n);

/** A row's outcome as `squadops campaigns log` prints it: a refusal names its reason. */
export const logOutcome = (e) => e.outcome + (e.refusal ? ` (${e.refusal})` : '');

// --- the link to the goals panel ---

/**
 * The goals panel's selection for a Campaign that names a goal set (`objective.goals`), or null
 * for one that doesn't (a requirements file, or a sample application's PRD).
 */
export function goalsSelection(campaign) {
  if (!campaign?.objective?.goals) return null;
  return { project_id: campaign.project_id, campaign_id: campaign.campaign_id };
}

/**
 * Opens the goals panel on the Campaign: announces `squadops:select-campaign` (kept for the panel
 * to take when it mounts), then opens the Projects perspective it lives in. Answers whether the
 * perspective was opened; false leaves the selection waiting for the next time it is.
 */
export function openGoals(campaign, { win = globalThis, doc = globalThis.document } = {}) {
  const detail = goalsSelection(campaign);
  if (!detail) return false;
  announce('squadops:select-campaign', detail, win);
  return openNav('Projects', doc);
}
