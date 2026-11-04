// The Campaigns plugin's reads (#2834, the 2.6 plan's Track G), under node's own runner (`npm test`
// in this plugin's ui/). Each fake answers as the runtime API's routes do: the response models'
// field names and the error envelope `{"detail": {"error": {...}}}`. The rows are shaped on a
// deploy's real control log (a goal-set Campaign: calibration record, an increment abandoned after
// its repair, one accepted, one rejected), with invented ids.
//
// Bugs caught: an unknown Campaign shown as an empty one, or a failure of another kind shown as
// "not found"; a Campaign with no ledger, escalations or package yet shown as a failure; one
// unreadable part blanking the whole view; the current increment counting a repair as a new
// increment, or naming the last proposal while the next is being drafted; a closed escalation or a
// revised proposal's earlier version shown as waiting; a goals link on a Campaign naming no goal set,
// or one that doesn't select the Campaign; a closed Campaign's log re-read on every poll.

import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  CampaignsReadError,
  acceptedCount,
  currentIncrement,
  goalsSelection,
  incrementText,
  ledgerRows,
  loadCampaignView,
  loadCampaigns,
  loadIncrements,
  openEscalations,
  openGoals,
  recentLog,
  waitingProposals,
} from './campaigns.js';
import { takeAnnounced } from '../../../shared/selection.js';

const envelope = (code, message) => ({ detail: { error: { code, message, details: null } } });

// A fake `apiFetch` answering by URL (an exact path, or that path with a query); records each call.
function api(routes) {
  const calls = [];
  const apiFetch = async (url) => {
    calls.push(url);
    const key = Object.keys(routes).find((k) => url === k || url.startsWith(`${k}?`));
    if (!key) throw new Error(`unexpected fetch ${url}`);
    const [status, body] = typeof routes[key] === 'function' ? routes[key](url) : routes[key];
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
      text: async () => (typeof body === 'string' ? body : JSON.stringify(body)),
    };
  };
  return { apiFetch, calls };
}

let seq = 0;
const row = (operation, prior, next, { target = null, launch_id = null, binding = {}, outcome = 'applied' } = {}) => ({
  entry_id: `cle_${++seq}`,
  campaign_id: 'cmp_one',
  seq,
  operation,
  actor: 'svc',
  actor_role: 'campaign-supervisor',
  reason: `${operation} row`,
  target,
  idempotency_key: `k${seq}`,
  binding,
  outcome,
  refusal: outcome === 'refused' ? 'stale_state' : null,
  prior_state: prior,
  next_state: next,
  committed_at: `2026-11-01T10:${String(seq).padStart(2, '0')}:00Z`,
  launch_id,
});

// A goal-set Campaign's log through its third increment's repair.
function goalSetLog() {
  seq = 0;
  return [
    row('create', null, 'draft'),
    row('start', 'draft', 'calibrating'),
    row('promote', 'calibrating', 'calibrating', { target: 'calrec_a' }),
    row('decide', 'calibrating', 'at_proposal', { launch_id: 'lnc_1', binding: { row: 5, action: 'propose' } }),
    row('mark_launched', 'at_proposal', 'at_proposal', { target: 'lnc_1', binding: { cycle_id: 'cyc_p1' } }),
    row('submit', 'at_proposal', 'awaiting_ruling', { binding: { proposal_id: 'prop_a', version: 1, cycle_id: 'cyc_p1' } }),
    row('rule', 'awaiting_ruling', 'building', { binding: { proposal_id: 'prop_a', version: 1, decision: 'approved' } }),
    row('decide', 'evaluating', 'repairing', { launch_id: 'lnc_2', binding: { row: 12, action: 'repair', cycle_id: 'cyc_p1' } }),
    row('mark_launched', 'repairing', 'repairing', { target: 'lnc_2', binding: { cycle_id: 'cyc_r1' } }),
    row('decide', 'evaluating', 'at_proposal', { launch_id: 'lnc_3', binding: { row: 13, action: 'abandon_and_propose', cycle_id: 'cyc_r1' } }),
    row('mark_launched', 'at_proposal', 'at_proposal', { target: 'lnc_3', binding: { cycle_id: 'cyc_p2' } }),
    row('submit', 'at_proposal', 'awaiting_ruling', { binding: { proposal_id: 'prop_b', version: 1, cycle_id: 'cyc_p2' } }),
    row('pause', 'awaiting_ruling', 'awaiting_ruling', { outcome: 'refused' }),
  ];
}

test('the current increment: a repair continues the increment in hand, a proposal cycle opens the next', () => {
  const log = goalSetLog();
  // Through the first repair: still increment 1, its repair cycle.
  assert.deepEqual(currentIncrement(log.slice(0, 9)), {
    number: 1, proposal_id: 'prop_a', version: 1, cycle_id: 'cyc_r1', cycle_kind: 'repair',
  });
  // The next proposal cycle launched, nothing submitted from it yet: increment 2, being drafted.
  assert.deepEqual(currentIncrement(log.slice(0, 11)), {
    number: 2, proposal_id: null, version: null, cycle_id: 'cyc_p2', cycle_kind: 'proposal',
  });
  // Submitted (and a refused row after it, which moves nothing).
  assert.deepEqual(currentIncrement(log), {
    number: 2, proposal_id: 'prop_b', version: 1, cycle_id: 'cyc_p2', cycle_kind: 'proposal',
  });
  assert.equal(incrementText(currentIncrement(log.slice(0, 9))), '#1 prop_a v1 · repair cyc_r1');
  assert.equal(incrementText(currentIncrement(log.slice(0, 11))), '#2 proposing · cyc_p2');
});

test('the current increment before any: none yet, or the calibration cycle a start launched', () => {
  seq = 0;
  const draft = [row('create', null, 'draft')];
  assert.equal(incrementText(currentIncrement(draft)), 'none yet');
  assert.equal(incrementText(currentIncrement([])), 'none yet');

  seq = 0;
  const calibrating = [
    row('create', null, 'draft'),
    row('start', 'draft', 'calibrating', { launch_id: 'lnc_c' }),
    row('mark_launched', 'calibrating', 'calibrating', { target: 'lnc_c', binding: { cycle_id: 'cyc_cal' } }),
  ];
  assert.deepEqual(currentIncrement(calibrating), {
    number: 0, proposal_id: null, version: null, cycle_id: 'cyc_cal', cycle_kind: 'calibration',
  });
  assert.equal(incrementText(currentIncrement(calibrating)), 'calibration · cyc_cal');
  assert.equal(incrementText({ error: 'boom' }), 'unreadable');
});

const BASE = '/api/v1/campaigns/cmp_one';
const CAMPAIGN = {
  campaign_id: 'cmp_one',
  project_id: 'prj-books',
  objective: {
    statement: 'work the goal set',
    allowed_scope: [],
    measurement: 'accepted increments',
    target_accepted_increments: 2,
    goals: { goal_set: 'prj-books', revision: 'current' },
  },
  policy: {},
  state: 'awaiting_ruling',
  outcome: null,
  created_at: '2026-11-01T10:00:00Z',
  created_by: 'owner',
  updated_at: '2026-11-01T10:12:00Z',
  accepted: null,
};

test('an unknown Campaign is "not found" in the API\'s words, and nothing else is read', async () => {
  const { apiFetch, calls } = api({
    '/api/v1/campaigns/cmp_gone': [404, envelope('CAMPAIGN_NOT_FOUND', 'Campaign not found: cmp_gone')],
  });
  const view = await loadCampaignView(apiFetch, '', 'cmp_gone');
  assert.deepEqual(view, { state: 'not-found', message: 'Campaign not found: cmp_gone' });
  assert.deepEqual(calls, ['/api/v1/campaigns/cmp_gone']);
});

test('a 404 that is not CAMPAIGN_NOT_FOUND, or any other refusal, is a read error, never "not found"', async () => {
  const { apiFetch } = api({ '/api/v1/campaigns/cmp_x': [404, 'Not Found'] });
  await assert.rejects(loadCampaignView(apiFetch, '', 'cmp_x'), (err) => {
    assert.ok(err instanceof CampaignsReadError);
    assert.equal(err.status, 404);
    assert.equal(err.message, 'cmp_x: Not Found');
    return true;
  });
  const forbidden = api({ '/api/v1/campaigns/cmp_x': [403, envelope('FORBIDDEN', 'missing campaigns:read')] });
  await assert.rejects(loadCampaignView(forbidden.apiFetch, '', 'cmp_x'), /missing campaigns:read/);
});

test('a new Campaign with no ledger, escalations or package yet reads as empty, not failed', async () => {
  seq = 0;
  const { apiFetch } = api({
    [BASE]: [200, { ...CAMPAIGN, state: 'draft' }],
    [`${BASE}/control-log`]: [200, [row('create', null, 'draft')]],
    [`${BASE}/ledger`]: [200, []],
    [`${BASE}/escalations`]: [200, []],
    [`${BASE}/package`]: [404, envelope('PACKAGE_NOT_FOUND', 'campaign cmp_one has no evidence package yet')],
  });
  const view = await loadCampaignView(apiFetch, '', 'cmp_one');
  assert.equal(view.state, 'ok');
  assert.deepEqual(view.ledger, { value: [] });
  assert.deepEqual(view.escalations, { value: [] });
  assert.deepEqual(view.digest, { none: 'campaign cmp_one has no evidence package yet' });
  assert.deepEqual(openEscalations(view.escalations.value), []);
  assert.deepEqual(waitingProposals(view.ledger.value, view.campaign), []);
  assert.equal(acceptedCount(view.ledger.value), 0);
  assert.deepEqual(ledgerRows(view.ledger.value), []);
});

test('one unreadable part is named, and the rest of the view still reads', async () => {
  const { apiFetch } = api({
    [BASE]: [200, CAMPAIGN],
    [`${BASE}/control-log`]: [200, goalSetLog()],
    [`${BASE}/ledger`]: [500, envelope('INTERNAL_ERROR', 'request req_1 failed')],
    [`${BASE}/escalations`]: [200, []],
    [`${BASE}/package`]: [200, { identity: 'abc', digest_artifact_id: 'art_1', digest: '# Campaign cmp_one' }],
  });
  const view = await loadCampaignView(apiFetch, '', 'cmp_one');
  assert.deepEqual(view.ledger, { error: 'The ledger: request req_1 failed' });
  assert.equal(view.log.value.length, 13);
  assert.equal(view.digest.value.digest, '# Campaign cmp_one');
});

const LEDGER = [
  {
    proposal_id: 'prop_a', version: 1, content_hash: 'h', baseline_tree: 't', cycle_id: 'cyc_p1', run_id: 'run_1',
    submitted_at: '2026-11-01T10:06:00Z',
    ruling: { decision: 'approved', reason: 'by the written rule', actor: 'svc', actor_role: 'campaign-supervisor', at: 'x' },
    outcome: { row: 13, ending: 'assessed', verdict: 'rejected', action: 'abandon_and_propose' },
    classification: { classification: 'scope_too_large', reason: 'r', actor: 'owner', at: 'y' },
    cycles: [
      { cycle_id: 'cyc_p1', kind: 'increment', row: 12, verdict: 'rejected', action: 'repair' },
      { cycle_id: 'cyc_r1', kind: 'repair', row: 13, verdict: 'rejected', action: 'abandon_and_propose' },
    ],
  },
  {
    proposal_id: 'prop_b', version: 1, content_hash: 'h', baseline_tree: 't', cycle_id: 'cyc_p2', run_id: 'run_2',
    submitted_at: '2026-11-01T10:12:00Z', ruling: null, outcome: null, classification: null, cycles: [{ cycle_id: 'cyc_p2', kind: 'increment' }],
  },
  {
    proposal_id: 'prop_c', version: 1, content_hash: 'h', baseline_tree: 't', cycle_id: 'cyc_p3', run_id: 'run_3',
    submitted_at: '2026-11-01T10:13:00Z', ruling: null, outcome: null, classification: null, cycles: [],
  },
  {
    proposal_id: 'prop_c', version: 2, content_hash: 'h2', baseline_tree: 't', cycle_id: 'cyc_p3', run_id: 'run_3',
    submitted_at: '2026-11-01T10:14:00Z', ruling: null, outcome: null, classification: null, cycles: [],
  },
  {
    proposal_id: 'prop_d', version: 1, content_hash: 'h', baseline_tree: 't', cycle_id: 'cyc_p4', run_id: 'run_4',
    submitted_at: '2026-11-01T10:15:00Z',
    ruling: { decision: 'approved', reason: 'ok', actor: 'svc', actor_role: 'owner', at: 'z' },
    outcome: { row: 7, ending: 'assessed', verdict: 'accepted', action: 'propose' }, classification: null, cycles: [],
  },
];

test('waiting for a ruling: the unruled latest version of each proposal, and none once the Campaign ended', () => {
  assert.deepEqual(
    waitingProposals(LEDGER, CAMPAIGN).map((e) => `${e.proposal_id} v${e.version}`),
    ['prop_b v1', 'prop_c v2'],
  );
  assert.deepEqual(waitingProposals(LEDGER, { ...CAMPAIGN, state: 'completed', outcome: 'failure' }), []);
  assert.equal(acceptedCount(LEDGER), 1);
});

test('the ledger rows say what the CLI says: ruling, verdict, the deciding row, each carrying cycle', () => {
  const [first, second] = ledgerRows(LEDGER);
  assert.deepEqual(first, {
    key: 'prop_a:1',
    proposal: 'prop_a v1',
    ruling: 'approved',
    ruled_by: 'campaign-supervisor',
    ruling_reason: 'by the written rule',
    verdict: 'rejected',
    decided_row: 13,
    ending: 'abandon_and_propose',
    cycles: ['increment cyc_p1 (row 12)', 'repair cyc_r1 (row 13)'],
    classification: 'scope_too_large',
    unbuilt: null,
  });
  assert.equal(second.ruling, null);
  assert.deepEqual(second.cycles, ['increment cyc_p2']);
});

test('open escalations are the pending ones only', () => {
  const esc = (id, state) => ({ escalation_id: id, state, kind: 'plan_review' });
  assert.deepEqual(
    openEscalations([esc('esc_1', 'resolved'), esc('esc_2', 'pending'), esc('esc_3', 'expired')]).map((e) => e.escalation_id),
    ['esc_2'],
  );
  assert.deepEqual(openEscalations(undefined), []);
});

test('the recent log is newest first and bounded', () => {
  const log = goalSetLog();
  const recent = recentLog(log, 3);
  assert.deepEqual(recent.map((e) => e.seq), [13, 12, 11]);
  assert.equal(recentLog([], 3).length, 0);
});

test('a Campaign naming no goal set has no goals link, and opening one does nothing', () => {
  const noGoals = { ...CAMPAIGN, objective: { ...CAMPAIGN.objective, goals: null, requirements: 'repo:file:docs/goals.md@current' } };
  const win = { CustomEvent: class {}, dispatchEvent: () => assert.fail('nothing is dispatched') };
  assert.equal(goalsSelection(noGoals), null);
  assert.equal(openGoals(noGoals, { win, doc: { querySelectorAll: () => assert.fail('no nav is opened') } }), false);
  assert.equal(takeAnnounced('squadops:select-campaign', win), null);
});

test('the goals link selects the Campaign in its Project and opens the Projects perspective', () => {
  const heard = [];
  const win = {
    CustomEvent: class {
      constructor(type, { detail }) {
        Object.assign(this, { type, detail });
      }
    },
    dispatchEvent: (e) => heard.push([e.type, e.detail]),
  };
  const clicked = [];
  const doc = { querySelectorAll: () => [{ textContent: 'Projects', click: () => clicked.push('Projects') }] };

  assert.equal(openGoals(CAMPAIGN, { win, doc }), true);
  const detail = { project_id: 'prj-books', campaign_id: 'cmp_one' };
  assert.deepEqual(heard, [['squadops:select-campaign', detail]]);
  assert.deepEqual(clicked, ['Projects']);
  // Kept for the goals panel to take when the Projects perspective mounts it.
  assert.deepEqual(takeAnnounced('squadops:select-campaign', win), detail);
});

test('the list: every Project\'s Campaigns newest first, a refused Project named, not fatal', async () => {
  const c = (id, project, created) => ({ ...CAMPAIGN, campaign_id: id, project_id: project, created_at: created });
  const { apiFetch, calls } = api({
    '/api/v1/projects': [200, [{ project_id: 'prj-a' }, { project_id: 'prj-b' }, { project_id: 'prj-c' }]],
    '/api/v1/campaigns': (url) => {
      if (url.includes('project_id=prj-a')) return [200, [c('cmp_a1', 'prj-a', '2026-11-01T09:00:00Z')]];
      if (url.includes('project_id=prj-b')) return [200, [c('cmp_b1', 'prj-b', '2026-11-02T09:00:00Z')]];
      return [403, envelope('FORBIDDEN', 'no')];
    },
  });
  const { campaigns, refused } = await loadCampaigns(apiFetch, '');
  assert.deepEqual(campaigns.map((x) => x.campaign_id), ['cmp_b1', 'cmp_a1']);
  assert.deepEqual(refused, [{ project_id: 'prj-c', status: 403 }]);
  // The list is paged: every read names its page.
  assert.ok(calls.filter((u) => u.startsWith('/api/v1/campaigns')).every((u) => /limit=500&offset=0/.test(u)));
});

test('the list\'s increments: a closed Campaign\'s log is read once while it stands, an open one\'s every poll', async () => {
  const log = goalSetLog();
  const { apiFetch, calls } = api({
    '/api/v1/campaigns/cmp_open/control-log': [200, log],
    '/api/v1/campaigns/cmp_done/control-log': [200, log.slice(0, 9)],
    '/api/v1/campaigns/cmp_bad/control-log': [500, envelope('INTERNAL_ERROR', 'request req_9 failed')],
  });
  const listed = [
    { campaign_id: 'cmp_open', state: 'awaiting_ruling', updated_at: 't1' },
    { campaign_id: 'cmp_done', state: 'completed', updated_at: 't1' },
    { campaign_id: 'cmp_bad', state: 'building', updated_at: 't1' },
  ];
  const cache = new Map();
  const first = await loadIncrements(apiFetch, '', listed, cache);
  assert.equal(incrementText(first.cmp_open), '#2 prop_b v1 · cyc_p2');
  assert.equal(incrementText(first.cmp_done), '#1 prop_a v1 · repair cyc_r1');
  assert.deepEqual(first.cmp_bad, { error: "cmp_bad's control log: request req_9 failed" });

  calls.length = 0;
  await loadIncrements(apiFetch, '', listed, cache);
  assert.deepEqual(calls.sort(), ['/api/v1/campaigns/cmp_bad/control-log', '/api/v1/campaigns/cmp_open/control-log']);

  // A row recorded on a closed Campaign (a late answer, a review push) moves its `updated_at`: read again.
  calls.length = 0;
  await loadIncrements(apiFetch, '', [{ ...listed[1], updated_at: 't2' }], cache);
  assert.deepEqual(calls, ['/api/v1/campaigns/cmp_done/control-log']);
});
