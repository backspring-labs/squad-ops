"""
Unit tests for QueuePort interface and adapters.
Tests port isolation, factory resolution, and payload integrity.
"""

from unittest.mock import MagicMock, patch

import pytest

from adapters.comms.factory import get_queue_adapter, validate_comms_config
from squadops.comms.queue_message import QueueMessage
from squadops.core.secrets import SecretManager
from squadops.ports.comms.queue import QueuePort
from squadops.ports.secrets import SecretProvider


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


class MockSecretProvider(SecretProvider):
    """Mock secret provider for testing factory resolution."""

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
    """Test factory correctly resolves secret:// references."""

    def test_factory_resolves_secret_references(self):
        """Test factory resolves secret:// references using SecretManager."""
        # Create mock secret provider
        mock_provider = MockSecretProvider({"rabbitmq_password": "secret123"})
        secret_manager = SecretManager(mock_provider)

        # Create profile with secret:// reference
        profile = {
            "comms": {
                "provider": "rabbitmq",
                "url": "amqp://user:secret://rabbitmq_password@localhost:5672/vhost",
            }
        }

        # Factory should resolve the secret
        with patch("adapters.comms.factory.RabbitMQAdapter") as mock_adapter_class:
            mock_adapter_instance = MagicMock()
            mock_adapter_class.return_value = mock_adapter_instance

            adapter = get_queue_adapter(profile, secret_manager)

            # Verify adapter was created
            assert adapter is not None
            # Verify factory was called (adapter creation happens)
            mock_adapter_class.assert_called_once()

            # Verify the URL passed to adapter has resolved secret
            call_args = mock_adapter_class.call_args
            assert call_args is not None
            # The factory resolves the secret in the URL before passing to adapter
            resolved_url = call_args.kwargs.get("url")
            assert resolved_url is not None
            # The URL should have the secret resolved (not the secret:// reference)
            assert "secret://" not in resolved_url
            assert "secret123" in resolved_url

    def test_factory_validates_config(self):
        """Test factory validates configuration before creating adapter."""
        # Missing comms config
        profile = {}
        secret_manager = SecretManager(MockSecretProvider({}))

        with pytest.raises(ValueError, match="Communication configuration"):
            validate_comms_config(profile)

        # Missing provider
        profile = {"comms": {}}
        with pytest.raises(ValueError, match="Queue provider|Communication configuration"):
            validate_comms_config(profile)

        # Missing URL for rabbitmq
        profile = {"comms": {"provider": "rabbitmq"}}
        with pytest.raises(ValueError, match="RabbitMQ URL"):
            validate_comms_config(profile)

    def test_factory_handles_namespace(self):
        """Test factory correctly passes namespace to adapter."""
        profile = {
            "comms": {
                "provider": "rabbitmq",
                "url": "amqp://user:pass@localhost:5672/vhost",
                "namespace": "test_namespace",
            }
        }
        secret_manager = SecretManager(MockSecretProvider({}))

        with patch("adapters.comms.factory.RabbitMQAdapter") as mock_adapter_class:
            mock_adapter_instance = MagicMock()
            mock_adapter_class.return_value = mock_adapter_instance

            get_queue_adapter(profile, secret_manager)

            # Verify namespace was passed
            call_args = mock_adapter_class.call_args
            assert call_args is not None
            namespace = call_args.kwargs.get("namespace")
            assert namespace == "test_namespace"


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
