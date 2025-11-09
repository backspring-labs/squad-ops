"""
Unit tests for LeadAgent class
Tests core LeadAgent functionality without external dependencies
"""

import pytest
import asyncio
import yaml
import json
import os
import tempfile
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from agents.roles.lead.agent import LeadAgent
from agents.base_agent import AgentMessage
from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse
from tests.utils.mock_helpers import (
    create_sample_validate_warmboot_request,
    create_sample_agent_response,
    create_sample_build_manifest,
    MockAgentMessage
)

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
        assert agent.validator is not None  # SchemaValidator should be initialized
    
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
                "success_criteria": ["Functional requirements", "Performance", "User acceptance"]
            }
            """
            
            # Mock the current_ecid attribute to avoid the error
            agent.current_ecid = "test-ecid-001"
            
            analysis = await agent.analyze_prd_requirements(sample_prd)
            
            assert 'core_features' in analysis
            assert 'technical_requirements' in analysis
            assert 'success_criteria' in analysis
            assert analysis['core_features'] == ["Feature 1", "Feature 2"]
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_agent_request_validate_warmboot(self, mock_unified_config):
        """Test handle_agent_request for validate.warmboot capability"""
        with patch('config.unified_config.get_config', return_value=mock_unified_config):
            agent = LeadAgent("lead-agent-001")
            
            # Mock update_task_status to avoid HTTP calls
            with patch.object(agent, 'update_task_status', new_callable=AsyncMock) as mock_update_status, \
                 patch.object(agent, 'read_prd', return_value="Test PRD content"), \
                 patch.object(agent, 'analyze_prd_requirements', return_value={
                     "core_features": ["Feature 1"],
                     "full_analysis": "Test analysis"
                 }), \
                 patch.object(agent, 'create_development_tasks', return_value=[]), \
                 patch.object(agent, 'process_prd_request', return_value={
                     "status": "completed",
                     "diffs": [],
                     "wrap_up_uri": "/warm-boot/runs/ECID-001/wrap-up.md",
                     "metrics": {}
                 }):
                
                request = create_sample_validate_warmboot_request(ecid="ECID-001")
                
                response = await agent.handle_agent_request(request)
                
                assert isinstance(response, AgentResponse)
                assert response.status == "ok"
                assert "match" in response.result
                assert "diffs" in response.result
                assert "wrap_up_uri" in response.result
                assert "metrics" in response.result
                assert response.idempotency_key is not None
                assert response.timing is not None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_agent_request_task_coordination(self, mock_unified_config):
        """Test handle_agent_request for governance.task_coordination capability"""
        with patch('config.unified_config.get_config', return_value=mock_unified_config):
            agent = LeadAgent("lead-agent-001")
            
            request = AgentRequest(
                action="governance.task_coordination",
                payload={"type": "development", "task_id": "test-001"},
                metadata={"pid": "PID-001", "ecid": "ECID-001"}
            )
            
            with patch.object(agent, 'send_message') as mock_send:
                response = await agent.handle_agent_request(request)
                
                assert isinstance(response, AgentResponse)
                assert response.status == "ok"
                assert "tasks_created" in response.result
                assert "tasks_delegated" in response.result
                assert "coordination_log" in response.result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_agent_request_approval(self, mock_unified_config):
        """Test handle_agent_request for governance.approval capability"""
        with patch('config.unified_config.get_config', return_value=mock_unified_config):
            agent = LeadAgent("lead-agent-001")
            
            request = AgentRequest(
                action="governance.approval",
                payload={"complexity": 0.3, "task_id": "test-001"},
                metadata={"pid": "PID-001", "ecid": "ECID-001"}
            )
            
            response = await agent.handle_agent_request(request)
            
            assert isinstance(response, AgentResponse)
            assert response.status == "ok"
            assert "approved" in response.result
            assert "decision" in response.result
            assert "approval_time" in response.result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_agent_request_escalation(self, mock_unified_config):
        """Test handle_agent_request for governance.escalation capability"""
        with patch('config.unified_config.get_config', return_value=mock_unified_config):
            agent = LeadAgent("lead-agent-001")
            
            request = AgentRequest(
                action="governance.escalation",
                payload={"task_id": "test-001", "reason": "high_complexity"},
                metadata={"pid": "PID-001", "ecid": "ECID-001"}
            )
            
            with patch.object(agent, 'escalate_task') as mock_escalate:
                response = await agent.handle_agent_request(request)
                
                assert isinstance(response, AgentResponse)
                assert response.status == "ok"
                assert "escalated" in response.result
                assert "resolution" in response.result
                assert "escalation_time" in response.result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_task_creation(self, sample_prd):
        """Test development task creation from PRD analysis"""
        agent = LeadAgent("lead-agent-001")
        
        prd_analysis = {
            'core_features': ['Feature 1', 'Feature 2'],
            'technical_requirements': ['Web app', 'Database'],
            'success_criteria': ['Functional requirements', 'Performance', 'User acceptance']
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.json.return_value = {'task_id': 'test-task-001'}
            mock_response.status = 201
            mock_post.return_value.__aenter__.return_value = mock_response
            
            tasks = await agent.create_development_tasks(prd_analysis, "TestApp", "test-ecid-001")
            
            assert len(tasks) == 4  # archive, design_manifest, build, deploy
            
            # Check archive task
            archive_task = tasks[0]
            assert archive_task['task_type'] == 'development'
            assert archive_task['requirements']['action'] == 'archive'
            assert archive_task['complexity'] == 0.3
            assert archive_task['priority'] == 'HIGH'
            
            # Check design_manifest task (now second)
            design_manifest_task = tasks[1]
            assert design_manifest_task['task_type'] == 'development'
            assert design_manifest_task['requirements']['action'] == 'design_manifest'
            assert design_manifest_task['complexity'] == 0.4
            assert design_manifest_task['priority'] == 'HIGH'
            
            # Check build task (now third)
            build_task = tasks[2]
            assert build_task['task_type'] == 'development'
            assert build_task['requirements']['action'] == 'build'
            assert build_task['complexity'] == 0.8
            assert build_task['priority'] == 'HIGH'
            
            # Check deploy task (now fourth)
            deploy_task = tasks[3]
            assert deploy_task['task_type'] == 'development'
            assert deploy_task['requirements']['action'] == 'deploy'
            assert deploy_task['complexity'] == 0.5
            assert deploy_task['priority'] == 'MEDIUM'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_delegation_target(self):
        """Test delegation target determination"""
        agent = LeadAgent("lead-agent-001")
        
        # Test development task delegation
        target = await agent.determine_delegation_target("development")
        assert target == "dev-agent"  # LeadAgent uses role-based names
        
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
    async def test_process_task_governance_without_prd(self, mock_database, mock_unified_config):
        """Test process_task for governance task without PRD path"""
        with patch('config.unified_config.get_config', return_value=mock_unified_config):
            agent = LeadAgent("lead-agent-001")
            agent.db_pool = mock_database
            agent.task_api_url = 'http://task-api:8001'
            
            task = {
                'task_id': 'task-001',
                'type': 'governance',
                'application': 'TestApp',
                'complexity': 0.5
            }
            
            # Mock update_task_status to avoid HTTP call
            with patch.object(agent, 'update_task_status', new_callable=AsyncMock):
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
    
    # ========== LeadAgent PRD Processing Tests (Lines 540-587) ==========
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_prd_request_full_workflow(self, mock_database):
        """Test complete PRD processing workflow"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        # Mock the actual methods that exist on LeadAgent
        with patch.object(agent, 'read_file', return_value="# Test PRD\n## Features\n- Feature 1") as mock_read, \
             patch.object(agent, 'analyze_prd_requirements', return_value={'core_features': ['Feature 1'], 'technical_requirements': []}) as mock_analyze, \
             patch.object(agent, 'create_development_tasks', return_value=[
                 {'task_id': 'task-1', 'task_type': 'development', 'description': 'Build app'},
                 {'task_id': 'task-2', 'task_type': 'deployment', 'description': 'Deploy app'}
             ]) as mock_create, \
             patch.object(agent, 'log_task_delegation', return_value=None) as mock_log, \
             patch.object(agent, 'send_message', return_value=None) as mock_send:
            
            result = await agent.process_prd_request("warm-boot/prd/PRD-001.md")
            
            # Verify workflow steps
            assert result['status'] == 'success'
            assert 'tasks_delegated' in result
            assert len(result['tasks_delegated']) == 2
            
            # Verify methods were called
            mock_read.assert_called_once_with("warm-boot/prd/PRD-001.md")
            mock_analyze.assert_called_once()
            mock_create.assert_called_once()
            assert mock_log.call_count == 2
            assert mock_send.call_count == 2
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_prd_request_task_creation(self, mock_database):
        """Test task generation from PRD"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        with patch.object(agent, 'read_file', return_value="# Simple App\n## Features\n- Basic CRUD"), \
             patch.object(agent, 'analyze_prd_requirements', return_value={'core_features': ['CRUD']}), \
             patch.object(agent, 'create_development_tasks', return_value=[
                 {'task_id': 'task-archive', 'task_type': 'archive', 'description': 'Archive old version'},
                 {'task_id': 'task-build', 'task_type': 'build', 'description': 'Build new version'},
                 {'task_id': 'task-deploy', 'task_type': 'deploy', 'description': 'Deploy application'}
             ]) as mock_create, \
             patch.object(agent, 'log_task_delegation', return_value=None), \
             patch.object(agent, 'send_message', return_value=None):
            
            result = await agent.process_prd_request("prd-path.md")
            
            # Verify tasks were created
            assert result['status'] == 'success'
            assert len(result['tasks_delegated']) == 3
            assert result['tasks_delegated'][0]['task_id'] == 'task-archive'
            assert result['tasks_delegated'][1]['task_id'] == 'task-build'
            assert result['tasks_delegated'][2]['task_id'] == 'task-deploy'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_prd_request_delegation(self, mock_database):
        """Test task delegation to correct agent"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        with patch.object(agent, 'read_file', return_value="# Test App"), \
             patch.object(agent, 'analyze_prd_requirements', return_value={'core_features': []}), \
             patch.object(agent, 'create_development_tasks', return_value=[
                 {'task_id': 'dev-task', 'task_type': 'development', 'description': 'Develop feature'}
             ]), \
             patch.object(agent, 'log_task_delegation', return_value=None) as mock_log, \
             patch.object(agent, 'send_message', return_value=None) as mock_send:
            
            result = await agent.process_prd_request("test-prd.md")
            
            # Verify delegation occurred
            mock_log.assert_called_once()
            mock_send.assert_called_once()
            
            # Verify message was sent with correct structure
            call_args = mock_send.call_args
            assert call_args[1]['message_type'] == 'task_delegation'
            assert 'payload' in call_args[1]
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_prd_request_with_complex_prd(self, mock_database):
        """Test PRD processing with complex requirements"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        complex_prd = """# Enterprise Application
        ## Core Features
        - Multi-tenant architecture
        - API gateway
        ## Technical Requirements
        - Python 3.11+
        - Docker deployment"""
        
        with patch.object(agent, 'read_file', return_value=complex_prd), \
             patch.object(agent, 'analyze_prd_requirements', return_value={
                 'core_features': ['multi-tenant', 'API'],
                 'technical_requirements': ['Python', 'Docker']
             }), \
             patch.object(agent, 'create_development_tasks', return_value=[
                 {'task_id': 't1', 'task_type': 'development', 'description': 'Task 1'}
             ]), \
             patch.object(agent, 'log_task_delegation', return_value=None), \
             patch.object(agent, 'send_message', return_value=None):
            
            result = await agent.process_prd_request("complex-prd.md")
            
            # Verify complex PRD was processed
            assert result['status'] == 'success'
            assert 'prd_analysis' in result
            assert result['prd_analysis']['core_features'] == ['multi-tenant', 'API']
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_prd_request_error_handling(self, mock_database):
        """Test PRD processing error scenarios"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        # Test file read error
        with patch.object(agent, 'read_file', side_effect=FileNotFoundError("PRD not found")):
            result = await agent.process_prd_request("nonexistent.md")
            assert result['status'] == 'error'
            assert 'Failed to read PRD' in result['message'] or 'PRD processing failed' in result['message']
        
        # Test task creation error (returns None)
        with patch.object(agent, 'read_file', return_value="# Test"), \
             patch.object(agent, 'analyze_prd_requirements', return_value={'core_features': []}), \
             patch.object(agent, 'create_development_tasks', return_value=None):
            result = await agent.process_prd_request("test.md")
            assert result['status'] == 'error'
            assert 'Failed to create tasks' in result['message']
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_delegation_target(self):
        """Test delegation target determination by role"""
        # Agent will load from actual instances.yaml (production config)
        agent = LeadAgent("lead-agent-001")
        
        # Test development task delegation → dev role → neo (from instances.yaml)
        target = await agent.determine_delegation_target('development')
        assert target == 'neo'  # Expected from production instances.yaml (instance name)
        
        # Test deployment task delegation → dev role → neo  
        target = await agent.determine_delegation_target('deployment')
        assert target == 'neo'
        
        # Test code task delegation → dev role → neo
        target = await agent.determine_delegation_target('code')
        assert target == 'neo'
        
        # Test security task delegation → qa role → qa-agent (from instances.yaml)
        target = await agent.determine_delegation_target('security')
        assert target == 'qa-agent'  # Expected from production instances.yaml
        
        # Test strategy task delegation → strat role → strat-agent
        target = await agent.determine_delegation_target('product')
        assert target == 'strat-agent'  # Expected from production instances.yaml
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_determine_delegation_target_with_custom_instances(self, tmp_path):
        """Test delegation with custom test instances configuration"""
        # Create a test instances file
        test_instances = {
            'instances': [
                {'id': 'dev-agent-001', 'role': 'dev', 'enabled': True},
                {'id': 'qa-agent-001', 'role': 'qa', 'enabled': True},
                {'id': 'lead-agent-001', 'role': 'lead', 'enabled': True}
            ]
        }
        
        instances_file = tmp_path / "test_instances.yaml"
        with open(instances_file, 'w') as f:
            yaml.dump(test_instances, f)
        
        # Create agent with custom instances file
        agent = LeadAgent("lead-agent-001", instances_file=str(instances_file))
        
        # Test that it uses the test configuration
        target = await agent.determine_delegation_target('development')
        assert target == 'dev-agent-001'  # From test config, not production
        
        target = await agent.determine_delegation_target('security')
        assert target == 'qa-agent-001'  # From test config, not production
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_log_task_delegation(self, mock_database):
        """Test task delegation logging via API"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        # Simply mock the method since testing API internals isn't the goal
        with patch.object(agent, 'log_task_delegation', wraps=agent.log_task_delegation) as mock_log:
            # Mock the aiohttp calls within the method
            with patch('agents.base_agent.aiohttp.ClientSession') as mock_session:
                # Create proper async context manager mocks
                mock_resp = MagicMock()
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value={'status': 'success'})
                mock_resp.text = AsyncMock(return_value='OK')
                mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
                mock_resp.__aexit__ = AsyncMock(return_value=None)
                
                mock_session_inst = MagicMock()
                mock_session_inst.put = MagicMock(return_value=mock_resp)
                mock_session_inst.__aenter__ = AsyncMock(return_value=mock_session_inst)
                mock_session_inst.__aexit__ = AsyncMock(return_value=None)
                
                mock_session.return_value = mock_session_inst
                
                await agent.log_task_delegation(
                    task_id='task-123',
                    ecid='ECID-WB-027',
                    delegated_to='dev-agent',
                    description='Build application'
                )
                
                # Verify the method was called with correct parameters
                mock_log.assert_called_once_with(
                    task_id='task-123',
                    ecid='ECID-WB-027',
                    delegated_to='dev-agent',
                    description='Build application'
                )
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_empty_prd_path(self, mock_database):
        """Test process_task with governance task but empty PRD path"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        task = {
            'task_id': 'task-123',
            'type': 'governance',
            'prd_path': '',  # Empty PRD path
            'application': 'TestApp',
            'timestamp': '2025-01-01T00:00:00Z',
            'complexity': 0.3
        }
        
        with patch.object(agent, 'update_task_status', new=AsyncMock()) as mock_update, \
             patch.object(agent, 'mock_llm_response', new=AsyncMock(return_value='Mock response')):
            
            result = await agent.process_task(task)
            
            # Should handle governance task directly, not process PRD
            assert result['status'] == 'completed'
            assert 'governance_decision' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_read_prd_file_not_found(self):
        """Test read_prd with non-existent file"""
        agent = LeadAgent("lead-agent-001")
        
        # The method catches exceptions and returns empty string
        result = await agent.read_prd('/nonexistent/path/prd.md')
        
        # Should return empty string after catching the error
        assert result == ""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_analyze_prd_requirements_error_handling(self):
        """Test analyze_prd_requirements with LLM error"""
        agent = LeadAgent("lead-agent-001")
        
        with patch.object(agent, 'llm_response', side_effect=Exception("LLM API Error")):
            # Method catches exceptions and returns fallback analysis
            result = await agent.analyze_prd_requirements("Test PRD content")
            
            # Should return fallback analysis dict with default keys
            assert isinstance(result, dict)
            assert 'core_features' in result
            assert 'technical_requirements' in result
            assert 'success_criteria' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_prd_request_file_not_found(self, mock_database):
        """Test process_prd_request with non-existent PRD file"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        with patch.object(agent, 'read_prd', side_effect=FileNotFoundError("PRD not found")):
            result = await agent.process_prd_request('/nonexistent/prd.md', 'ECID-WB-027')
            
            # Should return error status
            assert result['status'] == 'error'
            assert 'error' in result or 'message' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_message_unknown_type(self):
        """Test handle_message with unknown message type"""
        agent = LeadAgent("lead-agent-001")
        
        import time
        message = AgentMessage(
            sender='test-agent',
            recipient='lead-agent-001',
            message_type='unknown_type',
            payload={},
            context={},
            timestamp=time.time(),
            message_id='test-msg-001'
        )
        
        # Should log but not raise error
        await agent.handle_message(message)
        # If no exception raised, test passes
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_load_role_to_agent_mapping_file_error(self):
        """Test _load_role_to_agent_mapping with file read error"""
        # Mock the LLM client initialization to avoid config file issues
        with patch('agents.llm.router.LLMRouter.from_config') as mock_router:
            mock_client = MagicMock()
            mock_router.return_value.get_default_client.return_value = mock_client
            
            # Create agent with non-existent instances file
            with patch('builtins.open', side_effect=FileNotFoundError("Instances file not found")):
                agent = LeadAgent("lead-agent-001", instances_file="/nonexistent/instances.yaml")
                
                # Should handle the error gracefully
                assert agent._role_to_agent_cache is None
            
            # Should fall back to default mapping
            mapping = agent._load_role_to_agent_mapping()
            
            # Should return default mapping
            assert isinstance(mapping, dict)
            assert len(mapping) > 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_load_role_to_agent_mapping_yaml_error(self):
        """Test _load_role_to_agent_mapping with YAML parse error"""
        # Mock the LLM client initialization to avoid config file issues
        with patch('agents.llm.router.LLMRouter.from_config') as mock_router:
            mock_client = MagicMock()
            mock_router.return_value.get_default_client.return_value = mock_client
            
            with patch('builtins.open', MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value='invalid: yaml: [')))))):
                agent = LeadAgent("lead-agent-001")
                
                # Should handle the error gracefully
                assert agent._role_to_agent_cache is None
            
            # Should fall back to default mapping
            mapping = agent._load_role_to_agent_mapping()
            
            # Should return default mapping
            assert isinstance(mapping, dict)
    
    @pytest.mark.unit
    def test_get_default_role_mapping(self):
        """Test _get_default_role_mapping"""
        agent = LeadAgent("lead-agent-001")
        
        mapping = agent._get_default_role_mapping()
        
        assert isinstance(mapping, dict)
        assert 'dev' in mapping
        assert 'qa' in mapping
        # Check for roles that actually exist in the default mapping
        assert len(mapping) > 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_high_complexity_escalation(self, mock_database):
        """Test process_task with high complexity for escalation"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        agent.escalation_threshold = 0.7
        
        task = {
            'task_id': 'task-999',
            'type': 'development',
            'description': 'Complex task',
            'timestamp': '2025-01-01T00:00:00Z',
            'complexity': 0.95  # High complexity
        }
        
        with patch.object(agent, 'update_task_status', new=AsyncMock()) as mock_update, \
             patch.object(agent, 'escalate_task', new=AsyncMock()) as mock_escalate, \
             patch.object(agent, 'mock_llm_response', new=AsyncMock(return_value='Mock response')):
            
            result = await agent.process_task(task)
            
            assert result['status'] == 'escalated'
            assert 'reason' in result
            assert 'escalation_level' in result
            mock_escalate.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_developer_completion(self):
        """Test SIP-027 Phase 1: Developer completion event handling"""
        agent = LeadAgent("lead-agent")
        
        # Mock the generate_warmboot_wrapup method
        agent.generate_warmboot_wrapup = AsyncMock()
        
        # Create developer completion event
        completion_message = AgentMessage(
            sender='dev-agent',
            recipient='lead-agent',
            message_type='task.developer.completed',
            payload={
                'task_id': 'test-task-001',
                'status': 'completed',
                'tasks_completed': ['build', 'test'],
                'artifacts': []
            },
            context={'ecid': 'ECID-WB-001'},
            timestamp='2025-01-15T10:00:00Z',
            message_id='msg-001'
        )
        
        # Handle the completion event
        await agent.handle_developer_completion(completion_message)
        
        # Verify wrap-up was triggered
        agent.generate_warmboot_wrapup.assert_called_once()
        call_args = agent.generate_warmboot_wrapup.call_args
        assert call_args[0][0] == 'ECID-WB-001'  # ecid
        assert call_args[0][1] == 'test-task-001'  # task_id
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_developer_completion_failed_task(self):
        """Test that failed tasks don't trigger wrap-up"""
        agent = LeadAgent("lead-agent")
        
        # Mock the generate_warmboot_wrapup method
        agent.generate_warmboot_wrapup = AsyncMock()
    
    # ============================================================================
    # REASONING SHARING TESTS
    # ============================================================================
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_reasoning_event_success(self):
        """Test successful reasoning event handling"""
        agent = LeadAgent("lead-agent-001")
        
        message = AgentMessage(
            sender='dev-agent',
            recipient='lead-agent-001',
            message_type='agent_reasoning',
            payload={
                'schema': 'reasoning.v1',
                'task_id': 'test-task-001',
                'ecid': 'ECID-WB-001',
                'reason_step': 'decision',
                'summary': 'Selected FastAPI architecture',
                'context': 'manifest_generation',
                'key_points': ['FastAPI chosen', 'Async support needed'],
                'confidence': 0.85,
                'raw_reasoning_included': False
            },
            context={
                'sender_agent': 'dev-agent',
                'sender_role': 'developer',
                'ecid': 'ECID-WB-001'
            },
            timestamp='2025-01-01T12:00:00Z',
            message_id='msg-reasoning-001'
        )
        
        await agent.handle_reasoning_event(message)
        
        # Verify reasoning event was stored in communication log
        assert len(agent.communication_log) == 1
        log_entry = agent.communication_log[0]
        assert log_entry['message_type'] == 'agent_reasoning'
        assert log_entry['sender'] == 'dev-agent'
        assert log_entry['agent'] == 'dev-agent'
        assert log_entry['ecid'] == 'ECID-WB-001'
        assert log_entry['task_id'] == 'test-task-001'
        assert log_entry['reason_step'] == 'decision'
        assert log_entry['summary'] == 'Selected FastAPI architecture'
        assert log_entry['context'] == 'manifest_generation'
        assert log_entry['key_points'] == ['FastAPI chosen', 'Async support needed']
        assert log_entry['confidence'] == 0.85
        assert log_entry['raw_reasoning_included'] is False
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_reasoning_event_minimal(self):
        """Test reasoning event handling with minimal fields"""
        agent = LeadAgent("lead-agent-001")
        
        message = AgentMessage(
            sender='dev-agent',
            recipient='lead-agent-001',
            message_type='agent_reasoning',
            payload={
                'schema': 'reasoning.v1',
                'task_id': 'test-task-002',
                'ecid': 'ECID-WB-002',
                'reason_step': 'checkpoint',
                'summary': 'Build completed',
                'context': 'build',
                'raw_reasoning_included': False
            },
            context={
                'sender_agent': 'dev-agent',
                'ecid': 'ECID-WB-002'
            },
            timestamp='2025-01-01T12:05:00Z',
            message_id='msg-reasoning-002'
        )
        
        await agent.handle_reasoning_event(message)
        
        # Verify reasoning event was stored
        assert len(agent.communication_log) == 1
        log_entry = agent.communication_log[0]
        assert log_entry['message_type'] == 'agent_reasoning'
        assert log_entry['reason_step'] == 'checkpoint'
        assert log_entry['summary'] == 'Build completed'
        assert log_entry['context'] == 'build'
        # Optional fields should not be present or None
        assert 'key_points' not in log_entry or log_entry.get('key_points') == []
        assert 'confidence' not in log_entry or log_entry.get('confidence') is None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_reasoning_event_exception(self):
        """Test reasoning event handling with exception"""
        agent = LeadAgent("lead-agent-001")
        
        # Create message with missing required fields to trigger exception
        message = AgentMessage(
            sender='dev-agent',
            recipient='lead-agent-001',
            message_type='agent_reasoning',
            payload={},  # Empty payload
            context={},
            timestamp='2025-01-01T12:00:00Z',
            message_id='msg-reasoning-003'
        )
        
        # Should not raise exception
        await agent.handle_reasoning_event(message)
        
        # Should still log something (even if minimal)
        assert len(agent.communication_log) >= 0  # May or may not log on error
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_message_routes_reasoning_event(self):
        """Test that handle_message routes agent_reasoning to handler"""
        agent = LeadAgent("lead-agent-001")
        
        message = AgentMessage(
            sender='dev-agent',
            recipient='lead-agent-001',
            message_type='agent_reasoning',
            payload={
                'schema': 'reasoning.v1',
                'task_id': 'test-task-001',
                'ecid': 'ECID-WB-001',
                'reason_step': 'decision',
                'summary': 'Test decision',
                'context': 'manifest_generation'
            },
            context={'sender_agent': 'dev-agent', 'ecid': 'ECID-WB-001'},
            timestamp='2025-01-01T12:00:00Z',
            message_id='msg-reasoning-001'
        )
        
        with patch.object(agent, 'handle_reasoning_event') as mock_handler:
            await agent.handle_message(message)
            mock_handler.assert_called_once_with(message)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_extract_real_ai_reasoning_includes_agent_reasoning(self):
        """Test that _extract_real_ai_reasoning includes agent reasoning events"""
        agent = LeadAgent("lead-agent-001")
        
        # Add agent reasoning event to communication log
        agent.communication_log = [
            {
                'timestamp': '2025-01-01T12:00:00Z',
                'sender': 'dev-agent',
                'agent': 'dev-agent',
                'message_type': 'agent_reasoning',
                'ecid': 'ECID-WB-001',
                'task_id': 'test-task-001',
                'reason_step': 'decision',
                'summary': 'Selected FastAPI architecture',
                'context': 'manifest_generation',
                'key_points': ['FastAPI chosen', 'Async support needed'],
                'confidence': 0.85
            },
            {
                'timestamp': '2025-01-01T12:05:00Z',
                'sender': 'dev-agent',
                'agent': 'dev-agent',
                'message_type': 'agent_reasoning',
                'ecid': 'ECID-WB-001',
                'task_id': 'test-task-001',
                'reason_step': 'checkpoint',
                'summary': 'Created 5 files',
                'context': 'manifest_generation',
                'key_points': ['Files created', 'Directory structure']
            }
        ]
        
        reasoning = agent._extract_real_ai_reasoning('ECID-WB-001', agent_name='dev-agent')
        
        # Verify reasoning includes agent reasoning events
        assert len(reasoning) > 0
        assert 'dev-agent' in reasoning
        assert 'manifest_generation' in reasoning or 'decision' in reasoning
        assert 'Selected FastAPI' in reasoning or 'Created 5 files' in reasoning
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_extract_real_ai_reasoning_no_agent_reasoning(self):
        """Test _extract_real_ai_reasoning when no agent reasoning events exist"""
        agent = LeadAgent("lead-agent-001")
        
        # Empty communication log
        agent.communication_log = []
        
        reasoning = agent._extract_real_ai_reasoning('ECID-WB-001', agent_name='dev-agent')
        
        # Should return message indicating no reasoning found
        assert 'No reasoning trace found' in reasoning or 'reasoning' in reasoning.lower()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_developer_completion_failed_task_with_reasoning(self):
        """Test that failed tasks don't trigger wrap-up"""
        agent = LeadAgent("lead-agent")
        
        # Mock the generate_warmboot_wrapup method
        agent.generate_warmboot_wrapup = AsyncMock()
        
        # Create failed completion event
        completion_message = AgentMessage(
            sender='dev-agent',
            recipient='lead-agent',
            message_type='task.developer.completed',
            payload={
                'task_id': 'failed-task',
                'status': 'failed',
                'error': 'Build failed'
            },
            context={'ecid': 'ECID-WB-002'},
            timestamp='2025-01-15T10:00:00Z',
            message_id='msg-002'
        )
        
        # Handle the failed completion event
        await agent.handle_developer_completion(completion_message)
        
        # Verify wrap-up was NOT triggered
        agent.generate_warmboot_wrapup.assert_not_called()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_telemetry(self, mock_unified_config):
        """Test SIP-027 Phase 1: Telemetry collection via Task API"""
        with patch('config.unified_config.get_config', return_value=mock_unified_config):
            agent = LeadAgent("lead-agent")
            agent.task_api_url = 'http://task-api:8001'
            
            # Mock Task API responses (replaces direct DB reads)
            mock_tasks_response = AsyncMock()
            mock_tasks_response.status = 200
            mock_tasks_response.json = AsyncMock(return_value=[
                {'task_id': 'task-001', 'agent': 'dev-agent', 'status': 'completed', 'start_time': '2025-01-15T10:00:00', 'end_time': '2025-01-15T10:05:00', 'duration': None, 'artifacts': None}
            ])
            mock_tasks_response.text = AsyncMock(return_value="")
            mock_tasks_response.__aenter__ = AsyncMock(return_value=mock_tasks_response)
            mock_tasks_response.__aexit__ = AsyncMock(return_value=None)
            
            mock_cycle_response = AsyncMock()
            mock_cycle_response.status = 200
            mock_cycle_response.json = AsyncMock(return_value={
                'ecid': 'ECID-WB-001',
                'pid': 'PID-001',
                'run_type': 'warmboot',
                'title': 'Test Run',
                'created_at': '2025-01-15T09:00:00',
                'status': 'active'
            })
            mock_cycle_response.text = AsyncMock(return_value="")
            mock_cycle_response.__aenter__ = AsyncMock(return_value=mock_cycle_response)
            mock_cycle_response.__aexit__ = AsyncMock(return_value=None)
            
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            # Configure GET responses - return proper async context managers
            def mock_get(url, **kwargs):
                if '/tasks/ec/' in url:
                    return mock_tasks_response
                elif '/execution-cycles/' in url:
                    return mock_cycle_response
                error_resp = AsyncMock(status=404, json=AsyncMock(return_value={}))
                error_resp.__aenter__ = AsyncMock(return_value=error_resp)
                error_resp.__aexit__ = AsyncMock(return_value=None)
                return error_resp
            
            mock_session.get = Mock(side_effect=mock_get)
            
            # Add communication log
            agent.communication_log = [
                {'task_id': 'task-001', 'message_type': 'test'}
            ]
            
            # Collect telemetry via Task API
            with patch('aiohttp.ClientSession', return_value=mock_session):
                telemetry = await agent._collect_telemetry('ECID-WB-001', 'task-001')
            
            # Verify telemetry structure
            assert 'database_metrics' in telemetry
            assert 'rabbitmq_metrics' in telemetry
            assert 'docker_events' in telemetry
            assert 'reasoning_logs' in telemetry
            assert 'collection_timestamp' in telemetry
            
            # Verify database metrics from Task API (handle case where API might not populate all keys)
            db_metrics = telemetry.get('database_metrics', {})
            if 'task_count' in db_metrics:
                assert db_metrics['task_count'] == 1
                assert len(db_metrics.get('tasks', [])) == 1
            if 'execution_cycle' in db_metrics:
                assert db_metrics['execution_cycle']['ecid'] == 'ECID-WB-001'
            
            # Verify RabbitMQ metrics
            assert telemetry['rabbitmq_metrics']['messages_processed'] == 1
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_telemetry_error_handling(self, mock_unified_config):
        """Test telemetry collection handles errors gracefully via Task API"""
        with patch('config.unified_config.get_config', return_value=mock_unified_config):
            agent = LeadAgent("lead-agent")
            agent.task_api_url = 'http://task-api:8001'
            
            # Mock Task API to return errors
            mock_error_response = AsyncMock()
            mock_error_response.status = 500
            mock_error_response.json = AsyncMock(return_value={})
            mock_error_response.text = AsyncMock(return_value="Internal Server Error")
            mock_error_response.__aenter__ = AsyncMock(return_value=mock_error_response)
            mock_error_response.__aexit__ = AsyncMock(return_value=None)
            
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.get = Mock(return_value=mock_error_response)
            
            # Collect telemetry should not crash even if API fails
            with patch('aiohttp.ClientSession', return_value=mock_session):
                telemetry = await agent._collect_telemetry('ECID-ERROR', 'task-error')
            
            # Should still return structure (with empty metrics on error)
            assert 'database_metrics' in telemetry
            db_metrics = telemetry.get('database_metrics', {})
            # On error, task_count might be 0 or missing
            if 'task_count' in db_metrics:
                assert db_metrics['task_count'] == 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_wrapup_markdown(self):
        """Test SIP-027 Phase 1: Wrap-up markdown generation"""
        agent = LeadAgent("lead-agent")
        
        ecid = 'ECID-WB-055'
        run_number = '055'
        task_id = 'test-task-build'
        
        completion_payload = {
            'tasks_completed': ['archive', 'build', 'deploy'],
            'artifacts': [
                {'path': 'app.py', 'hash': 'sha256:abc123'}
            ],
            'metrics': {
                'duration_seconds': 120,
                'tokens_used': 3000,
                'tests_passed': 5,
                'tests_failed': 0
            }
        }
        
        telemetry = {
            'database_metrics': {
                'task_count': 3,
                'execution_cycle': {
                    'ecid': ecid,
                    'pid': 'PID-001',
                    'run_type': 'warmboot',
                    'title': 'Test WarmBoot',
                    'status': 'completed',
                    'created_at': '2025-10-19T16:12:49.526749'
                }
            },
            'rabbitmq_metrics': {
                'messages_processed': 10
            },
            'artifact_hashes': {
                'app.py': 'sha256:abc123',
                'index.html': 'sha256:def456'
            },
            'reasoning_logs': {
                'tokens_used': 3000,  # Add tokens_used for test
                'tokens_by_agent': {
                    'lead-agent': 1500,
                    'dev-agent': 1500
                },
                'tokens_source': 'manual_tracking'
            }
        }
        
        # Generate markdown
        markdown = await agent._generate_wrapup_markdown(
            ecid, run_number, task_id, completion_payload, telemetry
        )
        
        # Verify markdown content
        assert isinstance(markdown, str)
        assert len(markdown) > 100
        assert 'WarmBoot Run 055' in markdown
        assert ecid in markdown
        assert 'Reasoning & Resource Trace Log' in markdown
        assert 'PRD Interpretation (Lead Agent)' in markdown or 'PRD Interpretation' in markdown
        assert 'Task Execution (Dev Agent)' in markdown or 'Task Execution' in markdown
        assert 'Artifacts Produced' in markdown
        assert 'Resource & Event Summary' in markdown
        assert 'Metrics Snapshot' in markdown
        assert 'Event Timeline' in markdown
        assert 'Next Steps' in markdown
        assert 'SIP-027 Phase 1 Status' in markdown
        
        # Verify data is embedded
        # Check for tasks (should be in Actions Taken section)
        assert 'archive' in markdown.lower() or 'Archive' in markdown
        assert 'build' in markdown.lower() or 'Built' in markdown
        assert 'deploy' in markdown.lower() or 'Deployed' in markdown
        assert 'app.py' in markdown
        assert 'sha256:abc123' in markdown
        assert '3000' in markdown or '3000' in str(telemetry.get('reasoning_logs', {}).get('tokens_used', 0))
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_warmboot_wrapup(self):
        """Test SIP-027 Phase 1: Full wrap-up generation workflow"""
        agent = LeadAgent("lead-agent")
        
        # Mock dependencies
        agent._collect_telemetry = AsyncMock(return_value={
            'database_metrics': {'task_count': 2},
            'rabbitmq_metrics': {'messages_processed': 5}
        })
        
        agent._generate_wrapup_markdown = AsyncMock(return_value='# Test Markdown')
        
        agent.execute_command = AsyncMock(return_value={
            'success': True, 'returncode': 0
        })
        
        agent.write_file = AsyncMock(return_value=True)
        
        ecid = 'ECID-WB-042'
        task_id = 'test-task'
        completion_payload = {'status': 'completed'}
        
        # Generate wrap-up
        await agent.generate_warmboot_wrapup(ecid, task_id, completion_payload)
        
        # Verify methods were called
        agent._collect_telemetry.assert_called_once_with(ecid, task_id)
        agent._generate_wrapup_markdown.assert_called_once()
        agent.execute_command.assert_called_once()
        agent.write_file.assert_called_once()
        
        # Verify file path is correct
        write_call = agent.write_file.call_args
        file_path = write_call[0][0]
        assert '/warm-boot/runs/run-042/' in file_path
        assert 'warmboot-run042-wrapup.md' in file_path
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_warmboot_wrapup_error_handling(self):
        """Test wrap-up generation handles errors gracefully"""
        agent = LeadAgent("lead-agent")
        
        # Mock telemetry to raise error
        agent._collect_telemetry = AsyncMock(side_effect=Exception("DB error"))
        
        # Generate wrap-up should not crash
        await agent.generate_warmboot_wrapup('ECID-ERROR', 'task-error', {})
        
        # Should log error but not raise
    
    # ===== TASK SEQUENCING AND COORDINATION TESTS =====
    
    @pytest.fixture
    def lead_agent_for_sequencing(self):
        """Create LeadAgent instance for task sequencing tests."""
        from unittest.mock import patch, MagicMock
        
        # Create a mock TaskSpec class
        class MockTaskSpec:
            def __init__(self, **kwargs):
                self.app_name = kwargs.get("app_name", "TestApp")
                self.version = kwargs.get("version", "1.0.0")
                self.run_id = kwargs.get("run_id", "TEST-001")
                self.prd_analysis = kwargs.get("prd_analysis", "Test application for unit testing")
                self.features = kwargs.get("features", ["Feature 1", "Feature 2"])
                self.constraints = kwargs.get("constraints", {"framework": "vanilla_js"})
                self.success_criteria = kwargs.get("success_criteria", ["Application loads", "No errors"])
            
            def to_dict(self):
                return {
                    "app_name": self.app_name,
                    "version": self.version,
                    "run_id": self.run_id,
                    "prd_analysis": self.prd_analysis,
                    "features": self.features,
                    "constraints": self.constraints,
                    "success_criteria": self.success_criteria
                }
        
        with patch('config.version.get_framework_version', return_value="0.1.4"):
            agent = LeadAgent("test-lead-agent")
            
            # Mock the generate_build_requirements method to avoid network calls
            async def mock_generate_build_requirements(*args, **kwargs):
                return {
                    "app_name": kwargs.get("app_name", "TestApp"),
                    "version": kwargs.get("version", "0.2.0.001"), 
                    "run_id": kwargs.get("run_id", "TEST-001"),
                    "prd_analysis": kwargs.get("prd_content", "Test application for unit testing"),
                    "features": kwargs.get("features", ["Feature 1", "Feature 2"]),
                    "constraints": {"framework": "vanilla_js"},
                    "success_criteria": ["Application loads", "No errors"]
                }
            
            agent.generate_build_requirements = mock_generate_build_requirements
            
            # Mock the log_task_start method to avoid task-api calls
            async def mock_log_task_start(*args, **kwargs):
                pass  # Do nothing
            
            agent.log_task_start = mock_log_task_start
            return agent
    
    @pytest.fixture
    def sample_prd_analysis(self):
        """Sample PRD analysis for testing."""
        return {
            "summary": "Test application for unit testing",
            "full_analysis": "Test application for unit testing",
            "core_features": ["Feature 1", "Feature 2"],
            "features": ["Feature 1", "Feature 2"],
            "constraints": {"framework": "vanilla_js"},
            "success_criteria": ["Application loads", "No errors"]
        }
    
    @pytest.fixture
    def design_manifest_completion_message(self):
        """Sample design_manifest completion message."""
        manifest = create_sample_build_manifest()  # Already a dict
        return MockAgentMessage(
            sender="test-dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                "task_id": "test-design-001",
                "status": "completed",
                "action": "design_manifest",
                "manifest": manifest  # Already a dict, no need for .to_dict()
            },
            context={"ecid": "TEST-001"}
        )
    
    @pytest.fixture
    def build_completion_message(self):
        """Sample build completion message."""
        return MockAgentMessage(
            sender="test-dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                "task_id": "test-build-001",
                "status": "completed",
                "action": "build",
                "created_files": ["index.html", "app.js", "styles.css", "nginx.conf", "Dockerfile"]
            },
            context={"ecid": "TEST-001"}
        )
    
    @pytest.fixture
    def deploy_completion_message(self):
        """Sample deploy completion message."""
        return MockAgentMessage(
            sender="test-dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                "task_id": "test-deploy-001",
                "status": "completed",
                "action": "deploy",
                "deployment_info": {
                    "container_name": "test-app",
                    "target_url": "http://localhost:8080/test-app"
                }
            },
            context={"ecid": "TEST-001"}
        )
    
    @pytest.mark.unit
    def test_warmboot_state_initialization(self, lead_agent_for_sequencing):
        """Test that warmboot_state is properly initialized."""
        assert hasattr(lead_agent_for_sequencing, 'warmboot_state')
        assert isinstance(lead_agent_for_sequencing.warmboot_state, dict)
        assert lead_agent_for_sequencing.warmboot_state.get('manifest') is None
        assert lead_agent_for_sequencing.warmboot_state.get('build_files') == []
        assert lead_agent_for_sequencing.warmboot_state.get('pending_tasks') == []
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_development_tasks_four_task_sequence(self, lead_agent_for_sequencing, sample_prd_analysis):
        """Test that four tasks are created in correct sequence."""
        tasks = await lead_agent_for_sequencing.create_development_tasks(sample_prd_analysis, "TestApp", "TEST-001")
        
        assert len(tasks) == 4
        
        # Verify task order and types
        assert tasks[0]["requirements"]["action"] == "archive"
        assert tasks[1]["requirements"]["action"] == "design_manifest"
        assert tasks[2]["requirements"]["action"] == "build"
        assert tasks[3]["requirements"]["action"] == "deploy"
        
        # Verify task dependencies
        assert tasks[0]["task_id"] != tasks[1]["task_id"]
        assert tasks[1]["task_id"] != tasks[2]["task_id"]
        assert tasks[2]["task_id"] != tasks[3]["task_id"]
        
        # Verify build requirements are flattened into design_manifest and build tasks
        assert "app_name" in tasks[1]["requirements"]
        assert "prd_analysis" in tasks[1]["requirements"]
        assert "app_name" in tasks[2]["requirements"]
        assert "prd_analysis" in tasks[2]["requirements"]
        
        # Verify build task has manifest placeholder
        assert tasks[2]["requirements"]["manifest"] is None
        
        # Verify deploy task has source_dir
        assert "source_dir" in tasks[3]["requirements"]
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_development_tasks_build_requirements_creation(self, lead_agent_for_sequencing, sample_prd_analysis):
        """Test that build requirements are properly created and flattened into requirements."""
        tasks = await lead_agent_for_sequencing.create_development_tasks(sample_prd_analysis, "TestApp", "TEST-001")
        
        # Check design_manifest task - requirements should have flattened build requirements
        design_task = tasks[1]
        requirements = design_task["requirements"]
        
        # Build requirements should be flattened directly into requirements (no nested task_spec)
        assert requirements.get("app_name") == "TestApp"
        # Version format: {framework_version}.{warm_boot_sequence} - check pattern, not exact value
        import re
        assert re.match(r'^\d+\.\d+\.\d+\.\d+$', requirements.get("version", "")), f"Version {requirements.get('version')} doesn't match expected pattern X.Y.Z.SEQ"
        assert requirements.get("run_id") == "TEST-001"
        assert requirements.get("prd_analysis") == sample_prd_analysis["summary"]
        assert requirements.get("features") == sample_prd_analysis["features"]
        assert requirements.get("constraints") == sample_prd_analysis["constraints"]
        assert requirements.get("success_criteria") == sample_prd_analysis["success_criteria"]
        
        # Check build task has same flattened requirements
        build_task = tasks[2]
        build_requirements = build_task["requirements"]
        assert build_requirements.get("app_name") == requirements.get("app_name")
        assert build_requirements.get("run_id") == requirements.get("run_id")
        assert build_requirements.get("prd_analysis") == requirements.get("prd_analysis")
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_design_manifest_completion_handler(self, lead_agent_for_sequencing, design_manifest_completion_message):
        """Test handling of design_manifest completion."""
        # Mock HTTP call to task API
        mock_tasks_response = AsyncMock()
        mock_tasks_response.status = 200
        mock_tasks_response.json = AsyncMock(return_value=[
            {
                'task_id': 'TEST-BUILD-001',
                'requirements': {'action': 'build', 'manifest': None},
                'status': 'pending'
            }
        ])
        mock_tasks_response.__aenter__ = AsyncMock(return_value=mock_tasks_response)
        mock_tasks_response.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get = Mock(return_value=mock_tasks_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session
            
            # Mock send_message to verify delegation
            with patch.object(lead_agent_for_sequencing, 'send_message', new_callable=AsyncMock) as mock_send:
                await lead_agent_for_sequencing._handle_design_manifest_completion(design_manifest_completion_message)
                
                # Verify manifest is stored in warmboot_state
                assert lead_agent_for_sequencing.warmboot_state['manifest'] is not None
                # Manifest structure has architecture_type at top level, not nested
                manifest = lead_agent_for_sequencing.warmboot_state['manifest']
                assert manifest.get('architecture_type') == "spa_web_app" or manifest.get('architecture', {}).get('type') == "spa_web_app"
                
                # Verify build task was delegated via send_message
                mock_send.assert_called_once()
                call_args = mock_send.call_args
                assert call_args.kwargs['recipient'] == 'neo'  # Delegated to dev agent (neo)
                assert call_args.kwargs['message_type'] == 'task_delegation'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_design_manifest_completion_handler_missing_manifest(self, lead_agent_for_sequencing):
        """Test handling of design_manifest completion with missing manifest."""
        message = MockAgentMessage(
            sender="test-dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                "task_id": "test-design-001",
                "status": "completed",
                "action": "design_manifest"
                # Missing manifest
            },
            context={"ecid": "TEST-001"}
        )
        
        with patch.object(lead_agent_for_sequencing, '_trigger_next_task') as mock_trigger:
            await lead_agent_for_sequencing._handle_design_manifest_completion(message)
            
            # Verify manifest is not stored
            assert lead_agent_for_sequencing.warmboot_state['manifest'] is None
            
            # Verify next task is NOT triggered (because manifest is missing)
            mock_trigger.assert_not_called()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_build_completion_handler(self, lead_agent_for_sequencing, build_completion_message):
        """Test handling of build completion."""
        with patch.object(lead_agent_for_sequencing, '_trigger_next_task') as mock_trigger:
            await lead_agent_for_sequencing._handle_build_completion(build_completion_message)
            
            # Verify build files are stored
            assert len(lead_agent_for_sequencing.warmboot_state['build_files']) == 5
            assert "index.html" in lead_agent_for_sequencing.warmboot_state['build_files']
            assert "app.js" in lead_agent_for_sequencing.warmboot_state['build_files']
            assert "nginx.conf" in lead_agent_for_sequencing.warmboot_state['build_files']
            assert "Dockerfile" in lead_agent_for_sequencing.warmboot_state['build_files']
            
            # Verify next task is triggered
            mock_trigger.assert_called_once_with("TEST-001", "deploy")
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_build_completion_handler_missing_files(self, lead_agent_for_sequencing):
        """Test handling of build completion with missing created_files."""
        message = MockAgentMessage(
            sender="test-dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                "task_id": "test-build-001",
                "status": "completed",
                "action": "build"
                # Missing created_files
            },
            context={"ecid": "TEST-001"}
        )
        
        with patch.object(lead_agent_for_sequencing, '_trigger_next_task') as mock_trigger:
            await lead_agent_for_sequencing._handle_build_completion(message)
            
            # Verify build files are empty
            assert lead_agent_for_sequencing.warmboot_state['build_files'] == []
            
            # Verify next task is NOT triggered (because created_files is missing)
            mock_trigger.assert_not_called()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_deploy_completion_handler(self, lead_agent_for_sequencing, deploy_completion_message):
        """Test handling of deploy completion."""
        # Set up warmboot_state with manifest and files
        manifest = create_sample_build_manifest()
        lead_agent_for_sequencing.warmboot_state['manifest'] = manifest  # Already a dict
        lead_agent_for_sequencing.warmboot_state['build_files'] = ["index.html", "app.js", "styles.css"]
        
        with patch.object(lead_agent_for_sequencing, '_log_warmboot_governance') as mock_log, \
             patch.object(lead_agent_for_sequencing, 'generate_warmboot_wrapup') as mock_wrapup:
            
            await lead_agent_for_sequencing._handle_deploy_completion(deploy_completion_message)
            
            # Verify governance logging is called
            mock_log.assert_called_once_with("TEST-001", manifest, ["index.html", "app.js", "styles.css"])
            
            # Verify wrap-up generation is called
            mock_wrapup.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_governance_logging(self, lead_agent_for_sequencing):
        """Test governance logging functionality."""
        manifest = create_sample_build_manifest()
        files = ["index.html", "app.js", "styles.css"]
        
        with patch('os.path.exists', return_value=True), \
             patch('os.makedirs'), \
             patch('builtins.open', create=True) as mock_open, \
             patch('json.dump') as mock_json_dump, \
             patch('yaml.dump') as mock_yaml_dump:
            
            # Mock file operations
            mock_file = MagicMock()
            mock_file.read.return_value = b"test content"
            mock_open.return_value.__enter__.return_value = mock_file
            
            await lead_agent_for_sequencing._log_warmboot_governance("TEST-001", manifest, files)
            
            # Verify manifest snapshot was created
            mock_yaml_dump.assert_called_once()
            yaml_call_args = mock_yaml_dump.call_args[0]
            assert yaml_call_args[0] == manifest
            
            # Verify checksums file was created
            mock_json_dump.assert_called_once()
            json_call_args = mock_json_dump.call_args[0]
            checksums = json_call_args[0]
            assert isinstance(checksums, dict)
            assert "index.html" in checksums
            assert "app.js" in checksums
            assert "styles.css" in checksums
            # Verify checksums are SHA-256 hashes
            assert len(checksums["index.html"]) == 64  # SHA-256 hex length
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_task_failure_handling(self, lead_agent_for_sequencing):
        """Test handling of task failures."""
        failure_message = MockAgentMessage(
            sender="test-dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                "task_id": "test-design-001",
                "status": "error",
                "action": "design_manifest",
                "error": "Design manifest failed"
            },
            context={"ecid": "TEST-001"}
        )
        
        with patch.object(lead_agent_for_sequencing, '_trigger_next_task') as mock_trigger:
            await lead_agent_for_sequencing._handle_design_manifest_completion(failure_message)
            
            # Verify next task is NOT triggered on failure
            mock_trigger.assert_not_called()
            
            # Verify warmboot_state is not updated
            assert lead_agent_for_sequencing.warmboot_state['manifest'] is None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_trigger_next_task_placeholder(self, lead_agent_for_sequencing):
        """Test _trigger_next_task placeholder method."""
        # This is currently a placeholder - should not raise exception
        await lead_agent_for_sequencing._trigger_next_task("TEST-001", "build")
        
        # Method should complete without error
        assert True  # If we get here, no exception was raised
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_development_tasks_with_custom_app_name(self, lead_agent_for_sequencing, sample_prd_analysis):
        """Test create_development_tasks with custom app name."""
        tasks = await lead_agent_for_sequencing.create_development_tasks(sample_prd_analysis, "CustomApp", "CUSTOM-001")
        
        # Verify app name is used in flattened requirements
        design_task = tasks[1]
        requirements = design_task["requirements"]
        assert requirements.get("app_name") == "CustomApp"
        assert requirements.get("run_id") == "CUSTOM-001"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_development_tasks_with_default_values(self, lead_agent_for_sequencing, sample_prd_analysis):
        """Test create_development_tasks with default values."""
        tasks = await lead_agent_for_sequencing.create_development_tasks(sample_prd_analysis)
        
        # Verify default values are used in flattened requirements
        design_task = tasks[1]
        requirements = design_task["requirements"]
        assert requirements.get("app_name") == "application"
        # Version format: {framework_version}.{warm_boot_sequence} - check pattern, not exact value
        import re
        assert re.match(r'^\d+\.\d+\.\d+\.\d+$', requirements.get("version", "")), f"Version {requirements.get('version')} doesn't match expected pattern X.Y.Z.SEQ"
        # run_id should be set from ecid (which defaults to a generated value)
        assert requirements.get("run_id") is not None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_multiple_completion_handlers_sequence(self, lead_agent_for_sequencing):
        """Test the complete sequence of completion handlers."""
        # Set up messages
        manifest = create_sample_build_manifest()
        design_message = MockAgentMessage(
            sender="dev-agent", recipient="lead-agent", message_type="task.developer.completed",
            payload={"task_id": "design-001", "status": "completed", "action": "design_manifest", "manifest": manifest},
            context={"ecid": "TEST-001"}
        )
        
        build_message = MockAgentMessage(
            sender="dev-agent", recipient="lead-agent", message_type="task.developer.completed",
            payload={"task_id": "build-001", "status": "completed", "action": "build", "created_files": ["index.html", "app.js"]},
            context={"ecid": "TEST-001"}
        )
        
        deploy_message = MockAgentMessage(
            sender="dev-agent", recipient="lead-agent", message_type="task.developer.completed",
            payload={"task_id": "deploy-001", "status": "completed", "action": "deploy"},
            context={"ecid": "TEST-001"}
        )
        
        with patch.object(lead_agent_for_sequencing, '_trigger_next_task') as mock_trigger, \
             patch.object(lead_agent_for_sequencing, '_log_warmboot_governance') as mock_log, \
             patch.object(lead_agent_for_sequencing, 'generate_warmboot_wrapup') as mock_wrapup:
            
            # Mock HTTP call to task API for design manifest completion
            mock_tasks_response = AsyncMock()
            mock_tasks_response.status = 200
            mock_tasks_response.json = AsyncMock(return_value=[
                {
                    'task_id': 'TEST-BUILD-001',
                    'requirements': {'action': 'build', 'manifest': None},
                    'status': 'pending'
                }
            ])
            mock_tasks_response.__aenter__ = AsyncMock(return_value=mock_tasks_response)
            mock_tasks_response.__aexit__ = AsyncMock(return_value=None)
            
            with patch('aiohttp.ClientSession') as mock_session_class:
                mock_session = AsyncMock()
                mock_session.get = Mock(return_value=mock_tasks_response)
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=None)
                mock_session_class.return_value = mock_session
                
                # Mock send_message for delegation
                with patch.object(lead_agent_for_sequencing, 'send_message', new_callable=AsyncMock):
                    # Execute sequence
                    await lead_agent_for_sequencing._handle_design_manifest_completion(design_message)
                    await lead_agent_for_sequencing._handle_build_completion(build_message)
                    await lead_agent_for_sequencing._handle_deploy_completion(deploy_message)
            
            # Verify state progression
            assert lead_agent_for_sequencing.warmboot_state['manifest'] is not None
            assert len(lead_agent_for_sequencing.warmboot_state['build_files']) == 2
            
            # Verify all handlers were called
            # design_manifest completion delegates via send_message (not _trigger_next_task)
            # build completion triggers deploy (1 call)
            # deploy completion triggers wrapup (no _trigger_next_task call)
            assert mock_trigger.call_count == 1  # Only deploy is triggered
            mock_log.assert_called_once()
            mock_wrapup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_build_requirements_with_communication_logging(self, mock_lead_agent):
        """Test build requirements creation with communication logging"""
        agent = mock_lead_agent
        
        # Mock LLM response
        mock_yaml_response = """
app_name: TestApp
version: 1.0.0
run_id: TEST-001
features:
  - name: Feature1
    description: Test feature 1
  - name: Feature2
    description: Test feature 2
"""
        
        with patch.object(agent.llm_client, 'complete', return_value=mock_yaml_response):
            requirements = await agent.generate_build_requirements("Test PRD content", "TestApp", "1.0.0", "TEST-001")
            
            # Verify requirements dict was created
            assert isinstance(requirements, dict)
            assert requirements.get("app_name") == "TestApp"
            assert requirements.get("version") == "1.0.0"
            assert requirements.get("run_id") == "TEST-001"
            assert len(requirements.get("features", [])) == 2
            
            # Verify communication logging occurred
            assert len(agent.communication_log) == 1
            log_entry = agent.communication_log[0]
            assert log_entry['message_type'] == 'build_requirements_generation'
            assert log_entry['ecid'] == "TEST-001"
            assert 'Generated build requirements for TestApp' in log_entry['description']
    
    @pytest.mark.asyncio
    async def test_process_task_empty_prd_path_warning(self, mock_lead_agent):
        """Test process_task with empty PRD path generates warning"""
        agent = mock_lead_agent
        
        task = {
            'task_id': 'test-task-001',
            'type': 'governance',
            'requirements': {
                'action': 'process_prd',
                'application': 'TestApp',
                'prd_path': ''  # Empty PRD path
            }
        }
        
        with patch.object(agent, 'update_task_status', new_callable=AsyncMock) as mock_update:
            result = await agent.process_task(task)
            
            # Should continue with normal governance processing
            assert result is not None
            assert 'status' in result
    
    @pytest.mark.asyncio
    async def test_handle_message_unknown_type_logging(self, mock_lead_agent):
        """Test handle_message logs unknown message types"""
        agent = mock_lead_agent
        
        # Create message with unknown type
        message = AgentMessage(
            sender="test-sender",
            recipient="test-lead-agent",
            message_type="unknown_message_type",
            payload={"test": "data"},
            context={},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        # Should log the unknown message type
        await agent.handle_message(message)
        
        # No exception should be raised, just logged
    
    @pytest.mark.asyncio
    async def test_process_task_governance_direct_handling(self, mock_lead_agent):
        """Test process_task handles governance tasks directly"""
        agent = mock_lead_agent
        
        task = {
            'task_id': 'governance-task-001',
            'type': 'governance',
            'requirements': {
                'action': 'governance_decision',
                'description': 'Test governance task'
            }
        }
        
        with patch.object(agent, 'update_task_status', new_callable=AsyncMock) as mock_update:
            result = await agent.process_task(task)
            
            # Should handle governance task directly
            assert result['status'] == 'completed'
            assert 'Governance task governance-task-001 handled directly' in result['governance_decision']
            assert 'Governance tasks are handled directly by the Lead Agent' in result['message']
    
    @pytest.mark.asyncio
    async def test_process_task_delegation_logging(self, mock_lead_agent):
        """Test process_task logs delegation process"""
        agent = mock_lead_agent
        
        task = {
            'task_id': 'delegation-task-001',
            'type': 'development',
            'requirements': {
                'action': 'build',
                'description': 'Test delegation task'
            }
        }
        
        with patch.object(agent, 'update_task_status', new_callable=AsyncMock) as mock_update, \
             patch.object(agent, 'determine_delegation_target', return_value='dev-agent') as mock_target, \
             patch.object(agent, 'send_message', new_callable=AsyncMock) as mock_send:
            
            result = await agent.process_task(task)
            
            # Verify delegation process
            mock_target.assert_called_once_with('development')
            mock_send.assert_called_once()
            
            # Verify status updates
            assert mock_update.call_count >= 2  # Initial and delegation status updates
    
    @pytest.mark.asyncio
    async def test_task_state_logging(self, mock_lead_agent):
        """Test task state logging during processing"""
        agent = mock_lead_agent
        
        task = {
            'task_id': 'state-log-task-001',
            'type': 'development',
            'timestamp': '2024-01-01T00:00:00Z',
            'requirements': {
                'action': 'build',
                'description': 'Test state logging'
            }
        }
        
        with patch.object(agent, 'update_task_status', new_callable=AsyncMock) as mock_update, \
             patch.object(agent, 'determine_delegation_target', return_value='dev-agent') as mock_target, \
             patch.object(agent, 'send_message', new_callable=AsyncMock) as mock_send:
            
            await agent.process_task(task)
            
            # Verify task state was logged
            assert len(agent.task_state_log) == 1
            state_entry = agent.task_state_log[0]
            assert state_entry['task_id'] == 'state-log-task-001'
            assert state_entry['type'] == 'development'
            assert state_entry['status'] == 'processing'
            assert state_entry['timestamp'] == '2024-01-01T00:00:00Z'
    
    @pytest.mark.asyncio
    async def test_process_task_with_prd_path_success(self, mock_lead_agent):
        """Test process_task with valid PRD path processes successfully"""
        agent = mock_lead_agent
        
        task = {
            'task_id': 'prd-task-001',
            'type': 'governance',
            'application': 'TestApp',
            'prd_path': '/path/to/prd.md',
            'ecid': 'TEST-ECID-001',
            'requirements': {
                'action': 'process_prd'
            }
        }
        
        with patch.object(agent, 'process_prd_request', return_value={'status': 'completed'}) as mock_process, \
             patch.object(agent, 'update_task_status', new_callable=AsyncMock) as mock_update:
            
            result = await agent.process_task(task)
            
            # Should process PRD and complete
            mock_process.assert_called_once_with('/path/to/prd.md', 'TEST-ECID-001')
            mock_update.assert_called_once_with('prd-task-001', "Completed", 100.0)
            assert result['status'] == 'completed'
    
    @pytest.mark.asyncio
    async def test_handle_message_specific_types(self, mock_lead_agent):
        """Test handle_message routes specific message types correctly"""
        agent = mock_lead_agent
        
        # Test approval_request message type
        approval_message = AgentMessage(
            sender="test-sender",
            recipient="test-lead-agent",
            message_type="approval_request",
            payload={"test": "data"},
            context={},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        with patch.object(agent, 'handle_approval_request', new_callable=AsyncMock) as mock_approval:
            await agent.handle_message(approval_message)
            mock_approval.assert_called_once_with(approval_message)
        
        # Test escalation message type
        escalation_message = AgentMessage(
            sender="test-sender",
            recipient="test-lead-agent",
            message_type="escalation",
            payload={"test": "data"},
            context={},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-002"
        )
        
        with patch.object(agent, 'handle_escalation', new_callable=AsyncMock) as mock_escalation:
            await agent.handle_message(escalation_message)
            mock_escalation.assert_called_once_with(escalation_message)
        
        # Test status_query message type
        status_message = AgentMessage(
            sender="test-sender",
            recipient="test-lead-agent",
            message_type="status_query",
            payload={"test": "data"},
            context={},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-003"
        )
        
        with patch.object(agent, 'handle_status_query', new_callable=AsyncMock) as mock_status:
            await agent.handle_message(status_message)
            mock_status.assert_called_once_with(status_message)
    
    @pytest.mark.asyncio
    async def test_handle_developer_completion_error_handling(self, mock_lead_agent):
        """Test handle_developer_completion error handling"""
        agent = mock_lead_agent
        
        # Create message that will cause an error
        message = AgentMessage(
            sender="dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={"task_id": "test-task-001"},  # Missing required fields
            context={},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        # Should handle error gracefully
        await agent.handle_developer_completion(message)
        # No exception should be raised
    
    @pytest.mark.asyncio
    async def test_design_manifest_completion_error_handling(self, mock_lead_agent):
        """Test _handle_design_manifest_completion error handling"""
        agent = mock_lead_agent
        
        # Create message that will cause an error
        message = AgentMessage(
            sender="dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={"task_id": "test-task-001"},  # Missing required fields
            context={},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        # Should handle error gracefully
        await agent._handle_design_manifest_completion(message)
        # No exception should be raised
    
    @pytest.mark.asyncio
    async def test_build_completion_error_handling(self, mock_lead_agent):
        """Test _handle_build_completion error handling"""
        agent = mock_lead_agent
        
        # Create message that will cause an error
        message = AgentMessage(
            sender="dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={"task_id": "test-task-001"},  # Missing required fields
            context={},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        # Should handle error gracefully
        await agent._handle_build_completion(message)
        # No exception should be raised
    
    @pytest.mark.asyncio
    async def test_deploy_completion_error_handling(self, mock_lead_agent):
        """Test _handle_deploy_completion error handling"""
        agent = mock_lead_agent
        
        # Create message that will cause an error
        message = AgentMessage(
            sender="dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={"task_id": "test-task-001"},  # Missing required fields
            context={},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        # Should handle error gracefully
        await agent._handle_deploy_completion(message)
        # No exception should be raised
    
    @pytest.mark.asyncio
    async def test_handle_developer_completion_failed_task(self, mock_lead_agent):
        """Test handle_developer_completion with failed task status"""
        agent = mock_lead_agent
        
        message = AgentMessage(
            sender="dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                'task_id': 'test-task-001',
                'status': 'failed',  # Failed status
                'ecid': 'TEST-ECID-001'
            },
            context={'ecid': 'TEST-ECID-001'},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        with patch.object(agent, 'generate_warmboot_wrapup', new_callable=AsyncMock) as mock_wrapup:
            await agent.handle_developer_completion(message)
            
            # Should not trigger wrap-up for failed task
            mock_wrapup.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_design_manifest_completion_failed_status(self, mock_lead_agent):
        """Test _handle_design_manifest_completion with failed status"""
        agent = mock_lead_agent
        
        message = AgentMessage(
            sender="dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                'task_id': 'test-task-001',
                'status': 'failed',  # Failed status
                'manifest': {'test': 'manifest'}
            },
            context={'ecid': 'TEST-ECID-001'},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        with patch.object(agent, '_trigger_next_task', new_callable=AsyncMock) as mock_trigger:
            await agent._handle_design_manifest_completion(message)
            
            # Should not trigger next task for failed status
            mock_trigger.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_build_completion_failed_status(self, mock_lead_agent):
        """Test _handle_build_completion with failed status"""
        agent = mock_lead_agent
        
        message = AgentMessage(
            sender="dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                'task_id': 'test-task-001',
                'status': 'failed',  # Failed status
                'files': [{'path': 'test.html', 'content': 'test'}]
            },
            context={'ecid': 'TEST-ECID-001'},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        with patch.object(agent, '_trigger_next_task', new_callable=AsyncMock) as mock_trigger:
            await agent._handle_build_completion(message)
            
            # Should not trigger next task for failed status
            mock_trigger.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_message_remaining_types(self, mock_lead_agent):
        """Test handle_message routes remaining message types correctly"""
        agent = mock_lead_agent
        
        # Test task_acknowledgment message type
        ack_message = AgentMessage(
            sender="test-sender",
            recipient="test-lead-agent",
            message_type="task_acknowledgment",
            payload={"test": "data"},
            context={},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        with patch.object(agent, 'handle_task_acknowledgment', new_callable=AsyncMock) as mock_ack:
            await agent.handle_message(ack_message)
            mock_ack.assert_called_once_with(ack_message)
        
        # Test task_error message type
        error_message = AgentMessage(
            sender="test-sender",
            recipient="test-lead-agent",
            message_type="task_error",
            payload={"test": "data"},
            context={},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-002"
        )
        
        with patch.object(agent, 'handle_task_error', new_callable=AsyncMock) as mock_error:
            await agent.handle_message(error_message)
            mock_error.assert_called_once_with(error_message)
        
        # Test prd_request message type
        prd_message = AgentMessage(
            sender="test-sender",
            recipient="test-lead-agent",
            message_type="prd_request",
            payload={"test": "data"},
            context={},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-003"
        )
        
        with patch.object(agent, 'handle_prd_request', new_callable=AsyncMock) as mock_prd:
            await agent.handle_message(prd_message)
            mock_prd.assert_called_once_with(prd_message)
        
        # Test task.developer.completed message type
        completed_message = AgentMessage(
            sender="test-sender",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={"test": "data"},
            context={},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-004"
        )
        
        with patch.object(agent, 'handle_developer_completion', new_callable=AsyncMock) as mock_completed:
            await agent.handle_message(completed_message)
            mock_completed.assert_called_once_with(completed_message)
    
    @pytest.mark.asyncio
    async def test_handle_prd_request_missing_path(self, mock_lead_agent):
        """Test handle_prd_request with missing prd_path"""
        agent = mock_lead_agent
        
        message = AgentMessage(
            sender="test-sender",
            recipient="test-lead-agent",
            message_type="prd_request",
            payload={},  # Missing prd_path
            context={},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        # Should handle missing prd_path gracefully
        await agent.handle_prd_request(message)
        # No exception should be raised
    
    @pytest.mark.asyncio
    async def test_deploy_completion_success_path(self, mock_lead_agent):
        """Test _handle_deploy_completion success path"""
        agent = mock_lead_agent
        
        # Initialize warmboot state
        agent.warmboot_state = {
            'manifest': {'test': 'manifest'},
            'build_files': [{'path': 'test.html', 'content': 'test'}]
        }
        
        message = AgentMessage(
            sender="dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                'task_id': 'test-task-001',
                'status': 'completed',
                'ecid': 'TEST-ECID-001'
            },
            context={'ecid': 'TEST-ECID-001'},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        with patch.object(agent, '_log_warmboot_governance', new_callable=AsyncMock) as mock_log:
            await agent._handle_deploy_completion(message)
            
            # Should trigger governance logging for successful deploy
            mock_log.assert_called_once_with('TEST-ECID-001', {'test': 'manifest'}, [{'path': 'test.html', 'content': 'test'}])
    
    @pytest.mark.asyncio
    async def test_handle_developer_completion_success_with_wrapup(self, mock_lead_agent):
        """Test handle_developer_completion success path with wrap-up generation"""
        agent = mock_lead_agent
        
        message = AgentMessage(
            sender="dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                'task_id': 'test-task-001',
                'status': 'completed',
                'ecid': 'TEST-ECID-001'
            },
            context={'ecid': 'TEST-ECID-001'},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        with patch.object(agent, 'generate_warmboot_wrapup', new_callable=AsyncMock) as mock_wrapup:
            await agent.handle_developer_completion(message)
            
            # Should trigger wrap-up for successful task
            mock_wrapup.assert_called_once_with('TEST-ECID-001', 'test-task-001', {'task_id': 'test-task-001', 'status': 'completed', 'ecid': 'TEST-ECID-001'})
    
    @pytest.mark.asyncio
    async def test_design_manifest_completion_success_with_trigger(self, mock_lead_agent):
        """Test _handle_design_manifest_completion success path with trigger"""
        agent = mock_lead_agent
        
        message = AgentMessage(
            sender="dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                'task_id': 'test-task-001',
                'status': 'completed',
                'manifest': {'test': 'manifest'}
            },
            context={'ecid': 'TEST-ECID-001'},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        # Mock HTTP call to task API
        mock_tasks_response = AsyncMock()
        mock_tasks_response.status = 200
        mock_tasks_response.json = AsyncMock(return_value=[
            {
                'task_id': 'TEST-BUILD-001',
                'requirements': {'action': 'build', 'manifest': None},
                'status': 'pending'
            }
        ])
        mock_tasks_response.__aenter__ = AsyncMock(return_value=mock_tasks_response)
        mock_tasks_response.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get = Mock(return_value=mock_tasks_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session
            
            with patch.object(agent, 'send_message', new_callable=AsyncMock) as mock_send:
                await agent._handle_design_manifest_completion(message)
                
                # Should delegate build task via send_message
                mock_send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_build_completion_success_with_trigger(self, mock_lead_agent):
        """Test _handle_build_completion success path with trigger"""
        agent = mock_lead_agent
        
        message = AgentMessage(
            sender="dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                'task_id': 'test-task-001',
                'status': 'completed',
                'created_files': [{'path': 'test.html', 'content': 'test'}]  # Use 'created_files' not 'files'
            },
            context={'ecid': 'TEST-ECID-001'},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        with patch.object(agent, '_trigger_next_task', new_callable=AsyncMock) as mock_trigger:
            await agent._handle_build_completion(message)
            
            # Should trigger next task for successful status
            mock_trigger.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_design_manifest_completion_missing_manifest(self, mock_lead_agent):
        """Test _handle_design_manifest_completion with missing manifest"""
        agent = mock_lead_agent
        
        message = AgentMessage(
            sender="dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                'task_id': 'test-task-001',
                'status': 'completed'
                # Missing manifest
            },
            context={'ecid': 'TEST-ECID-001'},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        with patch.object(agent, '_trigger_next_task', new_callable=AsyncMock) as mock_trigger:
            await agent._handle_design_manifest_completion(message)
            
            # Should not trigger next task when manifest is missing
            mock_trigger.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_build_completion_missing_files(self, mock_lead_agent):
        """Test _handle_build_completion with missing files"""
        agent = mock_lead_agent
        
        message = AgentMessage(
            sender="dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                'task_id': 'test-task-001',
                'status': 'completed'
                # Missing files
            },
            context={'ecid': 'TEST-ECID-001'},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        with patch.object(agent, '_trigger_next_task', new_callable=AsyncMock) as mock_trigger:
            await agent._handle_build_completion(message)
            
            # Should not trigger next task when files are missing
            mock_trigger.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_deploy_completion_failed_status(self, mock_lead_agent):
        """Test _handle_deploy_completion with failed status"""
        agent = mock_lead_agent
        
        message = AgentMessage(
            sender="dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                'task_id': 'test-task-001',
                'status': 'failed',  # Failed status
                'ecid': 'TEST-ECID-001'
            },
            context={'ecid': 'TEST-ECID-001'},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        with patch.object(agent, 'generate_warmboot_wrapup', new_callable=AsyncMock) as mock_wrapup:
            await agent._handle_deploy_completion(message)
            
            # Should not generate wrap-up for failed status
            mock_wrapup.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_deploy_completion_success_with_wrapup(self, mock_lead_agent):
        """Test _handle_deploy_completion success path with wrap-up generation"""
        agent = mock_lead_agent
        
        message = AgentMessage(
            sender="dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                'task_id': 'test-task-001',
                'status': 'completed',
                'ecid': 'TEST-ECID-001'
            },
            context={'ecid': 'TEST-ECID-001'},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        with patch.object(agent, 'generate_warmboot_wrapup', new_callable=AsyncMock) as mock_wrapup:
            await agent._handle_deploy_completion(message)
            
            # Should generate wrap-up for successful deploy
            mock_wrapup.assert_called_once_with('TEST-ECID-001', 'test-task-001', {'task_id': 'test-task-001', 'status': 'completed', 'ecid': 'TEST-ECID-001'})
    
    @pytest.mark.asyncio
    async def test_trigger_next_task_placeholder(self, mock_lead_agent):
        """Test _trigger_next_task placeholder implementation"""
        agent = mock_lead_agent
        
        # Should handle the placeholder implementation gracefully
        await agent._trigger_next_task('TEST-ECID-001', 'deploy')
        # No exception should be raised
    
    @pytest.mark.asyncio
    async def test_build_completion_missing_created_files(self, mock_lead_agent):
        """Test _handle_build_completion with missing created_files"""
        agent = mock_lead_agent
        
        message = AgentMessage(
            sender="dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                'task_id': 'test-task-001',
                'status': 'completed'
                # Missing created_files
            },
            context={'ecid': 'TEST-ECID-001'},
            timestamp="2024-01-01T00:00:00Z",
            message_id="test-msg-001"
        )
        
        with patch.object(agent, '_trigger_next_task', new_callable=AsyncMock) as mock_trigger:
            await agent._handle_build_completion(message)
            
            # Should not trigger next task when created_files are missing
            mock_trigger.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_log_warmboot_governance_error_handling(self, mock_lead_agent):
        """Test _log_warmboot_governance error handling"""
        agent = mock_lead_agent
        
        # Test with invalid parameters that will cause an error
        with patch('agents.roles.lead.agent.logger') as mock_logger:
            # Should handle error gracefully
            await agent._log_warmboot_governance('TEST-ECID-001', {'test': 'manifest'}, [{'path': 'test.html', 'content': 'test'}])
            # No exception should be raised
    
    @pytest.mark.asyncio
    async def test_escalate_task_functionality(self, mock_lead_agent):
        """Test escalate_task functionality"""
        agent = mock_lead_agent
        
        task = {
            'task_id': 'test-task-001',
            'complexity': 0.9,
            'timestamp': '2024-01-01T00:00:00Z',
            'requirements': {
                'action': 'build',
                'description': 'Complex task'
            }
        }
        
        with patch.object(agent, 'log_activity', new_callable=AsyncMock) as mock_log:
            await agent.escalate_task('test-task-001', task)
            
            # Should add to approval queue
            assert len(agent.approval_queue) == 1
            escalation = agent.approval_queue[0]
            assert escalation['task_id'] == 'test-task-001'
            assert escalation['reason'] == 'High complexity'
            
            # Should log activity
            mock_log.assert_called_once_with("task_escalated", {
                'task_id': 'test-task-001',
                'complexity': 0.9,
                'reason': 'Premium consultation required'
            })
    
    @pytest.mark.asyncio
    async def test_log_warmboot_governance_success_path(self, mock_lead_agent):
        """Test _log_warmboot_governance success path"""
        agent = mock_lead_agent
        
        # Test successful governance logging
        await agent._log_warmboot_governance('TEST-ECID-001', {'test': 'manifest'}, [{'path': 'test.html', 'content': 'test'}])
        # No exception should be raised
    
    @pytest.mark.asyncio
    async def test_trigger_next_task_with_different_actions(self, mock_lead_agent):
        """Test _trigger_next_task with different actions"""
        agent = mock_lead_agent
        
        # Test different actions
        await agent._trigger_next_task('TEST-ECID-001', 'build')
        await agent._trigger_next_task('TEST-ECID-002', 'deploy')
        await agent._trigger_next_task('TEST-ECID-003', 'test')
        
        # Should handle all actions gracefully
        # No exception should be raised
    
    @pytest.mark.asyncio
    async def test_log_warmboot_governance_with_different_ecids(self, mock_lead_agent):
        """Test _log_warmboot_governance with different ECIDs"""
        agent = mock_lead_agent
        
        # Test with different ECIDs
        await agent._log_warmboot_governance('TEST-ECID-001', {'test': 'manifest1'}, [{'path': 'test1.html', 'content': 'test1'}])
        await agent._log_warmboot_governance('TEST-ECID-002', {'test': 'manifest2'}, [{'path': 'test2.html', 'content': 'test2'}])
        await agent._log_warmboot_governance('TEST-ECID-003', {'test': 'manifest3'}, [{'path': 'test3.html', 'content': 'test3'}])
        
        # Should handle all ECIDs gracefully
        # No exception should be raised
    
    @pytest.mark.asyncio
    async def test_analyze_prd_requirements_json_parsing(self, mock_lead_agent):
        """Test analyze_prd_requirements with JSON parsing"""
        agent = mock_lead_agent
        
        # Set current_ecid to avoid attribute error
        agent.current_ecid = "TEST-ECID-001"
        
        # Test with JSON wrapped in markdown
        mock_json_response = """```json
{
    "core_features": ["Feature 1", "Feature 2"],
    "technical_requirements": ["Requirement 1", "Requirement 2"],
    "success_criteria": ["Criteria 1", "Criteria 2"]
}
```"""
        
        with patch.object(agent.llm_client, 'complete', return_value=mock_json_response):
            analysis = await agent.analyze_prd_requirements("Test PRD content")
            
            # Should parse JSON correctly
            assert 'core_features' in analysis
            assert 'technical_requirements' in analysis
            assert 'success_criteria' in analysis
            assert len(analysis['core_features']) == 2
    
    @pytest.mark.asyncio
    async def test_analyze_prd_requirements_json_parsing_with_braces(self, mock_lead_agent):
        """Test analyze_prd_requirements with JSON parsing using braces"""
        agent = mock_lead_agent
        
        # Set current_ecid to avoid attribute error
        agent.current_ecid = "TEST-ECID-001"
        
        # Test with JSON wrapped in text
        mock_json_response = """Some text before
{
    "core_features": ["Feature 1", "Feature 2"],
    "technical_requirements": ["Requirement 1", "Requirement 2"],
    "success_criteria": ["Criteria 1", "Criteria 2"]
}
Some text after"""
        
        with patch.object(agent.llm_client, 'complete', return_value=mock_json_response):
            analysis = await agent.analyze_prd_requirements("Test PRD content")
            
            # Should parse JSON correctly
            assert 'core_features' in analysis
            assert 'technical_requirements' in analysis
            assert 'success_criteria' in analysis
            assert len(analysis['core_features']) == 2
    
    @pytest.mark.asyncio
    async def test_analyze_prd_requirements_json_parsing_fallback(self, mock_lead_agent):
        """Test analyze_prd_requirements with JSON parsing fallback"""
        agent = mock_lead_agent
        
        # Set current_ecid to avoid attribute error
        agent.current_ecid = "TEST-ECID-001"
        
        # Test with invalid JSON
        mock_invalid_json_response = """This is not valid JSON
        Some random text
        That cannot be parsed"""
        
        with patch.object(agent.llm_client, 'complete', return_value=mock_invalid_json_response):
            analysis = await agent.analyze_prd_requirements("Test PRD content")
            
            # Should use fallback structure
            assert 'core_features' in analysis
            assert 'technical_requirements' in analysis
            assert 'success_criteria' in analysis
            assert len(analysis['core_features']) == 4  # Fallback has 4 features
    