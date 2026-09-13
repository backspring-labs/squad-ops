"""
Unit tests for QueuePort interface and adapters.
Tests port isolation, factory resolution, and payload integrity.
"""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from adapters.comms.factory import create_a2a_client, create_a2a_server, create_queue_adapter
from squadops.comms.queue_message import QueueMessage
from squadops.config.schema import A2AConfig, CommsConfig, QueueConfig, RabbitMQConfig, RedisConfig
from squadops.ports.comms.queue import QueuePort


class MockQueueProvider(QueuePort):
    """Mock queue provider for testing port isolation."""

    def __init__(self):
        self.published_messages = []
        self.consumed_messages = []
        self.acked_messages = []
        self.retried_messages = []

    async def publish(
        self, queue_name: str, payload: str, delay_seconds: int | None = None
    ) -> None:
        """Mock publish."""
        self.published_messages.append((queue_name, payload, delay_seconds))

    async def consume(self, queue_name: str, max_messages: int = 1) -> list[QueueMessage]:
        """Mock consume."""
        return self.consumed_messages[:max_messages]

    async def ack(self, message: QueueMessage) -> None:
        """Mock ack."""
        self.acked_messages.append(message)

    async def retry(self, message: QueueMessage, delay_seconds: int) -> None:
        """Mock retry."""
        self.retried_messages.append((message, delay_seconds))

    async def health(self) -> dict:
        """Mock health."""
        return {"status": "healthy", "connected": True}

    def capabilities(self) -> dict[str, bool]:
        """Mock capabilities."""
        return {"delay": True, "fifo": False, "priority": True}


@pytest.mark.unit
class TestQueuePortIsolation:
    """Test that domain code can use QueuePort without RabbitMQ dependencies."""

    def test_port_interface_can_be_imported_without_rabbitmq(self):
        """Verify QueuePort can be imported without aio_pika."""
        # This test verifies that the port interface itself doesn't require
        # infrastructure dependencies
        from squadops.ports.comms.queue import QueuePort

        assert QueuePort is not None
        assert hasattr(QueuePort, "publish")
        assert hasattr(QueuePort, "consume")
        assert hasattr(QueuePort, "ack")
        assert hasattr(QueuePort, "retry")
        assert hasattr(QueuePort, "health")
        assert hasattr(QueuePort, "capabilities")

    @pytest.mark.asyncio
    async def test_mock_provider_implements_port(self):
        """Verify mock provider can be used as QueuePort."""
        provider = MockQueueProvider()

        # Test all port methods
        await provider.publish("test_queue", '{"test": "data"}', delay_seconds=5)
        assert len(provider.published_messages) == 1

        messages = await provider.consume("test_queue", max_messages=1)
        assert isinstance(messages, list)

        health = await provider.health()
        assert health["status"] == "healthy"

        caps = provider.capabilities()
        assert "delay" in caps
        assert "fifo" in caps
        assert "priority" in caps


@pytest.mark.unit
class TestFactoryResolution:
    """The typed factories (#301) — what each root calls, and what a wrong selector does.

    The profile-dict factory these replace resolved ``secret://`` itself; the loader does that
    before any factory runs, so that behaviour is gone rather than re-tested. It also forwarded
    a ``namespace`` the adapter accepts and no root ever set — dropped, named in the PR.
    """

    @staticmethod
    def _comms(**over) -> CommsConfig:
        return CommsConfig(
            queue=QueueConfig(provider="rabbitmq"),
            a2a=A2AConfig(provider="http", **over),
            rabbitmq=RabbitMQConfig(url="amqp://user:pass@localhost:5672/vhost"),
            redis=RedisConfig(url="redis://localhost:6379/0"),
        )

    def test_queue_adapter_is_built_from_the_vendor_url_verbatim(self):
        """The runtime root's call: no prefetch kwarg, so the adapter keeps its own default."""
        with patch("adapters.comms.factory.RabbitMQAdapter") as cls:
            create_queue_adapter(self._comms())
        cls.assert_called_once_with(url="amqp://user:pass@localhost:5672/vhost")

    def test_prefetch_count_passes_through_when_the_root_sets_it(self):
        """The agent root's call (#323: one unacked message at a time)."""
        with patch("adapters.comms.factory.RabbitMQAdapter") as cls:
            create_queue_adapter(self._comms(), prefetch_count=1)
        assert cls.call_args.kwargs["prefetch_count"] == 1

    def test_a_selector_the_factory_does_not_know_fails_loudly_by_name(self):
        """Unreachable through load_config (the field is a Literal), so built by hand: the
        factory must not silently pick a vendor — R2, the masking-fallback rule."""
        comms = self._comms()
        comms.queue = QueueConfig.model_construct(provider="kafka")
        with pytest.raises(ValueError, match="comms.queue.provider='kafka'"):
            create_queue_adapter(comms)

    def test_the_selector_is_required_not_defaulted(self):
        """R2 at the schema: a CommsConfig with no queue section does not validate."""
        with pytest.raises(ValidationError, match="queue"):
            CommsConfig(
                a2a=A2AConfig(provider="http"),
                rabbitmq=RabbitMQConfig(url="amqp://localhost/"),
                redis=RedisConfig(url="redis://localhost/0"),
            )

    def test_a2a_client_takes_its_timeouts_from_config(self):
        """The two constructor defaults became tunables (R5); a value set in config must
        reach the adapter, or the tunable is decoration."""
        with patch("adapters.comms.factory.A2AClientAdapter") as cls:
            create_a2a_client(self._comms(timeout_seconds=7.5, agent_card_timeout_seconds=2.5))
        cls.assert_called_once_with(timeout_seconds=7.5, agent_card_timeout_seconds=2.5)

    def test_a2a_server_binds_card_executor_and_port(self):
        # Patched at its DEFINING module, not on the factory: `create_a2a_server` imports
        # `A2AServerAdapter` inside the function, because at module scope the `a2a` SDK it
        # pulls made the whole factory unimportable in the runtime-api image, whose lock
        # ships no SDK it never calls (deploy B, 2026-09-11). A local import has no
        # attribute on the factory to patch.
        card, executor = object(), object()
        with patch("adapters.comms.a2a_server.A2AServerAdapter") as cls:
            create_a2a_server(self._comms(), agent_card=card, executor=executor, port=8080)
        kw = cls.call_args.kwargs
        assert (kw["agent_card"], kw["executor"], kw["port"]) == (card, executor, 8080)


@pytest.mark.unit
class TestPayloadIntegrity:
    """Test that TaskEnvelope JSON remains unchanged through adapter."""

    @pytest.mark.asyncio
    async def test_payload_integrity_through_mock_adapter(self):
        """Verify payload integrity through mock adapter round-trip."""
        # Sample ACI TaskEnvelope JSON
        original_payload = '{"task_id":"task-001","agent_id":"agent-001","cycle_id":"CYCLE-001","pulse_id":"pulse-001","project_id":"project-001","task_type":"code_generate","inputs":{},"correlation_id":"corr-001","causation_id":"cause-001","trace_id":"trace-001","span_id":"span-001"}'

        provider = MockQueueProvider()

        # Publish message
        await provider.publish("test_queue", original_payload)

        # Verify payload was stored correctly
        assert len(provider.published_messages) == 1
        published_queue, published_payload, _ = provider.published_messages[0]
        assert published_payload == original_payload

        # Simulate consume
        message = QueueMessage(
            message_id="msg-001",
            queue_name="test_queue",
            payload=original_payload,
            receipt_handle="handle-001",
            attributes={},
        )
        provider.consumed_messages = [message]

        consumed_messages = await provider.consume("test_queue", max_messages=1)
        assert len(consumed_messages) == 1
        consumed_payload = consumed_messages[0].payload

        # Verify payload integrity
        assert consumed_payload == original_payload

        # Verify identity fields are preserved (parse JSON to check)
        import json

        original_data = json.loads(original_payload)
        consumed_data = json.loads(consumed_payload)

        # Check identity fields
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
            assert original_data[field] == consumed_data[field], (
                f"Identity field {field} was mutated"
            )
