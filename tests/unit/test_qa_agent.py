import pytest
import asyncio
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
from agents.roles.qa.agent import QAAgent
from agents.base_agent import AgentMessage

class TestQAAgent:
    """Test QAAgent core functionality"""
    
    @pytest.mark.unit
    def test_qa_agent_initialization(self):
        """Test QAAgent initialization"""
        agent = QAAgent("qa-agent-001")
        
        assert agent.name == "qa-agent-001"
        assert agent.agent_type == "testing"
        assert agent.reasoning_style == "counterfactual"
        assert agent.state_machine == {}
        assert agent.test_suites == {}
        assert agent.security_protocols == {}
        assert agent.regression_tests == {}
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_testing(self, mock_database):
        """Test process_task for testing task"""
        agent = QAAgent("qa-agent-001")
        agent.db_pool = mock_database
        
        task = {
            'task_id': 'task-001',
            'type': 'testing',
            'requirements': {
                'application': 'TestApp',
                'test_types': ['unit', 'integration', 'security']
            },
            'complexity': 0.6
        }
        
        with patch.object(agent, 'update_task_status') as mock_update:
            result = await agent.process_task(task)
            
            assert result['status'] == 'completed'
            # Check for actual keys returned by process_task
            assert 'security_tests' in result
            assert 'regression_results' in result
            assert mock_update.call_count >= 3  # Called multiple times during process
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_define_testing_state_machine(self):
        """Test testing state machine definition"""
        agent = QAAgent("qa-agent-001")
        
        task = {
            'task_id': 'task-001',
            'requirements': {
                'application': 'TestApp',
                'test_types': ['unit', 'integration']
            }
        }
        
        await agent.define_testing_state_machine(task)
        
        # Method populates state_machine but doesn't return a value
        assert 'task-001' in agent.state_machine
        assert agent.state_machine['task-001']['current_state'] == 'initial'
        assert len(agent.state_machine['task-001']['states']) > 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_test_suites(self):
        """Test test suite creation"""
        agent = QAAgent("qa-agent-001")
        
        task = {
            'task_id': 'task-001',
            'requirements': {
                'application': 'TestApp',
                'test_types': ['unit', 'integration', 'security']
            }
        }
        
        result = await agent.create_test_suites(task)
        
        assert 'suites' in result
        assert 'total_coverage' in result
        assert len(result['suites']) > 0
        assert agent.test_suites != {}
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_security_tests(self):
        """Test security test execution"""
        agent = QAAgent("qa-agent-001")
        
        task = {
            'task_id': 'task-001',
            'requirements': {
                'application': 'TestApp',
                'security_requirements': ['authentication', 'authorization']
            }
        }
        
        result = await agent.execute_security_tests(task)
        
        # Returns dict with test types and results
        assert isinstance(result, dict)
        assert len(result) > 0  # Should have security test results
        # Check for expected test types
        assert any('test' in key for key in result.keys())
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_run_regression_tests(self):
        """Test regression test execution"""
        agent = QAAgent("qa-agent-001")
        
        task = {
            'task_id': 'task-001',
            'requirements': {
                'application': 'TestApp',
                'regression_scope': 'critical_paths'
            }
        }
        
        result = await agent.run_regression_tests(task)
        
        # Returns dict with regression test results
        assert isinstance(result, dict)
        assert 'passed' in result
        assert 'failed' in result
        assert 'total_tests' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_message(self):
        """Test message handling"""
        agent = QAAgent("qa-agent-001")
        
        message = AgentMessage(
            sender='lead-agent-001',
            recipient='qa-agent-001',
            message_type='security_audit',
            payload={'task_id': 'task-001', 'audit_type': 'security'},
            context={'priority': 'HIGH'},
            timestamp='2025-01-01T00:00:00Z',
            message_id='msg-001'
        )
        
        with patch.object(agent, 'handle_security_audit') as mock_handle:
            await agent.handle_message(message)
            mock_handle.assert_called_once_with(message)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_security_audit(self, mock_database):
        """Test security audit request handling"""
        agent = QAAgent("qa-agent-001")
        agent.db_pool = mock_database
        
        message = AgentMessage(
            sender='lead-agent-001',
            recipient='qa-agent-001',
            message_type='security_audit',
            payload={'task_id': 'task-001', 'audit_type': 'full'},
            context={'priority': 'HIGH'},
            timestamp='2025-01-01T00:00:00Z',
            message_id='msg-001'
        )
        
        with patch.object(agent, 'send_message') as mock_send:
            await agent.handle_security_audit(message)
            
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == "lead-agent-001"  # Response to lead agent
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_vulnerability_scan(self, mock_database):
        """Test vulnerability scan handling"""
        agent = QAAgent("qa-agent-001")
        agent.db_pool = mock_database
        
        message = AgentMessage(
            sender='lead-agent-001',
            recipient='qa-agent-001',
            message_type='vulnerability_scan',
            payload={'task_id': 'task-001', 'target': 'web_app'},
            context={'priority': 'HIGH'},
            timestamp='2025-01-01T00:00:00Z',
            message_id='msg-001'
        )
        
        with patch.object(agent, 'send_message') as mock_send:
            await agent.handle_vulnerability_scan(message)
            
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == "lead-agent-001"  # Notify lead agent
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_penetration_test(self, mock_database):
        """Test penetration test handling"""
        agent = QAAgent("qa-agent-001")
        agent.db_pool = mock_database
        
        message = AgentMessage(
            sender='lead-agent-001',
            recipient='qa-agent-001',
            message_type='penetration_test',
            payload={'task_id': 'task-001', 'test_scope': 'full'},
            context={'priority': 'HIGH'},
            timestamp='2025-01-01T00:00:00Z',
            message_id='msg-001'
        )
        
        with patch.object(agent, 'send_message') as mock_send:
            await agent.handle_penetration_test(message)
            
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == "lead-agent-001"  # Notify lead agent
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_counterfactual_scenarios(self):
        """Test counterfactual scenario generation"""
        agent = QAAgent("qa-agent-001")
        task = {'task_id': 'task-001', 'base_scenario': {}}
        scenarios = await agent.generate_counterfactual_scenarios(task)
        assert isinstance(scenarios, list)
        assert len(scenarios) > 0
        assert all('id' in s and 'description' in s for s in scenarios)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_analyze_vulnerabilities(self):
        """Test vulnerability analysis"""
        agent = QAAgent("qa-agent-001")
        test_results = {
            'test_details': [
                {'name': 'auth_test', 'status': 'failed', 'scenario_id': 'sc1', 'test_type': 'authentication'},
                {'name': 'validation_test', 'status': 'passed', 'scenario_id': 'sc2', 'test_type': 'validation'}
            ]
        }
        task = {'task_id': 'task-001'}
        vulnerabilities = await agent.analyze_vulnerabilities(test_results, task)
        assert isinstance(vulnerabilities, list)
        assert len(vulnerabilities) > 0
    
    @pytest.mark.unit
    def test_calculate_security_score(self):
        """Test security score calculation"""
        agent = QAAgent("qa-agent-001")
        vulnerabilities = [
            {'severity': 'critical'},
            {'severity': 'high'},
            {'severity': 'low'}
        ]
        score = agent.calculate_security_score(vulnerabilities)
        assert isinstance(score, float)
        assert 0.0 <= score <= 10.0
