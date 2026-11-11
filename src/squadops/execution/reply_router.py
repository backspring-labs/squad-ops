"""In-process reply router for per-agent reply queues (SIP-0094 §5.3).

The orchestrator dispatches a task to ``{agent_id}_comms`` and waits for the
agent to publish a ``TaskResult`` to ``{agent_id}_replies``. This router holds
one long-lived subscription per agent (opened lazily on first dispatch — the
squad roster isn't fixed at boot) and resolves an ``asyncio.Future`` keyed by
``task_id`` when the matching reply arrives. It replaces the old per-run
``cycle_results_{run_id}`` polling loop, eliminating both the consumer-tag-churn
reply loss and the orphan-queue leak.

**Which send a reply answers (#2932).** A task's id is stable across its retries and a resumed run's
re-dispatch, so ``task_id`` alone can't tell this send's reply from an earlier one's: after a reboot, a
FAILED reply to the broker's redelivery of the old send sat in the queue under the same id a resume
re-dispatches. Each send is stamped with its own ``dispatch_id`` (``DISPATCH_ID_METADATA_KEY``,
#2333), the waiter is registered under it, and the agent echoes it in its reply's metadata. A reply
is resolved only when its task **and** its dispatch match the waiter's. Any other reply is dropped
and counted (``stale_drops``), and the waiter is left for the reply to the current send. A reply
with no dispatch id answers no current send: agents and the runtime are rebuilt together, so only
one in flight across that rebuild lacks it, and its send times out and is sent again.

Ack ownership: the ``QueuePort.subscribe`` primitive (SIP-0094 94.2b) acks every
delivery *after* the callback returns. So ``_handle_reply`` must NOT ack — a
second ack on the same delivery is an AMQP error. "Dropping" a reply here means
resolving/failing/ignoring its future and returning; the primitive acks it.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from squadops.comms.queue_message import QueueMessage
from squadops.comms.task_delivery import DISPATCH_ID_METADATA_KEY
from squadops.ports.comms.queue import AckPolicy, QueuePort, SubscriptionHandle
from squadops.tasks.models import TaskResult

logger = logging.getLogger(__name__)


class DuplicateRegistration(Exception):
    """Raised when ``register`` is called for a ``task_id`` already pending.

    SIP-0094 D10: silently overwriting the future would strand the first waiter
    on the shared per-agent queue. ``task_id`` is the global correlation key
    (D14), so a duplicate is a programming error, not a normal condition.
    """


class ReplyRouterStopped(Exception):
    """Raised by ``ensure_subscribed`` / ``register`` after ``stop()``.

    SIP-0094 D13: once shutdown begins, a late dispatch must not register a
    future while subscriptions are being torn down.
    """


class ReplyRouter:
    """Routes agent replies on ``{agent_id}_replies`` to per-task futures."""

    def __init__(self, queue: QueuePort):
        self._queue = queue
        self._futures: dict[str, asyncio.Future[TaskResult]] = {}
        #: The send each pending waiter is for (#2932): a reply resolves it only when it echoes this.
        self._dispatches: dict[str, str] = {}
        self._subscriptions: dict[str, SubscriptionHandle] = {}
        # D4: opening a subscription is the one operation two concurrent
        # first-dispatches to the same agent could race; guard it.
        self._subscribe_lock = asyncio.Lock()
        self._stopped = False
        # D7/#6: observability counters (snapshot via metrics()).
        self._subscriptions_opened = 0
        self._late_drops = 0
        self._stale_drops = 0
        self._malformed_replies = 0
        self._from_dict_failures = 0

    async def ensure_subscribed(self, agent_id: str) -> None:
        """Open ``agent_id``'s reply subscription on first use (idempotent).

        D4: lock-guarded so two concurrent first-dispatches open exactly one
        subscription. D9: ``subscribe`` declares ``{agent_id}_replies`` before
        consuming, so the orchestrator never assumes the agent pre-declared it.
        D13: fails fast once stopped.
        """
        if self._stopped:
            raise ReplyRouterStopped(f"router stopped; refusing to subscribe {agent_id}")
        if agent_id in self._subscriptions:
            return
        async with self._subscribe_lock:
            # Re-check inside the lock: another coroutine may have opened it
            # while we awaited the lock.
            if agent_id in self._subscriptions:
                return
            if self._stopped:
                raise ReplyRouterStopped(f"router stopped; refusing to subscribe {agent_id}")
            handle = await self._queue.subscribe(
                f"{agent_id}_replies",
                on_message=self._handle_reply,
                ack_policy=AckPolicy.ACK_ALWAYS,  # SIP-0094 D12: a reply is never redelivered
            )
            self._subscriptions[agent_id] = handle
            self._subscriptions_opened += 1
            logger.info("reply-router: opened subscription for %s_replies", agent_id)

    def register(self, task_id: str, dispatch_id: str) -> asyncio.Future[TaskResult]:
        """Register interest in the reply to ``task_id``'s send ``dispatch_id``, and return its
        future. Only a reply echoing that ``dispatch_id`` resolves it (#2932).

        D10: raises :class:`DuplicateRegistration` if one is already pending —
        never overwrites. D13: refuses once stopped. Must be called *before*
        publishing (D14/#2) so the consumer is live before any reply arrives.
        """
        if not dispatch_id:
            raise ValueError(f"a waiter for {task_id} names the send it waits on (#2932)")
        if self._stopped:
            raise ReplyRouterStopped(f"router stopped; refusing to register {task_id}")
        existing = self._futures.get(task_id)
        if existing is not None and not existing.done():
            raise DuplicateRegistration(f"a reply is already pending for task_id {task_id}")
        fut: asyncio.Future[TaskResult] = asyncio.get_running_loop().create_future()
        self._futures[task_id] = fut
        self._dispatches[task_id] = dispatch_id
        return fut

    def current_dispatch(self, task_id: str) -> str | None:
        """The send of ``task_id`` the runtime is waiting on now, or ``None`` when it waits on
        none. A remote operation is asked for, read and stopped only under this send
        (SIP-0117 R5.6): an earlier send's reply would be dropped, so its operation is read by
        nobody."""
        fut = self._futures.get(task_id)
        if fut is None or fut.done():
            return None
        return self._dispatches.get(task_id)

    def cancel(self, task_id: str) -> None:
        """Drop a pending future (e.g. on dispatch timeout or publish failure).

        #9: every non-success exit path calls this so ``task_id`` never lingers
        in ``_futures`` (no pending-future leak).
        """
        self._futures.pop(task_id, None)
        self._dispatches.pop(task_id, None)

    async def _handle_reply(self, msg: QueueMessage) -> None:
        """Resolve the future for an incoming reply (D11: never strands the
        consumer; never acks — the subscribe primitive owns ack)."""
        try:
            data = json.loads(msg.payload)
            task_id = data["payload"]["task_id"]
            answers = (data.get("metadata") or {}).get(DISPATCH_ID_METADATA_KEY)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            self._malformed_replies += 1
            logger.warning("reply-router: malformed reply dropped (%s)", exc)
            return

        fut = self._futures.get(task_id)
        if fut is None or fut.done():
            self._futures.pop(task_id, None)
            self._dispatches.pop(task_id, None)
            self._late_drops += 1
            logger.warning("reply-router: reply for unknown/late task %s — dropping", task_id)
            return
        if answers != self._dispatches.get(task_id):
            # #2932: matched before the waiter is touched. A reply to an earlier send (a broker
            # redelivery of it, failed by an agent whose engine was down) is dropped, and the
            # waiter stays for the reply to the send it was registered for.
            self._stale_drops += 1
            logger.warning(
                "reply_router_stale_reply_dropped task=%s answers=%s waiting_on=%s",
                task_id,
                answers,
                self._dispatches.get(task_id),
            )
            return
        self._futures.pop(task_id, None)
        self._dispatches.pop(task_id, None)

        try:
            result = TaskResult.from_dict(data["payload"])
        except Exception as exc:
            # D11: bad result payload -> fail this waiter (so it doesn't hang to
            # timeout) but keep the consumer alive for every other agent.
            self._from_dict_failures += 1
            logger.error("reply-router: TaskResult.from_dict failed for %s: %s", task_id, exc)
            if not fut.done():
                fut.set_exception(exc)
            return

        fut.set_result(result)

    async def stop(self) -> None:
        """Stop accepting work, cancel all subscriptions, fail pending futures.

        D13: ``_stopped`` is set first so no new registration/subscription can
        slip in. Subscriptions are cancelled before futures are failed so a
        late reply can't race a future we're about to fail.
        """
        self._stopped = True
        for agent_id, handle in list(self._subscriptions.items()):
            try:
                await handle.cancel()
            except Exception:
                logger.exception("reply-router: error cancelling subscription for %s", agent_id)
        self._subscriptions.clear()

        for task_id, fut in list(self._futures.items()):
            if not fut.done():
                fut.set_exception(ReplyRouterStopped(f"router stopped before reply for {task_id}"))
        self._futures.clear()
        self._dispatches.clear()

    def metrics(self) -> dict[str, Any]:
        """Snapshot for soak/observability (SIP-0094 D7/#6)."""
        return {
            "subscriptions_open": len(self._subscriptions),
            "subscriptions_opened_total": self._subscriptions_opened,
            "pending_futures": len(self._futures),
            "late_drops": self._late_drops,
            "stale_drops": self._stale_drops,
            "malformed_replies": self._malformed_replies,
            "from_dict_failures": self._from_dict_failures,
        }
