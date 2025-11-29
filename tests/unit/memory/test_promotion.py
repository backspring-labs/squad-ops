"""
Unit tests for promotion service
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.memory.lancedb_adapter import LanceDBAdapter
from agents.memory.promotion import PromotionService
from agents.memory.sql_adapter import SqlAdapter


@pytest.fixture
def mock_lancedb_adapter():
    """Create mock LanceDBAdapter"""
    adapter = AsyncMock(spec=LanceDBAdapter)
    adapter.get = AsyncMock(return_value=[{
        'id': 'test-mem-id',
        'ns': 'role',
        'agent': 'TestAgent',
        'tags': ['test'],
        'content': {'action': 'test', 'pid': 'PID-001', 'ecid': 'ECID-001'},
        'importance': 0.8
    }])
    return adapter


@pytest.fixture
def mock_sql_adapter():
    """Create mock SqlAdapter"""
    adapter = AsyncMock(spec=SqlAdapter)
    adapter.put = AsyncMock(return_value="promoted-uuid-123")
    return adapter


@pytest.fixture
def mock_db_pool():
    """Create mock database pool"""
    pool = AsyncMock()
    pool.acquire = AsyncMock()
    
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=3)  # reuse count
    mock_conn.execute = AsyncMock()
    
    class MockConnectionContext:
        def __init__(self, conn):
            self.conn = conn
        
        async def __aenter__(self):
            return self.conn
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    
    pool.acquire = MagicMock(return_value=MockConnectionContext(mock_conn))
    
    return pool


@pytest.fixture
def promotion_service(mock_lancedb_adapter, mock_sql_adapter, mock_db_pool):
    """Create PromotionService instance"""
    return PromotionService(mock_lancedb_adapter, mock_sql_adapter, mock_db_pool)


@pytest.mark.asyncio
async def test_promotion_service_get_reuse_count(promotion_service):
    """Test getting reuse count"""
    count = await promotion_service.get_reuse_count("test-mem-id", "TestAgent")
    
    assert isinstance(count, int)
    assert count >= 0


@pytest.mark.asyncio
async def test_promotion_service_log_access(promotion_service):
    """Test logging memory access"""
    await promotion_service.log_memory_access("test-mem-id", "TestAgent", "test query")
    
    # Should not raise exception
    assert True


@pytest.mark.asyncio
async def test_promotion_service_promote_memory(promotion_service):
    """Test promoting memory"""
    promoted_id = await promotion_service.promote_memory(
        "test-mem-id",
        "lead-agent",
        "TestAgent",
        auto_promote=True
    )
    
    assert promoted_id is not None
    assert isinstance(promoted_id, str)


@pytest.mark.asyncio
async def test_promotion_service_get_promoted_memories(promotion_service):
    """Test getting promoted memories"""
    mock_sql_adapter = promotion_service.sql_adapter
    mock_sql_adapter.get = AsyncMock(return_value=[
        {'id': 'mem1', 'agent': 'TestAgent'},
        {'id': 'mem2', 'agent': 'TestAgent'}
    ])
    
    memories = await promotion_service.get_promoted_memories(agent='TestAgent')
    
    assert isinstance(memories, list)
    assert len(memories) == 2

