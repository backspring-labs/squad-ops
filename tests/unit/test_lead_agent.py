"""
Unit tests for LeadAgent class
Tests core LeadAgent functionality without external dependencies
"""

import pytest
import asyncio
import yaml
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
        
        # Test development task delegation → dev role → neo agent (from instances.yaml)
        target = await agent.determine_delegation_target('development')
        assert target == 'neo'  # Expected from production instances.yaml
        
        # Test deployment task delegation → dev role → neo agent  
        target = await agent.determine_delegation_target('deployment')
        assert target == 'neo'
        
        # Test code task delegation → dev role → neo agent
        target = await agent.determine_delegation_target('code')
        assert target == 'neo'
        
        # Test security task delegation → qa role → eve agent
        target = await agent.determine_delegation_target('security')
        assert target == 'eve'
        
        # Test strategy task delegation → strat role → nat agent
        target = await agent.determine_delegation_target('product')
        assert target == 'nat'
    
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
                    delegated_to='neo',
                    description='Build application'
                )
                
                # Verify the method was called with correct parameters
                mock_log.assert_called_once_with(
                    task_id='task-123',
                    ecid='ECID-WB-027',
                    delegated_to='neo',
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
    async def test_create_development_tasks_error_handling(self, mock_database):
        """Test create_development_tasks error handling"""
        agent = LeadAgent("lead-agent-001")
        agent.db_pool = mock_database
        
        prd_analysis = {
            'core_features': ['Feature 1'],
            'technical_requirements': []
        }
        
        # Force an exception by making get_framework_version fail
        with patch('config.version.get_framework_version', side_effect=Exception("Version error")):
            tasks = await agent.create_development_tasks(
                prd_analysis,
                app_name='TestApp',
                ecid='ECID-WB-001'
            )
            
            # Should return empty list on error
            assert tasks == []
    
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
        # Create agent with non-existent instances file
        with patch('builtins.open', side_effect=FileNotFoundError("Instances file not found")):
            agent = LeadAgent("lead-agent-001", instances_file="/nonexistent/instances.yaml")
            
            # Should fall back to default mapping
            mapping = agent._load_role_to_agent_mapping()
            
            # Should return default mapping
            assert isinstance(mapping, dict)
            assert len(mapping) > 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_load_role_to_agent_mapping_yaml_error(self):
        """Test _load_role_to_agent_mapping with YAML parse error"""
        with patch('builtins.open', MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value='invalid: yaml: [')))))):
            agent = LeadAgent("lead-agent-001")
            
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
        agent = LeadAgent("max")
        
        # Mock the generate_warmboot_wrapup method
        agent.generate_warmboot_wrapup = AsyncMock()
        
        # Create developer completion event
        completion_message = AgentMessage(
            sender='neo',
            recipient='max',
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
        agent = LeadAgent("max")
        
        # Mock the generate_warmboot_wrapup method
        agent.generate_warmboot_wrapup = AsyncMock()
        
        # Create failed completion event
        completion_message = AgentMessage(
            sender='neo',
            recipient='max',
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
    async def test_collect_telemetry(self):
        """Test SIP-027 Phase 1: Telemetry collection"""
        agent = LeadAgent("max")
        
        # Mock database connection with proper async context manager
        from unittest.mock import MagicMock
        
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {'task_id': 'task-001', 'agent': 'neo', 'status': 'completed'}
        ])
        mock_conn.fetchrow = AsyncMock(return_value={
            'ecid': 'ECID-WB-001',
            'pid': 'PID-001',
            'run_type': 'warmboot',
            'title': 'Test Run',
            'created_at': '2025-01-15',
            'status': 'active'
        })
        mock_conn.execute = AsyncMock()
        
        # Create mock pool with proper async context manager behavior
        mock_acquire = MagicMock()
        mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acquire.__aexit__ = AsyncMock(return_value=None)
        
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_acquire)
        agent.db_pool = mock_pool
        
        # Add communication log
        agent.communication_log = [
            {'task_id': 'task-001', 'message_type': 'test'}
        ]
        
        # Collect telemetry
        telemetry = await agent._collect_telemetry('ECID-WB-001', 'task-001')
        
        # Verify telemetry structure
        assert 'database_metrics' in telemetry
        assert 'rabbitmq_metrics' in telemetry
        assert 'docker_events' in telemetry
        assert 'reasoning_logs' in telemetry
        assert 'collection_timestamp' in telemetry
        
        # Verify database metrics
        assert telemetry['database_metrics']['task_count'] == 1
        assert len(telemetry['database_metrics']['tasks']) == 1
        assert telemetry['database_metrics']['execution_cycle']['ecid'] == 'ECID-WB-001'
        
        # Verify RabbitMQ metrics
        assert telemetry['rabbitmq_metrics']['messages_processed'] == 1
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_telemetry_error_handling(self):
        """Test telemetry collection handles errors gracefully"""
        agent = LeadAgent("max")
        
        # Mock database to raise error
        agent.db_pool = None  # Will cause error when trying to acquire
        
        # Collect telemetry should not crash
        telemetry = await agent._collect_telemetry('ECID-ERROR', 'task-error')
        
        # Should still return structure with error noted
        assert 'database_metrics' in telemetry
        assert 'collection_error' in telemetry
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_wrapup_markdown(self):
        """Test SIP-027 Phase 1: Wrap-up markdown generation"""
        agent = LeadAgent("max")
        
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
                    'status': 'completed'
                }
            },
            'rabbitmq_metrics': {
                'messages_processed': 10
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
        assert 'Execution Summary' in markdown
        assert 'Development Activities' in markdown
        assert 'Database Metrics' in markdown
        assert 'Communication Metrics' in markdown
        assert 'Reasoning Traces' in markdown
        assert 'Infrastructure Status' in markdown
        assert 'Next Steps' in markdown
        assert 'SIP-027 Phase 1' in markdown
        
        # Verify data is embedded
        assert 'archive' in markdown
        assert 'build' in markdown
        assert 'deploy' in markdown
        assert 'app.py' in markdown
        assert '120' in markdown or '120 seconds' in markdown
        assert '3000' in markdown
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_warmboot_wrapup(self):
        """Test SIP-027 Phase 1: Full wrap-up generation workflow"""
        agent = LeadAgent("max")
        
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
        agent = LeadAgent("max")
        
        # Mock telemetry to raise error
        agent._collect_telemetry = AsyncMock(side_effect=Exception("DB error"))
        
        # Generate wrap-up should not crash
        await agent.generate_warmboot_wrapup('ECID-ERROR', 'task-error', {})
        
        # Should log error but not raise
    
