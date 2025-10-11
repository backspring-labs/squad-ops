#!/usr/bin/env python3
"""
Unit tests for BaseAgent class
Tests core agent functionality without external dependencies
"""

import pytest
import asyncio
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
from agents.base_agent import BaseAgent, AgentMessage

class ConcreteTestAgent(BaseAgent):
    """Concrete test agent for testing BaseAgent functionality"""
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Mock implementation of process_task"""
        return {'task_id': task.get('task_id'), 'status': 'completed'}
    
    async def handle_message(self, message: AgentMessage) -> None:
        """Mock implementation of handle_message"""
        pass

class TestBaseAgent:
    """Test BaseAgent core functionality"""
    
    @pytest.mark.unit
    def test_agent_initialization(self):
        """Test agent initialization with basic parameters"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        assert agent.name == "test-agent"
        assert agent.agent_type == "test"
        assert agent.reasoning_style == "test"
        assert agent.status == "online"  # Changed from "initialized"
        assert agent.current_task is None  # Actual attribute
        assert agent.connection is None  # Actual attribute
    
    @pytest.mark.unit
    def test_agent_message_creation(self):
        """Test AgentMessage creation and validation"""
        message = AgentMessage(
            sender="test-sender",
            recipient="test-recipient",
            message_type="TEST_MESSAGE",
            payload={"test": "data"},
            context={"priority": "MEDIUM"},
            timestamp="2025-01-01T00:00:00Z",
            message_id="msg-001"
        )
        
        assert message.message_id == "msg-001"
        assert message.sender == "test-sender"
        assert message.recipient == "test-recipient"
        assert message.message_type == "TEST_MESSAGE"
        assert message.payload == {"test": "data"}
        assert message.context == {"priority": "MEDIUM"}
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_agent_startup(self, mock_database, mock_redis, mock_rabbitmq):
        """Test agent startup sequence"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        # Mock the actual connections BaseAgent creates
        async def mock_create_pool(*args, **kwargs):
            return mock_database
        
        with patch('aio_pika.connect_robust', return_value=mock_rabbitmq), \
             patch('asyncpg.create_pool', side_effect=mock_create_pool), \
             patch('redis.asyncio.from_url', return_value=mock_redis):
            
            await agent.initialize()  # Actual method name
            
            assert agent.connection is not None
            assert agent.db_pool is not None
            assert agent.redis_client is not None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_agent_shutdown(self, mock_database, mock_redis, mock_rabbitmq):
        """Test agent shutdown sequence"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        # Mock connections
        agent.db_pool = mock_database
        agent.redis_client = mock_redis
        agent.connection = mock_rabbitmq
        
        await agent.cleanup()  # Actual method name
        
        mock_database.close.assert_called_once()
        mock_redis.close.assert_called_once()
        mock_rabbitmq.close.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_message(self, mock_rabbitmq):
        """Test sending messages via RabbitMQ"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        # Mock the channel and exchange
        mock_exchange = AsyncMock()
        mock_rabbitmq.default_exchange = mock_exchange
        agent.channel = mock_rabbitmq
        
        await agent.send_message(
            recipient="other-agent",
            message_type="TEST_MESSAGE",
            payload={"test": "data"},
            context={"priority": "MEDIUM"}
        )
        
        mock_exchange.publish.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_broadcast_message(self, mock_rabbitmq):
        """Test broadcasting messages via RabbitMQ"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        # Mock the channel and exchange
        mock_exchange = AsyncMock()
        mock_rabbitmq.default_exchange = mock_exchange
        agent.channel = mock_rabbitmq
        
        await agent.broadcast_message(
            message_type="BROADCAST_MESSAGE",
            payload={"test": "broadcast"},
            context={"priority": "LOW"}
        )
        
        mock_exchange.publish.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_task_status(self, mock_database):
        """Test task status updates in database"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        agent.db_pool = mock_database
        
        await agent.update_task_status("task-001", "in_progress", 50.0)
        
        # Get the connection from the context manager
        conn = mock_database.acquire.return_value.conn
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert "task-001" in str(call_args)
        assert "in_progress" in str(call_args)
        assert "50.0" in str(call_args)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_log_activity(self, mock_database):
        """Test activity logging"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        agent.db_pool = mock_database
        
        await agent.log_activity("Test activity", {"details": "test"})
        
        # Get the connection from the context manager
        conn = mock_database.acquire.return_value.conn
        conn.execute.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_file_operations(self):
        """Test file system operations"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        # Test file reading
        with patch('aiofiles.open') as mock_open:
            mock_file = AsyncMock()
            mock_file.read.return_value = "test content"
            mock_open.return_value.__aenter__.return_value = mock_file
            
            content = await agent.read_file("/test/path/file.txt")
            assert content == "test content"
            mock_open.assert_called_with("/test/path/file.txt", "r", encoding="utf-8")
        
        # Test file writing
        with patch('aiofiles.open') as mock_open, \
             patch('os.makedirs') as mock_makedirs:
            mock_file = AsyncMock()
            mock_file.write.return_value = None
            mock_open.return_value.__aenter__.return_value = mock_file
            
            result = await agent.write_file("/tmp/test_file.txt", "test content")
            assert result is True
            mock_open.assert_called_with("/tmp/test_file.txt", "w", encoding="utf-8")
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_command_execution(self):
        """Test command execution"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        with patch('asyncio.create_subprocess_shell') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"test output", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await agent.execute_command("echo test", cwd="/tmp")
            
            assert result['stdout'] == "test output"
            assert result['stderr'] == ""
            assert result['returncode'] == 0
            mock_subprocess.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_send_heartbeat(self, mock_database):
        """Test heartbeat sending"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        agent.db_pool = mock_database
        
        await agent.send_heartbeat()
        
        # Get the connection from the context manager
        conn = mock_database.acquire.return_value.conn
        conn.execute.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_execution_cycle(self):
        """Test execution cycle creation via API"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {'ecid': 'test-ecid-001', 'status': 'created'}
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await agent.create_execution_cycle(
                ecid="test-ecid-001",
                pid="test-pid-001",
                run_type="warmboot",
                title="Test Execution Cycle",
                description="Test description"
            )
            
            assert result['ecid'] == 'test-ecid-001'
            assert result['status'] == 'created'
            mock_post.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_log_task_start(self):
        """Test task start logging via API"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {'task_id': 'task-001', 'status': 'started'}
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await agent.log_task_start(
                task_id="task-001",
                ecid="ecid-001",
                description="Test task",
                priority="HIGH",
                dependencies=["dep-001"],
                delegated_by="lead-agent",
                delegated_to="dev-agent"
            )
            
            assert result['task_id'] == 'task-001'
            assert result['status'] == 'started'
            mock_post.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_log_task_delegation(self):
        """Test task delegation logging via API"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        with patch('aiohttp.ClientSession.put') as mock_put:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {'task_id': 'task-001', 'status': 'delegated'}
            mock_put.return_value.__aenter__.return_value = mock_response
            
            result = await agent.log_task_delegation(
                task_id="task-001",
                ecid="ecid-001",
                delegated_to="dev-agent",
                description="Delegated task"
            )
            
            assert result['task_id'] == 'task-001'
            assert result['status'] == 'delegated'
            mock_put.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_log_task_completion(self):
        """Test task completion logging via API"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {'task_id': 'task-001', 'status': 'completed'}
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await agent.log_task_completion(
                task_id="task-001",
                artifacts={"result": "success", "output": "test output"}
            )
            
            assert result['task_id'] == 'task-001'
            assert result['status'] == 'completed'
            mock_post.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_log_task_failure(self):
        """Test task failure logging via API"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {'task_id': 'task-001', 'status': 'failed'}
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await agent.log_task_failure(
                task_id="task-001",
                error_log="Test error occurred"
            )
            
            assert result['task_id'] == 'task-001'
            assert result['status'] == 'failed'
            mock_post.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_execution_cycle_status(self):
        """Test execution cycle status update via API"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        with patch('aiohttp.ClientSession.put') as mock_put:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {'ecid': 'ecid-001', 'status': 'completed'}
            mock_put.return_value.__aenter__.return_value = mock_response
            
            result = await agent.update_execution_cycle_status(
                ecid="ecid-001",
                status="completed",
                notes="Execution completed successfully"
            )
            
            assert result['ecid'] == 'ecid-001'
            assert result['status'] == 'completed'
            mock_put.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_mock_llm_response(self):
        """Test mock LLM response generation"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="governance",
            reasoning_style="test"
        )
        
        response = await agent.mock_llm_response("Test prompt for governance decision")
        
        assert "[MOCK GOVERNANCE]" in response
        assert "Test prompt for governance decision" in response
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_llm_response_with_mock(self):
        """Test LLM response with mock fallback"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="code",
            reasoning_style="test"
        )
        
        with patch.dict('os.environ', {'USE_LOCAL_LLM': 'false'}):
            response = await agent.llm_response("Test prompt for code generation")
            
            assert "[MOCK CODE RESPONSE]" in response
            assert "Test prompt for code generation" in response
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_llm_response_with_ollama(self):
        """Test LLM response with Ollama"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="development",
            reasoning_style="test"
        )
        
        with patch.dict('os.environ', {'USE_LOCAL_LLM': 'true', 'AGENT_MODEL': 'llama2'}), \
             patch.object(agent, '_ollama_response') as mock_ollama:
            
            mock_ollama.return_value = "Ollama response for test prompt"
            
            response = await agent.llm_response("Test prompt", "Test context")
            
            assert response == "Ollama response for test prompt"
            mock_ollama.assert_called_once_with("Test prompt", "Test context", "llama2")
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_ollama_response(self):
        """Test Ollama response generation"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="development",
            reasoning_style="test"
        )
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {
                'response': 'Generated code for test prompt',
                'done': True
            }
            mock_post.return_value.__aenter__.return_value = mock_response
            
            response = await agent._ollama_response("Test prompt", "Test context", "llama2")
            
            assert response == "Generated code for test prompt"
            mock_post.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_file_exists(self):
        """Test file existence check"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True
            
            result = await agent.file_exists("/test/path/file.txt")
            
            assert result is True
            mock_exists.assert_called_once_with("/test/path/file.txt")
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_files(self):
        """Test file listing"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        with patch('os.walk') as mock_walk, \
             patch('os.path.isabs') as mock_isabs:
            
            mock_isabs.return_value = True  # Absolute path
            mock_walk.return_value = [
                ("/test/path", [], ["file1.txt", "file2.py", "dir1"])
            ]
            
            result = await agent.list_files("/test/path", ".txt")
            
            assert "/test/path/file1.txt" in result
            assert "/test/path/file2.py" not in result  # Pattern doesn't match
            assert "/test/path/dir1" not in result  # Not a file
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_agent_initialize_error_handling(self):
        """Test error handling during agent initialization"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        # Mock connection to fail
        with patch('aio_pika.connect_robust', side_effect=Exception("Connection failed")):
            with pytest.raises(Exception, match="Connection failed"):
                await agent.initialize()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_agent_cleanup_on_error(self):
        """Test cleanup method"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        # Setup mocks
        agent.connection = AsyncMock()
        agent.db_pool = AsyncMock()
        agent.redis_client = AsyncMock()
        
        await agent.cleanup()
        
        agent.connection.close.assert_called_once()
        agent.db_pool.close.assert_called_once()
        agent.redis_client.close.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_command_execution_error(self):
        """Test command execution with error"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"Command failed")
        mock_process.returncode = 1
        
        with patch('asyncio.create_subprocess_shell', return_value=mock_process):
            result = await agent.execute_command("false")
            
            assert result['success'] is False
            assert result['returncode'] == 1  # Note: returncode not return_code
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_file_write_error(self):
        """Test file write error handling - returns False on error"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        # write_file catches exceptions and returns False
        with patch('os.makedirs', side_effect=IOError("Cannot create dir")):
            result = await agent.write_file("/test/file.txt", "content")
            assert result is False
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_file_exists_false(self):
        """Test file_exists returns False for non-existent file"""
        agent = ConcreteTestAgent(
            name="test-agent",
            agent_type="test",
            reasoning_style="test"
        )
        
        with patch('os.path.exists', return_value=False):
            result = await agent.file_exists("/test/nonexistent.txt")
            assert result is False
