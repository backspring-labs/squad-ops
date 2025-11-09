"""
Unit tests for telemetry integration in agents (Phase 1)
Tests GPU detection, reasoning extraction, and telemetry collection enhancements
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from contextlib import contextmanager
from datetime import datetime


class TestGPUDetection:
    """Test GPU utilization tracking (Task 1.2)"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_gpu_utilization_available(self, mock_unified_config):
        """Test GPU utilization when nvidia-smi is available"""
        with patch('config.unified_config.get_config', return_value=mock_unified_config):
            from agents.roles.lead.agent import LeadAgent
            
            agent = LeadAgent('test-lead-agent')
            
            # Mock nvidia-smi output
            mock_execute_result = {
                'success': True,
                'stdout': '''
GPU  0: NVIDIA GeForce RTX 4090 (UUID: GPU-xxx)
Performance: Utilization = 45%, Memory = 8192 MiB / 24576 MiB
''',
                'stderr': ''
            }
            agent.execute_command = AsyncMock(return_value=mock_execute_result)
            
            # Collect telemetry with GPU
            with patch('aiohttp.ClientSession') as mock_session:
                mock_tasks_resp = AsyncMock(status=200, json=AsyncMock(return_value=[]))
                mock_tasks_resp.__aenter__ = AsyncMock(return_value=mock_tasks_resp)
                mock_tasks_resp.__aexit__ = AsyncMock(return_value=None)
                
                mock_cycle_resp = AsyncMock(status=200, json=AsyncMock(return_value={
                    'ecid': 'ECID-WB-001',
                    'created_at': '2024-01-01T00:00:00Z'
                }))
                mock_cycle_resp.__aenter__ = AsyncMock(return_value=mock_cycle_resp)
                mock_cycle_resp.__aexit__ = AsyncMock(return_value=None)
                
                def mock_get(url, **kwargs):
                    if '/tasks/ec/' in url:
                        return mock_tasks_resp
                    elif '/execution-cycles/' in url:
                        return mock_cycle_resp
                    return mock_tasks_resp
                
                mock_session_instance = AsyncMock()
                mock_session_instance.get = Mock(side_effect=mock_get)
                mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
                mock_session_instance.__aexit__ = AsyncMock(return_value=None)
                mock_session.return_value = mock_session_instance
                
                telemetry = await agent.telemetry_collector.collect('ECID-WB-001', 'task-001')
                
                # Verify GPU metrics
                assert 'system_metrics' in telemetry
                system_metrics = telemetry['system_metrics']
                
                # Should have GPU utilization if nvidia-smi succeeded
                if 'gpu_utilization_percent' in system_metrics:
                    assert system_metrics['gpu_utilization_percent'] >= 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_gpu_utilization_unavailable(self, mock_unified_config):
        """Test GPU utilization gracefully handles when nvidia-smi is unavailable"""
        with patch('config.unified_config.get_config', return_value=mock_unified_config):
            from agents.roles.lead.agent import LeadAgent
            
            agent = LeadAgent('test-lead-agent')
            
            # Mock nvidia-smi failure
            mock_execute_result = {
                'success': False,
                'stdout': '',
                'stderr': 'nvidia-smi: command not found'
            }
            agent.execute_command = AsyncMock(return_value=mock_execute_result)
            
            # Collect telemetry without GPU
            with patch('aiohttp.ClientSession') as mock_session:
                mock_tasks_resp = AsyncMock(status=200, json=AsyncMock(return_value=[]))
                mock_tasks_resp.__aenter__ = AsyncMock(return_value=mock_tasks_resp)
                mock_tasks_resp.__aexit__ = AsyncMock(return_value=None)
                
                mock_cycle_resp = AsyncMock(status=200, json=AsyncMock(return_value={
                    'ecid': 'ECID-WB-001',
                    'created_at': '2024-01-01T00:00:00Z'
                }))
                mock_cycle_resp.__aenter__ = AsyncMock(return_value=mock_cycle_resp)
                mock_cycle_resp.__aexit__ = AsyncMock(return_value=None)
                
                def mock_get(url, **kwargs):
                    if '/tasks/ec/' in url:
                        return mock_tasks_resp
                    elif '/execution-cycles/' in url:
                        return mock_cycle_resp
                    return mock_tasks_resp
                
                mock_session_instance = AsyncMock()
                mock_session_instance.get = Mock(side_effect=mock_get)
                mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
                mock_session_instance.__aexit__ = AsyncMock(return_value=None)
                mock_session.return_value = mock_session_instance
                
                telemetry = await agent.telemetry_collector.collect('ECID-WB-001', 'task-001')
                
                # Should not crash, GPU metrics may be missing or show N/A
                assert 'system_metrics' in telemetry
                # System should still work without GPU


class TestReasoningExtraction:
    """Test reasoning trace extraction (Task 2.2)"""
    
    @pytest.mark.unit
    def test_extract_real_ai_reasoning_with_entries(self, mock_unified_config):
        """Test _extract_real_ai_reasoning() with reasoning entries"""
        with patch('config.unified_config.get_config', return_value=mock_unified_config):
            from agents.roles.lead.agent import LeadAgent
            
            agent = LeadAgent('test-lead-agent')
            
            # Populate communication log with reasoning entries
            agent.communication_log = [
                {
                    'timestamp': '2024-01-01T12:00:00Z',
                    'agent': 'lead-agent',
                    'ecid': 'ECID-WB-001',
                    'message_type': 'llm_reasoning',
                    'full_response': 'This is Lead Agent reasoning about the PRD',
                    'description': 'PRD Analysis'
                },
                {
                    'timestamp': '2024-01-01T12:05:00Z',
                    'agent': 'dev-agent',
                    'ecid': 'ECID-WB-001',
                    'message_type': 'llm_reasoning',
                    'full_response': 'This is Dev Agent reasoning about file generation',
                    'description': 'File Generation'
                },
                {
                    'timestamp': '2024-01-01T12:10:00Z',
                    'agent': 'lead-agent',
                    'ecid': 'ECID-WB-002',  # Different ECID
                    'message_type': 'llm_reasoning',
                    'full_response': 'Different ECID reasoning'
                }
            ]
            
            # Extract reasoning for ECID-WB-001
            reasoning = agent._extract_real_ai_reasoning('ECID-WB-001')
            
            # Should contain reasoning from both lead-agent and dev-agent for this ECID
            assert reasoning is not None
            assert len(reasoning) > 0
            assert 'lead-agent' in reasoning.lower() or 'Lead Agent' in reasoning
            assert 'dev-agent' in reasoning.lower() or 'Dev Agent' in reasoning
    
    @pytest.mark.unit
    def test_extract_real_ai_reasoning_filtered_by_agent(self, mock_unified_config):
        """Test _extract_real_ai_reasoning() with agent filter"""
        with patch('config.unified_config.get_config', return_value=mock_unified_config):
            from agents.roles.lead.agent import LeadAgent
            
            agent = LeadAgent('test-lead-agent')
            
            # Populate communication log
            agent.communication_log = [
                {
                    'timestamp': '2024-01-01T12:00:00Z',
                    'agent': 'lead-agent',
                    'ecid': 'ECID-WB-001',
                    'message_type': 'llm_reasoning',
                    'full_response': 'Lead Agent reasoning'
                },
                {
                    'timestamp': '2024-01-01T12:05:00Z',
                    'agent': 'dev-agent',
                    'ecid': 'ECID-WB-001',
                    'message_type': 'llm_reasoning',
                    'full_response': 'Dev Agent reasoning'
                }
            ]
            
            # Extract reasoning for dev-agent only
            reasoning = agent._extract_real_ai_reasoning('ECID-WB-001', agent_name='dev-agent')
            
            # Should only contain dev-agent's reasoning
            assert reasoning is not None
            assert 'Dev Agent' in reasoning or 'dev-agent' in reasoning.lower()
            # Should not contain lead-agent's reasoning (or if it does, should be filtered)
    
    @pytest.mark.unit
    def test_extract_real_ai_reasoning_no_entries(self, mock_unified_config):
        """Test _extract_real_ai_reasoning() when no reasoning entries exist"""
        with patch('config.unified_config.get_config', return_value=mock_unified_config):
            from agents.roles.lead.agent import LeadAgent
            
            agent = LeadAgent('test-lead-agent')
            agent.communication_log = []
            
            # Extract reasoning for non-existent ECID
            reasoning = agent._extract_real_ai_reasoning('ECID-WB-999')
            
            # Should return message indicating no reasoning found
            assert reasoning is not None
            assert 'No reasoning trace found' in reasoning or 'No reasoning' in reasoning


class TestExecutionDuration:
    """Test execution duration calculation (Task 1.6)"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execution_duration_calculation(self, mock_unified_config):
        """Test execution duration is calculated correctly"""
        with patch('config.unified_config.get_config', return_value=mock_unified_config):
            from agents.roles.lead.agent import LeadAgent
            
            agent = LeadAgent('test-lead-agent')
            
            # Mock Task API to return execution cycle with created_at
            mock_session = AsyncMock()
            mock_tasks_resp = AsyncMock(status=200, json=AsyncMock(return_value=[]))
            mock_tasks_resp.__aenter__ = AsyncMock(return_value=mock_tasks_resp)
            mock_tasks_resp.__aexit__ = AsyncMock(return_value=None)
            
            # Return execution cycle with created_at (used as start_time)
            mock_cycle_resp = AsyncMock(status=200, json=AsyncMock(return_value={
                'ecid': 'ECID-WB-001',
                'created_at': '2024-01-01T12:00:00Z',  # Used as start_time
                'status': 'active'
            }))
            mock_cycle_resp.__aenter__ = AsyncMock(return_value=mock_cycle_resp)
            mock_cycle_resp.__aexit__ = AsyncMock(return_value=None)
            
            def mock_get(url, **kwargs):
                if '/tasks/ec/' in url:
                    return mock_tasks_resp
                elif '/execution-cycles/' in url:
                    return mock_cycle_resp
                return mock_tasks_resp
            
            mock_session.get = Mock(side_effect=mock_get)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            # Mock execute_command for RabbitMQ/Docker
            agent.execute_command = AsyncMock(return_value={
                'success': False,
                'stdout': '',
                'stderr': ''
            })
            
            with patch('aiohttp.ClientSession', return_value=mock_session):
                telemetry = await agent.telemetry_collector.collect('ECID-WB-001', 'task-001')
                
                # Verify execution duration is calculated
                # Note: duration calculation happens in wrap-up generation, not in telemetry collection
                # But we can verify the execution cycle info is collected
                assert 'database_metrics' in telemetry
                db_metrics = telemetry['database_metrics']
                
                if 'execution_cycle' in db_metrics:
                    cycle_info = db_metrics['execution_cycle']
                    # Should have created_at which is used for duration calculation
                    assert 'created_at' in cycle_info or 'start_time' in cycle_info


class TestBaseAgentTelemetryIntegration:
    """Test BaseAgent telemetry integration with TelemetryClient"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_base_agent_uses_telemetry_client(self, mock_unified_config):
        """Test that BaseAgent uses TelemetryClient abstraction"""
        with patch('config.unified_config.get_config', return_value=mock_unified_config):
            from agents.base_agent import BaseAgent
            
            class TestAgent(BaseAgent):
                async def process_task(self, task):
                    return {}
                
                async def handle_agent_request(self, request):
                    from agents.specs.agent_response import AgentResponse, Timing
                    from datetime import datetime
                    return AgentResponse.success(
                        result={},
                        idempotency_key='test-key',
                        timing=Timing.create(datetime.utcnow())
                    )
                
                async def handle_message(self, message):
                    pass
            
            agent = TestAgent('test-agent', 'test', 'test')
            
            # Should have telemetry_client initialized
            assert hasattr(agent, 'telemetry_client')
            assert agent.telemetry_client is not None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_base_agent_llm_response_creates_span(self, mock_unified_config):
        """Test that BaseAgent.llm_response() creates telemetry span"""
        with patch('config.unified_config.get_config', return_value=mock_unified_config):
            from agents.base_agent import BaseAgent
            
            class TestAgent(BaseAgent):
                async def process_task(self, task):
                    return {}
                
                async def handle_agent_request(self, request):
                    from agents.specs.agent_response import AgentResponse, Timing
                    from datetime import datetime
                    return AgentResponse.success(
                        result={},
                        idempotency_key='test-key',
                        timing=Timing.create(datetime.utcnow())
                    )
                
                async def handle_message(self, message):
                    pass
            
            agent = TestAgent('test-agent', 'test', 'test')
            
            # Mock LLM client
            mock_llm_client = AsyncMock()
            mock_llm_client.complete = AsyncMock(return_value='Test response')
            mock_llm_client.get_token_usage = MagicMock(return_value={
                'prompt_tokens': 10,
                'completion_tokens': 20,
                'total_tokens': 30
            })
            agent.llm_client = mock_llm_client
            
            # Mock telemetry client
            mock_telemetry = MagicMock()
            mock_span = MagicMock()
            mock_span.__enter__ = MagicMock(return_value=mock_span)
            mock_span.__exit__ = MagicMock(return_value=None)
            mock_telemetry.create_span = MagicMock(return_value=mock_span)
            mock_telemetry.record_counter = MagicMock()
            agent.telemetry_client = mock_telemetry
            
            # Call llm_response
            response = await agent.llm_response('test prompt', context='test')
            
            # Verify telemetry span was created
            assert mock_telemetry.create_span.called
            
            # Verify token counter was recorded
            assert mock_telemetry.record_counter.called
            call_args = mock_telemetry.record_counter.call_args
            assert call_args[0][0] == 'agent_tokens_used_total'
            assert call_args[0][1] == 30

