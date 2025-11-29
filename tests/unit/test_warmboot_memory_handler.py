#!/usr/bin/env python3
"""
Unit tests for WarmBootMemoryHandler capability
Tests WarmBoot memory loading
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.capabilities.warmboot_memory_handler import WarmBootMemoryHandler


class TestWarmBootMemoryHandler:
    """Test WarmBootMemoryHandler capability"""
    
    @pytest.fixture
    def mock_agent(self):
        """Create mock agent instance"""
        agent = MagicMock()
        agent.name = "test-agent"
        agent.sql_adapter = MagicMock()
        agent.record_memory = AsyncMock()
        return agent
    
    @pytest.fixture
    def handler(self, mock_agent):
        """Create WarmBootMemoryHandler instance"""
        return WarmBootMemoryHandler(mock_agent)
    
    @pytest.mark.unit
    def test_handler_initialization(self, mock_agent):
        """Test WarmBootMemoryHandler initialization"""
        handler = WarmBootMemoryHandler(mock_agent)
        assert handler.agent == mock_agent
        assert handler.name == "test-agent"
        assert handler.sql_adapter == mock_agent.sql_adapter
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_load_memories_success(self, handler, mock_agent):
        """Test loading memories successfully"""
        mock_memories = [
            {'id': 'mem-1', 'content': {'action': 'test', 'result': 'success'}},
            {'id': 'mem-2', 'content': {'action': 'test2', 'result': 'success'}}
        ]
        
        mock_agent.sql_adapter.get = AsyncMock(return_value=mock_memories)
        
        result = await handler.load_memories(ecid='ec-001', pid='p-001')
        
        assert result['memories_loaded'] is True
        assert result['memory_count'] == 2
        assert len(result['memories']) == 2
        assert hasattr(mock_agent, 'warmboot_memories')
        assert mock_agent.warmboot_memories == mock_memories
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_load_memories_no_sql_adapter(self, handler, mock_agent):
        """Test loading memories when SQL adapter not available"""
        handler.sql_adapter = None
        
        result = await handler.load_memories()
        
        assert result['memories_loaded'] is False
        assert result['memory_count'] == 0
        assert 'error' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_load_memories_no_memories(self, handler, mock_agent):
        """Test loading memories when none found"""
        mock_agent.sql_adapter.get = AsyncMock(return_value=[])
        
        result = await handler.load_memories(ecid='ec-001')
        
        assert result['memories_loaded'] is False
        assert result['memory_count'] == 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_load_memories_with_filters(self, handler, mock_agent):
        """Test loading memories with ECID and PID filters"""
        mock_agent.sql_adapter.get = AsyncMock(return_value=[])
        
        await handler.load_memories(ecid='ec-001', pid='p-001')
        
        # Verify get was called with filters
        call_kwargs = mock_agent.sql_adapter.get.call_args[1]
        assert call_kwargs['ecid'] == 'ec-001'
        assert call_kwargs['pid'] == 'p-001'
        assert call_kwargs['status'] == 'validated'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_load_memories_exception(self, handler, mock_agent):
        """Test loading memories when exception occurs"""
        mock_agent.sql_adapter.get = AsyncMock(side_effect=Exception("DB error"))
        
        result = await handler.load_memories(ecid='ec-001')
        
        assert result['memories_loaded'] is False
        assert result['memory_count'] == 0
        assert 'error' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_log_governance_success(self, handler, mock_agent):
        """Test logging governance successfully"""
        manifest = {'app_name': 'TestApp', 'version': '1.0.0'}
        files = ['file1.js', 'file2.js']
        
        result = await handler.log_governance('001', manifest, files)
        
        assert result['governance_logged'] is True
        assert result['run_id'] == '001'
        assert result['file_count'] == 2
        mock_agent.record_memory.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_log_governance_with_ecid(self, handler, mock_agent):
        """Test logging governance with full ECID"""
        manifest = {'app_name': 'TestApp'}
        files = ['file1.js']
        
        result = await handler.log_governance('ECID-WB-001', manifest, files)
        
        assert result['governance_logged'] is True
        assert result['run_id'] == '001'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_log_governance_no_record_memory(self, handler, mock_agent):
        """Test logging governance when record_memory not available"""
        handler.record_memory = None
        manifest = {'app_name': 'TestApp'}
        files = ['file1.js']
        
        result = await handler.log_governance('001', manifest, files)
        
        assert result['governance_logged'] is True
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_log_governance_exception(self, handler, mock_agent):
        """Test logging governance when exception occurs"""
        handler.record_memory = AsyncMock(side_effect=Exception("Error"))
        manifest = {'app_name': 'TestApp'}
        files = ['file1.js']
        
        result = await handler.log_governance('001', manifest, files)
        
        assert result['governance_logged'] is False
        assert 'error' in result

