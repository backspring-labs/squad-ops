"""
Unit tests for BaseAgent memory integration
"""

from unittest.mock import AsyncMock, patch

import pytest

from agents.base_agent import BaseAgent


class MemoryTestAgent(BaseAgent):
    """Concrete agent for testing memory functionality"""

    async def process_task(self, task):
        return {"status": "completed"}

    async def handle_agent_request(self, request):
        """Required abstract method"""
        from datetime import datetime

        from agents.specs.agent_response import AgentResponse, Timing

        return AgentResponse.success(
            result={"status": "completed"},
            idempotency_key="test-key",
            timing=Timing.create(datetime.utcnow()),
        )

    async def handle_message(self, message):
        """Required abstract method"""
        return {"status": "handled"}


@pytest.fixture
def mock_memory_provider():
    """Create mock memory provider"""
    provider = AsyncMock()
    provider.put = AsyncMock(return_value="test-memory-id")
    provider.get = AsyncMock(return_value=[])
    provider.promote = AsyncMock(return_value="promoted-id")
    return provider


@pytest.fixture
def mock_sql_adapter():
    """Create mock SQL adapter"""
    adapter = AsyncMock()
    adapter.put = AsyncMock(return_value="promoted-uuid")
    adapter.get = AsyncMock(return_value=[])
    adapter.promote = AsyncMock(return_value="promoted-id")
    return adapter


@pytest.mark.asyncio
async def test_base_agent_record_memory():
    """Test record_memory method in BaseAgent"""
    from unittest.mock import MagicMock

    with (
        patch("agents.memory.lancedb_adapter.LanceDBAdapter") as MockLanceDBAdapter,
        patch("agents.memory.sql_adapter.SqlAdapter") as MockSqlAdapter,
        patch.object(MemoryTestAgent, "_initialize_llm_client", return_value=MagicMock()),
    ):
        mock_lancedb = AsyncMock()
        mock_lancedb.put = AsyncMock(return_value="test-mem-id")
        MockLanceDBAdapter.return_value = mock_lancedb

        mock_sql = AsyncMock()
        MockSqlAdapter.return_value = mock_sql

        agent = MemoryTestAgent("TestAgent", "test", "test")
        agent.db_pool = AsyncMock()
        agent.redis_client = AsyncMock()

        # Initialize memory providers
        await agent._initialize_memory_providers()

        # Test record_memory
        mem_id = await agent.record_memory(
            kind="test_action",
            payload={"result": "success"},
            importance=0.8,
            task_context={"pid": "PID-001", "cycle_id": "CYCLE-001"},  # SIP-0048: renamed from ecid
        )

        assert mem_id is not None
        assert mem_id == "test-mem-id"


@pytest.mark.asyncio
async def test_base_agent_extract_memory_context():
    """Test _extract_memory_context method"""
    from unittest.mock import MagicMock

    with patch.object(MemoryTestAgent, "_initialize_llm_client", return_value=MagicMock()):
        agent = MemoryTestAgent("TestAgent", "test", "test")

        # Test with direct keys (SIP-0048: renamed from ecid to cycle_id)
        task1 = {"pid": "PID-001", "cycle_id": "CYCLE-001"}  # SIP-0048: renamed from ecid
        context1 = agent._extract_memory_context(task1)
        assert context1["pid"] == "PID-001"
        assert context1["cycle_id"] == "CYCLE-001"  # SIP-0048: renamed from ecid

        # Test with context dict (SIP-0048: renamed from ecid to cycle_id)
        task2 = {
            "context": {"pid": "PID-002", "cycle_id": "CYCLE-002"}
        }  # SIP-0048: renamed from ecid
        context2 = agent._extract_memory_context(task2)
        assert context2["pid"] == "PID-002"
        assert context2["cycle_id"] == "CYCLE-002"  # SIP-0048: renamed from ecid

        # Test with payload (cycle_id only)
        task3 = {
            "payload": {"pid": "PID-003", "cycle_id": "CYCLE-003"}
        }  # SIP-0048: renamed from ecid
        context3 = agent._extract_memory_context(task3)
        assert context3["pid"] == "PID-003"
        assert context3["cycle_id"] == "CYCLE-003"  # SIP-0048: renamed from ecid

        # Test with missing keys
        task4 = {}
        context4 = agent._extract_memory_context(task4)
        assert context4["pid"] == "unknown"
        assert context4["cycle_id"] == "unknown"  # SIP-0048: renamed from ecid


@pytest.mark.asyncio
async def test_base_agent_record_memory_role_identity_uses_singleton():
    """Test that role_identity memories use put_if_not_exists (singleton storage)"""
    from unittest.mock import MagicMock

    with (
        patch("agents.memory.lancedb_adapter.LanceDBAdapter") as MockLanceDBAdapter,
        patch("agents.memory.sql_adapter.SqlAdapter") as MockSqlAdapter,
        patch.object(MemoryTestAgent, "_initialize_llm_client", return_value=MagicMock()),
    ):
        mock_lancedb = AsyncMock()
        mock_lancedb.put = AsyncMock(return_value="regular-mem-id")
        mock_lancedb.put_if_not_exists = AsyncMock(return_value="role-identity-id")
        MockLanceDBAdapter.return_value = mock_lancedb

        mock_sql = AsyncMock()
        MockSqlAdapter.return_value = mock_sql

        agent = MemoryTestAgent("TestAgent", "test", "test")
        agent.db_pool = AsyncMock()
        agent.redis_client = AsyncMock()

        # Initialize memory providers
        await agent._initialize_memory_providers()

        # Test role_identity uses put_if_not_exists
        mem_id = await agent.record_memory(
            kind="role_identity",
            payload={"role_name": "qa", "role_context": "You are a QA agent"},
            importance=1.0,
            ns="role",
            task_context=None,
        )

        assert mem_id is not None
        assert mem_id == "role-identity-id"
        # Verify put_if_not_exists was called, not put
        mock_lancedb.put_if_not_exists.assert_called_once()
        mock_lancedb.put.assert_not_called()

        # Test regular memory still uses put
        mem_id2 = await agent.record_memory(
            kind="test_action",
            payload={"result": "success"},
            importance=0.8,
            ns="role",
            task_context={"pid": "PID-001", "cycle_id": "CYCLE-001"},  # SIP-0048: renamed from ecid
        )

        assert mem_id2 == "regular-mem-id"
        # Verify put was called for regular memory
        mock_lancedb.put.assert_called_once()
