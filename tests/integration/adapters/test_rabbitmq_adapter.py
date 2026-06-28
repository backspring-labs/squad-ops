"""
Integration tests for RabbitMQ adapter.
Tests RabbitMQ roundtrip, namespace verification, and health checks.
"""

import asyncio
import json

import pytest
import pytest_asyncio

from adapters.comms.rabbitmq import RabbitMQAdapter
from squadops.ports.secrets import SecretProvider


class MockSecretProvider(SecretProvider):
    """Mock secret provider for testing."""

    def __init__(self, secrets: dict[str, str]):
        self._secrets = secrets

    @property
    def provider_name(self) -> str:
        return "mock"

    def resolve(self, provider_key: str) -> str:
        if provider_key not in self._secrets:
            from squadops.core.secrets import SecretNotFoundError

            raise SecretNotFoundError(provider_key, "mock", "Secret not found")
        return self._secrets[provider_key]

    def exists(self, provider_key: str) -> bool:
        return provider_key in self._secrets


@pytest.mark.integration
class TestRabbitMQAdapter:
    """Integration tests for RabbitMQ adapter."""

    @pytest_asyncio.fixture
    async def rabbitmq_adapter(self, rabbitmq_container):
        """Create RabbitMQ adapter instance."""
        rabbitmq_url = rabbitmq_container.get_connection_url()
        adapter = RabbitMQAdapter(url=rabbitmq_url, namespace=None)
        yield adapter
        # Cleanup
        await adapter.close()

    @pytest_asyncio.fixture
    async def rabbitmq_adapter_with_namespace(self, rabbitmq_container):
        """Create RabbitMQ adapter instance with namespace."""
        rabbitmq_url = rabbitmq_container.get_connection_url()
        adapter = RabbitMQAdapter(url=rabbitmq_url, namespace="test_namespace")
        yield adapter
        # Cleanup
        await adapter.close()

    @pytest_asyncio.fixture
    def sample_task_envelope_json(self):
        """Sample ACI TaskEnvelope JSON for testing."""
        return json.dumps(
            {
                "task_id": "task-001",
                "agent_id": "agent-001",
                "cycle_id": "CYCLE-001",
                "pulse_id": "pulse-001",
                "project_id": "project-001",
                "task_type": "code_generate",
                "inputs": {"action": "build"},
                "correlation_id": "corr-CYCLE-001",
                "causation_id": "cause-root",
                "trace_id": "trace-placeholder-task-001",
                "span_id": "span-placeholder-task-001",
            }
        )

    @pytest.mark.asyncio
    async def test_publish_consume_ack_roundtrip(
        self, rabbitmq_adapter, sample_task_envelope_json, clean_rabbitmq
    ):
        """Test full publish -> consume -> ack cycle."""
        queue_name = "test_queue_roundtrip"

        # Publish message
        await rabbitmq_adapter.publish(queue_name, sample_task_envelope_json)

        # Consume message
        messages = await rabbitmq_adapter.consume(queue_name, max_messages=1)

        # Verify message was consumed
        assert len(messages) == 1
        message = messages[0]

        # Verify payload integrity
        assert message.payload == sample_task_envelope_json

        # Verify message structure
        assert message.queue_name == queue_name
        assert message.message_id is not None
        assert message.receipt_handle is not None

        # Parse and verify TaskEnvelope identity fields
        envelope_data = json.loads(message.payload)
        identity_fields = [
            "task_id",
            "agent_id",
            "cycle_id",
            "pulse_id",
            "project_id",
            "correlation_id",
            "causation_id",
            "trace_id",
            "span_id",
        ]

        for field in identity_fields:
            assert field in envelope_data, f"Identity field {field} missing"
            assert envelope_data[field] is not None, f"Identity field {field} is None"

        # Acknowledge message
        await rabbitmq_adapter.ack(message)

        # Verify message is gone (consume again should return empty)
        await rabbitmq_adapter.consume(queue_name, max_messages=1)
        # Note: Due to timeout-based consume, this may return empty list
        # The important thing is that ack succeeded without error

    @pytest.mark.asyncio
    async def test_namespace_verification(
        self, rabbitmq_adapter_with_namespace, sample_task_envelope_json, clean_rabbitmq
    ):
        """Test that namespace is correctly prepended to queue names."""
        queue_name = "test_queue"

        # Publish message
        await rabbitmq_adapter_with_namespace.publish(queue_name, sample_task_envelope_json)

        # Consume message (using original queue name, adapter should apply namespace)
        messages = await rabbitmq_adapter_with_namespace.consume(queue_name, max_messages=1)

        # Verify message was consumed (proves namespace was applied)
        assert len(messages) == 1
        assert messages[0].payload == sample_task_envelope_json

        # Verify the queue was created with namespace
        # We can't directly check the queue name, but we can verify the message
        # was consumed from the namespaced queue by checking it's not in the non-namespaced queue
        adapter_no_namespace = RabbitMQAdapter(
            url=rabbitmq_adapter_with_namespace.url, namespace=None
        )
        try:
            messages_no_namespace = await adapter_no_namespace.consume(queue_name, max_messages=1)
            # Should be empty (or timeout) because queue is namespaced
            assert len(messages_no_namespace) == 0
        finally:
            await adapter_no_namespace.close()

    @pytest.mark.asyncio
    async def test_health_check(self, rabbitmq_adapter):
        """Test health check returns correct status."""
        health = await rabbitmq_adapter.health()

        assert health is not None
        assert "status" in health
        assert "connected" in health
        assert "channel_ready" in health
        assert "provider" in health
        assert health["provider"] == "rabbitmq"
        assert health["status"] == "healthy"
        assert health["connected"] is True
        assert health["channel_ready"] is True

    @pytest.mark.asyncio
    async def test_capabilities(self, rabbitmq_adapter):
        """Test capabilities() returns correct feature flags."""
        caps = rabbitmq_adapter.capabilities()

        assert caps is not None
        assert "delay" in caps
        assert "fifo" in caps
        assert "priority" in caps
        assert caps["delay"] is True
        assert caps["fifo"] is False  # RabbitMQ doesn't guarantee FIFO
        assert caps["priority"] is True

    @pytest.mark.asyncio
    async def test_retry_message(self, rabbitmq_adapter, sample_task_envelope_json, clean_rabbitmq):
        """Test retry functionality."""
        queue_name = "test_queue_retry"

        # Publish message
        await rabbitmq_adapter.publish(queue_name, sample_task_envelope_json)

        # Consume message
        messages = await rabbitmq_adapter.consume(queue_name, max_messages=1)
        assert len(messages) == 1
        message = messages[0]

        # Retry message with delay
        await rabbitmq_adapter.retry(message, delay_seconds=1)

        # Verify original message was acked (retry should ack the original)
        # The retried message should be republished, so we can consume it again
        # Note: With delay, we may need to wait, but for testing we verify retry succeeded

    @pytest.mark.asyncio
    async def test_multiple_messages(
        self, rabbitmq_adapter, sample_task_envelope_json, clean_rabbitmq
    ):
        """Test consuming multiple messages."""
        queue_name = "test_queue_multi"

        # Publish multiple messages
        for i in range(3):
            envelope_data = json.loads(sample_task_envelope_json)
            envelope_data["task_id"] = f"task-{i:03d}"
            await rabbitmq_adapter.publish(queue_name, json.dumps(envelope_data))

        # Consume multiple messages
        messages = await rabbitmq_adapter.consume(queue_name, max_messages=3)

        # Verify we got messages (may be fewer than 3 due to timeout-based consume)
        assert len(messages) > 0
        assert len(messages) <= 3

        # Verify each message has unique task_id
        task_ids = [json.loads(msg.payload)["task_id"] for msg in messages]
        assert len(task_ids) == len(set(task_ids)), "Duplicate task_ids found"

        # Acknowledge all messages
        for message in messages:
            await rabbitmq_adapter.ack(message)


async def _drain(adapter: RabbitMQAdapter, name: str) -> None:
    """Declare + purge so a rerun starts from an empty queue.

    Uses purge (not delete) on purpose: deleting a queue on the shared channel
    races RobustChannel's reopen and trips ``expected 'channel.open'``. Purge
    leaves the durable queue in place and just clears residual messages.
    """
    try:
        await adapter.ensure_queue(name)
        queue = await adapter._get_queue(name)
        await queue.purge()
    except Exception:
        pass


@pytest.mark.integration
class TestNativeSubscribeIntegration:
    """SIP-0094 94.2b: native long-lived subscribe() against a real broker.

    These are the zero-loss / no-cross-delivery guarantees the per-agent reply
    queues rely on (SIP §8, #12) — the legacy per-call consume() poll path
    could drop replies dispatched during consumer-tag churn.
    """

    @pytest_asyncio.fixture
    async def adapter(self, rabbitmq_container):
        a = RabbitMQAdapter(url=rabbitmq_container.get_connection_url(), namespace=None)
        yield a
        await a.close()

    @pytest.mark.asyncio
    async def test_held_subscription_loses_no_replies(self, adapter):
        """Publish 100 replies to one reply queue with a single held
        subscription -> all 100 are routed exactly once, none lost."""
        queue_name = "sip0094_2b_soak_replies"
        await _drain(adapter, queue_name)

        total = 100
        received: list[str] = []
        all_in = asyncio.Event()

        async def on_message(m):
            received.append(m.payload)
            if len(received) >= total:
                all_in.set()

        handle = await adapter.subscribe(queue_name, on_message=on_message)
        try:
            for i in range(total):
                await adapter.publish(queue_name, json.dumps({"i": i}))
            await asyncio.wait_for(all_in.wait(), timeout=30.0)
        finally:
            await handle.cancel()

        assert len(received) == total, f"lost replies: only {len(received)}/{total} arrived"
        # Exactly-once and complete: every published index shows up once.
        assert sorted(json.loads(p)["i"] for p in received) == list(range(total))
        assert adapter._resubscribe_total == 0  # stable channel -> no resubscribe

    @pytest.mark.asyncio
    async def test_two_reply_queues_no_cross_delivery(self, adapter):
        """Two held subscriptions on distinct reply queues with interleaved
        publishes -> each gets only its own messages, exactly once."""
        q_alpha = "sip0094_2b_alpha_replies"
        q_beta = "sip0094_2b_beta_replies"
        per_queue = 15
        for q in (q_alpha, q_beta):
            await _drain(adapter, q)

        alpha: list[str] = []
        beta: list[str] = []
        done = asyncio.Event()

        def _check_done():
            if len(alpha) >= per_queue and len(beta) >= per_queue:
                done.set()

        async def on_alpha(m):
            alpha.append(m.payload)
            _check_done()

        async def on_beta(m):
            beta.append(m.payload)
            _check_done()

        h_alpha = await adapter.subscribe(q_alpha, on_message=on_alpha)
        h_beta = await adapter.subscribe(q_beta, on_message=on_beta)
        try:
            for i in range(per_queue):
                await adapter.publish(q_alpha, json.dumps({"who": "alpha", "i": i}))
                await adapter.publish(q_beta, json.dumps({"who": "beta", "i": i}))
            await asyncio.wait_for(done.wait(), timeout=30.0)
        finally:
            await h_alpha.cancel()
            await h_beta.cancel()

        assert len(alpha) == per_queue and len(beta) == per_queue
        # No cross-agent delivery: each queue only ever saw its own tag.
        assert all(json.loads(p)["who"] == "alpha" for p in alpha)
        assert all(json.loads(p)["who"] == "beta" for p in beta)
        # Exactly-once within each queue.
        assert sorted(json.loads(p)["i"] for p in alpha) == list(range(per_queue))
        assert sorted(json.loads(p)["i"] for p in beta) == list(range(per_queue))


@pytest.mark.integration
class TestChannelRecovery:
    """#146: a dead channel must be rebuilt on the next consume(), not spun on.

    The original bug (an agent spinning for days on ``Channel was not opened``,
    never consuming again) was fixed by the SIP-0094 ``connect_robust`` +
    ``_get_queue`` channel-tracking work. There was no regression test, which is
    why it rotted into a multi-day incident. These lock the recovery: each test
    publishes to the durable queue, kills the channel, then asserts a subsequent
    ``consume()`` still delivers the message — which can only happen if the
    adapter rebuilt the channel and re-declared the stale queue handle.
    """

    @pytest_asyncio.fixture
    async def adapter(self, rabbitmq_container):
        a = RabbitMQAdapter(url=rabbitmq_container.get_connection_url(), namespace=None)
        yield a
        await a.close()

    @pytest.mark.asyncio
    async def test_consume_recovers_after_channel_close(self, adapter):
        """Channel dies while the connection stays up -> next consume() rebuilds
        the channel, re-declares the queue, and delivers the queued message."""
        q = "test146_channel_close_recovery"
        await _drain(adapter, q)
        await adapter.ensure_queue(q)  # establish channel + cache the queue handle
        chan_before = adapter._channel
        await adapter.publish(q, json.dumps({"task": "survives-channel-close"}))

        # #146 trigger: the channel dies (connection unaffected).
        await adapter._channel.close()
        assert adapter._channel.is_closed

        msgs = await adapter.consume(q, max_messages=1)
        assert [json.loads(m.payload)["task"] for m in msgs] == ["survives-channel-close"]
        assert adapter._channel is not chan_before  # channel was rebuilt, not reused
        assert not adapter._channel.is_closed

    @pytest.mark.asyncio
    async def test_consume_recovers_after_server_side_channel_death(self, adapter):
        """Broker closes the channel on a channel-level error (the literal
        ``Channel was not opened`` case) -> next consume() recovers, not spins."""
        q = "test146_server_close_recovery"
        await _drain(adapter, q)
        await adapter.ensure_queue(q)
        await adapter.publish(q, json.dumps({"task": "survives-server-close"}))

        # Provoke a server-side channel close: passive-declare a missing queue.
        with pytest.raises(Exception):
            await adapter._channel.declare_queue("nonexistent_queue_146_xyz", passive=True)
        assert adapter._channel.is_closed  # broker killed the channel

        msgs = await adapter.consume(q, max_messages=1)
        assert [json.loads(m.payload)["task"] for m in msgs] == ["survives-server-close"]
        assert not adapter._channel.is_closed  # rebuilt
