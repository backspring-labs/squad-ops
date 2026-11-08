// #2921: the Signal view's artifact panels read every page of every Project's artifacts, and each page
// made the API walk all of a Project's metadata, so a full read cost the square of the Project and
// held the API for minutes. Bugs caught: the newest page asked for at an offset other than 0, or
// without a limit (the API's default); a full page not flagged as more; a refusal read as empty.

import assert from 'node:assert/strict';
import { test } from 'node:test';

import { PAGE_LIMIT, fetchAllPages, fetchNewestPage } from './paging.js';

function api(pages, status = 200) {
  const asked = [];
  const apiFetch = async (url) => {
    asked.push(url);
    const offset = Number(new URL(url, 'http://x').searchParams.get('offset'));
    const page = pages[offset / PAGE_LIMIT] ?? [];
    return { ok: status < 400, status, json: async () => page };
  };
  return { apiFetch, asked };
}

const full = Array.from({ length: PAGE_LIMIT }, (_, i) => ({ id: i }));

test('the newest page is one request at offset 0, flagged when the list holds more', async () => {
  const { apiFetch, asked } = api([full, [{ id: 'older' }]]);

  const listed = await fetchNewestPage(apiFetch, '/api/v1/projects/p/artifacts');

  assert.deepEqual(asked, [`/api/v1/projects/p/artifacts?limit=${PAGE_LIMIT}&offset=0`]);
  assert.equal(listed.items.length, PAGE_LIMIT);
  assert.equal(listed.more, true);
});

test('a short newest page is the whole list', async () => {
  const { apiFetch } = api([[{ id: 1 }, { id: 2 }]]);

  const listed = await fetchNewestPage(apiFetch, '/a?type=code', 10);

  assert.deepEqual(listed, { ok: true, status: 200, items: [{ id: 1 }, { id: 2 }], more: false });
});

test('a refused page is reported, not read as an empty list', async () => {
  const { apiFetch } = api([], 401);

  assert.deepEqual(await fetchNewestPage(apiFetch, '/a'), { ok: false, status: 401, items: [], more: false });
});

test('fetchAllPages still reads until a short page', async () => {
  const { apiFetch, asked } = api([full, [{ id: 'last' }]]);

  const listed = await fetchAllPages(apiFetch, '/a');

  assert.equal(listed.items.length, PAGE_LIMIT + 1);
  assert.equal(asked.length, 2);
});
