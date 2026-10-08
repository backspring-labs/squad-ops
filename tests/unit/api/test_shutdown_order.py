"""The runtime's shutdown tells the flow executor first (#1929).

Bug caught: the executor told after the pool closes, or not at all. The pool closing and the reply
router failing its waits are what a run in flight reads as its own failure, so the executor has to
know the process is stopping before either happens.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from squadops.api.runtime.main import _shutdown


async def test_the_executor_is_told_before_the_pool_closes_and_the_reply_waits_fail():
    order: list[str] = []
    executor = MagicMock()
    executor.begin_shutdown.side_effect = lambda: order.append("executor told")
    pool = AsyncMock()
    pool.close.side_effect = lambda: order.append("pool closed")
    router = AsyncMock()
    router.stop.side_effect = lambda: order.append("reply waits failed")
    state = SimpleNamespace(
        flow_executor=executor,
        pool=pool,
        reply_router=router,
        duty_scheduler=None,
        health_checker=None,
        reconciliation_task=None,
        campaign_sweep_task=None,
        memory_reconcile_task=None,
        redis_client=None,
        rabbitmq_connection=None,
        log_forwarder=None,
        workflow_tracker=None,
    )

    await _shutdown(SimpleNamespace(state=state))

    assert order == ["executor told", "pool closed", "reply waits failed"]
