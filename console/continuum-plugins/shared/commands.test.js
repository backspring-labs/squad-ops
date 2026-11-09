// #2903/#2904: what `executeCommand` sends to the pinned shell's command route and how it reads
// the answer. Node's own runner (`npm test` here; the console image's node 20 has it), no
// dependencies. Bugs caught: the body keyed `params` again; `resp.ok` read as success; the bus's
// `pending` or `failed` read as success; `confirmed: true` sent before the bus asked, or not sent
// after the user said yes; a handler's relayed refusal read as success.

import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';

import { COMMAND_ROUTE, CommandDeclined, CommandError, executeCommand } from './commands.js';

// A fake `apiFetch` answering each post from `answers` in turn, recording what was posted.
function bus(...answers) {
  const posts = [];
  const apiFetch = async (url, opts) => {
    posts.push({ url, method: opts.method, contentType: opts.headers['Content-Type'], body: JSON.parse(opts.body) });
    const next = answers.shift();
    if (next === undefined) throw new Error('the bus was posted to more often than the test answered');
    const [httpStatus, answer] = Array.isArray(next) ? next : [200, next];
    return {
      ok: httpStatus >= 200 && httpStatus < 300,
      status: httpStatus,
      text: async () => (typeof answer === 'string' ? answer : JSON.stringify(answer)),
    };
  };
  return { apiFetch, posts };
}

const ARGS = { project_id: 'p-1', cycle_id: 'c-1', run_id: 'r-1', gate_name: 'plan_review' };

afterEach(() => {
  delete globalThis.confirm;
});

test('posts {command_id, args} to the command route and returns the handler\'s result', async () => {
  const { apiFetch, posts } = bus({ command_id: 'squadops.gate_approve', status: 'success', result: { decision: 'approved' } });

  const result = await executeCommand(apiFetch, 'squadops.gate_approve', ARGS);

  assert.deepEqual(result, { decision: 'approved' });
  assert.deepEqual(posts, [
    {
      url: COMMAND_ROUTE,
      method: 'POST',
      contentType: 'application/json',
      body: { command_id: 'squadops.gate_approve', args: ARGS },
    },
  ]);
});

test('re-posts the same body with confirmed: true when the bus asks and the caller says yes', async () => {
  const asked = { command_id: 'squadops.gate_reject', status: 'pending', requires_confirmation: true, danger_level: 'confirm', result: { message: 'This command requires confirmation (danger level: confirm)' } };
  const { apiFetch, posts } = bus(asked, { command_id: 'squadops.gate_reject', status: 'success', result: { decision: 'rejected' } });
  const seen = [];

  const result = await executeCommand(apiFetch, 'squadops.gate_reject', ARGS, {
    confirm: async (answer) => { seen.push(answer); return true; },
  });

  assert.deepEqual(result, { decision: 'rejected' });
  assert.deepEqual(seen, [asked], 'the dialog is given the bus\'s answer');
  assert.deepEqual(posts.map((p) => p.body), [
    { command_id: 'squadops.gate_reject', args: ARGS },
    { command_id: 'squadops.gate_reject', args: ARGS, confirmed: true },
  ]);
});

test('does not re-post when the caller says no, and the decline is not an error', async () => {
  const { apiFetch, posts } = bus({ command_id: 'squadops.gate_reject', status: 'pending', requires_confirmation: true, danger_level: 'confirm' });

  await assert.rejects(
    executeCommand(apiFetch, 'squadops.gate_reject', ARGS, { confirm: () => false }),
    (err) => err instanceof CommandDeclined && !(err instanceof CommandError) && err.commandId === 'squadops.gate_reject',
  );
  assert.equal(posts.length, 1);
});

test('with no dialog of its own, the caller is asked in the browser, naming the command and its danger level', async () => {
  const { apiFetch, posts } = bus(
    { command_id: 'squadops.set_active_profile', status: 'pending', requires_confirmation: true, danger_level: 'confirm' },
    { command_id: 'squadops.set_active_profile', status: 'success', result: { profile_id: 'full' } },
  );
  const messages = [];
  globalThis.confirm = (message) => { messages.push(message); return true; };

  await executeCommand(apiFetch, 'squadops.set_active_profile', { profile_id: 'full' });

  assert.deepEqual(messages, ['squadops.set_active_profile asks for confirmation (danger level: confirm). Run it?']);
  assert.equal(posts[1].body.confirmed, true);
});

test('with no dialog at all (no window), the bus\'s question is answered no', async () => {
  const { apiFetch, posts } = bus({ command_id: 'squadops.set_active_profile', status: 'pending', requires_confirmation: true, danger_level: 'confirm' });

  await assert.rejects(executeCommand(apiFetch, 'squadops.set_active_profile', { profile_id: 'full' }), CommandDeclined);
  assert.equal(posts.length, 1);
});

test('a second pending answer after confirming is a failure, not a loop', async () => {
  const pending = { command_id: 'squadops.gate_reject', status: 'pending', requires_confirmation: true, danger_level: 'confirm', result: { message: 'still asking' } };
  const { apiFetch, posts } = bus(pending, pending);

  await assert.rejects(
    executeCommand(apiFetch, 'squadops.gate_reject', ARGS, { confirm: () => true }),
    (err) => err instanceof CommandError && err.commandStatus === 'pending' && err.message === 'still asking',
  );
  assert.equal(posts.length, 2);
});

for (const status of ['failed', 'timeout', 'denied']) {
  test(`a 200 answer with status ${status} rejects with the bus's error`, async () => {
    const { apiFetch } = bus({ command_id: 'squadops.create_cycle', status, error: `KeyError: 'project_id'`, audit_id: 'a-1' });

    await assert.rejects(
      executeCommand(apiFetch, 'squadops.create_cycle', {}),
      (err) => err instanceof CommandError && err.commandStatus === status && err.status === undefined && err.message === `KeyError: 'project_id'`,
    );
  });
}

test('a handler\'s relayed refusal is a failure carrying the runtime API\'s status', async () => {
  const { apiFetch } = bus({ command_id: 'squadops.gate_approve', status: 'success', result: { error: '{"detail":"gate already decided"}', status_code: 409 } });

  await assert.rejects(
    executeCommand(apiFetch, 'squadops.gate_approve', ARGS),
    (err) => err instanceof CommandError && err.status === 409 && err.commandStatus === 'success' && err.message.includes('already decided'),
  );
});

test('the route\'s own refusal is a failure carrying its HTTP status and body', async () => {
  const { apiFetch } = bus([422, '{"detail":[{"loc":["body","command_id"]}]}']);

  await assert.rejects(
    executeCommand(apiFetch, 'squadops.gate_approve', ARGS),
    (err) => err instanceof CommandError && err.status === 422 && err.commandStatus === null && err.message.includes('command_id'),
  );
});

test('an answer that is not JSON is a failure, not a success', async () => {
  const { apiFetch } = bus([200, '<html>signed out</html>']);

  await assert.rejects(
    executeCommand(apiFetch, 'squadops.gate_approve', ARGS),
    (err) => err instanceof CommandError && err.message === 'squadops.gate_approve: the command route answered no JSON',
  );
});
