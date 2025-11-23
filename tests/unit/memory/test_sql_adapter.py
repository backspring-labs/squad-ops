"""
Unit tests for SqlAdapter
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncpg
from agents.memory.sql_adapter import SqlAdapter


@pytest.fixture
def mock_db_pool():
    """Create mock database pool"""
    pool = AsyncMock(spec=asyncpg.Pool)
    
    # Mock connection context manager
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value="test-uuid-123")
    mock_conn.fetch = AsyncMock(return_value=[
        {
            'id': 'test-uuid-123',
            'agent': 'TestAgent',
            'ns': 'squad',
            'pid': 'PID-001',
            'ecid': 'ECID-001',
            'tags': ['test'],
            'importance': 0.8,
            'status': 'validated',
            'validator': 'lead-agent',
            'content': {'action': 'test'},
            'created_at': None
        }
    ])
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")
    
    # Create context manager
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
def sql_adapter(mock_db_pool):
    """Create SqlAdapter instance for testing"""
    return SqlAdapter(mock_db_pool)


@pytest.mark.asyncio
async def test_sql_adapter_put(sql_adapter):
    """Test storing memory in SqlAdapter"""
    item = {
        'agent': 'TestAgent',
        'ns': 'squad',
        'pid': 'PID-001',
        'ecid': 'ECID-001',
        'tags': ['test'],
        'importance': 0.8,
        'status': 'validated',
        'validator': 'lead-agent',
        'content': {'action': 'test', 'result': 'success'}
    }
    
    mem_id = await sql_adapter.put(item)
    
    assert mem_id is not None
    assert isinstance(mem_id, str)


@pytest.mark.asyncio
async def test_sql_adapter_get(sql_adapter):
    """Test retrieving memories from SqlAdapter"""
    results = await sql_adapter.get("test", k=10)
    
    assert isinstance(results, list)
    assert len(results) > 0
    
    # Check result structure
    result = results[0]
    assert 'id' in result
    assert 'agent' in result
    assert 'content' in result


@pytest.mark.asyncio
async def test_sql_adapter_get_with_filters(sql_adapter):
    """Test retrieving memories with filters"""
    results = await sql_adapter.get("test", k=10, agent='TestAgent', pid='PID-001')
    
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_sql_adapter_promote(sql_adapter):
    """Test promoting memory"""
    mem_id = "test-uuid-123"
    result = await sql_adapter.promote(mem_id, "lead-agent", "squad")
    
    assert result == mem_id


@pytest.mark.asyncio
async def test_sql_adapter_put_if_not_exists_new_memory(sql_adapter):
    """Test put_if_not_exists stores memory when it doesn't exist"""
    mock_conn = AsyncMock()
    
    # Make fetchval return None first (doesn't exist), then new ID (after insert)
    call_count = [0]
    async def fetchval_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return None  # First call: check existence
        else:
            return "new-uuid-456"  # Second call: insert
    
    mock_conn.fetchval = AsyncMock(side_effect=fetchval_side_effect)
    
    class MockConnectionContext:
        def __init__(self, conn):
            self.conn = conn
        
        async def __aenter__(self):
            return self.conn
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    
    sql_adapter.db_pool.acquire = MagicMock(return_value=MockConnectionContext(mock_conn))
    
    item = {
        'agent': 'TestAgent',
        'ns': 'squad',
        'pid': 'PID-001',
        'ecid': 'ECID-001',
        'tags': ['test'],
        'importance': 0.8,
        'status': 'validated',
        'validator': 'lead-agent',
        'content': {'action': 'role_identity', 'result': {'role': 'qa'}}
    }
    
    mem_id = await sql_adapter.put_if_not_exists(item)
    
    assert mem_id is not None
    assert isinstance(mem_id, str)
    # Should have called fetchval at least once (check existence)
    assert mock_conn.fetchval.call_count >= 1


@pytest.mark.asyncio
async def test_sql_adapter_put_if_not_exists_existing_memory(sql_adapter):
    """Test put_if_not_exists skips storage when memory already exists"""
    mock_conn = AsyncMock()
    # Mock fetchval to return existing ID (memory exists)
    mock_conn.fetchval = AsyncMock(return_value="existing-uuid-123")
    
    class MockConnectionContext:
        def __init__(self, conn):
            self.conn = conn
        
        async def __aenter__(self):
            return self.conn
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    
    sql_adapter.db_pool.acquire = MagicMock(return_value=MockConnectionContext(mock_conn))
    
    item = {
        'agent': 'TestAgent',
        'ns': 'squad',
        'pid': 'PID-001',
        'ecid': 'ECID-001',
        'tags': ['test'],
        'importance': 0.8,
        'status': 'validated',
        'validator': 'lead-agent',
        'content': {'action': 'role_identity', 'result': {'role': 'qa'}}
    }
    
    mem_id = await sql_adapter.put_if_not_exists(item)
    
    assert mem_id is None
    # Should have called fetchval once (check existence)
    assert mock_conn.fetchval.call_count == 1

