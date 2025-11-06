"""
Unit tests for BaseAgent memory integration
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.base_agent import BaseAgent


class MemoryTestAgent(BaseAgent):
    """Concrete agent for testing memory functionality"""
    
    async def process_task(self, task):
        return {'status': 'completed'}
    
    async def handle_message(self, message):
        """Required abstract method"""
        return {'status': 'handled'}


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
    with patch('agents.memory.lancedb_adapter.LanceDBAdapter') as MockLanceDBAdapter, \
         patch('agents.memory.sql_adapter.SqlAdapter') as MockSqlAdapter:
        
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
            payload={'result': 'success'},
            importance=0.8,
            task_context={'pid': 'PID-001', 'ecid': 'ECID-001'}
        )
        
        assert mem_id is not None
        assert mem_id == "test-mem-id"


@pytest.mark.asyncio
async def test_base_agent_extract_memory_context():
    """Test _extract_memory_context method"""
    agent = MemoryTestAgent("TestAgent", "test", "test")
    
    # Test with direct keys
    task1 = {'pid': 'PID-001', 'ecid': 'ECID-001'}
    context1 = agent._extract_memory_context(task1)
    assert context1['pid'] == 'PID-001'
    assert context1['ecid'] == 'ECID-001'
    
    # Test with context dict
    task2 = {'context': {'pid': 'PID-002', 'ecid': 'ECID-002'}}
    context2 = agent._extract_memory_context(task2)
    assert context2['pid'] == 'PID-002'
    assert context2['ecid'] == 'ECID-002'
    
    # Test with payload
    task3 = {'payload': {'pid': 'PID-003', 'ecid': 'ECID-003'}}
    context3 = agent._extract_memory_context(task3)
    assert context3['pid'] == 'PID-003'
    assert context3['ecid'] == 'ECID-003'
    
    # Test with missing keys
    task4 = {}
    context4 = agent._extract_memory_context(task4)
    assert context4['pid'] == 'unknown'
    assert context4['ecid'] == 'unknown'

