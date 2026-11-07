// The goals panel's reads and its one write (SIP-0115 §8.3, slice 4, #2887). Plain functions over
// the console's `apiFetch`, so node's own runner tests them (`npm test` here) without a browser;
// `GoalsPanel.svelte` renders what they answer.
//
// What it reads, all on main (the routes' response models are the field names used here):
//   - `GET /api/v1/projects/{id}/goal-set`: the active goal set, its latest revision
//     (`GoalSetRevisionResponse`: project_id, revision, author, reason, source_ref, created_at,
//     goal_set). A Project with none written answers 404 `GOAL_SET_NOT_FOUND`;
//   - `GET /api/v1/projects/{id}/goal-set/revisions`: every revision, newest first;
//   - `GET /api/v1/campaigns?project_id=`: the Project's Campaigns, paged (`fetchAllPages`);
//   - `GET /api/v1/campaigns/{id}/backlog`: the backlog as one Campaign stands on it
//     (`BacklogResponse`: revision, reads, next_item, done, items). A Campaign naming no goal set
//     answers 404 `CAMPAIGN_HAS_NO_GOAL_SET`;
//   - `GET /api/v1/campaigns/{id}/assessments`: the operator's assessment of each expected result as
//     that Campaign stands (slice 5, #2888; `shared/assessments.js` says what each reads as).
// What it writes: the next revision, through the command bus (`squadops.revise_goal_set`, the
// console app's handler for `POST /api/v1/projects/{id}/goal-set/revisions`). The revision the
// edit began from is its `expected_revision`, so a revision written first by someone else is
// the API's 409 `STALE_GOAL_SET_REVISION`, said plainly and never retried over.
//
// Slice 3's candidate actions (promote, drop, split) are not here: candidates are read-only.

import { CommandDeclined, CommandError, executeCommand } from '../../../shared/commands.js';
import { errorFromText } from '../../../shared/errors.js';
import { fetchAllPages } from '../../../shared/paging.js';

export const REVISE_COMMAND = 'squadops.revise_goal_set';

/** A read the API refused for a reason the panel doesn't answer itself. */
export class GoalsReadError extends Error {
  constructor(message, { status, code = null } = {}) {
    super(message);
    this.name = 'GoalsReadError';
    this.status = status;
    this.code = code;
  }
}

async function refusal(resp, what) {
  const { code, message } = errorFromText(await resp.text(), resp.status);
  return new GoalsReadError(`${what}: ${message}`, { status: resp.status, code });
}

const enc = encodeURIComponent;

/**
 * The Project's goal set: `{state: 'none'}` when none is written, else
 * `{state: 'ok', current, revisions}` (revisions newest first).
 */
export async function loadGoalSet(apiFetch, apiBase, projectId) {
  const base = `${apiBase}/api/v1/projects/${enc(projectId)}/goal-set`;
  const resp = await apiFetch(base);
  if (resp.status === 404) {
    const { code, message } = errorFromText(await resp.text(), 404);
    if (code === 'GOAL_SET_NOT_FOUND') return { state: 'none', message };
    throw new GoalsReadError(`The goal set: ${message}`, { status: 404, code });
  }
  if (!resp.ok) throw await refusal(resp, 'The goal set');
  const current = await resp.json();
  const history = await apiFetch(`${base}/revisions`);
  if (!history.ok) throw await refusal(history, 'The revision history');
  return { state: 'ok', current, revisions: await history.json() };
}

/** The Project's Campaigns that work through its goal set (`objective.goals`), newest first. */
export async function loadGoalSetCampaigns(apiFetch, apiBase, projectId) {
  const { ok, status, items } = await fetchAllPages(
    apiFetch,
    `${apiBase}/api/v1/campaigns?project_id=${enc(projectId)}`,
  );
  if (!ok) throw new GoalsReadError(`The Project's Campaigns: the API answered ${status}`, { status });
  return items.filter((c) => c.objective?.goals);
}

/**
 * The backlog as `campaignId` stands on it: `{state: 'ok', backlog}`, or
 * `{state: 'no-goal-set', message}` for a Campaign that names none.
 */
export async function loadBacklog(apiFetch, apiBase, campaignId) {
  const resp = await apiFetch(`${apiBase}/api/v1/campaigns/${enc(campaignId)}/backlog`);
  if (resp.status === 404) {
    const { code, message } = errorFromText(await resp.text(), 404);
    if (code === 'CAMPAIGN_HAS_NO_GOAL_SET') return { state: 'no-goal-set', message };
    throw new GoalsReadError(`The backlog: ${message}`, { status: 404, code });
  }
  if (!resp.ok) throw await refusal(resp, 'The backlog');
  return { state: 'ok', backlog: await resp.json() };
}

/**
 * The operator's assessments as `campaignId` stands (`CampaignAssessmentsResponse`), or null for a
 * Campaign that names no goal set, which has none.
 */
export async function loadAssessments(apiFetch, apiBase, campaignId) {
  const resp = await apiFetch(`${apiBase}/api/v1/campaigns/${enc(campaignId)}/assessments`);
  if (resp.status === 404) {
    const { code, message } = errorFromText(await resp.text(), 404);
    if (code === 'CAMPAIGN_HAS_NO_GOAL_SET') return null;
    throw new GoalsReadError(`The operator's assessments: ${message}`, { status: 404, code });
  }
  if (!resp.ok) throw await refusal(resp, "The operator's assessments");
  return resp.json();
}

/** Whether the viewer may write a revision: the API requires `admin:write`. */
export async function canWriteGoalSet(apiFetch, apiBase) {
  try {
    const resp = await apiFetch(`${apiBase}/auth/userinfo`);
    if (!resp.ok) return false;
    const info = await resp.json();
    return Array.isArray(info.scopes) && info.scopes.includes('admin:write');
  } catch {
    return false;
  }
}

// --- the backlog table ---

/**
 * One row per backlog item: the goal set's own order, with each item's derived status from the
 * chosen Campaign's backlog when there is one. An item the Campaign's backlog holds and the goal
 * set no longer does (removed in a later revision, or read at a pinned one) follows, as that
 * backlog lists it.
 */
export function backlogRows(goalSet, backlog) {
  const derived = new Map((backlog?.items ?? []).map((i) => [i.item_id, i]));
  const rows = (goalSet?.backlog ?? []).map((item, index) => ({
    item_id: item.id,
    title: item.title,
    serves: item.serves ?? [],
    position: index + 1,
    derived: derived.get(item.id) ?? null,
  }));
  const listed = new Set(rows.map((r) => r.item_id));
  for (const item of backlog?.items ?? []) {
    if (listed.has(item.item_id)) continue;
    rows.push({
      item_id: item.item_id,
      title: item.title,
      serves: item.serves ?? [],
      position: null,
      derived: item,
    });
  }
  return rows;
}

/** An item's increment, as its derived status names it: proposal, version and cycle. */
export function incrementOf(derived) {
  if (!derived?.proposal_id) return null;
  const parts = [`${derived.proposal_id}${derived.version != null ? ` v${derived.version}` : ''}`];
  if (derived.cycle_id) parts.push(`cycle ${derived.cycle_id}`);
  if (derived.revision != null) parts.push(`under r${derived.revision}`);
  return parts.join(' · ');
}

// --- editing ---

/** An editable copy of a stored goal set: lists of statements become text, one per line. */
export function draftFrom(goalSet) {
  const doc = structuredClone(goalSet);
  return {
    doc,
    constraintsText: (doc.constraints ?? []).join('\n'),
    outOfScopeText: (doc.out_of_scope ?? []).join('\n'),
  };
}

const lines = (text) =>
  text
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean);

/** The goal set a draft submits: the stored document's shape, every field the draft left alone kept. */
export function documentFrom(draft) {
  return {
    ...draft.doc,
    constraints: lines(draft.constraintsText),
    out_of_scope: lines(draft.outOfScopeText),
  };
}

/** `list` with the entry at `index` moved by `delta` (-1 up, +1 down); unchanged at an end. */
export function moved(list, index, delta) {
  const to = index + delta;
  if (index < 0 || index >= list.length || to < 0 || to >= list.length) return list;
  const next = [...list];
  const [entry] = next.splice(index, 1);
  next.splice(to, 0, entry);
  return next;
}

/** The command's args: the API's `GoalSetRevisionRequest` and the Project it is for. */
export function revisionArgs(projectId, { expectedRevision, reason, goalSet, idempotencyKey }) {
  return {
    project_id: projectId,
    expected_revision: expectedRevision,
    reason,
    idempotency_key: idempotencyKey,
    goal_set: goalSet,
  };
}

/** A key per edit: a retry of the same edit replays rather than writing twice. */
export function newIdempotencyKey() {
  return `console-goals-${globalThis.crypto.randomUUID()}`;
}

/**
 * Writes the next revision. Answers one of:
 *   - `{state: 'written', revision}`: the revision as recorded (`replayed` when a retry);
 *   - `{state: 'declined'}`: the bus asked for confirmation and the user said no;
 *   - `{state: 'conflict', message}`: another revision was written first (409);
 *   - `{state: 'refused', status, code, message, field}`: any other refusal, the API's own words.
 */
export async function submitRevision(apiFetch, args, { confirm, execute = executeCommand } = {}) {
  let result;
  try {
    result = await execute(apiFetch, REVISE_COMMAND, args, confirm ? { confirm } : {});
  } catch (err) {
    if (err instanceof CommandDeclined) return { state: 'declined' };
    if (!(err instanceof CommandError)) throw err;
    const { code, message, details } = errorFromText(err.message, err.status);
    if (err.status === 409 && code === 'STALE_GOAL_SET_REVISION') {
      return {
        state: 'conflict',
        message:
          `Another revision was written after you began editing from revision ` +
          `${args.expected_revision}, so yours was not saved. ${message}. ` +
          `Your edits are still here: reload the latest, then make them again.`,
      };
    }
    return {
      state: 'refused',
      status: err.status ?? null,
      code,
      message,
      field: details?.field ?? null,
    };
  }
  return { state: 'written', revision: result.revision, replayed: Boolean(result.replayed) };
}
