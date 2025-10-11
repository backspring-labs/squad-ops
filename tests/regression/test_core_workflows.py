#!/usr/bin/env python3
"""
Regression tests for core SquadOps workflows
Tests critical paths to prevent regressions during rapid development
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from agents.roles.lead.agent import LeadAgent
from agents.roles.dev.agent import RefactoredDevAgent

class TestCoreWorkflows:
    """Test critical SquadOps workflows for regression prevention"""
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_prd_to_task_workflow(self, sample_prd):
        """Test complete PRD to task breakdown workflow"""
        agent = LeadAgent("max")
        
        with patch.object(agent, 'call_llm') as mock_llm, \
             patch.object(agent, 'update_task_status') as mock_update:
            
            # Mock PRD analysis
            mock_llm.return_value = {
                'core_features': ['Web Interface', 'API Endpoints'],
                'technical_requirements': ['HTML/CSS/JS', 'REST API', 'Database'],
                'complexity_score': 0.7,
                'estimated_effort': '3-4 days'
            }
            
            # Test PRD analysis
            analysis = await agent.analyze_prd_requirements(sample_prd)
            assert analysis['complexity_score'] == 0.7
            assert len(analysis['core_features']) == 2
            
            # Test task creation
            tasks = await agent.create_development_tasks(analysis, "TestApp", "test-ecid-001")
            assert len(tasks) == 3
            
            # Verify task structure
            for task in tasks:
                assert 'task_id' in task
                assert 'task_type' in task
                assert 'ecid' in task
                assert 'requirements' in task
                assert 'complexity' in task
                assert 'priority' in task
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_agent_communication_workflow(self, sample_task, mock_rabbitmq):
        """Test agent-to-agent communication workflow"""
        max_agent = LeadAgent("max")
        neo_agent = RefactoredDevAgent("neo")
        
        max_agent.rabbitmq = mock_rabbitmq
        neo_agent.rabbitmq = mock_rabbitmq
        
        # Test task delegation
        await max_agent.delegate_task(sample_task, "neo")
        
        # Verify message was sent
        mock_rabbitmq.publish.assert_called_once()
        call_args = mock_rabbitmq.publish.call_args
        assert call_args[0][0] == "neo"
        
        message = call_args[0][1]
        assert message.message_type == "TASK_ASSIGNMENT"
        assert message.sender == "max"
        assert message.recipient == "neo"
        assert message.content['task_id'] == sample_task['task_id']
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_task_lifecycle_workflow(self, sample_task, mock_database):
        """Test complete task lifecycle management"""
        agent = LeadAgent("max")
        agent.database = mock_database
        
        # Test task status updates
        statuses = [
            ("started", 0.0),
            ("in_progress", 25.0),
            ("in_progress", 50.0),
            ("in_progress", 75.0),
            ("completed", 100.0)
        ]
        
        for status, progress in statuses:
            await agent.update_task_status(sample_task['task_id'], status, progress)
        
        # Verify database calls
        assert mock_database.execute.call_count == len(statuses)
        
        # Verify final status
        final_call = mock_database.execute.call_args_list[-1]
        assert "completed" in str(final_call)
        assert "100.0" in str(final_call)
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_version_management_workflow(self):
        """Test version calculation and management"""
        agent = LeadAgent("max")
        
        with patch('config.version.get_framework_version', return_value="0.1.4"):
            # Test version calculation
            version1 = agent.calculate_version("test-ecid-001")
            version2 = agent.calculate_version("test-ecid-002")
            
            # Verify version format
            assert version1.startswith("0.1.4.")
            assert version2.startswith("0.1.4.")
            
            # Verify versions are different for different ECIDs
            assert version1 != version2
            
            # Verify version structure
            parts1 = version1.split('.')
            parts2 = version2.split('.')
            assert len(parts1) == 4
            assert len(parts2) == 4
            assert parts1[:3] == parts2[:3]  # Framework version same
            assert parts1[3] != parts2[3]    # Sequence different
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_complexity_assessment_workflow(self):
        """Test complexity assessment and decision making"""
        agent = LeadAgent("max")
        
        test_cases = [
            # (task_complexity, expected_assessment)
            (0.2, "LOW"),
            (0.5, "MEDIUM"),
            (0.8, "HIGH"),
            (0.9, "HIGH")
        ]
        
        for complexity, expected in test_cases:
            task = {'complexity': complexity, 'requirements': {'action': 'test'}}
            assessment = agent.assess_complexity(task)
            assert assessment == expected
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_governance_decision_workflow(self):
        """Test governance decision making workflow"""
        agent = LeadAgent("max")
        
        # Test approval for simple tasks
        simple_task = {'complexity': 0.3, 'priority': 'LOW'}
        decision = agent.make_governance_decision(simple_task)
        assert decision['action'] == 'approve'
        assert 'approved' in decision['reason'].lower()
        
        # Test escalation for complex tasks
        complex_task = {'complexity': 0.9, 'priority': 'HIGH'}
        decision = agent.make_governance_decision(complex_task)
        assert decision['action'] == 'escalate'
        assert 'escalate' in decision['reason'].lower()
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_agent_health_monitoring_workflow(self):
        """Test agent health monitoring workflow"""
        max_agent = LeadAgent("max")
        neo_agent = RefactoredDevAgent("neo")
        
        # Test health status
        max_health = max_agent.get_health_status()
        neo_health = neo_agent.get_health_status()
        
        # Verify health structure
        for health in [max_health, neo_health]:
            assert 'name' in health
            assert 'status' in health
            assert 'agent_type' in health
            assert 'reasoning_style' in health
            assert 'uptime' in health
        
        # Verify agent-specific fields
        assert max_health['agent_type'] == 'governance'
        assert neo_health['agent_type'] == 'code'
        assert max_health['reasoning_style'] == 'governance'
        assert neo_health['reasoning_style'] == 'deductive'
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_error_handling_workflow(self):
        """Test error handling in critical workflows"""
        agent = LeadAgent("max")
        
        # Test PRD analysis with invalid input
        with patch.object(agent, 'call_llm') as mock_llm:
            mock_llm.side_effect = Exception("LLM service unavailable")
            
            with pytest.raises(Exception):
                await agent.analyze_prd_requirements("invalid prd")
        
        # Test task delegation with invalid recipient
        with patch.object(agent, 'send_message') as mock_send:
            mock_send.side_effect = Exception("Message send failed")
            
            with pytest.raises(Exception):
                await agent.delegate_task({'task_id': 'test'}, "invalid-agent")
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_concurrent_task_processing(self, sample_task):
        """Test concurrent task processing"""
        agent = LeadAgent("max")
        
        with patch.object(agent, 'delegate_task') as mock_delegate, \
             patch.object(agent, 'update_task_status') as mock_update:
            
            # Process multiple tasks concurrently
            tasks = [sample_task.copy() for _ in range(3)]
            for i, task in enumerate(tasks):
                task['task_id'] = f"task-{i:03d}"
            
            # Process all tasks concurrently
            results = await asyncio.gather(*[
                agent.process_task(task) for task in tasks
            ])
            
            # Verify all tasks were processed
            assert len(results) == 3
            for result in results:
                assert result['status'] == 'completed'
            
            # Verify delegation was called for each task
            assert mock_delegate.call_count == 3
    
    @pytest.mark.regression
    def test_agent_initialization_consistency(self):
        """Test agent initialization consistency"""
        # Test LeadAgent initialization
        max_agent = LeadAgent("max")
        assert max_agent.name == "max"
        assert max_agent.agent_type == "governance"
        assert max_agent.reasoning_style == "governance"
        
        # Test DevAgent initialization
        neo_agent = RefactoredDevAgent("neo")
        assert neo_agent.name == "neo"
        assert neo_agent.agent_type == "code"
        assert neo_agent.reasoning_style == "deductive"
        
        # Verify both agents have required attributes
        for agent in [max_agent, neo_agent]:
            assert hasattr(agent, 'message_queue')
            assert hasattr(agent, 'task_history')
            assert hasattr(agent, 'status')
            assert agent.status == "initialized"


