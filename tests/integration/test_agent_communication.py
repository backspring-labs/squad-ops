"""
Integration tests for agent-to-agent communication
Tests real message passing through RabbitMQ with actual agent instances
"""

import pytest
import asyncio
import json
from typing import Dict, Any
from unittest.mock import patch, AsyncMock
from agents.roles.lead.agent import LeadAgent
from agents.base_agent import AgentMessage

class TestAgentCommunication:
    """Test real agent communication through RabbitMQ"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_lead_to_dev_communication(self, integration_config, clean_database, clean_rabbitmq):
        """Test message passing from LeadAgent to DevAgent"""
        import tempfile
        import os
        
        # Create a temporary PRD file
        sample_prd_content = """
# Test Application PRD

## Overview
Test application for SquadOps integration testing

## Core Features
- Web Interface: User-friendly web application
- API Endpoints: RESTful API for data access
- Database Integration: PostgreSQL database connectivity

## Technical Requirements
- Frontend: HTML/CSS/JavaScript
- Backend: Python REST API
- Database: PostgreSQL
- Deployment: Docker containers

## Success Criteria
- Application runs successfully
- All features work as expected
- Performance meets requirements
- Integration tests pass
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as temp_prd:
            temp_prd.write(sample_prd_content)
            temp_prd_path = temp_prd.name
        
        try:
            # Set environment variables for external services from integration config
            import os
            os.environ['OLLAMA_URL'] = integration_config['ollama_url']
            os.environ['TASK_API_URL'] = integration_config['task_api_url']
            os.environ['USE_LOCAL_LLM'] = integration_config['use_local_llm']
            
            # Create LeadAgent with real connections - no mocking for true integration test
            lead_agent = LeadAgent("lead-agent-001")
            
            # Override connection URLs with test container URLs
            lead_agent.postgres_url = integration_config['database_url']
            lead_agent.redis_url = integration_config['redis_url']
            lead_agent.rabbitmq_url = integration_config['rabbitmq_url']
            
            # Initialize the agent
            await lead_agent.initialize()
            
            try:
                # Process a PRD request with the temporary file
                result = await lead_agent.process_prd_request(temp_prd_path, "test-ecid-001")
                
                # Verify successful processing
                assert result['status'] == 'success'
                assert 'tasks_delegated' in result
                assert len(result['tasks_delegated']) > 0
                
                # Verify tasks were delegated to dev agent
                delegated_tasks = result['tasks_delegated']
                dev_tasks = [task for task in delegated_tasks if task['delegated_to'] == 'dev-agent']
                assert len(dev_tasks) > 0
                
                # Integration test success - agent communication working
                print(f"✅ Integration test passed: {len(result['tasks_delegated'])} tasks delegated")
                
            finally:
                # Clean up agent connections
                await lead_agent.cleanup()
                    
        finally:
            # Clean up temporary file
            if os.path.exists(temp_prd_path):
                os.unlink(temp_prd_path)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_task_acknowledgment_flow(self, integration_config, clean_database, clean_rabbitmq):
        """Test task acknowledgment flow from dev agent back to lead agent"""
        lead_agent = LeadAgent("lead-agent-001")
        
        # Override connection URLs
        lead_agent.postgres_url = integration_config['database_url']
        lead_agent.redis_url = integration_config['redis_url']
        lead_agent.rabbitmq_url = integration_config['rabbitmq_url']
        
        await lead_agent.initialize()
        
        try:
            # Create a task acknowledgment message
            ack_message = AgentMessage(
                sender='dev-agent',
                recipient='lead-agent-001',
                message_type='task_acknowledgment',
                payload={
                    'task_id': 'test-task-001',
                    'status': 'accepted',
                    'understanding': 'I will build the web interface as specified'
                },
                context={'priority': 'HIGH'},
                timestamp='2025-01-01T00:00:00Z',
                message_id='msg-ack-001'
            )
            
            # Handle the acknowledgment
            await lead_agent.handle_message(ack_message)
            
            # Verify communication was logged
            assert len(lead_agent.communication_log) == 1
            log_entry = lead_agent.communication_log[0]
            assert log_entry['task_id'] == 'test-task-001'
            assert log_entry['from_agent'] == 'dev-agent'
            assert log_entry['message_type'] == 'task_acknowledgment'
            assert log_entry['status'] == 'success'
            
        finally:
            await lead_agent.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_approval_request_flow(self, integration_config, clean_database, clean_rabbitmq):
        """Test approval request flow from dev agent to lead agent"""
        lead_agent = LeadAgent("lead-agent-001")
        
        # Override connection URLs
        lead_agent.postgres_url = integration_config['database_url']
        lead_agent.redis_url = integration_config['redis_url']
        lead_agent.rabbitmq_url = integration_config['rabbitmq_url']
        
        await lead_agent.initialize()
        
        try:
            # Create an approval request message
            approval_message = AgentMessage(
                sender='dev-agent',
                recipient='lead-agent-001',
                message_type='approval_request',
                payload={
                    'task_id': 'test-task-001',
                    'complexity': 0.8,
                    'reason': 'Requires external API integration'
                },
                context={'priority': 'HIGH'},
                timestamp='2025-01-01T00:00:00Z',
                message_id='msg-approval-001'
            )
            
            # Handle the approval request
            await lead_agent.handle_message(approval_message)
            
            # Integration test success - approval request handled
            print(f"✅ Approval request flow test passed")
            
        finally:
            await lead_agent.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_escalation_flow(self, integration_config, clean_database, clean_rabbitmq):
        """Test task escalation flow"""
        from unittest.mock import AsyncMock
        
        lead_agent = LeadAgent("lead-agent-001")
        
        # Override connection URLs
        lead_agent.postgres_url = integration_config['database_url']
        lead_agent.redis_url = integration_config['redis_url']
        lead_agent.rabbitmq_url = integration_config['rabbitmq_url']
        
        # Mock database logging to avoid schema requirements
        lead_agent.log_activity = AsyncMock()
        
        await lead_agent.initialize()
        
        try:
            # Create a high-complexity task
            complex_task = {
                'task_id': 'complex-task-001',
                'complexity': 0.9,
                'description': 'Complex task requiring premium consultation',
                'timestamp': '2025-01-01T00:00:00Z'
            }
            
            # Escalate the task
            await lead_agent.escalate_task('complex-task-001', complex_task)
            
            # Verify task was added to approval queue
            assert len(lead_agent.approval_queue) == 1
            escalated_task = lead_agent.approval_queue[0]
            assert escalated_task['task_id'] == 'complex-task-001'
            assert escalated_task['reason'] == 'High complexity'
            
            # Integration test success - escalation handled
            print(f"✅ Escalation flow test passed")
            
        finally:
            await lead_agent.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_heartbeat_monitoring(self, integration_config, clean_database, clean_redis):
        """Test agent heartbeat monitoring"""
        lead_agent = LeadAgent("lead-agent-001")
        
        # Override connection URLs
        lead_agent.postgres_url = integration_config['database_url']
        lead_agent.redis_url = integration_config['redis_url']
        lead_agent.rabbitmq_url = integration_config['rabbitmq_url']
        
        await lead_agent.initialize()
        
        try:
            # Send heartbeat
            await lead_agent.send_heartbeat()
            
            # Integration test success - heartbeat sent
            print(f"✅ Heartbeat monitoring test passed")
            
        finally:
            await lead_agent.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_delegation_target_determination(self, integration_config):
        """Test delegation target determination with real agent"""
        lead_agent = LeadAgent("lead-agent-001")
        
        # Test various task types
        test_cases = [
            ('development', 'dev-agent'),
            ('code', 'dev-agent'),
            ('security', 'qa-agent'),
            ('data', 'data-agent'),
            ('financial', 'finance-agent'),
            ('creative', 'creative-agent'),
            ('analysis', 'curator-agent'),
            ('communication', 'comms-agent'),
            ('unknown_type', 'dev-agent')  # Default fallback
        ]
        
        for task_type, expected_target in test_cases:
            target = await lead_agent.determine_delegation_target(task_type)
            assert target == expected_target, f"Expected {expected_target} for {task_type}, got {target}"
        
        # Test governance task (should raise error)
        with pytest.raises(ValueError, match="Governance tasks should not be delegated"):
            await lead_agent.determine_delegation_target('governance')


