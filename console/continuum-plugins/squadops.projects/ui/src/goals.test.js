// The goals panel's reads and its write (SIP-0115 slice 4, #2887), under node's own runner
// (`npm test` in this plugin's ui/). Each fake answers as the runtime API's routes do: the
// response models' field names and the error envelope `{"detail": {"error": {...}}}`.
//
// Bugs caught: a Project with no goal set, or a Campaign naming none, shown as a failure (or a
// missing Project shown as "no goal set"); the 409 of a revision written first read as success,
// retried over, or shown as raw JSON; the write sent with the wrong expected revision or around
// the command bus; an edit dropping the fields it doesn't touch (candidates above all, which
// slice 3 owns); an item's derived status attached to the wrong row.

import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  GoalsReadError,
  backlogRows,
  documentFrom,
  draftFrom,
  incrementOf,
  loadAssessments,
  loadBacklog,
  loadGoalSet,
  loadGoalSetCampaigns,
  moved,
  revisionArgs,
  submitRevision,
} from './goals.js';
import { COMMAND_ROUTE } from '../../../shared/commands.js';

const envelope = (code, message, details = null) => ({ detail: { error: { code, message, details } } });

// A fake `apiFetch` answering by URL; records every call.
function api(routes) {
  const calls = [];
  const apiFetch = async (url, opts = {}) => {
    calls.push({ url, method: opts.method ?? 'GET', body: opts.body ? JSON.parse(opts.body) : undefined });
    const key = Object.keys(routes).find((k) => url === k || url.startsWith(`${k}?`) || url.startsWith(`${k}&`));
    if (!key) throw new Error(`unexpected fetch ${url}`);
    const route = routes[key];
    const [status, body] = typeof route === 'function' ? route(url, opts) : route;
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
      text: async () => (typeof body === 'string' ? body : JSON.stringify(body)),
    };
  };
  return { apiFetch, calls };
}

const GOAL_SET = {
  api_version: 'squadops.project-goal-set/v1',
  goal: 'Readers keep a log of what they read',
  expected_results: [
    { id: 'er-log', statement: 'A reader adds a book', surface: { kind: 'page', ref: '/books' } },
  ],
  constraints: ['No accounts'],
  out_of_scope: [],
  backlog: [
    { id: 'add-book', title: 'Add a book', description: '', serves: ['er-log'] },
    { id: 'rate-book', title: 'Rate a book', description: '', serves: ['er-log'] },
  ],
  candidates: [
    {
      id: 'export-csv',
      title: 'Export the log',
      description: 'found by a reviewer',
      found_by: 'qa',
      found_at: '2026-11-01T10:00:00+00:00',
      evidence: [],
    },
  ],
};

const REVISION = (n) => ({
  project_id: 'prj-x',
  revision: n,
  author: 'owner',
  reason: `revision ${n}`,
  source_ref: null,
  created_at: '2026-11-02T10:00:00Z',
  goal_set: GOAL_SET,
});

// --- reading the goal set ---

test('a Project\'s goal set is its latest revision, with every revision newest first', async () => {
  const { apiFetch, calls } = api({
    '/api/v1/projects/prj-x/goal-set': [200, REVISION(2)],
    '/api/v1/projects/prj-x/goal-set/revisions': [200, [REVISION(2), REVISION(1)]],
  });

  const got = await loadGoalSet(apiFetch, '', 'prj-x');

  assert.equal(got.state, 'ok');
  assert.equal(got.current.revision, 2);
  assert.deepEqual(got.revisions.map((r) => r.revision), [2, 1]);
  assert.deepEqual(calls.map((c) => c.url), [
    '/api/v1/projects/prj-x/goal-set',
    '/api/v1/projects/prj-x/goal-set/revisions',
  ]);
});

test('a Project with no goal set written reads as none, not as a failure', async () => {
  const { apiFetch, calls } = api({
    '/api/v1/projects/prj-x/goal-set': [404, envelope('GOAL_SET_NOT_FOUND', 'Project prj-x has no goal set written')],
  });

  const got = await loadGoalSet(apiFetch, '', 'prj-x');

  assert.deepEqual(got, { state: 'none', message: 'Project prj-x has no goal set written' });
  assert.equal(calls.length, 1, 'no history is asked for a goal set that does not exist');
});

test('a missing Project is a refusal, not "no goal set"', async () => {
  const { apiFetch } = api({
    '/api/v1/projects/prj-gone/goal-set': [404, envelope('PROJECT_NOT_FOUND', 'Project not found: prj-gone')],
  });

  await assert.rejects(
    loadGoalSet(apiFetch, '', 'prj-gone'),
    (err) => err instanceof GoalsReadError && err.code === 'PROJECT_NOT_FOUND' && err.message === 'The goal set: Project not found: prj-gone',
  );
});

// --- the Campaigns and the backlog ---

test('only the Project\'s Campaigns on a goal set are offered, read through the pager', async () => {
  const onGoals = { campaign_id: 'cmp-a', objective: { goals: { goal_set: 'prj-x', revision: 'current' } } };
  const onRequirements = { campaign_id: 'cmp-b', objective: { goals: null, requirements: 'repo:file:PRD.md@current' } };
  const { apiFetch, calls } = api({ '/api/v1/campaigns': [200, [onGoals, onRequirements]] });

  const got = await loadGoalSetCampaigns(apiFetch, '', 'prj-x');

  assert.deepEqual(got.map((c) => c.campaign_id), ['cmp-a']);
  assert.equal(calls[0].url, '/api/v1/campaigns?project_id=prj-x&limit=500&offset=0');
});

test('a Campaign naming no goal set reads as having no backlog, not as a failure', async () => {
  const { apiFetch } = api({
    '/api/v1/campaigns/cmp-b/backlog': [
      404,
      envelope('CAMPAIGN_HAS_NO_GOAL_SET', 'campaign cmp-b names no goal set (objective.goals), so it has no backlog'),
    ],
  });

  const got = await loadBacklog(apiFetch, '', 'cmp-b');

  assert.deepEqual(got, {
    state: 'no-goal-set',
    message: 'campaign cmp-b names no goal set (objective.goals), so it has no backlog',
  });
});

test('a Campaign that does not exist is a refusal', async () => {
  const { apiFetch } = api({
    '/api/v1/campaigns/cmp-gone/backlog': [404, envelope('CAMPAIGN_NOT_FOUND', 'Campaign not found: cmp-gone')],
  });

  await assert.rejects(loadBacklog(apiFetch, '', 'cmp-gone'), (err) => err.code === 'CAMPAIGN_NOT_FOUND');
});

test('each row carries its own item\'s derived status; an item only the Campaign still holds follows', () => {
  const backlog = {
    revision: 2,
    items: [
      { item_id: 'rate-book', title: 'Rate a book', serves: ['er-log'], status: 'in_increment', label: 'in increment', position: 2, proposal_id: 'prop-9', version: 2, cycle_id: 'cyc-4', revision: 2 },
      { item_id: 'add-book', title: 'Add a book', serves: ['er-log'], status: 'accepted', label: 'accepted', position: 1, proposal_id: 'prop-3', version: 1, cycle_id: 'cyc-1', revision: 1 },
      { item_id: 'old-item', title: 'Gone now', serves: ['er-log'], status: 'removed', label: 'accepted (removed in r2)', position: null, removed_in: 2 },
    ],
  };

  const rows = backlogRows(GOAL_SET, backlog);

  assert.deepEqual(
    rows.map((r) => [r.item_id, r.position, r.derived?.label ?? null]),
    [
      ['add-book', 1, 'accepted'],
      ['rate-book', 2, 'in increment'],
      ['old-item', null, 'accepted (removed in r2)'],
    ],
  );
  assert.equal(incrementOf(rows[1].derived), 'prop-9 v2 · cycle cyc-4 · under r2');
  assert.equal(incrementOf(rows[2].derived), null, 'an item no proposal named has no increment');
});

test('with no Campaign chosen, rows are the goal set\'s order with no status', () => {
  assert.deepEqual(
    backlogRows(GOAL_SET, null).map((r) => [r.item_id, r.position, r.derived]),
    [['add-book', 1, null], ['rate-book', 2, null]],
  );
});

// --- editing ---

test('an edit submits the stored document with only what was edited changed: candidates kept', () => {
  const draft = draftFrom(GOAL_SET);
  draft.doc.goal = 'Readers keep and share a log';
  draft.doc.backlog = moved(draft.doc.backlog, 1, -1);
  draft.constraintsText = 'No accounts\n\n  Works offline  \n';

  const doc = documentFrom(draft);

  assert.deepEqual(doc, {
    ...GOAL_SET,
    goal: 'Readers keep and share a log',
    constraints: ['No accounts', 'Works offline'],
    backlog: [GOAL_SET.backlog[1], GOAL_SET.backlog[0]],
  });
  assert.equal(GOAL_SET.goal, 'Readers keep a log of what they read', 'the stored revision is not mutated');
});

test('moving past either end leaves the order as it was', () => {
  const list = ['a', 'b', 'c'];
  assert.deepEqual(moved(list, 0, -1), ['a', 'b', 'c']);
  assert.deepEqual(moved(list, 2, 1), ['a', 'b', 'c']);
  assert.deepEqual(moved(list, 2, -1), ['a', 'c', 'b']);
});

// --- writing: through the command bus, as the console app's handler answers ---

// A fake command route: answers `pending` until `confirmed`, then the handler's result.
function bus(handlerResult) {
  const posts = [];
  const apiFetch = async (url, opts) => {
    const body = JSON.parse(opts.body);
    posts.push({ url, body });
    const answer = body.confirmed
      ? { command_id: body.command_id, status: 'success', danger_level: 'confirm', result: handlerResult }
      : { command_id: body.command_id, status: 'pending', requires_confirmation: true, danger_level: 'confirm' };
    return { ok: true, status: 200, text: async () => JSON.stringify(answer) };
  };
  return { apiFetch, posts };
}

const ARGS = revisionArgs('prj-x', {
  expectedRevision: 2,
  reason: 'Rate before add',
  goalSet: GOAL_SET,
  idempotencyKey: 'console-goals-k-1',
});

test('a confirmed edit posts the revision request through the bus and reads back the new revision', async () => {
  const { apiFetch, posts } = bus({ revision: REVISION(3), idempotency_key: 'console-goals-k-1', replayed: false });

  const got = await submitRevision(apiFetch, ARGS, { confirm: () => true });

  assert.deepEqual(got, { state: 'written', revision: REVISION(3), replayed: false });
  assert.deepEqual(posts.map((p) => p.url), [COMMAND_ROUTE, COMMAND_ROUTE]);
  assert.deepEqual(posts[1].body, {
    command_id: 'squadops.revise_goal_set',
    args: {
      project_id: 'prj-x',
      expected_revision: 2,
      reason: 'Rate before add',
      idempotency_key: 'console-goals-k-1',
      goal_set: GOAL_SET,
    },
    confirmed: true,
  });
});

test('a revision written first by someone else is a conflict, said plainly, and not retried', async () => {
  const relayed = {
    error: JSON.stringify(
      envelope('STALE_GOAL_SET_REVISION', "Project prj-x's goal set is at revision 3; revision 3 doesn't follow it"),
    ),
    status_code: 409,
  };
  const { apiFetch, posts } = bus(relayed);

  const got = await submitRevision(apiFetch, ARGS, { confirm: () => true });

  assert.equal(got.state, 'conflict');
  assert.equal(
    got.message,
    'Another revision was written after you began editing from revision 2, so yours was not saved. ' +
      "Project prj-x's goal set is at revision 3; revision 3 doesn't follow it. " +
      'Your edits are still here: reload the latest, then make them again.',
  );
  assert.equal(posts.length, 2, 'asked, confirmed, refused: no third post');
});

test('a goal set the API refuses names the field, in its own words', async () => {
  const relayed = {
    error: JSON.stringify(
      envelope('GOAL_SET_INVALID', 'backlog[0].serves: the ids of the expected results it serves, at least one', {
        field: 'backlog[0].serves',
      }),
    ),
    status_code: 422,
  };
  const { apiFetch } = bus(relayed);

  const got = await submitRevision(apiFetch, ARGS, { confirm: () => true });

  assert.deepEqual(got, {
    state: 'refused',
    status: 422,
    code: 'GOAL_SET_INVALID',
    message: 'backlog[0].serves: the ids of the expected results it serves, at least one',
    field: 'backlog[0].serves',
  });
});

test('saying no to the bus\'s confirmation writes nothing and is not an error', async () => {
  const { apiFetch, posts } = bus({ revision: REVISION(3) });

  const got = await submitRevision(apiFetch, ARGS, { confirm: () => false });

  assert.deepEqual(got, { state: 'declined' });
  assert.equal(posts.length, 1);
});

// --- the crew's assessment of each expected result (SIP-0115 §8.3, slice 5, #2888) ---

test('the panel reads a Campaign\'s assessments, and a Campaign with no goal set has none', async () => {
  // Bugs caught: the wrong route, so each expected result stays unassessed; a requirements
  // Campaign's 404 shown as a failure; an unknown Campaign's shown as nothing to show.
  const view = { campaign_id: 'cmp-b', revision: 2, results: [] };
  const { apiFetch, calls } = api({ '/api/v1/campaigns/cmp-b/assessments': [200, view] });
  assert.deepEqual(await loadAssessments(apiFetch, '', 'cmp-b'), view);
  assert.deepEqual(calls.map((c) => c.url), ['/api/v1/campaigns/cmp-b/assessments']);

  const requirements = api({
    '/api/v1/campaigns/cmp-r/assessments': [404, envelope('CAMPAIGN_HAS_NO_GOAL_SET', 'names none')],
  });
  assert.equal(await loadAssessments(requirements.apiFetch, '', 'cmp-r'), null);

  const gone = api({
    '/api/v1/campaigns/cmp-x/assessments': [404, envelope('CAMPAIGN_NOT_FOUND', 'no such Campaign')],
  });
  await assert.rejects(loadAssessments(gone.apiFetch, '', 'cmp-x'), (err) => {
    assert.ok(err instanceof GoalsReadError);
    return err.code === 'CAMPAIGN_NOT_FOUND';
  });
});
