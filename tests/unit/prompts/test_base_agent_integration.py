"""
Unit tests for BaseAgent prompt service integration.

Verifies that BaseAgent correctly uses the injected PromptService.
"""

from unittest.mock import MagicMock, Mock

from squadops.execution.agent import BaseAgent
from squadops.ports.prompts.service import PromptService
from squadops.prompts.models import AssembledPrompt


def create_mock_prompt_service(content: str = "Test prompt content") -> PromptService:
    """Create a mock PromptService."""
    service = Mock(spec=PromptService)
    service.get_system_prompt.return_value = AssembledPrompt(
        content=content,
        fragment_hashes=("hash1", "hash2"),
        assembly_hash="assembly_hash",
        role="lead",
        hook="agent_start",
        version="0.8.5",
    )
    return service


class TestBaseAgentPromptIntegration:
    """Tests for BaseAgent prompt service integration."""

    def test_agent_with_prompt_service(self):
        """Agent should use prompt service to get system prompt."""
        prompt_service = create_mock_prompt_service("Lead agent prompt content")

        agent = BaseAgent(
            secret_manager=MagicMock(),
            db_runtime=MagicMock(),
            heartbeat_reporter=MagicMock(),
            agent_id="lead-001",
            prompt_service=prompt_service,
        )

        result = agent.get_system_prompt()

        assert result == "Lead agent prompt content"
        prompt_service.get_system_prompt.assert_called_once_with("lead")

    def test_agent_without_prompt_service(self):
        """Agent without prompt service should return empty string."""
        agent = BaseAgent(
            secret_manager=MagicMock(),
            db_runtime=MagicMock(),
            heartbeat_reporter=MagicMock(),
            agent_id="dev-002",
            prompt_service=None,
        )

        result = agent.get_system_prompt()

        assert result == ""

    def test_role_extraction_with_hyphen(self):
        """Role should be extracted from agent_id with hyphen."""
        prompt_service = create_mock_prompt_service()

        agent = BaseAgent(
            secret_manager=MagicMock(),
            db_runtime=MagicMock(),
            heartbeat_reporter=MagicMock(),
            agent_id="qa-test-instance-001",
            prompt_service=prompt_service,
        )

        agent.get_system_prompt()

        # Should extract "qa" from "qa-test-instance-001"
        prompt_service.get_system_prompt.assert_called_once_with("qa")

    def test_role_extraction_without_hyphen(self):
        """Role should be the full agent_id if no hyphen."""
        prompt_service = create_mock_prompt_service()

        agent = BaseAgent(
            secret_manager=MagicMock(),
            db_runtime=MagicMock(),
            heartbeat_reporter=MagicMock(),
            agent_id="strat",
            prompt_service=prompt_service,
        )

        agent.get_system_prompt()

        prompt_service.get_system_prompt.assert_called_once_with("strat")

    def test_prompt_service_stored_as_attribute(self):
        """Prompt service should be accessible as agent attribute."""
        prompt_service = create_mock_prompt_service()

        agent = BaseAgent(
            secret_manager=MagicMock(),
            db_runtime=MagicMock(),
            heartbeat_reporter=MagicMock(),
            agent_id="dev-001",
            prompt_service=prompt_service,
        )

        assert agent.prompt_service is prompt_service
