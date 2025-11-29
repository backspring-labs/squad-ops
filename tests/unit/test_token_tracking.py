"""
Unit tests for token usage tracking (Task 1.3)
"""
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from agents.llm.providers.ollama import OllamaClient


class TestTokenTracking:
    """Test token usage tracking functionality"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_ollama_client_extracts_token_usage(self):
        """Test that OllamaClient extracts token counts from API responses"""
        client = OllamaClient(url='http://localhost:11434', model='test-model')
        
        # Mock Ollama API response with token counts
        mock_response_data = {
            'response': 'Test response from Ollama',
            'prompt_eval_count': 10,
            'eval_count': 20
        }
        
        # Mock aiohttp response
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response_data)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)
        
        # Mock ClientSession
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await client.complete('test prompt')
            token_usage = client.get_token_usage()
            
            assert result == 'Test response from Ollama'
            assert token_usage is not None
            assert token_usage['prompt_tokens'] == 10
            assert token_usage['completion_tokens'] == 20
            assert token_usage['total_tokens'] == 30
    
    @pytest.mark.unit
    def test_task_completion_emitter_calculates_total_tokens(self, mock_unified_config):
        """Test TaskCompletionEmitter._calculate_total_tokens_used() method"""
        from unittest.mock import Mock

        from agents.capabilities.task_completion_emitter import TaskCompletionEmitter
        
        # Create a mock agent with communication log
        mock_agent = Mock()
        mock_agent.communication_log = [
            {'message_type': 'llm_reasoning', 'token_usage': {'total_tokens': 100}},
            {'message_type': 'other', 'no_tokens': True},  # Should be skipped
            {'message_type': 'llm_reasoning', 'token_usage': {'total_tokens': 50}},
            {'message_type': 'llm_reasoning', 'token_usage': {'total_tokens': 25}},
            {'message_type': 'llm_reasoning'},  # No token_usage - should be skipped
        ]
        
        capability = TaskCompletionEmitter(mock_agent)
        total = capability._calculate_total_tokens_used()
        
        assert total == 175  # 100 + 50 + 25
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_base_agent_tracks_tokens_in_communication_log(self, mock_unified_config):
        """Test that BaseAgent tracks token usage in communication log"""
        with patch('config.unified_config.get_config', return_value=mock_unified_config):
            from agents.base_agent import BaseAgent
            
            class TestAgent(BaseAgent):
                async def process_task(self, task):
                    return {}
                
                async def handle_agent_request(self, request):
                    from datetime import datetime

                    from agents.specs.agent_response import AgentResponse, Timing
                    return AgentResponse.success(
                        result={},
                        idempotency_key='test-key',
                        timing=Timing.create(datetime.utcnow())
                    )
                
                async def handle_message(self, message):
                    pass
            
            with patch.object(TestAgent, '_initialize_llm_client', return_value=MagicMock()):
                agent = TestAgent('test-agent', 'test', 'test')
                
                # Mock LLM client with token usage
                mock_llm_client = AsyncMock()
                mock_llm_client.complete = AsyncMock(return_value='Test response')
                mock_llm_client.get_token_usage = MagicMock(return_value={
                    'prompt_tokens': 15,
                    'completion_tokens': 25,
                    'total_tokens': 40
                })
                agent.llm_client = mock_llm_client
                
                # Mock telemetry client
                mock_telemetry = MagicMock()
                mock_telemetry.create_span = MagicMock(return_value=__import__('contextlib').nullcontext())
                mock_telemetry.record_counter = MagicMock()
                agent.telemetry_client = mock_telemetry
                
                # Call llm_response
                response = await agent.llm_response('test prompt', context='test')
                
                # Verify response
                assert response == 'Test response'
                
                # Verify communication log has token usage
                assert len(agent.communication_log) > 0
                last_entry = agent.communication_log[-1]
                assert 'token_usage' in last_entry
                assert last_entry['token_usage']['total_tokens'] == 40
                
                # Verify telemetry client was called
                assert mock_telemetry.record_counter.called
                call_args = mock_telemetry.record_counter.call_args
                assert call_args[0][0] == 'agent_tokens_used_total'
                assert call_args[0][1] == 40
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_lead_agent_collects_token_metrics(self, mock_unified_config):
        """Test that LeadAgent collects token metrics in telemetry"""
        with patch('config.unified_config.get_config', return_value=mock_unified_config):
            from agents.roles.lead.agent import LeadAgent
            
            with patch.object(LeadAgent, '_initialize_llm_client', return_value=MagicMock()):
                agent = LeadAgent('test-lead-agent')
                
                # Populate communication log with token usage
                agent.communication_log = [
                    {
                        'message_type': 'llm_reasoning',
                        'agent': 'test-lead-agent',
                        'token_usage': {'total_tokens': 100, 'prompt_tokens': 50, 'completion_tokens': 50}
                    },
                    {
                        'message_type': 'llm_reasoning',
                        'agent': 'test-dev-agent',
                        'token_usage': {'total_tokens': 75, 'prompt_tokens': 30, 'completion_tokens': 45}
                    },
                    {
                        'message_type': 'other',
                        'agent': 'test-max'
                    }
                ]
            
            # Mock Task API responses
            mock_session = AsyncMock()
            mock_tasks_resp = AsyncMock(status=200, json=AsyncMock(return_value=[]))
            mock_tasks_resp.__aenter__ = AsyncMock(return_value=mock_tasks_resp)
            mock_tasks_resp.__aexit__ = AsyncMock(return_value=None)
            
            mock_cycle_resp = AsyncMock(status=200, json=AsyncMock(return_value={
                'ecid': 'ECID-WB-001',
                'start_time': '2024-01-01T00:00:00Z'
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
            
            # Mock execute_command for RabbitMQ and Docker
            agent.execute_command = AsyncMock(return_value={
                'success': False,
                'stdout': '',
                'stderr': ''
            })
            
            # Mock Prometheus query (should fail gracefully)
            with patch('aiohttp.ClientSession', return_value=mock_session):
                from agents.capabilities.telemetry_collector import TelemetryCollector
                telemetry_collector = TelemetryCollector(agent)
                telemetry = await telemetry_collector.collect('ECID-WB-001', 'task-001')
            
            # Verify token metrics in telemetry
            assert 'reasoning_logs' in telemetry
            reasoning_logs = telemetry['reasoning_logs']
            
            # Should have token usage (from manual tracking since Prometheus will fail)
            assert 'tokens_used' in reasoning_logs
            assert reasoning_logs['tokens_used'] == 175  # 100 + 75
            
            # Should have tokens by agent
            assert 'tokens_by_agent' in reasoning_logs
            assert reasoning_logs['tokens_by_agent']['test-lead-agent'] == 100
            assert reasoning_logs['tokens_by_agent']['test-dev-agent'] == 75
            
            # Should have tokens_source
            assert 'tokens_source' in reasoning_logs
            assert reasoning_logs['tokens_source'] == 'manual_tracking'
            
            # Should have ollama_logs with token usage
            assert 'ollama_logs' in reasoning_logs
            ollama_logs = reasoning_logs['ollama_logs']
            assert len(ollama_logs) == 2  # Two LLM reasoning entries
            
            # Verify token usage is included in JSONL logs
            for log_entry in ollama_logs:
                if log_entry['agent'] == 'test-lead-agent':
                    assert 'token_usage' in log_entry
                    assert log_entry['token_usage']['total_tokens'] == 100
                elif log_entry['agent'] == 'test-dev-agent':
                    assert 'token_usage' in log_entry
                    assert log_entry['token_usage']['total_tokens'] == 75
