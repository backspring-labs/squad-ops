// A selection handed across perspectives (`selection.js`), under node's own runner. Bugs caught:
// a selection dispatched while the receiving panel isn't mounted being lost (the shell mounts only
// the open perspective's panels); one taken twice, so an old Campaign re-selects itself on a later
// visit; a nav entry clicked by a partial label, or a missing one answered as opened.

import assert from 'node:assert/strict';
import { test } from 'node:test';

import { OPEN_CREATE_CYCLE, announce, openCreateCycle, openNav, takeAnnounced } from './selection.js';

class FakeEvent {
  constructor(type, { detail }) {
    this.type = type;
    this.detail = detail;
  }
}

function fakeWindow() {
  const heard = [];
  return {
    CustomEvent: FakeEvent,
    heard,
    dispatchEvent(e) {
      heard.push([e.type, e.detail]);
      return true;
    },
  };
}

test('a selection announced with no listener is taken once by the panel that mounts later', () => {
  const win = fakeWindow();
  const detail = { project_id: 'prj-a', campaign_id: 'cmp_1' };

  announce('squadops:select-campaign', detail, win);

  assert.deepEqual(win.heard, [['squadops:select-campaign', detail]]);
  assert.deepEqual(takeAnnounced('squadops:select-campaign', win), detail);
  assert.equal(takeAnnounced('squadops:select-campaign', win), null);
});

test('the latest announcement wins, and another name is kept apart', () => {
  const win = fakeWindow();
  announce('squadops:select-campaign', { campaign_id: 'cmp_1' }, win);
  announce('squadops:select-project', { project_id: 'prj-b' }, win);
  announce('squadops:select-campaign', { campaign_id: 'cmp_2' }, win);

  assert.deepEqual(takeAnnounced('squadops:select-campaign', win), { campaign_id: 'cmp_2' });
  assert.deepEqual(takeAnnounced('squadops:select-project', win), { project_id: 'prj-b' });
});

test('nothing announced: nothing to take', () => {
  assert.equal(takeAnnounced('squadops:select-campaign', fakeWindow()), null);
});

function fakeDocument(labels) {
  const clicked = [];
  const items = labels.map((label) => ({
    textContent: `\n  ${label}\n`,
    click: () => clicked.push(label),
  }));
  return { clicked, querySelectorAll: (sel) => (sel === '.nav-item' ? items : []) };
}

test('openNav clicks the entry whose label is exactly the one named', () => {
  const doc = fakeDocument(['Projects list', 'Projects', 'Campaigns']);
  assert.equal(openNav('Projects', doc), true);
  assert.deepEqual(doc.clicked, ['Projects']);
});

test('openNav answers false, and clicks nothing, when the shell shows no such entry', () => {
  const doc = fakeDocument(['Cycles', 'Memory']);
  assert.equal(openNav('Projects', doc), false);
  assert.deepEqual(doc.clicked, []);
  assert.equal(openNav('Projects', undefined), false);
});

// #2909: Home's "Create Cycle" called a window function the console never defines, so it did
// nothing. Bugs caught: the request lost because the Cycles panel isn't mounted when it's sent;
// the wrong perspective opened; a request left behind to reopen the form on a later visit.
test("Home's Create Cycle opens Cycles with the request held for the panel that mounts", () => {
  const win = fakeWindow();
  const doc = fakeDocument(['Home', 'Cycles', 'Campaigns']);

  assert.equal(openCreateCycle({ win, doc }), true);

  assert.deepEqual(doc.clicked, ['Cycles']);
  assert.deepEqual(win.heard, [[OPEN_CREATE_CYCLE, {}]]);
  assert.deepEqual(takeAnnounced(OPEN_CREATE_CYCLE, win), {});
  assert.equal(takeAnnounced(OPEN_CREATE_CYCLE, win), null);
});

test('with no Cycles entry, Create Cycle says so and keeps the request for the next visit', () => {
  const win = fakeWindow();
  const doc = fakeDocument(['Home']);

  assert.equal(openCreateCycle({ win, doc }), false);

  assert.deepEqual(doc.clicked, []);
  assert.deepEqual(takeAnnounced(OPEN_CREATE_CYCLE, win), {});
});
