"""
Unit tests for LeadAgent class
Tests core LeadAgent functionality without external dependencies
"""

import pytest
import asyncio
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
from agents.roles.lead.agent import LeadAgent
from agents.base_agent import AgentMessage

class TestLeadAgent:
    """Test LeadAgent core functionality"""
    
    @pytest.mark.unit
    def test_lead_agent_initialization(self):
        """Test LeadAgent initialization"""
        agent = LeadAgent("lead-agent-001")
        
        assert agent.name == "lead-agent-001"
        assert agent.agent_type == "governance"
        assert agent.reasoning_style == "governance"
        assert agent.escalation_threshold is not None
        assert agent.task_state_log is not None
        assert agent.approval_queue is not None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_prd_analysis(self, sample_prd):
        """Test PRD analysis functionality"""
        agent = LeadAgent("lead-agent-001")
        
        with patch.object(agent, 'llm_response') as mock_llm:
            mock_llm.return_value = """
            {
                "core_features": ["Feature 1", "Feature 2"],
                "technical_requirements": ["Web app", "Database"],
                "complexity_score": 0.6,
                "estimated_effort": "2-3 days"
            }
            """
            
            analysis = await agent.analyze_prd_requirements(sample_prd)
            
            assert 'core_features' in analysis
            assert 'technical_requirements' in analysis
            assert 'complexity_score' in analysis
            assert 'estimated_effort' in analysis
            assert analysis['complexity_score'] == 0.6
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_task_creation(self, sample_prd):
        """Test development task creation from PRD analysis"""
        agent = LeadAgent("lead-agent-001")
        
        prd_analysis = {
            'core_features': ['Feature 1', 'Feature 2'],
            'technical_requirements': ['Web app', 'Database'],
            'complexity_score': 0.6,
            'estimated_effort': '2-3 days'
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.json.return_value = {'task_id': 'test-task-001'}
            mock_response.status = 201
            mock_post.return_value.__aenter__.return_value = mock_response
            
            tasks = await agent.create_development_tasks(prd_analysis, "TestApp", "test-ecid-001")
            
            assert len(tasks) == 3  # archive, build, deploy
            
            # Check archive task
            archive_task = tasks[0]
            assert archive_task['task_type'] == 'development'
            assert archive_task['requirements']['action'] == 'archive'
            assert archive_task['complexity'] == 0.3
            assert archive_task['priority'] == 'HIGH'
            
            # Check build task
            build_task = tasks[1]
            assert build_task['requirements']['action'] == 'build'
            assert build_task['complexity'] == 0.8
            assert build_task['requirements']['from_scratch'] is True
            
            # Check deploy task
            deploy_task = tasks[2]
            assert deploy_task['requirements']['action'] == 'deploy'
            assert deploy_task['complexity'] == 0.5
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_delegation_target(self):
        """Test delegation target determination"""
        agent = LeadAgent("lead-agent-001")
        
        # Test development task delegation
        target = await agent.determine_delegation_target("development")
        assert target == "Neo"  # LeadAgent uses hardcoded names
        
        # Test security task delegation
        target = await agent.determine_delegation_target("security")
        assert target == "EVE"  # LeadAgent uses hardcoded names
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_escalate_task(self, mock_database):
        """Test task escalation functionality"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        task = {
            'task_id': 'test-task-001',
            'complexity': 0.9,
            'description': 'Complex task requiring escalation',
            'timestamp': '2025-01-01T00:00:00Z'
        }
        
        await agent.escalate_task('test-task-001', task)
        
        # Verify task was added to approval queue
        assert len(agent.approval_queue) == 1
        assert agent.approval_queue[0]['task_id'] == 'test-task-001'
        assert agent.approval_queue[0]['reason'] == 'High complexity'
        
        # Verify activity was logged
        conn = agent.db_pool.acquire.return_value.conn
        conn.execute.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_read_prd(self):
        """Test PRD reading functionality"""
        agent = LeadAgent("lead-agent-001")
        
        with patch.object(agent, 'read_file') as mock_read:
            mock_read.return_value = "# Test PRD\n## Overview\nTest application"
            
            content = await agent.read_prd("/test/prd.md")
            
            assert content == "# Test PRD\n## Overview\nTest application"
            mock_read.assert_called_once_with("/test/prd.md")
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_prd_request(self, mock_database):
        """Test PRD processing workflow"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        with patch.object(agent, 'read_prd') as mock_read, \
             patch.object(agent, 'analyze_prd_requirements') as mock_analyze, \
             patch.object(agent, 'create_development_tasks') as mock_create, \
             patch.object(agent, 'create_execution_cycle') as mock_create_ec, \
             patch.object(agent, 'log_task_delegation') as mock_log, \
             patch.object(agent, 'send_message') as mock_send:
            
            mock_read.return_value = "# Test PRD"
            mock_analyze.return_value = {'core_features': ['Feature 1']}
            mock_create.return_value = [{'task_id': 'task-001', 'task_type': 'development', 'description': 'Test task'}]
            mock_create_ec.return_value = None
            
            result = await agent.process_prd_request("/test/prd.md", "test-ecid-001")
            
            assert 'prd_analysis' in result
            assert 'tasks_delegated' in result
            assert result['status'] == 'success'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_message(self):
        """Test message handling"""
        agent = LeadAgent("lead-agent-001")
        
        message = AgentMessage(
            sender='dev-agent',
            recipient='lead-agent-001',
            message_type='task_acknowledgment',
            payload={'task_id': 'task-001'},
            context={'status': 'accepted'},
            timestamp='2025-01-01T00:00:00Z',
            message_id='msg-001'
        )
        
        with patch.object(agent, 'handle_task_acknowledgment') as mock_handle:
            await agent.handle_message(message)
            mock_handle.assert_called_once_with(message)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_task_acknowledgment(self, mock_database):
        """Test task acknowledgment handling"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        message = AgentMessage(
            sender='dev-agent',
            recipient='lead-agent-001',
            message_type='task_acknowledgment',
            payload={'task_id': 'task-001', 'status': 'accepted', 'understanding': 'Task understood'},
            context={'status': 'accepted'},
            timestamp='2025-01-01T00:00:00Z',
            message_id='msg-001'
        )
        
        await agent.handle_task_acknowledgment(message)
        
        # Verify communication was logged
        assert len(agent.communication_log) == 1
        log_entry = agent.communication_log[0]
        assert log_entry['task_id'] == 'task-001'
        assert log_entry['from_agent'] == 'dev-agent'
        assert log_entry['message_type'] == 'task_acknowledgment'
        assert log_entry['status'] == 'success'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_approval_request(self, mock_database):
        """Test approval request handling"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        message = AgentMessage(
            sender='dev-agent',
            recipient='lead-agent-001',
            message_type='approval_request',
            payload={'task_id': 'task-001', 'complexity': 0.7},
            context={'priority': 'HIGH'},
            timestamp='2025-01-01T00:00:00Z',
            message_id='msg-001'
        )
        
        with patch.object(agent, 'send_message') as mock_send:
            await agent.handle_approval_request(message)
            
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == "dev-agent"  # Response to dev agent
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_governance_with_prd(self, mock_database):
        """Test process_task for governance task with PRD path"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        task = {
            'task_id': 'task-001',
            'type': 'governance',
            'prd_path': '/test/prd.md',
            'application': 'TestApp',
            'ecid': 'ecid-001',
            'complexity': 0.5
        }
        
        with patch.object(agent, 'process_prd_request') as mock_process_prd, \
             patch.object(agent, 'update_task_status') as mock_update_status:
            
            mock_process_prd.return_value = {'status': 'success', 'tasks_delegated': 3}
            
            result = await agent.process_task(task)
            
            assert result['status'] == 'success'
            assert result['tasks_delegated'] == 3
            mock_process_prd.assert_called_once_with('/test/prd.md', 'ecid-001')
            mock_update_status.assert_called_once_with('task-001', 'Completed', 100.0)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_governance_without_prd(self, mock_database):
        """Test process_task for governance task without PRD path"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        task = {
            'task_id': 'task-001',
            'type': 'governance',
            'application': 'TestApp',
            'complexity': 0.5
        }
        
        result = await agent.process_task(task)
        
        assert result['task_id'] == 'task-001'
        assert result['status'] == 'completed'  # LeadAgent returns 'completed' for governance tasks
        assert 'governance_decision' in result
        assert 'message' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_escalation(self, mock_database):
        """Test escalation handling"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        message = AgentMessage(
            sender='dev-agent',
            recipient='lead-agent-001',
            message_type='escalation',
            payload={'task_id': 'task-001', 'reason': 'Complex issue'},
            context={'priority': 'HIGH'},
            timestamp='2025-01-01T00:00:00Z',
            message_id='msg-001'
        )
        
        with patch.object(agent, 'log_activity') as mock_log:
            await agent.handle_escalation(message)
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[0][0] == "escalation_received"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_status_query(self, mock_database):
        """Test status query handling"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        message = AgentMessage(
            sender='dev-agent',
            recipient='lead-agent-001',
            message_type='status_query',
            payload={'query': 'task_status', 'task_id': 'task-001'},
            context={'priority': 'MEDIUM'},
            timestamp='2025-01-01T00:00:00Z',
            message_id='msg-001'
        )
        
        with patch.object(agent, 'send_message') as mock_send:
            await agent.handle_status_query(message)
            
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == "dev-agent"  # Response to dev agent
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_task_error(self, mock_database):
        """Test task error handling"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        message = AgentMessage(
            sender='dev-agent',
            recipient='lead-agent-001',
            message_type='task_error',
            payload={'task_id': 'task-001', 'error': 'Test error'},
            context={'priority': 'HIGH'},
            timestamp='2025-01-01T00:00:00Z',
            message_id='msg-001'
        )
        
        await agent.handle_task_error(message)
        
        # Verify error was logged in communication_log
        assert len(agent.communication_log) == 1
        log_entry = agent.communication_log[0]
        assert log_entry['task_id'] == 'task-001'
        assert log_entry['from_agent'] == 'dev-agent'
        assert log_entry['message_type'] == 'task_error'
        assert log_entry['status'] == 'error'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_prd_request(self, mock_database):
        """Test PRD request handling"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        message = AgentMessage(
            sender='dev-agent',
            recipient='lead-agent-001',
            message_type='prd_request',
            payload={'prd_path': '/test/prd.md', 'ecid': 'ecid-001'},
            context={'priority': 'HIGH'},
            timestamp='2025-01-01T00:00:00Z',
            message_id='msg-001'
        )
        
        with patch.object(agent, 'process_prd_request') as mock_process_prd, \
             patch.object(agent, 'send_message') as mock_send:
            
            mock_process_prd.return_value = {'status': 'success'}
            
            await agent.handle_prd_request(message)
            
            mock_process_prd.assert_called_once_with('/test/prd.md')  # Only prd_path, no ecid
            mock_send.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_message_routing(self):
        """Test message routing to appropriate handlers"""
        agent = LeadAgent("lead-agent-001")
        
        # Test escalation message routing
        escalation_message = AgentMessage(
            sender='dev-agent',
            recipient='lead-agent-001',
            message_type='escalation',
            payload={'task_id': 'task-001'},
            context={},
            timestamp='2025-01-01T00:00:00Z',
            message_id='msg-001'
        )
        
        with patch.object(agent, 'handle_escalation') as mock_handle:
            await agent.handle_message(escalation_message)
            mock_handle.assert_called_once_with(escalation_message)
        
        # Test status query message routing
        status_message = AgentMessage(
            sender='dev-agent',
            recipient='lead-agent-001',
            message_type='status_query',
            payload={'query': 'status'},
            context={},
            timestamp='2025-01-01T00:00:00Z',
            message_id='msg-002'
        )
        
        with patch.object(agent, 'handle_status_query') as mock_handle:
            await agent.handle_message(status_message)
            mock_handle.assert_called_once_with(status_message)    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_escalate_task(self, mock_database):
        """Test task escalation"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_analyze_prd_requirements(self):
        """Test PRD requirements analysis"""
        agent = LeadAgent("lead-agent-001")
        
        prd_content = """# Test App
        ## Core Features
        - Authentication
        ## Technical Requirements
        - Python 3.11"""
        
        analysis = await agent.analyze_prd_requirements(prd_content)
        assert isinstance(analysis, dict)
        assert 'core_features' in analysis
    
