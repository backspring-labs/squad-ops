#!/usr/bin/env python3
"""
Unit tests for ChatHandler capability
Tests chat message handling capability
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.capabilities.comms_chat import ChatHandler


class TestChatHandler:
    """Test ChatHandler capability"""
    
    @pytest.fixture
    def mock_agent(self):
        """Create mock agent instance"""
        agent = MagicMock()
        agent.name = "test-agent"
        agent.agent_type = "test"
        agent.status = "online"
        agent.current_task = None
        agent.llm_client = MagicMock()
        agent.retrieve_memories = AsyncMock(return_value=[])
        return agent
    
    @pytest.fixture
    def chat_handler(self, mock_agent):
        """Create ChatHandler instance"""
        return ChatHandler(mock_agent)
    
    @pytest.mark.unit
    def test_chat_handler_initialization(self, mock_agent):
        """Test ChatHandler initialization"""
        handler = ChatHandler(mock_agent)
        assert handler.agent == mock_agent
        assert handler.name == "test-agent"
    
    @pytest.mark.unit
    def test_should_retrieve_memories_short_message(self, chat_handler):
        """Test memory retrieval decision for short messages"""
        assert chat_handler._should_retrieve_memories("hi") is False
        assert chat_handler._should_retrieve_memories("hello") is False
    
    @pytest.mark.unit
    def test_should_retrieve_memories_greetings(self, chat_handler):
        """Test memory retrieval decision for greetings"""
        assert chat_handler._should_retrieve_memories("hi") is False
        assert chat_handler._should_retrieve_memories("good morning") is False
    
    @pytest.mark.unit
    def test_should_retrieve_memories_simple_commands(self, chat_handler):
        """Test memory retrieval decision for simple commands"""
        assert chat_handler._should_retrieve_memories("help") is False
        assert chat_handler._should_retrieve_memories("status") is False
    
    @pytest.mark.unit
    def test_should_retrieve_memories_questions(self, chat_handler):
        """Test memory retrieval decision for questions"""
        assert chat_handler._should_retrieve_memories("what is the status?") is True
        assert chat_handler._should_retrieve_memories("how does this work?") is True
        assert chat_handler._should_retrieve_memories("can you tell me?") is True
    
    @pytest.mark.unit
    def test_should_retrieve_memories_long_message(self, chat_handler):
        """Test memory retrieval decision for long messages"""
        long_message = "This is a very long message that should trigger memory retrieval because it's longer than 30 characters"
        assert chat_handler._should_retrieve_memories(long_message) is True
    
    @pytest.mark.unit
    def test_format_memory_dict_content(self, chat_handler):
        """Test formatting memory with dict content"""
        mem = {
            'id': 'mem-123',
            'content': {
                'action': 'task_completion',
                'result': {
                    'task_id': 'task-001',
                    'status': 'completed'
                }
            }
        }
        
        formatted = chat_handler._format_memory(mem, 1)
        assert 'Memory 1' in formatted
        assert 'task_completion' in formatted
        assert 'task-001' in formatted
    
    @pytest.mark.unit
    def test_format_memory_string_content(self, chat_handler):
        """Test formatting memory with string content"""
        mem = {
            'id': 'mem-123',
            'content': 'Simple text content'
        }
        
        formatted = chat_handler._format_memory(mem, 1)
        assert 'Memory 1' in formatted
        assert 'Simple text content' in formatted
    
    @pytest.mark.unit
    def test_format_memory_json_string_content(self, chat_handler):
        """Test formatting memory with JSON string content"""
        import json
        mem = {
            'id': 'mem-123',
            'content': json.dumps({'action': 'test', 'result': 'success'})
        }
        
        formatted = chat_handler._format_memory(mem, 1)
        assert 'Memory 1' in formatted
    
    @pytest.mark.unit
    def test_filter_memories_by_relevance_with_distance(self, chat_handler):
        """Test filtering memories by relevance with distance scores"""
        memories = [
            {'id': 'mem-1', '_distance': 0.3},  # High similarity
            {'id': 'mem-2', '_distance': 0.8},  # Low similarity
            {'id': 'mem-3', '_distance': 0.5}   # Medium similarity
        ]
        
        filtered = chat_handler._filter_memories_by_relevance(memories, min_relevance=0.6)
        
        # Should filter out mem-2 (similarity = 0.2) and mem-3 (similarity = 0.5)
        # Only mem-1 (similarity = 0.7) passes the 0.6 threshold
        assert len(filtered) == 1
        assert 'mem-1' in [m['id'] for m in filtered]
    
    @pytest.mark.unit
    def test_filter_memories_by_relevance_no_distance(self, chat_handler):
        """Test filtering memories without distance scores"""
        memories = [
            {'id': 'mem-1', 'content': 'test1'},
            {'id': 'mem-2', 'content': 'test2'}
        ]
        
        filtered = chat_handler._filter_memories_by_relevance(memories)
        
        # Should include all if no distance available
        assert len(filtered) == 2
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_agent_busy(self, chat_handler, mock_agent):
        """Test handling chat when agent is busy"""
        mock_agent.status = "Active-Blocking"
        mock_agent.current_task = "task-001"
        
        result = await chat_handler.handle("test message", "session-001")
        
        assert result['status'] == 'busy'
        assert 'busy' in result['response_text'].lower()
        assert result['agent_name'] == "test-agent"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_agent_available_simple_message(self, chat_handler, mock_agent):
        """Test handling chat when agent is available with simple message"""
        mock_agent.status = "online"
        mock_agent.current_task = None
        mock_agent.llm_client.complete = AsyncMock(return_value={'response': 'Hello!'})
        
        result = await chat_handler.handle("hi", "session-001")
        
        assert result['status'] == 'available'
        assert result['agent_name'] == "test-agent"
        assert 'timestamp' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_with_memory_retrieval(self, chat_handler, mock_agent):
        """Test handling chat with memory retrieval"""
        mock_agent.status = "online"
        mock_agent.current_task = None
        mock_agent.retrieve_memories = AsyncMock(return_value=[
            {'id': 'mem-1', 'content': {'action': 'test', 'result': 'success'}}
        ])
        mock_agent.llm_client.complete = AsyncMock(return_value={'response': 'Response with context'})
        
        result = await chat_handler.handle("what happened with the last task?", "session-001")
        
        assert result['status'] == 'available'
        assert mock_agent.retrieve_memories.called
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_with_role_context(self, chat_handler, mock_agent):
        """Test handling chat with role context from memory"""
        mock_agent.status = "online"
        mock_agent.current_task = None
        mock_agent.retrieve_memories = AsyncMock(side_effect=[
            [],  # No relevant memories for query
            [  # Role context memory
                {
                    'id': 'role-mem',
                    'content': {
                        'action': 'role_identity',
                        'result': {
                            'role_context': 'You are a helpful assistant.'
                        }
                    }
                }
            ]
        ])
        mock_agent.llm_client.complete = AsyncMock(return_value={'response': 'Response'})
        
        result = await chat_handler.handle("test", "session-001")
        
        assert result['status'] == 'available'
        # Should retrieve role context
        assert mock_agent.retrieve_memories.call_count >= 1
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_llm_client_not_available(self, chat_handler, mock_agent):
        """Test handling chat when LLM client is not available"""
        mock_agent.status = "online"
        mock_agent.current_task = None
        mock_agent.llm_client = None
        
        result = await chat_handler.handle("test", "session-001")
        
        assert result['status'] == 'available'
        assert 'not properly configured' in result['response_text'].lower()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_llm_error(self, chat_handler, mock_agent):
        """Test handling chat when LLM call fails"""
        mock_agent.status = "online"
        mock_agent.current_task = None
        mock_agent.llm_client.complete = AsyncMock(side_effect=Exception("LLM error"))
        
        result = await chat_handler.handle("test", "session-001")
        
        assert result['status'] == 'available'
        assert 'error' in result['response_text'].lower()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_memory_retrieval_error(self, chat_handler, mock_agent):
        """Test handling chat when memory retrieval fails"""
        mock_agent.status = "online"
        mock_agent.current_task = None
        mock_agent.retrieve_memories = AsyncMock(side_effect=Exception("Memory error"))
        mock_agent.llm_client.complete = AsyncMock(return_value={'response': 'Response'})
        
        result = await chat_handler.handle("what happened?", "session-001")
        
        # Should still respond even if memory retrieval fails
        assert result['status'] == 'available'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_exception(self, chat_handler, mock_agent):
        """Test handling chat exception handling"""
        # Cause an exception by making llm_client.complete fail
        mock_agent.status = "online"
        mock_agent.current_task = None
        mock_agent.llm_client.complete = MagicMock()  # Not AsyncMock, will cause error when awaited
        
        result = await chat_handler.handle("test", "session-001")
        
        # Exception is caught and returns 'available' with error message
        assert result['status'] == 'available'
        assert 'error' in result['response_text'].lower()

