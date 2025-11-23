"""
Unit tests for LanceDBAdapter
"""

import pytest
import tempfile
import shutil
from unittest.mock import patch, MagicMock, AsyncMock
import sys


@pytest.fixture
def temp_db_path():
    """Create temporary database path for testing"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_lancedb_available():
    """Mock LanceDB availability and imports"""
    # Mock the imports before importing the adapter
    mock_lancedb_module = MagicMock()
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_db.open_table = MagicMock(side_effect=Exception("Table not found"))
    mock_db.create_table = MagicMock(return_value=mock_table)
    mock_lancedb_module.connect = MagicMock(return_value=mock_db)
    
    mock_pa = MagicMock()
    mock_pa.schema = MagicMock()
    mock_pa.field = MagicMock()
    mock_pa.string = MagicMock()
    mock_pa.list_ = MagicMock(return_value=MagicMock())
    mock_pa.float32 = MagicMock()
    mock_pa.timestamp = MagicMock()
    
    # Create a proper mock schema for the table
    mock_schema = MagicMock()
    mock_table.schema = mock_schema
    
    # Mock Table.from_pydict to return a mock table
    mock_table_instance = MagicMock()
    mock_pa.Table = MagicMock()
    mock_pa.Table.from_pydict = MagicMock(return_value=mock_table_instance)
    
    # Create a proper mock for pandas that can be used as DataFrame
    mock_pd = MagicMock()
    mock_pd.DataFrame = MagicMock()  # Callable mock, not just MagicMock class
    
    with patch.dict('sys.modules', {
        'lancedb': mock_lancedb_module,
        'pyarrow': mock_pa,
        'pandas': mock_pd
    }):
        with patch('agents.memory.lancedb_adapter.LANCEDB_AVAILABLE', True):
            # Also patch the module-level pd after import
            yield mock_db, mock_table, mock_pd


@pytest.mark.asyncio
async def test_lancedb_adapter_initialization(temp_db_path, mock_lancedb_available):
    """Test LanceDBAdapter initialization"""
    mock_db, mock_table, mock_pd = mock_lancedb_available
    from agents.memory.lancedb_adapter import LanceDBAdapter
    
    adapter = LanceDBAdapter("TestAgent", db_path=temp_db_path)
    
    assert adapter.agent_name == "TestAgent"
    assert adapter.db_path == temp_db_path
    assert adapter._table_name == "testagent_memories"


@pytest.mark.asyncio
async def test_generate_embedding_ollama(temp_db_path, mock_lancedb_available):
    """Test embedding generation using Ollama"""
    mock_db, mock_table, mock_pd = mock_lancedb_available
    from agents.memory.lancedb_adapter import LanceDBAdapter
    
    adapter = LanceDBAdapter("TestAgent", db_path=temp_db_path)
    
    # Mock Ollama API response
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1] * 768}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        embedding = adapter._generate_embedding("test text")
        
        assert len(embedding) == 768
        assert all(isinstance(x, float) for x in embedding)
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_generate_embedding_sentence_transformers_fallback(temp_db_path, mock_lancedb_available):
    """Test embedding generation fallback to SentenceTransformers"""
    mock_db, mock_table, mock_pd = mock_lancedb_available
    from agents.memory.lancedb_adapter import LanceDBAdapter
    
    adapter = LanceDBAdapter("TestAgent", db_path=temp_db_path)
    
    # Mock Ollama failure
    with patch('requests.post') as mock_post:
        mock_post.side_effect = Exception("Ollama unavailable")
        
        # Mock SentenceTransformers module
        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(tolist=lambda: [0.2] * 384)
        mock_st_module = MagicMock()
        mock_st_module.SentenceTransformer = MagicMock(return_value=mock_model)
        
        with patch.dict('sys.modules', {'sentence_transformers': mock_st_module}):
            embedding = adapter._generate_embedding("test text")
            
            # Should be padded to 768 dimensions
            assert len(embedding) == 768
            assert all(isinstance(x, float) for x in embedding)


@pytest.mark.asyncio
async def test_put_memory(temp_db_path, mock_lancedb_available):
    """Test storing a memory"""
    mock_db, mock_table, mock_pd = mock_lancedb_available
    from agents.memory.lancedb_adapter import LanceDBAdapter
    
    adapter = LanceDBAdapter("TestAgent", db_path=temp_db_path)
    adapter._table = mock_table
    
    # Ensure pd is available in the adapter module (it's conditionally imported)
    import agents.memory.lancedb_adapter as adapter_module
    adapter_module.pd = mock_pd
    
    # Mock DataFrame to return a proper mock instance
    mock_df_instance = MagicMock()
    mock_pd.DataFrame = MagicMock(return_value=mock_df_instance)
    
    # Get mock_pa from sys.modules (it was patched there by the fixture)
    # But don't modify sys.modules - only modify the adapter module
    import sys
    mock_pa = sys.modules.get('pyarrow')
    if mock_pa is None or not isinstance(mock_pa, MagicMock):
        # If not available, create a new mock
        mock_pa = MagicMock()
        mock_pa.Table = MagicMock()
        mock_pa.Table.from_pydict = MagicMock(return_value=MagicMock())
    
    # Ensure pa module is properly mocked in the adapter module
    # Always use the mock, even if pa is already imported
    # Store original to restore later
    original_pa = getattr(adapter_module, 'pa', None)
    adapter_module.pa = mock_pa
    # Ensure the mock is set up correctly
    adapter_module.pa.Table.from_pydict = MagicMock(return_value=MagicMock())
    
    try:
        # Mock embedding generation
        # Patch pa.Table.from_pydict to bypass schema validation
        with patch.object(adapter_module.pa.Table, 'from_pydict', return_value=MagicMock()) as mock_from_pydict:
            with patch.object(adapter, '_generate_embedding', return_value=[0.1] * 768):
                memory_item = {
                    'ns': 'role',
                    'agent': 'TestAgent',
                    'tags': ['test', 'memory'],
                    'content': {'action': 'test_action', 'result': {'status': 'success'}},
                    'importance': 0.8,
                    'pid': 'PID-001',
                    'ecid': 'ECID-001'
                }
                
                mem_id = await adapter.put(memory_item)
                
                assert mem_id is not None
                assert len(mem_id) == 16  # SHA256 hex digest first 16 chars
                mock_table.add.assert_called_once()
                # Verify PyArrow Table.from_pydict was called at least once
                assert mock_from_pydict.call_count >= 1
    finally:
        # Restore original pa module to avoid polluting other tests
        if original_pa is not None:
            adapter_module.pa = original_pa
        elif hasattr(adapter_module, 'pa'):
            delattr(adapter_module, 'pa')


@pytest.mark.asyncio
async def test_put_if_not_exists_new_memory(temp_db_path, mock_lancedb_available):
    """Test put_if_not_exists stores memory when it doesn't exist"""
    mock_db, mock_table, mock_pd = mock_lancedb_available
    from agents.memory.lancedb_adapter import LanceDBAdapter
    
    adapter = LanceDBAdapter("TestAgent", db_path=temp_db_path)
    adapter._table = mock_table
    
    import agents.memory.lancedb_adapter as adapter_module
    adapter_module.pd = mock_pd
    
    mock_df_instance = MagicMock()
    mock_pd.DataFrame = MagicMock(return_value=mock_df_instance)
    
    import sys
    mock_pa = sys.modules.get('pyarrow')
    if mock_pa is None or not isinstance(mock_pa, MagicMock):
        mock_pa = MagicMock()
        mock_pa.Table = MagicMock()
        mock_pa.Table.from_pydict = MagicMock(return_value=MagicMock())
    
    original_pa = getattr(adapter_module, 'pa', None)
    adapter_module.pa = mock_pa
    adapter_module.pa.Table.from_pydict = MagicMock(return_value=MagicMock())
    
    try:
        with patch.object(adapter_module.pa.Table, 'from_pydict', return_value=MagicMock()):
            with patch.object(adapter, '_generate_embedding', return_value=[0.1] * 768):
                # Mock get() to return empty list (memory doesn't exist)
                with patch.object(adapter, 'get', new_callable=AsyncMock, return_value=[]):
                    memory_item = {
                        'ns': 'role',
                        'agent': 'TestAgent',
                        'tags': ['test', 'memory'],
                        'content': {'action': 'role_identity', 'result': {'role': 'qa'}},
                        'importance': 1.0,
                        'pid': '',
                        'ecid': ''
                    }
                    
                    mem_id = await adapter.put_if_not_exists(memory_item)
                    
                    assert mem_id is not None
                    assert len(mem_id) == 16
                    mock_table.add.assert_called_once()
    finally:
        if original_pa is not None:
            adapter_module.pa = original_pa
        elif hasattr(adapter_module, 'pa'):
            delattr(adapter_module, 'pa')


@pytest.mark.asyncio
async def test_put_if_not_exists_existing_memory(temp_db_path, mock_lancedb_available):
    """Test put_if_not_exists skips storage when memory already exists"""
    mock_db, mock_table, mock_pd = mock_lancedb_available
    from agents.memory.lancedb_adapter import LanceDBAdapter
    
    adapter = LanceDBAdapter("TestAgent", db_path=temp_db_path)
    adapter._table = mock_table
    
    import agents.memory.lancedb_adapter as adapter_module
    adapter_module.pd = mock_pd
    
    memory_item = {
        'ns': 'role',
        'agent': 'TestAgent',
        'tags': ['test', 'memory'],
        'content': {'action': 'role_identity', 'result': {'role': 'qa'}},
        'importance': 1.0,
        'pid': '',
        'ecid': ''
    }
    
    # Mock get() to return existing memory
    existing_memory = [{'id': 'abc123def4567890', 'content': memory_item['content']}]
    with patch.object(adapter, 'get', new_callable=AsyncMock, return_value=existing_memory):
        mem_id = await adapter.put_if_not_exists(memory_item)
        
        assert mem_id is None
        # put() should not be called
        mock_table.add.assert_not_called()


@pytest.mark.asyncio
async def test_get_memories(temp_db_path, mock_lancedb_available):
    """Test retrieving memories"""
    mock_db, mock_table, mock_pd = mock_lancedb_available
    from agents.memory.lancedb_adapter import LanceDBAdapter
    
    adapter = LanceDBAdapter("TestAgent", db_path=temp_db_path)
    adapter._table = mock_table
    
    # Mock embedding generation
    with patch.object(adapter, '_generate_embedding', return_value=[0.1] * 768):
        # Mock search results
        mock_results_df = MagicMock()
        mock_results_df.__len__ = MagicMock(return_value=1)  # Support len() check
        mock_results_df.iterrows.return_value = [
            (0, {
                'id': 'mem-001',
                'ns': 'role',
                'agent': 'TestAgent',
                'pid': 'PID-001',
                'ecid': 'ECID-001',
                'tags': ['test'],
                'importance': 0.8,
                'content': '{"action": "test"}',
                'created_at': '2024-01-01T00:00:00'
            })
        ]
        
        mock_search_builder = MagicMock()
        mock_search_builder.where.return_value = mock_search_builder
        mock_search_builder.limit.return_value = mock_search_builder
        mock_search_builder.to_pandas.return_value = mock_results_df
        mock_table.search.return_value = mock_search_builder
        
        results = await adapter.get("test query", k=5)
        
        assert len(results) == 1
        assert results[0]['id'] == 'mem-001'
        mock_table.search.assert_called_once()


@pytest.mark.asyncio
async def test_get_memories_with_filters(temp_db_path, mock_lancedb_available):
    """Test retrieving memories with metadata filters"""
    mock_db, mock_table, mock_pd = mock_lancedb_available
    from agents.memory.lancedb_adapter import LanceDBAdapter
    
    adapter = LanceDBAdapter("TestAgent", db_path=temp_db_path)
    adapter._table = mock_table
    
    # Mock embedding generation
    with patch.object(adapter, '_generate_embedding', return_value=[0.1] * 768):
        # Mock search results
        mock_results_df = MagicMock()
        mock_results_df.iterrows.return_value = []
        
        mock_search_builder = MagicMock()
        mock_search_builder.where.return_value = mock_search_builder
        mock_search_builder.limit.return_value = mock_search_builder
        mock_search_builder.to_pandas.return_value = mock_results_df
        mock_table.search.return_value = mock_search_builder
        
        results = await adapter.get(
            "test query",
            k=5,
            ns='role',
            agent='TestAgent',
            tags=['test']
        )
        
        # Verify where clause was called
        mock_search_builder.where.assert_called_once()


@pytest.mark.asyncio
async def test_promote_memory(temp_db_path, mock_lancedb_available):
    """Test promote method (delegates to SqlAdapter)"""
    mock_db, mock_table, mock_pd = mock_lancedb_available
    from agents.memory.lancedb_adapter import LanceDBAdapter
    
    adapter = LanceDBAdapter("TestAgent", db_path=temp_db_path)
    
    mem_id = await adapter.promote("mem-001", "validator-agent", "squad")
    
    # Should return original memory ID (promotion handled by SqlAdapter)
    assert mem_id == "mem-001"


@pytest.mark.asyncio
async def test_get_memories_by_id(temp_db_path, mock_lancedb_available):
    """Test retrieving memories by memory ID filter"""
    mock_db, mock_table, mock_pd = mock_lancedb_available
    from agents.memory.lancedb_adapter import LanceDBAdapter
    
    adapter = LanceDBAdapter("TestAgent", db_path=temp_db_path)
    adapter._table = mock_table
    
    # Mock embedding generation
    with patch.object(adapter, '_generate_embedding', return_value=[0.1] * 768):
        # Mock search results
        mock_results_df = MagicMock()
        mock_results_df.__len__ = MagicMock(return_value=1)  # Support len() check
        mock_results_df.iterrows.return_value = [
            (0, {
                'id': 'mem-001',
                'ns': 'role',
                'agent': 'TestAgent',
                'pid': 'PID-001',
                'ecid': 'ECID-001',
                'tags': ['test'],
                'importance': 0.8,
                'content': '{"action": "test"}',
                'created_at': '2024-01-01T00:00:00'
            })
        ]
        
        mock_search_builder = MagicMock()
        mock_search_builder.where.return_value = mock_search_builder
        mock_search_builder.limit.return_value = mock_search_builder
        mock_search_builder.to_pandas.return_value = mock_results_df
        mock_table.search.return_value = mock_search_builder
        
        # Test filtering by memory ID
        results = await adapter.get("", k=10, mem_ids=['mem-001'])
        
        assert len(results) == 1
        assert results[0]['id'] == 'mem-001'
        # Verify where clause was called with ID filter
        mock_search_builder.where.assert_called_once()
        

@pytest.mark.asyncio
async def test_extract_content_text(temp_db_path, mock_lancedb_available):
    """Test content text extraction"""
    mock_db, mock_table, mock_pd = mock_lancedb_available
    from agents.memory.lancedb_adapter import LanceDBAdapter
    
    adapter = LanceDBAdapter("TestAgent", db_path=temp_db_path)
    
    # Test with dict content
    content_dict = {
        'action': 'test_action',
        'result': {'status': 'success', 'value': 42}
    }
    text = adapter._extract_content_text(content_dict)
    assert 'test_action' in text
    assert 'success' in text
    
    # Test with string content
    text = adapter._extract_content_text("simple string")
    assert text == "simple string"
