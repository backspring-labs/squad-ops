# Plan: SIP-0094 — Per-Agent Reply Queues + Long-Lived Subscription Model

## Context

SIP-0094 replaces the orchestrator↔agent reply path. Today `_publish_and_await`
polls a per-run reply queue (`cycle_results_{run_id}`) with short-lived consumer
subscriptions, which (a) loses replies in the gap between subscriptions and (b)
leaks an orphan `cycle_results_*` queue per run. The fix mirrors the existing
dispatch-queue design: per-agent reply queues (`{agent_id}_results`, parallel to
`{agent_id}_comms`) plus a single long-lived subscription per agent, opened
**lazily on first dispatch**, with an in-process `ReplyRouter` that resolves an
`asyncio.Future` keyed by `task_id`.

This is **S1**, the runtime-substrate precondition in the 1.0.x build-reliability
hardening plan. The tactical patch (PR #89, `consume_blocking` + `invalidate_queue`)
contains the bleeding; **this work supersedes that workaround in the reply path**
(the primitives stay on the port for other callers — see D5).

- **SIP:** `sips/accepted/SIP-0094-Per-Agent-Reply-Queues-Long-Lived.md` (Rev 3, accepted 2026-06-20, PR #193)
- **Hardening plan:** `docs/plans/1-0-x-build-reliability-hardening-plan.md` (item S1)
- **Motivating incident:** `cyc_c9ca088599c0` / `run_edc1d0dc7bf4` (reply published, lost in the polling gap, task FAILED at the 1800s timeout, replies stuck in an orphan queue)

## Branch model & PR sequence

Each PR lands on a feature branch off main. **PR 94.1 and 94.2 are inert** —
nothing calls the new path until **PR 94.3, the cutover**, flips the dispatch-side
`reply_queue` value and rewrites `_publish_and_await`. PR 94.4 is soak + cleanup +
promotion.

| PR | Scope | Inert? | Deploy |
|----|-------|--------|--------|
| **94.1** | Agent-side `{agent_id}_results` declaration at startup | yes (extra unused queue) | agents first |
| **94.2** | `QueuePort.subscribe()` + `SubscriptionHandle` + RabbitMQ native override (+ default polling impl) | yes (nothing subscribes yet) | runtime-api + agents |
| **94.3** | `ReplyRouter` + `_publish_and_await` rewrite + DI wiring + `reply_queue` value flip | **no — behavior changes** | runtime-api |
| **94.4** | Soak, drop orphan `cycle_results_*` queues, promote SIP→implemented | — | ops |

> **94.2 may split if the adapter code grows** (D6/§7 is the riskiest part): **94.2a** = port shape, default `subscribe()`, `SubscriptionHandle` lifecycle; **94.2b** = RabbitMQ native `subscribe()` + channel-close recovery + integration tests. Keeps the risky adapter code isolated and reviewable.

**Deploy ordering is a safety preference, not a correctness dependency** (see D9):
deploy agents (94.1) before the runtime-api cutover (94.3) so `{agent_id}_results`
already exists, but the cutover declares idempotently regardless.

## Binding decisions

Resolve the SIP §10 open questions, the three impl-notes, and the long-lived-consumer
robustness gaps that a polling loop never had to handle.

- **D1 — `on_message` is async.** The router awaits `queue.ack(msg)` inside it. `subscribe(queue_name, *, on_message: Callable[[QueueMessage], Awaitable[None]])`.
- **D2 — Router does NOT survive runtime-api restart.** In-process futures vanish on restart; an in-flight reply is ack'd-and-dropped on next boot. Durable resume is the SIP-0079 resume-contract's job, out of scope here.
- **D3 — `{agent_id}_results` is durable, non-exclusive, `auto_delete=False`** (same args as `{agent_id}_comms`). Exclusive would block multiple runtime-api instances behind a load balancer; single-consumer is enforced by convention. **Declaration args MUST be identical everywhere** — agent `ensure_queue`, orchestrator `subscribe`, and any manual creation — via a single shared constant/helper (e.g. `REPLY_QUEUE_DECLARE_ARGS`), since a mismatch on a durable queue causes broker `PRECONDITION_FAILED`. A unit test asserts the helper is the only source of declare args.
- **D4 — `ensure_subscribed` is guarded by an `asyncio.Lock`.** Dispatch is sequential within a run, but `_execute_fan_out` (`dispatched_flow_executor.py:2402`) can dispatch concurrently; two concurrent first-dispatches to one agent must not open two subscriptions.
- **D5 — `consume()`/`consume_blocking()`/`invalidate_queue()` STAY on `QueuePort`** (SIP §6). Only the executor's *use* of `consume_blocking`+`invalidate_queue` in the reply path is removed in 94.3. This is what "supersedes, not layers on" the PR #89 patch means concretely.
- **D6 — Default `subscribe()` polls `consume_blocking()`; the native RabbitMQ override is THE structural fix.** The default exists only for non-RabbitMQ adapters and tests — it is explicitly NOT the SIP-0094 fix and must not be treated as satisfying it. `NoOpQueuePort` inherits the default and never fires a callback (its `consume()` returns `[]`) — fine for tests.
- **D7 — Observability ships in 94.3** (see Observability section). At minimum a late-drop counter, plus the metrics needed to make the channel-close recovery (the riskiest path) observable during soak.
- **D8 — Harden `TaskResult.from_dict` to ignore unknown keys.** It currently does `cls(**data)` (`tasks/models.py:109`), unlike `TaskEnvelope.from_dict` which filters. A forward-incompatible result payload would otherwise raise inside `_handle_reply` and (without D11) could strand the consumer.
- **D9 — 94.1 is a rollout-safety + observability step, NOT a correctness dependency.** `ReplyRouter.ensure_subscribed()` / `QueuePort.subscribe()` MUST declare `{agent_id}_results` idempotently before publishing, so the cutover never assumes the agent pre-declared the queue. A future implementer must not bake in that assumption.
- **D10 — `register(task_id)` raises a typed `DuplicateRegistration` error if a future is already pending for that `task_id`.** It must never silently overwrite an existing future — that would strand the first waiter on the shared per-agent queue.
- **D11 — `_handle_reply` must never strand the consumer.** Parse `json.loads(msg.payload)["payload"]["task_id"]`. On malformed payload (bad JSON / missing `task_id`): log, increment a malformed-reply counter, ack/drop (or nack-without-requeue per adapter capability). On unknown/late `task_id` (no pending future): ack, increment the late-drop counter. If `TaskResult.from_dict` fails: log, fail the matching future if one exists, drop the bad message — do not let the exception kill the long-lived consumer task.
- **D12 — `subscribe()` isolates callback exceptions.** Both the native and default impls catch exceptions from `on_message`, log, apply the ack/nack policy, and **continue consuming**. A single bad callback invocation must not terminate the durable subscription.
- **D13 — Graceful shutdown ordering.** Runtime shutdown stops accepting new dispatches before calling `ReplyRouter.stop()`. The router carries a `stopped` state: once stopping, `ensure_subscribed()` and `register()` fail fast (typed error), so a late dispatch can't register a future while subscriptions are being cancelled. Document the lifespan ordering in `main.py` if it already guarantees this; otherwise enforce via the stopped state.
- **D14 — `task_id` is the global correlation key.** Per-queue subscription already gives per-agent isolation: a reply on `{agent_id}_results` came, by construction, from a dispatch to that agent. Global uniqueness across normal / repair / correction task_ids is the only requirement (tested per SIP Risk 2). An explicit agent-identity match in the reply is **optional defense-in-depth** and is deferred — the reply envelope (`TaskResult` + `{correlation_id}`) carries no `agent_id` today, so it would require a payload addition.

## Cross-cutting requirements (every PR)

- No change to the per-task timeout (`SQUADOPS__LLM__TIMEOUT=1800`).
- No change to the agent `_consume_tasks` loop (SIP §4 non-goal — same churn class, tolerable because the comms queue is rarely idle).
- The published dispatch-message dict shape is preserved (`action`/`metadata`/`payload: envelope.to_dict()`); only the `reply_queue` *value* changes (94.3).
- `task_id` stays the correlation key (matched at `dispatched_flow_executor.py:733`); no new field.
- Every PR keeps the regression suite green: `./scripts/dev/run_regression_tests.sh -v`.

---

## PR 94.1 — Agent-side `{agent_id}_results` declaration (deploy-first, inert)

**Goal:** ensure each agent's `{agent_id}_results` queue exists before runtime-api
ever addresses it — a **defensive rollout step (D9)**, not a correctness source.

**Finding that shapes this PR:** agents do **not** explicitly declare their
`{agent_id}_comms` queue today — declaration is lazy inside
`RabbitMQAdapter._get_queue()` (`adapters/comms/rabbitmq.py:82`) on the first
`consume()`. There is no existing explicit-declare line to sit beside, and the
agent only *publishes* to (never consumes from) its `_results` queue, so lazy
declaration won't cover it.

### Modified / new files
- `src/squadops/ports/comms/queue.py` — add `ensure_queue(self, queue_name: str) -> None` (concrete default = no-op so NoOp works). Add the shared `REPLY_QUEUE_DECLARE_ARGS` constant (D3).
- `adapters/comms/rabbitmq.py` — implement `ensure_queue` as a thin wrapper over `_get_queue(queue_name)` using `REPLY_QUEUE_DECLARE_ARGS`.
- `src/squadops/ports/comms/noop.py` — inherits the no-op default.
- `src/squadops/agents/entrypoint.py` — at startup (in `start()` after the adapter is built at `:351-352`, or top of `_consume_tasks` after `:438`): `await self._queue.ensure_queue(f"{self.agent_id}_results")`.

### Tests
- `tests/unit/comms/test_rabbitmq_adapter.py` — `ensure_queue` declares with the shared args; idempotent across channel swap (extend `TestQueueCacheInvalidation` `:30`).
- `tests/unit/agents/test_entrypoint_task.py` — agent startup calls `ensure_queue("{agent_id}_results")` exactly once.
- Deploy: `rebuild_and_deploy.sh agents` before 94.3.

---

## PR 94.2 — `QueuePort.subscribe()` + `SubscriptionHandle` + RabbitMQ native impl (inert)

**Goal:** add the long-lived subscription primitive. Dormant — no caller yet.

### Modified / new files
- `src/squadops/ports/comms/queue.py` — add `SubscriptionHandle` (with `async cancel()`) and `subscribe(self, queue_name, *, on_message) -> SubscriptionHandle` as a **concrete default** (D6): a background task looping `consume_blocking()` → `on_message`, with **callback exception isolation (D12)**; `cancel()` stops the task.
- `adapters/comms/rabbitmq.py` — **native override**: long-lived `queue.iterator(no_ack=False)` (or registered consumer) on the queue, dispatching each delivery to `on_message` with D12 isolation.
- `src/squadops/ports/comms/noop.py` — inherits default.

### The hard part — channel-close resubscribe (SIP §7 Risk 1)

**Today `RabbitMQAdapter` shares one `RobustChannel` and registers NO close
callbacks** (`adapters/comms/rabbitmq.py:50-58`); staleness is detected reactively
via the `cached.channel is self._channel` check in `_get_queue` (`:66-85`). A
long-lived consumer can't poll for staleness — it must be *resumed* when its
channel dies. So native `subscribe()` must: (1) register `add_close_callback`,
(2) on close re-`_ensure_connection()` + re-declare (the `_get_queue` `is
self._channel` path gives re-declaration), (3) re-establish the consumer.
Re-declaration is reusable; **consumer resumption is genuinely new code** and the
riskiest part of the SIP — emit resubscribe metrics (D7) and test it directly.

### Tests
- `tests/unit/adapters/test_queue_port.py` — default `subscribe()`: published message reaches `on_message`; `cancel()` stops delivery; **a raising `on_message` does not stop the loop** (D12).
- `tests/unit/comms/test_rabbitmq_adapter.py` — native `subscribe()`: happy path; **channel-close triggers transparent re-subscribe** (simulate close, assert a post-reconnect message is delivered); `cancel()` cleans up the consumer tag; raising `on_message` does not kill the consumer (D12).
- `tests/integration/adapters/test_rabbitmq_adapter.py` — **new (SIP §8):** publish 100 replies to one `{agent_id}_results` queue with a single held subscriber → all 100 routed, zero lost; compare against the legacy `consume()` path.
- `tests/integration/adapters/test_rabbitmq_adapter.py` — **new (multi-agent, #12):** subscribe to ≥2 `{agent_id}_results` queues, publish interleaved replies to both, assert each future resolves exactly once with **no cross-agent delivery**.

---

## PR 94.3 — `ReplyRouter` + `_publish_and_await` rewrite + DI wiring (CUTOVER)

**Goal:** route replies through the long-lived per-agent subscription. Behavior
changes here.

### New file — `adapters/cycles/reply_router.py`
`ReplyRouter` per SIP §5.3, with the D-decisions baked in:
- `ensure_subscribed(agent_id)` — idempotent, **lock-guarded (D4)**, declares the queue idempotently (D9), fails fast if stopped (D13).
- `register(task_id) -> Future` — **raises `DuplicateRegistration` on a pending task_id (D10)**, fails fast if stopped (D13).
- `_handle_reply(msg)` — **robust per D11** (malformed → log+count+ack/drop; unknown/late → ack+count; `from_dict` failure → log+fail-future-if-present+drop; never strands the consumer). `TaskResult.from_dict` hardened per D8.
- `cancel(task_id)`, `stop()` (set stopped state, cancel subscriptions, fail pending futures with `ReplyRouterStopped`).

Confirmed shapes: `QueueMessage.payload` is a raw JSON string (`comms/queue_message.py:24`); the agent reply envelope is `{"action":"comms.task.result","metadata":{...},"payload": result.to_dict()}` (`entrypoint.py:726-730`) → `data["payload"]["task_id"]` resolves. ✓

### Rewrite — `adapters/cycles/dispatched_flow_executor.py:669-743`
`_publish_and_await` before → after:
- **Remove** `reply_queue = f"cycle_results_{run_id}"` (`:675`) and the entire `while`/`consume_blocking`/`invalidate_queue`/`asyncio.sleep` recovery block (`:697-743`).
- **Add:** `await self._reply_router.ensure_subscribed(envelope.agent_id)` → `fut = self._reply_router.register(envelope.task_id)` → set `reply_queue = f"{envelope.agent_id}_results"` in the message metadata (`:680`) → `publish(f"{envelope.agent_id}_comms", ...)` → `await asyncio.wait_for(fut, timeout=self._task_timeout)`.
- **Ordering (D14/#2):** `ensure_subscribed → register → publish` — the consumer is live before any reply can arrive (no first-dispatch race). A pre-existing message for the same `task_id` would be dropped before registration, which is impossible given global `task_id` uniqueness (covered by the cross-run test).
- **Publish-failure cleanup (#10):** wrap `publish` so that if it raises *after* `register()`, the future is cancelled/removed before returning/raising — no pending-future leak when the agent never received the task.
- **Pending-future leak invariant (#9):** on EVERY exit path — success, timeout (`cancel(task_id)`), publish failure, router failure, cancellation — `task_id` must not remain pending. Asserted by tests.
- All **6 dispatch call sites** (`:1199, 2144, 2319, 2426, 2903`) inherit this via the single `_publish_and_await`. `_task_heartbeat` (`:586`) and `_dispatch_task` (`:614`) untouched.

### Executor `__init__` + DI wiring
- `dispatched_flow_executor.py:89` — add `reply_router: ReplyRouter | None = None`; store `self._reply_router`.
- `adapters/cycles/factory.py:102` (provider `"dispatched"`, only construction site) — accept + pass `reply_router`.
- `src/squadops/api/runtime/main.py` — in `_init_cycle_subsystem` (after `queue_adapter` `:275`): construct `ReplyRouter(queue_adapter)`, stash in a module global (pattern `:139-143`), pass into `create_flow_executor` (`:295`). In `@app.on_event("shutdown")` (`:430-449`): per **D13**, stop accepting dispatches first, then `await _reply_router.stop()` (beside `_workflow_tracker.close()`).

### Observability (D7 / #6)
Emit (counters/gauges + structured logs), labelled by `agent_id` where applicable:
- reply-router subscriptions opened
- resubscribe attempts (+ reason)
- late-reply drops
- malformed replies
- pending futures (gauge)
- reply-wait timeouts
Soak (94.4) checks these.

### Test migration (the §6 work — ~40 executor tests)
`tests/unit/cycles/test_dispatched_flow_executor.py` drives the wait path via the
`mock_queue` shim (`:109-125`). Post-cutover the executor awaits the router, not
the queue. Migrate by injecting a fake `ReplyRouter` whose `register()` returns a
controllable future. Three helpers gate the bulk:
- `mock_queue` fixture (`:109`) → add a `reply_router` fixture.
- `_make_result_message` (`:42`, default `cycle_results_run_001`) → router-result helper.
- pulse `_consume_side_effect` keyed on `startswith("cycle_results_")` (`:2565`) → re-key on the router.
- **Obsolete:** `test_recovers_from_transient_consume_error` (`:609`, asserts `invalidate_queue` `:660`), `test_uses_long_block_consume_not_short_poll` (`:662`). `test_publishes_to_agent_comms_queue` (`:494`) updates its `reply_queue` assertion (`:548`) → `{agent_id}_results`.

### New tests
- `tests/unit/cycles/test_reply_router.py`: register/resolve by `task_id`; **duplicate `register()` raises typed error (D10)**; late reply → drop + counter (D11); **malformed payload → log+count, consumer survives (D11)**; `from_dict` failure → fails the future, consumer survives (D11); `stop()` fails pending futures with the typed error; `ensure_subscribed` idempotent + **concurrency-safe (D4)**; `ensure_subscribed`/`register` fail fast once stopped (D13).
- `_publish_and_await`: registers before publishing; resolves on reply; timeout → cancels future + FAILED; **publish failure after register removes the pending future (#10)**; **no path leaves `task_id` pending (#9)**.
- **Concurrent first-dispatch at executor level (#13):** two concurrent `_publish_and_await` for the same `agent_id` → exactly one subscription opened, both futures resolve, both publish to the same `{agent_id}_results`.
- **Cross-run / global uniqueness (SIP Risk 2 / D14):** two runs' `task-{run_id[:12]}-...` ids don't collide on a shared queue; cover a correction/repair id (`dispatched_flow_executor.py:2092,2259`) too.

---

## PR 94.4 — Soak, orphan cleanup, promote

1. **Soak** in Spark dev for one full long-cycle build (SIP E2E): re-run a `group_run`
   cycle; verify no `cycle_results_*` queues are created, `{agent_id}_results` queues
   exist and drain to zero after the run, a late dispatch completes in peer wall time,
   and the **late-drop / malformed counters are zero or understood**.
2. **Guarded orphan cleanup (#15):** before deleting, list queues and confirm —
   no active runtime-api is still on the legacy path; target queues have **zero
   consumers**; target queues are **older than the cutover timestamp**; names match
   the **exact prefix `cycle_results_`**. **Never touch any `{agent_id}_results`
   queue.** One-shot `rabbitmqctl`, not code.
3. **Promote only when (#17):** soak passed, no new `cycle_results_*` created, all
   `{agent_id}_results` drain to zero, late-drop/malformed counters zero-or-understood,
   the rollback window has passed, and orphan cleanup is done (or explicitly deferred
   with an owner + date). Then: `SQUADOPS_MAINTAINER=1 python scripts/maintainer/update_sip_status.py sips/accepted/SIP-0094-Per-Agent-Reply-Queues-Long-Lived.md implemented`.

## Rollback (#16)

- **94.1 / 94.2 are inert** — leave them deployed; they're compatible with the legacy path.
- **If 94.3 fails:** roll runtime-api back to the previous image. Agents carrying extra `{agent_id}_results` queues remain compatible with the old `cycle_results_{run_id}` path.
- **Do not drop `cycle_results_*` queues until after soak AND the rollback window** — the legacy path needs them on rollback.
- If rollback happens after some `{agent_id}_results` queues accumulated messages, inspect and purge **only after confirming no 94.3 runtime is active**.

## Risks & mitigations

| Risk | Mitigation | PR |
|------|-----------|----|
| Long-lived consumer channel death strands waits | Native `subscribe()` close-callback + re-declare + re-consume; resubscribe metric; direct test | 94.2 |
| Mismatched durable-queue declare args → broker `PRECONDITION_FAILED` | Single shared `REPLY_QUEUE_DECLARE_ARGS` helper used everywhere + test (D3) | 94.1/94.3 |
| One bad reply payload kills the consumer | D11 robust `_handle_reply` + D12 callback isolation | 94.2/94.3 |
| Pending-future leak (publish fail, exceptional exit) | #9 invariant + #10 publish-failure cleanup + tests | 94.3 |
| Duplicate `task_id` overwrites a waiter | D10 typed `DuplicateRegistration` | 94.3 |
| Late dispatch registers a future during shutdown | D13 stopped-state + shutdown ordering | 94.3 |
| Cross-run `task_id` collision on shared queue | `run_id[:12]` prefix + deliberate test (D14) | 94.3 |
| Default polling impl mistaken for the fix | D6 explicit caveat | 94.2 |
| Deploy ordering | Agents (94.1) before runtime-api cutover (94.3); idempotent declare (D9) | rollout |

## Acceptance criteria

- **Unit/integration:** all new tests pass; the ~40 migrated executor tests pass against the router; the 100-reply single-subscriber and the multi-agent interleaved tests show zero loss / no cross-agent delivery; full regression green.
- **Robustness invariants proven by test:** duplicate `task_id` registration fails fast (typed error); publish failure after registration removes the pending future; callback exceptions do not terminate the subscription; malformed reply payloads are logged, counted, and don't kill the subscription; concurrent first-dispatches to one agent create exactly one subscription; queue declare args are identical across agent startup and orchestrator subscribe; runtime shutdown prevents new future registration before router stop; no `_publish_and_await` exit path leaves a pending future.
- **E2E (the original failure mode):** re-run the incident cycle on a clean stack — the previously-lost late reply is delivered within normal wall time; **no `cycle_results_*` queue is created**; `{agent_id}_results` queues exist and drain to zero after the run.
- **Operational:** rollback from 94.3 to the legacy path is documented and validated; observability counters are emitted and checked during soak.
- **No regression** to the per-task timeout, agent comms loop, or dispatch-message shape.

## References

- `sips/accepted/SIP-0094-Per-Agent-Reply-Queues-Long-Lived.md` (full design; §5 approach / §7 risks / §8 test plan / §9 rollout / §10 open questions resolved by D1–D14)
- Tactical patch PR #89 (`fix/cycle-results-channel-recovery`) — superseded in the reply path per D5
- #186 (executor decomposition) — overlaps the dispatch-transport seam (`_publish_and_await`/`_dispatch_task`); implement S1 in place, let #186 extract `TaskDispatcher` around the new subscription model later
- Current-state code map: `_publish_and_await` (`dispatched_flow_executor.py:669`), `QueuePort` (`ports/comms/queue.py`), `RabbitMQAdapter._get_queue`/`consume_blocking` (`adapters/comms/rabbitmq.py:66/212`), agent reply (`agents/entrypoint.py:661/731`), boot wiring (`api/runtime/main.py:275/295/430`)

## Revision history

- **2026-06-21 — Rev 2.** Incorporated review feedback: 94.1 reframed as defensive not load-bearing (D9); added duplicate-registration guard (D10), `_handle_reply` robustness (D11), callback exception isolation (D12), shutdown ordering/stopped-state (D13), global-key + per-queue isolation rationale (D14); shared declare-args helper (D3); native-is-the-fix caveat (D6); publish-failure cleanup + pending-future leak invariant in the rewrite; Observability, Rollback sections; multi-agent + concurrent-executor tests; guarded orphan cleanup + conditional promotion; optional 94.2 split.
- **2026-06-20 — Rev 1.** Initial phased plan grounded in the current dispatch/reply code.
