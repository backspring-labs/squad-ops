# SIP-0XXX: Long-Lived Subscription Model for Cycle Reply Channels

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-05-02
**Revision:** 1

## 1. Abstract

The orchestrator's request/reply path between `runtime-api` and agents uses a poll-and-sleep loop on a per-run RabbitMQ reply queue. The loop opens a fresh, short-lived consumer subscription on every poll, generating thousands of consumer-tag open/close cycles per long task. This pattern is fragile under aio_pika RobustChannel: replies have been observed to remain undelivered for the full task timeout (30 minutes) even though the agent published them within the first few minutes. This SIP replaces the polling loop with a single long-lived subscription per wait and cleans up the reply-queue lifecycle so we eliminate the entire class of "agent succeeded but reply lost" failures. A tactical patch (`fix/cycle-results-channel-recovery`) has already landed cache-recovery and longer poll chunks that contain the bleeding; this SIP is the structural fix.

## 2. Problem Statement

Investigation of `cyc_c9ca088599c0` / `run_edc1d0dc7bf4` (group_run, 2026-05-02) confirmed:

- Agent (Neo) published the reply to `cycle_results_run_edc1d0dc7bf4` at 21:50:26 — 9 minutes after dispatch.
- Orchestrator's polling loop never delivered the reply during the next 21 minutes.
- At exactly the 1800s task timeout, the polling loop hit `Channel was not opened`, and the task was marked FAILED.
- A retry was triggered, which consumed another 8 minutes of GPU time before failing again.
- Three reply messages remain durably stuck in the queue, never consumed.

Root cause: `RabbitMQAdapter.consume()` opens `queue.iterator(no_ack=False)` with a 1.0-second timeout on every call. Called every ~0.5s by `_publish_and_await`, this generates ~3600 consumer subscriptions per 30-minute wait. Per AMQP semantics, when a consumer is canceled while a message is being dispatched to it, the message is meant to be redelivered to another consumer — but with the orchestrator's pattern there are no other consumers, only a future iterator that hasn't been created yet. Messages can be lost in the gap, and the constant subscribe/cancel churn appears to push the channel into states from which it does not recover.

The tactical fix in `fix/cycle-results-channel-recovery` introduces `consume_blocking()` (one consumer per chunk, default 30 s) and queue-cache invalidation on transient errors. That shrinks the failure window dramatically but still uses chunked polling — there is still a (small) gap between chunks during which messages must be redelivered. The structural fix is to maintain a single subscription for the whole wait.

Secondary problems this SIP also addresses:

- **Reply-queue leakage**: `cycle_results_*` queues are declared `durable=True` and never deleted. Production has 18+ orphan queues from completed runs.
- **Redispatch on lost reply**: `_dispatch_task_with_retry` re-runs the task on timeout, even though the agent's reply may already be in the queue. This wastes another full LLM run.

## 3. Goals

1. Replace the chunked-poll wait in `_publish_and_await` with a single long-lived consumer subscription that survives the full task timeout.
2. Define an explicit `subscribe()` primitive on `QueuePort` with callback / async-iterator semantics so reply waiting is no longer expressed as polling.
3. Add reply-queue lifecycle management: declare with TTL or auto-delete (whichever is safe for the runtime topology) and explicit cleanup on run completion.
4. Before re-dispatching a task on timeout, drain the existing reply queue once — recover the original reply if it arrived late, instead of paying for a duplicate LLM run.

## 4. Non-Goals

- Replacing RabbitMQ with another transport.
- Changing the request/reply pairing semantics (still 1 reply queue per run, still task_id-based correlation).
- Refactoring the agent-side `_consume_messages` loop in `entrypoint.py`. That loop has the same anti-pattern but is tolerable because the comms queue is rarely empty for long. Will be addressed in a follow-up.
- Changing the per-task timeout (`SQUADOPS__LLM__TIMEOUT=1800`).
- Per-message TTL on individual messages — queue-level TTL is sufficient and simpler.

## 5. Approach Sketch

### 5.1 New port primitive

```python
class QueuePort(ABC):
    async def subscribe(
        self,
        queue_name: str,
        *,
        until: Callable[[QueueMessage], bool],
        timeout: float,
    ) -> QueueMessage | None:
        """Hold a single consumer on ``queue_name`` for up to ``timeout``
        seconds. Return the first message for which ``until(msg)`` is True;
        ack and discard others. Return None on timeout."""
```

`subscribe()` takes a predicate so the executor can match on `task_id` directly inside the consumer callback — no separate ack/discard dance in user code. Default implementation in the abstract base falls back to `consume_blocking()` for adapters that don't have native long-subscription support.

### 5.2 RabbitMQ implementation

In `RabbitMQAdapter.subscribe()`:

```python
async with queue.iterator(no_ack=False) as queue_iter:
    deadline_task = asyncio.create_task(asyncio.sleep(timeout))
    async for message in queue_iter:
        if predicate matches:
            await message.ack()
            return QueueMessage(...)
        await message.ack()  # discard non-matching
        if deadline_task.done():
            return None
```

One iterator, one consumer tag, lives for the whole timeout. Messages dispatched while the consumer is registered land in the iterator immediately. No subscribe/cancel churn.

### 5.3 Executor wiring

`_publish_and_await` becomes:

```python
reply = await self._queue.subscribe(
    reply_queue,
    until=lambda msg: json.loads(msg.payload).get("payload", {}).get("task_id") == envelope.task_id,
    timeout=self._task_timeout,
)
if reply is None:
    return TaskResult(task_id=envelope.task_id, status="FAILED", error="Timed out ...")
data = json.loads(reply.payload)
return TaskResult.from_dict(data["payload"])
```

No while loop, no asyncio.sleep, no error-recovery branch (subscribe internally retries on transient channel errors).

### 5.4 Reply-queue lifecycle

Declare reply queues with both:

- `arguments={"x-expires": 3600 * 1000}` — broker auto-deletes the queue if no consumer binds for 1 hour. Catches orphan cleanup.
- Explicit `delete_queue(reply_queue)` call in the run-completion path of `DistributedFlowExecutor.execute()`. Catches the happy path immediately.

### 5.5 Drain-before-retry

In `_dispatch_task_with_retry` before re-dispatching a timed-out task, call `subscribe(reply_queue, until=task_id-match, timeout=5)` to scoop any reply that arrived after the wait timed out. If found, return SUCCEEDED without paying for a re-run.

## 6. Migration / Compatibility

- `consume()` and `consume_blocking()` (added in tactical patch) remain on `QueuePort`. They are still useful for the agent-side comms loop and future use cases.
- `subscribe()` is added as a non-abstract method with a default implementation that wraps `consume_blocking()`. NoOpQueuePort needs no changes. RabbitMQAdapter overrides with the native long-iterator implementation.
- Existing tests using `mock_queue.consume.side_effect = ...` continue to work.
- Tests that exercise `_publish_and_await` after this SIP must mock `subscribe()` instead.

## 7. Risks

- **Single-consumer failure mode**: if the long-lived consumer's channel dies mid-wait, we lose the reply window. The implementation must catch channel-close events and re-subscribe transparently (RobustChannel reconnect plus our own re-declare on the new channel).
- **Reply queue auto-delete races**: if the consumer binds late (e.g., orchestrator restart), the broker may have already deleted the queue and the agent's reply will be lost. Mitigation: declare the queue at dispatch time, before publishing the request, with a generous TTL (1 hour). Run-completion cleanup is best-effort.
- **Drain-before-retry false positives**: if a stale reply from a prior dispatch matches the new dispatch's task_id (which would indicate a deeper bug), drain returns the stale result. Use the run-completion cleanup to keep the queue fresh; additionally, increment a dispatch attempt counter and include it in correlation metadata so stale matches can be detected.

## 8. Test Plan

- Unit: `subscribe()` happy path, timeout returns None, predicate filters non-matching messages, transient channel error is retried internally.
- Unit: reply-queue declaration includes TTL argument; explicit cleanup is called on run completion (success and failure).
- Unit: drain-before-retry returns existing reply without re-publishing.
- Integration (`tests/integration/adapters/test_rabbitmq_adapter.py`): publish 100 messages while a single subscriber is held — all 100 delivered, zero lost. Compare to the same load against `consume()` to demonstrate the regression.
- E2E: re-run the `group_run` cycle that surfaced this issue (`cyc_c9ca088599c0`) on a clean stack; verify dev[3] completes within the same wall time as dev[0–2].

## 9. Rollout

1. Land tactical patch (`fix/cycle-results-channel-recovery`) — already in PR. Contains the bleeding.
2. Implement subscribe() + RabbitMQ override + executor wiring on a feature branch.
3. Soak in dev environment for one full long-cycle build.
4. Promote.

## 10. Open Questions

- Should reply queues be per-run (current) or per-task? Per-task gives natural isolation but multiplies queue declarations. Recommend keeping per-run.
- Should `subscribe()`'s predicate be sync or async? Sync is simpler; async unlocks future use cases (e.g., HTTP lookup to validate a result). Recommend sync for v1.
