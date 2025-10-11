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
        # Mock the LLM responses to avoid external dependencies
        with patch('agents.roles.lead.agent.LeadAgent.llm_response') as mock_llm:
            mock_llm.return_value = """
            {
                "core_features": ["Web Interface", "API Endpoints"],
                "technical_requirements": ["HTML/CSS/JS", "REST API", "Database"],
                "complexity_score": 0.7,
                "estimated_effort": "3-4 days"
            }
            """
            
            # Create LeadAgent with real connections
            lead_agent = LeadAgent("lead-agent-001")
            
            # Override connection URLs with test container URLs
            lead_agent.postgres_url = integration_config['database_url']
            lead_agent.redis_url = integration_config['redis_url']
            lead_agent.rabbitmq_url = integration_config['rabbitmq_url']
            
            # Initialize the agent
            await lead_agent.initialize()
            
            try:
                # Process a PRD request
                result = await lead_agent.process_prd_request("/test/prd.md", "test-ecid-001")
                
                # Verify successful processing
                assert result['status'] == 'success'
                assert 'tasks_delegated' in result
                assert len(result['tasks_delegated']) > 0
                
                # Verify tasks were delegated to dev agent
                delegated_tasks = result['tasks_delegated']
                dev_tasks = [task for task in delegated_tasks if task['delegated_to'] == 'Neo']
                assert len(dev_tasks) > 0
                
                # Verify database logging
                # Check that execution cycle was created
                async with lead_agent.db_pool.acquire() as conn:
                    ec_record = await conn.fetch_one(
                        "SELECT * FROM execution_cycles WHERE ecid = $1", "test-ecid-001"
                    )
                    assert ec_record is not None
                    assert ec_record['status'] == 'active'
                
                # Check that tasks were logged
                async with lead_agent.db_pool.acquire() as conn:
                    task_logs = await conn.fetch_all(
                        "SELECT * FROM agent_task_logs WHERE task_id LIKE $1", "test-ecid-001%"
                    )
                    assert len(task_logs) > 0
                
            finally:
                # Clean up
                await lead_agent.cleanup()
    
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
            
            # Verify activity was logged
            async with lead_agent.db_pool.acquire() as conn:
                activity_logs = await conn.fetch_all(
                    "SELECT * FROM agent_task_logs WHERE task_id = $1", "test-task-001"
                )
                assert len(activity_logs) > 0
            
        finally:
            await lead_agent.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_escalation_flow(self, integration_config, clean_database, clean_rabbitmq):
        """Test task escalation flow"""
        lead_agent = LeadAgent("lead-agent-001")
        
        # Override connection URLs
        lead_agent.postgres_url = integration_config['database_url']
        lead_agent.redis_url = integration_config['redis_url']
        lead_agent.rabbitmq_url = integration_config['rabbitmq_url']
        
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
            
            # Verify activity was logged
            async with lead_agent.db_pool.acquire() as conn:
                activity_logs = await conn.fetch_all(
                    "SELECT * FROM agent_task_logs WHERE task_id = $1", "complex-task-001"
                )
                assert len(activity_logs) > 0
            
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
            
            # Verify heartbeat was logged
            async with lead_agent.db_pool.acquire() as conn:
                heartbeat_logs = await conn.fetch_all(
                    "SELECT * FROM agent_heartbeats WHERE agent_name = $1", "lead-agent-001"
                )
                assert len(heartbeat_logs) == 1
                assert heartbeat_logs[0]['status'] == 'active'
            
        finally:
            await lead_agent.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_delegation_target_determination(self, integration_config):
        """Test delegation target determination with real agent"""
        lead_agent = LeadAgent("lead-agent-001")
        
        # Test various task types
        test_cases = [
            ('development', 'Neo'),
            ('code', 'Neo'),
            ('security', 'EVE'),
            ('data', 'Data'),
            ('financial', 'Quark'),
            ('creative', 'Glyph'),
            ('analysis', 'Og'),
            ('communication', 'Joi'),
            ('unknown_type', 'Neo')  # Default fallback
        ]
        
        for task_type, expected_target in test_cases:
            target = await lead_agent.determine_delegation_target(task_type)
            assert target == expected_target, f"Expected {expected_target} for {task_type}, got {target}"
        
        # Test governance task (should raise error)
        with pytest.raises(ValueError, match="Governance tasks should not be delegated"):
            await lead_agent.determine_delegation_target('governance')


