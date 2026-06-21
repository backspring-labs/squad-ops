---
title: Per-Agent Reply Queues + Long-Lived Subscription Model
status: accepted
author: SquadOps Architecture
created_at: '2026-05-02T00:00:00Z'
sip_number: 94
updated_at: '2026-06-20T19:43:25.130339Z'
---
# SIP-0094: Per-Agent Reply Queues + Long-Lived Subscription Model

**Status:** Accepted
**Authors:** SquadOps Architecture
**Created:** 2026-05-02
**Revision:** 3

**Rev 3 (2026-06-20):** Reply router subscribes **lazily** on first dispatch to each agent instead of enumerating a boot-time roster — squad profiles resolve per-run (`SquadProfilePort.resolve_snapshot(profile_id)`) and are overridable per run, so there is no fixed agent set at orchestrator startup. Touches §1, §5.1, §5.3, §5.4, §7. (Rev 2: tactical-patch split + per-agent-queue approach.)

## 1. Abstract

The orchestrator's request/reply path between `runtime-api` and agents has two structural problems: (a) it polls a per-run RabbitMQ reply queue with thousands of short-lived consumer subscriptions per long task, losing replies in the gap between subscriptions, and (b) it scopes the reply queue by run instead of by agent, so every completed run leaves an orphaned `cycle_results_*` queue that nobody ever cleans up. This SIP fixes both by mirroring the existing dispatch-channel design — replace per-run reply queues with per-agent reply queues (`{agent_id}_results`, parallel to the existing `{agent_id}_comms`), and replace the polling loop with a single long-lived subscription per agent, established lazily on first dispatch to each agent. The result eliminates the "agent succeeded but reply lost" failure class and the orphan-queue leakage class in one step. A tactical patch (PR #89, `fix/cycle-results-channel-recovery`, merged 2026-05-02) already lands cache-recovery and longer poll chunks that contain the bleeding; this SIP is the structural fix.

## 2. Problem Statement

Investigation of `cyc_c9ca088599c0` / `run_edc1d0dc7bf4` (group_run, 2026-05-02) confirmed:

- Agent (Neo) published the reply to `cycle_results_run_edc1d0dc7bf4` at 21:50:26 — 9 minutes after dispatch.
- Orchestrator's polling loop never delivered the reply during the next 21 minutes.
- At exactly the 1800s task timeout, the polling loop hit `Channel was not opened`, and the task was marked FAILED.
- A retry was triggered, which consumed another 8 minutes of GPU time before failing again.
- Three reply messages remain durably stuck in the queue, never consumed.

Two independent root causes:

**Cause A — Polling-iterator anti-pattern.** `RabbitMQAdapter.consume()` opens `queue.iterator(no_ack=False)` with a 1.0-second timeout on every call. Called every ~0.5s by `_publish_and_await`, this generates ~3600 consumer subscriptions per 30-minute wait. Per AMQP semantics, when a consumer is canceled while a message is being dispatched to it, the message is meant to be redelivered to another consumer — but with the orchestrator's pattern there are no other consumers, only a future iterator that hasn't been created yet. Messages can be lost in the gap, and the constant subscribe/cancel churn appears to push the channel into states from which it does not recover.

**Cause B — Per-run reply queue scoping.** The reply queue is named `cycle_results_{run_id}` and declared `durable=True` on first dispatch. There is no run-completion cleanup. As of 2026-05-02 production has 18+ orphan `cycle_results_*` queues from prior runs. The per-run choice is unmotivated: tasks within a run dispatch sequentially, only the orchestrator consumes from the queue, and `task_id` is already the correlation key. The per-run partition gives no isolation that `task_id` matching doesn't already provide; it only adds lifecycle work that nobody is doing.

The tactical fix on PR #89 introduces `consume_blocking()` (one consumer per chunk, default 30s) and queue-cache invalidation on transient errors. That shrinks Cause A's failure window dramatically but still uses chunked polling — there is still a (small) gap between chunks during which messages must be redelivered. It does nothing about Cause B.

## 3. Goals

1. Replace per-run reply queues (`cycle_results_{run_id}`) with per-agent reply queues (`{agent_id}_results`). One declaration per agent at orchestrator startup; durable; never cleaned up because they are the agent's permanent reply address (parallel structure to the existing `{agent_id}_comms` dispatch queue). Eliminates the orphan-queue class.
2. Replace `_publish_and_await`'s polling loop with a long-lived per-agent subscription established lazily on first dispatch to each agent (the squad roster isn't fixed at boot — profiles resolve per-run), plus an in-process router that resolves an `asyncio.Future` keyed by `task_id` when a matching reply arrives. Eliminates the consumer-tag-churn failure class.
3. Define an explicit `subscribe()` primitive on `QueuePort` with callback/async-iterator semantics so reply consumption is no longer expressed as polling at any layer.

## 4. Non-Goals

- Replacing RabbitMQ with another transport.
- Refactoring the agent-side `_consume_messages` loop in `entrypoint.py`. That loop has the same iterator-churn anti-pattern but is tolerable because the comms queue is rarely empty for long. Will be addressed in a follow-up.
- Changing the per-task timeout (`SQUADOPS__LLM__TIMEOUT=1800`).
- Adopting `amq.rabbitmq.reply-to` (broker-managed temporary reply channel). Architecturally cleaner still, but requires a different consumer-binding model than what aio_pika's high-level abstractions provide. Tracked as a future evolution; per-agent queues land first because they slot into the existing dispatch-queue pattern with minimal new infrastructure.
- Per-message TTL or queue-level TTL. Per-agent queues are persistent by design, like the dispatch queues — no TTL needed.

## 5. Approach Sketch

### 5.1 Per-agent reply queue

Each agent gets a permanent reply queue named `{agent_id}_results`, declared durable. Symmetric to the existing `{agent_id}_comms`:

| Direction | Queue | Writer | Reader |
|---|---|---|---|
| Dispatch | `{agent_id}_comms` | runtime-api | the named agent |
| Reply (new) | `{agent_id}_results` | the named agent | runtime-api |

Declaration happens in two places:
- **Orchestrator, on first dispatch to an agent**: `ReplyRouter.ensure_subscribed(agent_id)` opens the subscription, which declares `{agent_id}_results` (idempotent — broker no-ops on re-declare with same args). There is no boot-time roster to enumerate; the squad profile is resolved per-run and can be overridden per run (see §5.3).
- **Agent startup**: also declares its own `{agent_id}_results` (defensive — if the orchestrator hasn't dispatched to it yet, the agent shouldn't fail its first reply).

The `reply_queue` field in dispatch metadata becomes `{envelope.agent_id}_results` instead of `cycle_results_{run_id}`. Agents see no semantic change — they still publish wherever metadata says to publish.

### 5.2 New port primitive

```python
class QueuePort(ABC):
    async def subscribe(
        self,
        queue_name: str,
        *,
        on_message: Callable[[QueueMessage], Awaitable[None]],
    ) -> SubscriptionHandle:
        """Open a long-lived consumer on ``queue_name``. Each delivery is
        handed to ``on_message``, which is responsible for ack/discard. Returns
        a handle whose ``cancel()`` shuts down the consumer cleanly."""
```

This shape is closer to "register a callback" than "wait for one message." It's the right shape for the orchestrator's reply-router pattern (one subscription per agent, lives for the orchestrator's lifetime, dispatches every delivery to a router). Default implementation in the abstract base spawns a background task that polls `consume_blocking()` for adapters that don't have native long-subscription support.

### 5.3 Reply router

A new `ReplyRouter` component in `adapters/cycles/`. It subscribes **lazily**: there is no fixed agent roster at orchestrator boot — squad profiles are resolved per-run via `SquadProfilePort.resolve_snapshot(profile_id)` and can be overridden per run, so the router cannot enumerate agents at startup. Instead the executor calls `ensure_subscribed(agent_id)` before each dispatch; the first call for a given agent opens that agent's `{agent_id}_results` subscription, and subsequent calls are no-ops. Once opened, a subscription lives for the process lifetime.

```python
class ReplyRouter:
    def __init__(self, queue: QueuePort):
        self._queue = queue
        self._futures: dict[str, asyncio.Future[TaskResult]] = {}
        self._subscriptions: dict[str, SubscriptionHandle] = {}

    async def ensure_subscribed(self, agent_id: str) -> None:
        """Idempotent: open the agent's reply subscription on first use."""
        if agent_id in self._subscriptions:
            return
        self._subscriptions[agent_id] = await self._queue.subscribe(
            f"{agent_id}_results",
            on_message=self._handle_reply,
        )

    async def _handle_reply(self, msg: QueueMessage) -> None:
        data = json.loads(msg.payload)
        task_id = data["payload"]["task_id"]
        fut = self._futures.pop(task_id, None)
        await self._queue.ack(msg)
        if fut is None or fut.done():
            logger.warning("Reply for unknown/late task %s — dropping", task_id)
            return
        fut.set_result(TaskResult.from_dict(data["payload"]))

    def register(self, task_id: str) -> asyncio.Future[TaskResult]:
        fut = asyncio.get_running_loop().create_future()
        self._futures[task_id] = fut
        return fut

    def cancel(self, task_id: str) -> None:
        """Drop a pending future (e.g. on dispatch timeout) to avoid leaks."""
        self._futures.pop(task_id, None)

    async def stop(self) -> None:
        """Shutdown: cancel all subscriptions and fail any pending futures."""
        for handle in self._subscriptions.values():
            await handle.cancel()
        self._subscriptions.clear()
        for fut in self._futures.values():
            if not fut.done():
                fut.set_exception(ReplyRouterStopped())
        self._futures.clear()
```

Lifecycle: constructed at runtime-api boot, `stop()` at shutdown. No boot-time subscription — the first dispatch to each agent opens that agent's subscription, which then persists for the process lifetime. This stays correct under per-run profile overrides: an agent that only appears in one run's profile is subscribed the moment it is first dispatched to, and never needs a pre-registered roster.

### 5.4 Executor wiring

`_publish_and_await` becomes:

```python
await self._reply_router.ensure_subscribed(envelope.agent_id)
fut = self._reply_router.register(envelope.task_id)
reply_queue = f"{envelope.agent_id}_results"
message = {
    "action": "comms.task",
    "metadata": {"reply_queue": reply_queue, "correlation_id": envelope.correlation_id},
    "payload": envelope.to_dict(),
}
await self._queue.publish(f"{envelope.agent_id}_comms", json.dumps(message))
try:
    return await asyncio.wait_for(fut, timeout=self._task_timeout)
except asyncio.TimeoutError:
    self._reply_router.cancel(envelope.task_id)
    return TaskResult(
        task_id=envelope.task_id,
        status="FAILED",
        error=f"Timed out waiting for agent {envelope.agent_id} after {self._task_timeout}s",
    )
```

`ensure_subscribed` runs before `register`/`publish`, so the agent's consumer is live before any reply can arrive — there is no first-dispatch race. No while loop, no asyncio.sleep, no error-recovery branch (the long-lived consumer's channel-close events are handled inside `subscribe()` via RobustChannel + our own resubscribe-on-channel-swap logic). Drain-before-retry is unnecessary: a reply that arrives after timeout still hits the always-on consumer, finds no awaiting future, and is logged-and-dropped — no orphan messages.

### 5.5 Migration

The dispatch-side change (use `{agent_id}_results` as `reply_queue`) is invisible to agents because they read the address out of metadata. The cutover is therefore a runtime-api-only change once the agents have their `_results` queues declared. Order of operations:

1. Land tactical patch (PR #89, done).
2. Add `_results` queue declaration to agent startup (`entrypoint.py`). Deploy agents first. Old runtime-api still uses `cycle_results_{run_id}`; agents now have an extra unused queue. No behavior change.
3. Land `subscribe()` + `ReplyRouter` + executor wiring in runtime-api. Deploy.
4. After one soak cycle, manually drop the historical `cycle_results_*` queues (one-shot rabbitmqctl command).

## 6. Compatibility

- `consume()` and `consume_blocking()` (added in tactical patch) remain on `QueuePort`. Still useful for the agent-side comms loop and other future use cases.
- `subscribe()` is added as a non-abstract method with a default implementation that spawns a background task polling `consume_blocking()`. NoOpQueuePort needs no changes. RabbitMQAdapter overrides with the native long-iterator implementation.
- Existing tests using `mock_queue.consume.side_effect = ...` continue to work for code paths that don't go through the executor.
- Tests that exercise `_publish_and_await` after this SIP must mock the `ReplyRouter` rather than `consume_blocking()` (they no longer interact with the queue port directly during a wait).

## 7. Risks

- **Long-lived consumer channel death**: if a `_results` consumer's channel closes (network blip, broker restart), in-flight waits are silently stranded until either the channel reconnects or the dispatch times out. Mitigation: `subscribe()` implementation must register channel-close callbacks, re-declare its queue on the new channel, and re-establish the consumer. Existing `_get_queue` channel-swap detection (already in tactical patch) covers re-declaration; subscription resumption is new code.
- **Cross-run task_id collision**: per-agent queues are shared across runs, so task_id must be globally unique (not just per-run). Audit `TaskEnvelope.task_id` generation — currently UUID-based (`task-{run_short}-{m_idx}-{capability}`), which encodes the run prefix, so collision is unlikely but worth a deliberate test.
- **Late-reply leakage**: if an agent's reply arrives after the orchestrator has timed out and given up on a task, the reply lands in `_results`, gets ack'd by the router, and is dropped with a warning log. Cost: zero broker-side leakage but a small observability gap. Mitigation: counter metric for late-drop events so we can detect a regression.
- **Agent-orchestrator startup ordering**: largely dissolved by lazy subscription (§5.3). The orchestrator's `subscribe()` now happens on first dispatch, not at boot, and itself declares `{agent_id}_results` (idempotent), so it no longer depends on the agent having booted first. Both sides own their queue declarations; first-mover wins. Residual requirement: `subscribe()` must tolerate being the declarer (not assume the queue already exists).

## 8. Test Plan

- Unit: `ReplyRouter` registers/resolves futures by task_id; late replies (no awaiting future) are dropped with a warning; on shutdown, all pending futures are failed with a typed error.
- Unit: `subscribe()` happy path; channel-close triggers re-subscribe transparently; cancel cleans up consumer tag.
- Unit: `_publish_and_await` registers with router before publishing, resolves on reply, fails cleanly on timeout, and unregisters on timeout to avoid future-leak.
- Integration (`tests/integration/adapters/test_rabbitmq_adapter.py`): publish 100 replies to one `{agent_id}_results` queue while a single subscriber is held — all 100 routed correctly to their futures, zero lost. Compare to the same load against the legacy `consume()` path to demonstrate the regression.
- E2E: re-run the `group_run` cycle that surfaced this issue (`cyc_c9ca088599c0`) on a clean stack; verify dev[3] completes within the same wall time as dev[0–2]. Verify no `cycle_results_*` queues are created. Verify `{agent_id}_results` queues exist and have zero ready messages after the run completes.

## 9. Rollout

1. **Done**: tactical patch (`fix/cycle-results-channel-recovery`, PR #89, merged 2026-05-02). Contains the bleeding.
2. Agent-side: declare `{agent_id}_results` queue at agent startup. Ship and deploy first so that when runtime-api starts using the new path, the queues exist. No behavior change in this step.
3. Runtime-api side: land `subscribe()` + `ReplyRouter` + dispatch-metadata change in one feature branch off main. Tests required per §8.
4. Soak in Spark dev environment for one full long-cycle build.
5. Drop historical `cycle_results_*` queues via one-shot rabbitmqctl command after soak.
6. Promote SIP to implemented.

## 10. Open Questions

- Should `subscribe()`'s `on_message` callback be sync or async? Async is required for the router (which calls `await queue.ack(msg)` inside it). Recommend async.
- Should the router survive runtime-api restarts? If runtime-api restarts mid-task, in-process futures vanish and any reply already in flight will be ack'd-and-dropped on next boot. Out of scope for this SIP — that's the SIP-0079-style resume contract's job.
- Should `{agent_id}_results` queues be declared with `auto_delete=False, exclusive=False` (current per-run default) or `exclusive=True` to enforce single-consumer semantics? Recommend non-exclusive — exclusive prevents the orchestrator from running multiple instances behind a load balancer. Single-consumer is enforced by convention, not broker.
