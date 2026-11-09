// The Continuum command bus, as the pinned shell answers it (console/continuum.lock, v1.0.3).
// Every console write goes through it (SIP-0074 §5.1): `POST /api/commands/execute` with
// `{command_id, args, dry_run, confirmed}` (the shell's `CommandExecuteRequestBody`,
// `src/continuum/adapters/web/api.py:79-85`), answered 200 with `{command_id, status, result,
// error, requires_confirmation, danger_level, audit_id, duration_ms}`:
//   - `success`: the handler ran, and `result` is what it returned;
//   - `pending` with `requires_confirmation: true`: a `confirm`/`danger` command sent without
//     `confirmed: true`. Nothing ran (`app/command_bus.py:293-303`). The caller is asked, and on
//     yes the same body is sent again with `confirmed: true`;
//   - `failed`, `timeout` or `denied`: nothing happened, and `error` says why (`:401-421`).
// The handler is called with `args` (`:357`) and unknown body keys are dropped.
//
// #2903: the plugins posted `params`, so every handler got `{}`, raised, and the bus's 200
// `failed` passed as success because only `resp.ok` was read. #2904: no plugin sent `confirmed`,
// so a confirm-level command's `pending` answer passed as success too. The plugins' bodies are
// built here and nowhere else (tests/unit/console/test_command_bus_bodies.py).
//
// The console app's handlers (console/app/main.py) answer `{error, status_code}` when the runtime
// API refused; the bus reports that as `success`, so it is read here as the refusal it is, with
// the API's status (a gate decided twice is the API's 409).
//
// The route is the console's own, whatever `apiBaseUrl` names: the shell mounts it beside the
// registry, and Caddy sends it to the console (console/Caddyfile).

export const COMMAND_ROUTE = '/api/commands/execute';

/** The route, the bus or the handler refused: the command did not run, or ran and was refused. */
export class CommandError extends Error {
  constructor(message, { commandId, commandStatus = null, status = undefined, answer = null } = {}) {
    super(message);
    this.name = 'CommandError';
    this.commandId = commandId;
    // The bus's `status` (`failed`, `timeout`, `denied`; `success` when the handler relayed the
    // runtime API's refusal), or null when the route itself answered outside 2xx.
    this.commandStatus = commandStatus;
    // An HTTP status: the route's refusal, or the runtime API's that the handler relayed.
    this.status = status;
    this.answer = answer;
  }
}

/** The bus asked for confirmation and the user said no: nothing ran, and nothing is wrong. */
export class CommandDeclined extends Error {
  constructor(commandId, answer) {
    super(`${commandId}: not confirmed`);
    this.name = 'CommandDeclined';
    this.commandId = commandId;
    this.answer = answer;
  }
}

// The dialog a caller gives none of its own: it names the command and the danger level the bus
// answered. With no dialog to ask (no window), the answer is no.
function askInTheBrowser(answer) {
  if (typeof globalThis.confirm !== 'function') return false;
  return globalThis.confirm(
    `${answer.command_id} asks for confirmation (danger level: ${answer.danger_level}). Run it?`,
  );
}

async function post(apiFetch, body) {
  const resp = await apiFetch(COMMAND_ROUTE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const text = await resp.text();
  if (!resp.ok) {
    throw new CommandError(text || `${body.command_id}: the command route answered ${resp.status}`, {
      commandId: body.command_id,
      status: resp.status,
    });
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new CommandError(`${body.command_id}: the command route answered no JSON`, {
      commandId: body.command_id,
      status: resp.status,
    });
  }
}

/**
 * Runs `commandId` with `args` on the bus and returns the handler's result.
 *
 * When the bus answers `requires_confirmation`, `confirm(answer)` is asked (the bus's answer, with
 * its `command_id` and `danger_level`; it may be async) and on yes the same body is sent again
 * with `confirmed: true`. A no rejects with `CommandDeclined`. Any answer but `success`, and a
 * handler's `{error, status_code}`, rejects with `CommandError`.
 */
export async function executeCommand(apiFetch, commandId, args, { confirm = askInTheBrowser } = {}) {
  const body = { command_id: commandId, args };
  let answer = await post(apiFetch, body);
  if (answer.status === 'pending' && answer.requires_confirmation) {
    if (!(await confirm(answer))) throw new CommandDeclined(commandId, answer);
    answer = await post(apiFetch, { ...body, confirmed: true });
  }
  if (answer.status !== 'success') {
    throw new CommandError(
      answer.error || answer.result?.message || `${commandId}: ${answer.status ?? 'no status'}`,
      { commandId, commandStatus: answer.status ?? null, answer },
    );
  }
  const result = answer.result ?? {};
  if (result.error) {
    throw new CommandError(result.error, {
      commandId,
      commandStatus: answer.status,
      status: result.status_code,
      answer,
    });
  }
  return result;
}
