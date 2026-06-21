"""Unit tests for the SIP-0094 ReplyRouter (cutover, 94.3).

Covers the D-decisions: lazy/concurrency-safe subscribe (D4), duplicate-register
guard (D10), robust _handle_reply that never strands the consumer (D11), shutdown
that fails pending futures (D13), and the ack-ownership reconciliation — the
subscribe primitive auto-acks, so the router must never ack (double-ack here
raises, mimicking AMQP).
"""

from __future__ import annotations

import asyncio
import json

import pytest

from adapters.cycles.reply_router import (
    DuplicateRegistration,
    ReplyRouter,
    ReplyRouterStopped,
)
from squadops.comms.queue_message import QueueMessage
from squadops.ports.comms.queue import QueuePort
from squadops.tasks.models import TaskResult

pytestmark = [pytest.mark.unit]


def _reply(task_id: str, *, status: str = "SUCCEEDED", outputs=None, extra=None) -> str:
    """Agent reply envelope (entrypoint.py shape): payload is the TaskResult."""
    payload = {"task_id": task_id, "status": status}
    if outputs is not None:
        payload["outputs"] = outputs
    if extra:
        payload.update(extra)
    return json.dumps(
        {
            "action": "comms.task.result",
            "metadata": {"correlation_id": "c"},
            "payload": payload,
        }
    )


class _Handle:
    """Duck-typed SubscriptionHandle the fake queue hands back."""

    def __init__(self):
        self.cancelled = False

    @property
    def active(self) -> bool:
        return not self.cancelled

    async def cancel(self) -> None:
        self.cancelled = True


class FakeQueue(QueuePort):
    """Models the 94.2b subscribe primitive: captures the on_message callback,
    and ``deliver`` hands a message to it then **acks exactly once** (as the
    real primitive does). ``ack`` raises on a repeat so a router that wrongly
    acked would blow up the test."""

    def __init__(self):
        self.handlers: dict[str, object] = {}
        self.handles: dict[str, _Handle] = {}
        self.acked: list[str] = []
        self._tag = 0

    async def subscribe(self, queue_name: str, *, on_message):
        await asyncio.sleep(0)  # force a yield so D4 concurrency is exercised
        self.handlers[queue_name] = on_message
        handle = _Handle()
        self.handles[queue_name] = handle
        return handle

    async def deliver(self, queue_name: str, payload: str) -> None:
        """Simulate one broker delivery + the primitive's auto-ack."""
        self._tag += 1
        msg = QueueMessage(
            message_id=str(self._tag),
            queue_name=queue_name,
            payload=payload,
            receipt_handle=str(self._tag),
            attributes={},
        )
        await self.handlers[queue_name](msg)  # router._handle_reply (must NOT ack)
        await self.ack(msg)  # primitive auto-ack, exactly once

    async def ack(self, message: QueueMessage) -> None:
        if message.receipt_handle in self.acked:
            raise RuntimeError(f"double-ack on delivery {message.receipt_handle}")
        self.acked.append(message.receipt_handle)

    # --- unused abstract surface ---
    async def publish(self, queue_name, payload, delay_seconds=None):  # pragma: no cover
        pass

    async def consume(self, queue_name, max_messages=1):  # pragma: no cover
        return []

    async def retry(self, message, delay_seconds):  # pragma: no cover
        pass

    async def health(self):  # pragma: no cover
        return {"status": "healthy"}

    def capabilities(self):  # pragma: no cover
        return {"delay": False, "fifo": True, "priority": False}


async def test_register_and_resolve_by_task_id():
    """Happy path: a reply resolves its future to the exact TaskResult, the
    delivery is acked exactly once (by the primitive, not the router), and no
    pending future is left behind."""
    q = FakeQueue()
    router = ReplyRouter(q)
    await router.ensure_subscribed("neo")
    fut = router.register("t1")

    await q.deliver("neo_replies", _reply("t1", outputs={"x": 1}))
    result = await asyncio.wait_for(fut, timeout=1.0)

    assert result == TaskResult(task_id="t1", status="SUCCEEDED", outputs={"x": 1})
    assert q.acked == ["1"]  # exactly one ack, from the primitive
    assert router.metrics()["pending_futures"] == 0


async def test_duplicate_register_raises():
    """D10: a second register() for a pending task_id raises rather than
    silently overwriting (which would strand the first waiter)."""
    q = FakeQueue()
    router = ReplyRouter(q)
    router.register("t1")
    with pytest.raises(DuplicateRegistration):
        router.register("t1")


async def test_late_reply_dropped_and_counted():
    """D11: a reply with no pending future (timed-out/unknown) is dropped and
    counted, the delivery still acked, and the consumer is unaffected."""
    q = FakeQueue()
    router = ReplyRouter(q)
    await router.ensure_subscribed("neo")

    await q.deliver("neo_replies", _reply("ghost"))

    assert router.metrics()["late_drops"] == 1
    assert q.acked == ["1"]


async def test_malformed_reply_survives_consumer():
    """D11: malformed payloads (bad JSON, missing task_id) are counted, not
    raised — and a later valid reply still resolves (consumer survived)."""
    q = FakeQueue()
    router = ReplyRouter(q)
    await router.ensure_subscribed("neo")

    await q.deliver("neo_replies", "this is not json")
    # well-formed envelope but payload has no task_id
    await q.deliver("neo_replies", json.dumps({"payload": {"status": "SUCCEEDED"}}))

    assert router.metrics()["malformed_replies"] == 2

    fut = router.register("t9")
    await q.deliver("neo_replies", _reply("t9"))
    result = await asyncio.wait_for(fut, timeout=1.0)
    assert result.task_id == "t9"


async def test_from_dict_failure_fails_future_but_consumer_lives():
    """D11: a reply whose payload can't build a TaskResult (missing required
    status) fails *that* waiter instead of hanging it, and keeps the consumer
    alive for other tasks."""
    q = FakeQueue()
    router = ReplyRouter(q)
    await router.ensure_subscribed("neo")

    bad_fut = router.register("t_bad")
    await q.deliver(
        "neo_replies",
        json.dumps({"payload": {"task_id": "t_bad"}}),  # no status -> from_dict raises
    )
    with pytest.raises(TypeError):
        await asyncio.wait_for(bad_fut, timeout=1.0)
    assert router.metrics()["from_dict_failures"] == 1

    # Consumer still healthy: a subsequent good reply resolves.
    good_fut = router.register("t_ok")
    await q.deliver("neo_replies", _reply("t_ok"))
    assert (await asyncio.wait_for(good_fut, timeout=1.0)).task_id == "t_ok"


async def test_stop_fails_pending_futures_and_cancels_subscriptions():
    """D13: stop() fails every pending future with the typed error and cancels
    each open subscription."""
    q = FakeQueue()
    router = ReplyRouter(q)
    await router.ensure_subscribed("neo")
    fut = router.register("t1")

    await router.stop()

    with pytest.raises(ReplyRouterStopped):
        await asyncio.wait_for(fut, timeout=1.0)
    assert q.handles["neo_replies"].cancelled is True
    assert router.metrics()["pending_futures"] == 0


async def test_ensure_subscribed_is_concurrency_safe():
    """D4: five concurrent first-dispatches to one agent open exactly one
    subscription (double-checked lock), not five."""
    q = FakeQueue()
    router = ReplyRouter(q)

    await asyncio.gather(*(router.ensure_subscribed("neo") for _ in range(5)))

    assert router.metrics()["subscriptions_opened_total"] == 1
    assert list(q.handlers.keys()) == ["neo_replies"]


async def test_fails_fast_once_stopped():
    """D13: after stop(), both ensure_subscribed and register refuse with the
    typed error so a late dispatch can't slip a future past shutdown."""
    q = FakeQueue()
    router = ReplyRouter(q)
    await router.stop()

    with pytest.raises(ReplyRouterStopped):
        await router.ensure_subscribed("neo")
    with pytest.raises(ReplyRouterStopped):
        router.register("t1")
