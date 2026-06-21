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
(the primitives stay on the port for other callers — see Binding Decision D5).

- **SIP:** `sips/accepted/SIP-0094-Per-Agent-Reply-Queues-Long-Lived.md` (Rev 3, accepted 2026-06-20, PR #193)
- **Hardening plan:** `docs/plans/1-0-x-build-reliability-hardening-plan.md` (item S1)
- **Motivating incident:** `cyc_c9ca088599c0` / `run_edc1d0dc7bf4` (reply published, lost in the polling gap, task FAILED at the 1800s timeout, replies stuck in an orphan queue)

## Branch model & PR sequence

Each PR lands on a feature branch off main. **PR 94.1 and 94.2 are inert** — they
add a defensively-declared queue and a dormant `subscribe()` primitive; nothing
calls the new path until **PR 94.3, the cutover**, flips the dispatch-side
`reply_queue` value and rewrites `_publish_and_await`. PR 94.4 is soak + cleanup +
promotion.

| PR | Scope | Inert? | Deploy |
|----|-------|--------|--------|
| **94.1** | Agent-side `{agent_id}_results` declaration at startup | yes (extra unused queue) | **agents first** |
| **94.2** | `QueuePort.subscribe()` + `SubscriptionHandle` + RabbitMQ native override (+ default polling impl) | yes (nothing subscribes yet) | runtime-api + agents |
| **94.3** | `ReplyRouter` + `_publish_and_await` rewrite + DI wiring + `reply_queue` value flip | **no — behavior changes** | runtime-api |
| **94.4** | Soak, drop orphan `cycle_results_*` queues, promote SIP→implemented | — | ops |

Deploy ordering is load-bearing: agents must have `{agent_id}_results` declared
(94.1) **before** runtime-api starts addressing replies there (94.3).

## Binding decisions (resolve SIP §10 open questions + the three impl-notes)

- **D1 — `on_message` is async.** The router awaits `queue.ack(msg)` inside it. `subscribe(queue_name, *, on_message: Callable[[QueueMessage], Awaitable[None]])`.
- **D2 — Router does NOT survive runtime-api restart.** In-process futures vanish on restart; an in-flight reply is ack'd-and-dropped on next boot. Durable resume is the SIP-0079 resume-contract's job, explicitly out of scope here.
- **D3 — `{agent_id}_results` is non-exclusive, durable, `auto_delete=False`.** Exclusive would block running multiple runtime-api instances behind a load balancer. Single-consumer is enforced by convention, not the broker. Same declare args as the existing `{agent_id}_comms`.
- **D4 — `ensure_subscribed` is guarded by an `asyncio.Lock`** (impl-note 1). Dispatch is sequential within a run, but `_execute_fan_out` (`dispatched_flow_executor.py:2402`) can dispatch concurrently; two concurrent first-dispatches to one agent must not open two subscriptions. Cheap insurance.
- **D5 — `consume()`/`consume_blocking()`/`invalidate_queue()` STAY on `QueuePort`** (SIP §6). They remain for the agent-side comms loop and future use. Only the executor's *use* of `consume_blocking`+`invalidate_queue` in the reply path is removed in 94.3. This is what "supersedes, not layers on" means concretely.
- **D6 — Default `subscribe()` impl polls `consume_blocking()`** (impl-note 2). Only `RabbitMQAdapter` gets the native long-iterator. `NoOpQueuePort` inherits the default and never fires a callback (its `consume()` returns `[]`) — fine for tests.
- **D7 — Late-drop counter metric ships in 94.3** (impl-note 3 / SIP Risk 3). The router increments a counter when a reply arrives with no awaiting future, so we can detect a regression.
- **D8 — Harden `TaskResult.from_dict` to ignore unknown keys.** It currently does `cls(**data)` (`tasks/models.py:109`), unlike `TaskEnvelope.from_dict` which filters. In a long-lived consumer a single forward-incompatible result payload would raise inside `_handle_reply`; filter unknown keys defensively (mirrors the envelope parser).

## Cross-cutting requirements (every PR)

- No change to the per-task timeout (`SQUADOPS__LLM__TIMEOUT=1800`).
- No change to the agent `_consume_tasks` loop (SIP §4 non-goal — same churn class, tolerable because the comms queue is rarely idle).
- The published dispatch-message dict shape is preserved (`action`/`metadata`/`payload: envelope.to_dict()`); only the `reply_queue` *value* changes (94.3).
- `task_id` stays the correlation key (already matched at `dispatched_flow_executor.py:733`); no new correlation field.
- Every PR keeps the regression suite green: `./scripts/dev/run_regression_tests.sh -v`.

---

## PR 94.1 — Agent-side `{agent_id}_results` declaration (deploy-first, inert)

**Goal:** ensure each agent's `{agent_id}_results` queue exists before runtime-api
ever addresses it. No behavior change — agents gain an extra, unused, durable
queue.

**Finding that shapes this PR:** agents do **not** explicitly declare their
`{agent_id}_comms` queue today — declaration happens lazily inside
`RabbitMQAdapter._get_queue()` (`adapters/comms/rabbitmq.py:82`) on the first
`consume()`. There is no existing explicit-declare line to sit beside, and the
agent only *publishes* to (never consumes from) its `_results` queue, so lazy
declaration won't cover it.

### Modified / new files
- `src/squadops/ports/comms/queue.py` — add a minimal `ensure_queue(self, queue_name: str) -> None` (concrete default = no-op; or default raises `NotImplementedError` only if you want adapters to opt in — prefer no-op so NoOp works). Declares a queue without consuming.
- `adapters/comms/rabbitmq.py` — implement `ensure_queue` as a thin wrapper over `_get_queue(queue_name)` (which already declares `durable=True`). Reuses the channel-swap-safe path.
- `src/squadops/ports/comms/noop.py` — inherits the no-op default (no change, or explicit pass).
- `src/squadops/agents/entrypoint.py` — at agent startup (in `start()` after the queue adapter is built at `:351-352`, or at the top of `_consume_tasks` after `:438`), call `await self._queue.ensure_queue(f"{self.agent_id}_results")`. Belt-and-suspenders: the orchestrator's `subscribe()` (94.2/94.3) also declares idempotently, but declaring agent-side removes any first-dispatch ordering dependency.

### Tests
- `tests/unit/comms/test_rabbitmq_adapter.py` — `ensure_queue` declares with `durable=True` and is idempotent (re-call after channel swap re-declares). Extend `TestQueueCacheInvalidation` (`:30`).
- `tests/unit/agents/test_entrypoint_task.py` — agent startup calls `ensure_queue("{agent_id}_results")` exactly once.
- Deploy note: ship + deploy agents (`rebuild_and_deploy.sh agents`) before 94.3.

---

## PR 94.2 — `QueuePort.subscribe()` + `SubscriptionHandle` + RabbitMQ native impl (inert)

**Goal:** add the long-lived subscription primitive. Dormant — no caller yet.

### Modified / new files
- `src/squadops/ports/comms/queue.py` — add:
  - `SubscriptionHandle` (small class/dataclass with `async cancel()`).
  - `subscribe(self, queue_name, *, on_message: Callable[[QueueMessage], Awaitable[None]]) -> SubscriptionHandle` as a **concrete default** (per D6): spawns a background task that loops `consume_blocking()` and dispatches each delivery to `on_message`; `cancel()` stops the task.
- `adapters/comms/rabbitmq.py` — **native override** of `subscribe()`: open a long-lived `queue.iterator(no_ack=False)` (or a registered consumer) on `{agent_id}_results`, dispatch each delivery to `on_message`. **This is the hard part — see below.**
- `src/squadops/ports/comms/noop.py` — inherits default (no change).

### The hard part — channel-close resubscribe (SIP §7 Risk 1)

**Today `RabbitMQAdapter` shares one `RobustChannel` and registers NO close
callbacks** (`adapters/comms/rabbitmq.py:50-58`); staleness is detected reactively
via the `cached.channel is self._channel` check in `_get_queue` (`:66-85`). A
long-lived consumer can't poll for staleness — it must be *resumed* when its
channel dies. So `subscribe()`'s native impl must:
1. register a channel-close callback (`add_close_callback`),
2. on close, re-`_ensure_connection()` + re-declare the queue (the existing
   `_get_queue` `is self._channel` path gives re-declaration),
3. re-establish the consumer on the new channel.

`_get_queue`'s re-declaration is reusable; **consumer resumption is genuinely new
code** and the riskiest part of the SIP. Budget review/test effort here.

### Tests
- `tests/unit/adapters/test_queue_port.py` — default `subscribe()` impl: a published message reaches `on_message`; `cancel()` stops delivery. (Mock-provider level.)
- `tests/unit/comms/test_rabbitmq_adapter.py` — native `subscribe()`: happy-path delivery; **channel-close triggers transparent re-subscribe** (simulate close, assert the consumer resumes and a post-reconnect message is delivered); `cancel()` cleans up the consumer tag.
- `tests/integration/adapters/test_rabbitmq_adapter.py` — **new** (SIP §8): publish 100 replies to one `{agent_id}_results` queue with a single held subscriber → all 100 routed, zero lost. Compare against the legacy `consume()` path to demonstrate the regression it fixes.

---

## PR 94.3 — `ReplyRouter` + `_publish_and_await` rewrite + DI wiring (CUTOVER)

**Goal:** route replies through the long-lived per-agent subscription. Behavior
changes here.

### New file — `adapters/cycles/reply_router.py`
`ReplyRouter` per SIP §5.3: `ensure_subscribed(agent_id)` (idempotent, **lock-guarded per D4**), `register(task_id) -> Future`, `_handle_reply(msg)` (parse `json.loads(msg.payload)["payload"]["task_id"]`, pop+resolve the future, ack, **late-drop counter per D7**), `cancel(task_id)`, `stop()` (cancel subscriptions, fail pending futures with `ReplyRouterStopped`). Confirmed shapes:
- `QueueMessage.payload` is a raw JSON string (`comms/queue_message.py:24`) → `json.loads(msg.payload)` is correct.
- Agent reply envelope is `{"action":"comms.task.result","metadata":{...},"payload": result.to_dict()}` (`entrypoint.py:726-730`) → `data["payload"]["task_id"]` resolves. ✓
- `TaskResult.from_dict` (`tasks/models.py:109`) — apply D8 hardening (filter unknown keys).

### Rewrite — `adapters/cycles/dispatched_flow_executor.py:669-743`
`_publish_and_await` before → after:
- **Remove:** `reply_queue = f"cycle_results_{run_id}"` (`:675`), the `while`/`consume_blocking`/`invalidate_queue`/`asyncio.sleep` recovery block (`:697-743`).
- **Add:** `await self._reply_router.ensure_subscribed(envelope.agent_id)` → `fut = self._reply_router.register(envelope.task_id)` → set `reply_queue = f"{envelope.agent_id}_results"` in the message metadata (`:680`) → `publish(f"{envelope.agent_id}_comms", ...)` (unchanged) → `await asyncio.wait_for(fut, timeout=self._task_timeout)`; on `TimeoutError` → `self._reply_router.cancel(task_id)` + return the same `FAILED` TaskResult.
- `ensure_subscribed` before `register`/`publish` ⇒ the consumer is live before any reply can arrive (no first-dispatch race). All **6 dispatch call sites** (`:1199, 2144, 2319, 2426, 2903`) inherit this via the single `_publish_and_await`. `_task_heartbeat` (`:586`) and `_dispatch_task` (`:614`) are untouched.

### Executor `__init__` + DI wiring
- `dispatched_flow_executor.py:89` — add `reply_router: ReplyRouter | None = None`; store `self._reply_router` (construct from `queue` if not injected).
- `adapters/cycles/factory.py:102` (provider `"dispatched"`, the only construction site) — accept + pass `reply_router`.
- `src/squadops/api/runtime/main.py` — in `_init_cycle_subsystem` (after `queue_adapter` at `:275`): construct `ReplyRouter(queue_adapter)`, stash in a module global (pattern at `:139-143`), pass into `create_flow_executor` (`:295`). In the `@app.on_event("shutdown")` handler (`:430-449`, beside `_workflow_tracker.close()`): `await _reply_router.stop()`.

### Test migration (the §6 work — ~40 executor tests)
`tests/unit/cycles/test_dispatched_flow_executor.py` drives the wait path via the
`mock_queue` shim (`:109-125`, routes `consume_blocking`→`consume`). Post-cutover
the executor no longer touches the queue port during a wait — it awaits the
router. Migrate by injecting a fake `ReplyRouter` whose `register()` returns a
pre-resolved (or controllable) future. Three helpers gate the bulk:
- `mock_queue` fixture (`:109`) — add/replace with a `reply_router` fixture.
- `_make_result_message` (`:42`, default `queue_name="cycle_results_run_001"`) — replace with a router-result helper.
- pulse `_consume_side_effect` branching on `queue_name.startswith("cycle_results_")` (`:2565`) — re-key on the router.
- **Obsolete assertions to delete/rewrite:** `test_recovers_from_transient_consume_error` (`:609`, asserts `invalidate_queue(...)` at `:660`), `test_uses_long_block_consume_not_short_poll` (`:662`, premise superseded). `test_publishes_to_agent_comms_queue` (`:494`) updates its `reply_queue` assertion (`:548`) from `cycle_results_run_001` → `{agent_id}_results`.

### New tests
- `tests/unit/cycles/test_reply_router.py` (new): register/resolve by `task_id`; late reply (no future) → dropped + counter incremented; `stop()` fails pending futures with the typed error; `ensure_subscribed` idempotent + concurrency-safe (two concurrent calls → one subscription).
- `_publish_and_await`: registers with router before publishing; resolves on reply; `TimeoutError` → cancels the future (no leak) + returns FAILED.
- **Cross-run uniqueness** (SIP Risk 2): two runs' `task-{run_id[:12]}-...` ids don't collide on a shared `{agent_id}_results` queue (a deliberate test, per SIP). Correction/repair ids (`dispatched_flow_executor.py:2092,2259`) also carry the run prefix — cover one.

---

## PR 94.4 — Soak, orphan cleanup, promote

1. Soak in the Spark dev environment for one full long-cycle build (the SIP's
   E2E: re-run a `group_run` cycle; verify no `cycle_results_*` queues are
   created, `{agent_id}_results` queues exist with zero ready messages after the
   run, and a late dispatch (dev[3]-style) completes in the same wall time as its
   peers).
2. Drop historical `cycle_results_*` queues via one-shot `rabbitmqctl` (18+ orphans as of the incident). One-shot ops command, not code.
3. Promote: `SQUADOPS_MAINTAINER=1 python scripts/maintainer/update_sip_status.py sips/accepted/SIP-0094-Per-Agent-Reply-Queues-Long-Lived.md implemented`.

---

## Risks & mitigations

| Risk | Mitigation | PR |
|------|-----------|----|
| Long-lived consumer channel death strands in-flight waits | Native `subscribe()` registers close-callback + re-declare + re-consume (genuinely new code — review/test heavily) | 94.2 |
| Cross-run `task_id` collision on shared queue | `task-{run_id[:12]}-...` prefix gives uniqueness; deliberate test | 94.3 |
| Late reply after timeout | Router ack+drop with warning + counter metric (D7); zero broker leakage | 94.3 |
| Forward-incompatible result payload raises in long-lived consumer | `TaskResult.from_dict` filters unknown keys (D8) | 94.3 |
| Agent/orchestrator startup ordering | Lazy subscribe (orchestrator declares on first dispatch) + agent-side defensive declare (94.1); first-mover wins, both own their declarations | 94.1/94.3 |
| Deploy ordering (runtime-api addresses `_results` before agents declare it) | Phased deploy: agents (94.1) before runtime-api cutover (94.3) | rollout |

## Acceptance criteria

- **Unit/integration:** all new tests pass; the ~40 migrated executor tests pass against the router; the 100-reply single-subscriber integration test shows zero loss; full regression green.
- **E2E (the original failure mode):** re-run the incident cycle on a clean stack — the previously-lost late reply is delivered within normal wall time; **no `cycle_results_*` queue is created**; `{agent_id}_results` queues exist and drain to zero after the run.
- **No regression** to the per-task timeout, agent comms loop, or dispatch-message shape.

## References

- `sips/accepted/SIP-0094-Per-Agent-Reply-Queues-Long-Lived.md` (full design, §5 approach / §7 risks / §8 test plan / §9 rollout)
- Tactical patch PR #89 (`fix/cycle-results-channel-recovery`) — `consume_blocking` + `invalidate_queue`; superseded in the reply path per D5
- #186 (executor decomposition) — overlaps the dispatch-transport seam (`_publish_and_await`/`_dispatch_task`); implement S1 in place, let #186 extract `TaskDispatcher` around the new subscription model later
- Current-state code map: `_publish_and_await` (`dispatched_flow_executor.py:669`), `QueuePort` (`ports/comms/queue.py`), `RabbitMQAdapter._get_queue`/`consume_blocking` (`adapters/comms/rabbitmq.py:66/212`), agent reply (`agents/entrypoint.py:661/731`), boot wiring (`api/runtime/main.py:275/295/430`)
