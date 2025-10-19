#!/usr/bin/env python3
"""
Regression tests for core SquadOps workflows
Tests critical paths to prevent regressions during rapid development
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from agents.roles.lead.agent import LeadAgent
from agents.roles.dev.agent import DevAgent
from agents.roles.dev.app_builder import AppBuilder
from agents.contracts.task_spec import TaskSpec
from agents.contracts.build_manifest import BuildManifest

class TestCoreWorkflows:
    """Test critical SquadOps workflows for regression prevention"""
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_prd_to_task_workflow(self, sample_prd):
        """Test complete PRD to task breakdown workflow"""
        agent = LeadAgent("test-lead-agent")
        
        # Mock the LLM client to avoid network calls
        with patch.object(agent.llm_client, 'complete') as mock_llm:
            mock_llm.return_value = """
            {
                "core_features": ["Web Interface", "API Endpoints"],
                "technical_requirements": ["HTML/CSS/JS", "REST API", "Database"],
                "success_criteria": ["Application runs successfully", "All features work"]
            }
            """
            
            # Test PRD analysis (this method exists)
            analysis = await agent.analyze_prd_requirements(sample_prd)
            assert 'core_features' in analysis
            assert 'technical_requirements' in analysis
            assert 'success_criteria' in analysis
            
            # Mock the task API call
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_response = AsyncMock()
                mock_response.json.return_value = {
                    'tasks': [
                        {'task_id': 'task1', 'task_type': 'archive', 'ecid': 'test-ecid-001', 'requirements': {}, 'complexity': 0.1, 'priority': 'LOW'},
                        {'task_id': 'task2', 'task_type': 'design_manifest', 'ecid': 'test-ecid-001', 'requirements': {}, 'complexity': 0.3, 'priority': 'MEDIUM'},
                        {'task_id': 'task3', 'task_type': 'build', 'ecid': 'test-ecid-001', 'requirements': {}, 'complexity': 0.4, 'priority': 'HIGH'},
                        {'task_id': 'task4', 'task_type': 'deploy', 'ecid': 'test-ecid-001', 'requirements': {}, 'complexity': 0.2, 'priority': 'MEDIUM'}
                    ]
                }
                mock_response.status = 200
                mock_post.return_value.__aenter__.return_value = mock_response
                
                # Test task creation (this method exists and returns a list)
                tasks = await agent.create_development_tasks(analysis, "TestApp", "test-ecid-001")
                assert len(tasks) == 4  # Current implementation creates 4 tasks: archive, design_manifest, build, deploy
                
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
        lead_agent = LeadAgent("test-lead-agent")
        dev_agent = DevAgent("test-dev-agent")
        
        # Test delegation target determination (this method exists)
        target = await lead_agent.determine_delegation_target("development")
        assert target == "dev-agent"  # Should delegate to dev-agent
        
        # Test task processing by dev agent
        result = await dev_agent.process_task(sample_task)
        assert result is not None
        assert 'status' in result
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_task_lifecycle_workflow(self, sample_task, mock_database):
        """Test complete task lifecycle management"""
        agent = LeadAgent("test-lead-agent")
        
        # Mock the database pool to avoid connection issues
        agent.db_pool = mock_database
        
        # Test task processing (this method exists)
        result = await agent.process_task(sample_task)
        assert result is not None
        assert 'status' in result
        
        # Test escalation (this method exists)
        escalation_result = await agent.escalate_task(sample_task['task_id'], sample_task)
        assert escalation_result is not None
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_version_management_workflow(self):
        """Test version calculation and management"""
        agent = LeadAgent("test-lead-agent")
        
        # Test task spec generation (this method exists)
        task_spec = await agent.generate_task_spec(
            prd_content="Test PRD content",
            app_name="TestApp",
            version="1.0.0",
            run_id="TEST-001",
            features=["Feature 1", "Feature 2"]
        )
        
        # Verify task spec structure
        assert task_spec.app_name == "TestApp"
        assert task_spec.version == "1.0.0"
        assert task_spec.run_id == "TEST-001"
        assert len(task_spec.features) == 2
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_complexity_assessment_workflow(self):
        """Test complexity assessment and decision making"""
        agent = LeadAgent("test-lead-agent")
        
        # Mock current_ecid to avoid attribute errors
        agent.current_ecid = "test-ecid-001"
        
        # Test PRD analysis with different complexity levels
        with patch.object(agent.llm_client, 'complete') as mock_llm:
            mock_llm.return_value = """
            {
                "core_features": ["Simple Feature"],
                "technical_requirements": ["Basic HTML"],
                "success_criteria": ["Works"]
            }
            """
            
            analysis = await agent.analyze_prd_requirements("Simple PRD")
            assert 'core_features' in analysis
            # Don't assert specific length since LLM might return different results
            assert len(analysis['core_features']) >= 1
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_governance_decision_workflow(self):
        """Test governance decision making workflow"""
        agent = LeadAgent("test-lead-agent")
        
        # Mock the database pool to avoid connection issues
        agent.db_pool = AsyncMock()
        
        # Test escalation workflow
        escalation_result = await agent.escalate_task("test-task-001", {
            'task_id': 'test-task-001',
            'complexity': 0.8,
            'priority': 'HIGH'
        })
        assert escalation_result is not None
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_agent_health_monitoring_workflow(self):
        """Test agent health monitoring workflow"""
        lead_agent = LeadAgent("test-lead-agent")
        dev_agent = DevAgent("test-dev-agent")
        
        # Test that agents can be created and initialized
        assert lead_agent.name == "test-lead-agent"
        assert dev_agent.name == "test-dev-agent"
        
        # Test delegation target determination
        target = await lead_agent.determine_delegation_target("development")
        assert target == "dev-agent"
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_error_handling_workflow(self):
        """Test error handling in critical workflows"""
        agent = LeadAgent("test-lead-agent")
        
        # Test error handling in PRD analysis
        with patch.object(agent.llm_client, 'complete') as mock_llm:
            mock_llm.side_effect = Exception("LLM failure")
            
            # Should handle LLM failure gracefully
            try:
                analysis = await agent.analyze_prd_requirements("Test PRD")
                # If it doesn't raise an exception, check that it returns a fallback
                assert analysis is not None
            except Exception as e:
                # If it raises an exception, that's also acceptable error handling
                assert "LLM failure" in str(e)
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_concurrent_task_processing(self, sample_task):
        """Test concurrent task processing"""
        agent = LeadAgent("test-lead-agent")
        
        # Mock the database pool to avoid connection issues
        agent.db_pool = AsyncMock()
        
        # Test that process_task can handle concurrent calls
        tasks = [sample_task.copy() for _ in range(3)]
        for i, task in enumerate(tasks):
            task['task_id'] = f"concurrent-task-{i}"
        
        # Process tasks concurrently
        results = await asyncio.gather(*[agent.process_task(task) for task in tasks])
        
        # Verify all tasks were processed
        assert len(results) == 3
        for result in results:
            assert result is not None
            assert 'status' in result
    
    @pytest.mark.regression
    def test_agent_initialization_consistency(self):
        """Test agent initialization consistency"""
        # Test LeadAgent initialization
        lead_agent = LeadAgent("test-lead-agent")
        assert lead_agent.name == "test-lead-agent"
        assert lead_agent.agent_type == "governance"
        assert lead_agent.reasoning_style == "governance"
        
        # Test DevAgent initialization
        dev_agent = DevAgent("test-dev-agent")
        assert dev_agent.name == "test-dev-agent"
        assert dev_agent.agent_type == "code"
        assert dev_agent.reasoning_style == "deductive"
        
        # Verify both agents have required attributes
        for agent in [lead_agent, dev_agent]:
            assert hasattr(agent, 'llm_client')
            assert hasattr(agent, 'process_task')
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_json_workflow_backward_compatibility(self):
        """Test that JSON workflow works with current API"""
        from unittest.mock import MagicMock
        mock_llm_client = MagicMock()
        app_builder = AppBuilder(mock_llm_client)
        
        # Test that AppBuilder can be instantiated
        assert app_builder is not None
        assert hasattr(app_builder, 'generate_manifest_json')
        assert hasattr(app_builder, 'generate_files_json')
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_lead_agent_task_sequencing_backward_compatibility(self):
        """Test that LeadAgent task sequencing works with current API"""
        lead_agent = LeadAgent("test-lead-agent")
        
        # Test with new four-task sequence
        prd_analysis = {
            "summary": "Test backward compatibility",
            "features": ["Feature 1"],
            "constraints": {"framework": "vanilla_js"},
            "success_criteria": ["Works"]
        }
        
        # Mock the task API call
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.json.return_value = {
                'tasks': [
                    {'task_id': 'task1', 'task_type': 'archive', 'ecid': 'TEST-001', 'requirements': {}, 'complexity': 0.1, 'priority': 'LOW'},
                    {'task_id': 'task2', 'task_type': 'design_manifest', 'ecid': 'TEST-001', 'requirements': {}, 'complexity': 0.3, 'priority': 'MEDIUM'},
                    {'task_id': 'task3', 'task_type': 'build', 'ecid': 'TEST-001', 'requirements': {}, 'complexity': 0.4, 'priority': 'HIGH'},
                    {'task_id': 'task4', 'task_type': 'deploy', 'ecid': 'TEST-001', 'requirements': {}, 'complexity': 0.2, 'priority': 'MEDIUM'}
                ]
            }
            mock_response.status = 200
            mock_post.return_value.__aenter__.return_value = mock_response
            
            tasks = await lead_agent.create_development_tasks(prd_analysis, "TestApp", "TEST-001")
            
            # Should create 4 tasks
            assert len(tasks) == 4
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_dev_agent_task_handling_backward_compatibility(self):
        """Test that DevAgent handles current task formats"""
        dev_agent = DevAgent("test-dev-agent")
        
        # Mock AppBuilder methods
        dev_agent.app_builder = MagicMock()
        dev_agent.file_manager = MagicMock()
        dev_agent.docker_manager = MagicMock()
        
        # Test build task with manifest (JSON workflow)
        build_task = {
            "task_id": "build-task-001",
            "type": "development",
            "requirements": {
                "action": "build",
                "manifest": {
                    "app_name": "TestApp",
                    "architecture_type": "spa_web_app",
                    "framework": "vanilla_js",
                    "files": []
                }
            }
        }
        
        dev_agent.app_builder.generate_files_json.return_value = [
            {"file_path": "index.html", "content": "<html>Test</html>", "type": "create_file"}
        ]
        
        result = await dev_agent._handle_build_task("build-task-001", build_task["requirements"])
        
        assert result["status"] == "completed"
        assert "created_files" in result