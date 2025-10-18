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
        dev_agent = DevAgent("neo")
        
        max_agent.rabbitmq = mock_rabbitmq
        dev_agent.rabbitmq = mock_rabbitmq
        
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
        dev_agent = DevAgent("neo")
        
        # Test health status
        max_health = max_agent.get_health_status()
        neo_health = dev_agent.get_health_status()
        
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
        dev_agent = DevAgent("neo")
        assert dev_agent.name == "neo"
        assert dev_agent.agent_type == "code"
        assert dev_agent.reasoning_style == "deductive"
        
        # Verify both agents have required attributes
        for agent in [max_agent, dev_agent]:
            assert hasattr(agent, 'message_queue')
            assert hasattr(agent, 'task_history')
            assert hasattr(agent, 'status')
            assert agent.status == "initialized"
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_legacy_workflow_still_works(self):
        """Test that legacy workflow still works alongside JSON workflow."""
        from unittest.mock import MagicMock
        mock_llm_client = MagicMock()
        app_builder = AppBuilder(mock_llm_client)
        
        # Create sample TaskSpec
        task_spec = TaskSpec(
            app_name="LegacyTestApp",
            version="1.0.0",
            run_id="LEGACY-001",
            prd_analysis="Test legacy workflow compatibility",
            features=["Legacy feature"],
            constraints={"framework": "vanilla_js"},
            success_criteria=["Works with legacy workflow"]
        )
        
        with patch.object(app_builder, 'build_from_task_spec') as mock_legacy:
            mock_legacy.return_value = [
                {"path": "index.html", "content": "<html>Legacy</html>"},
                {"path": "app.js", "content": "console.log('legacy');"}
            ]
            
            # Test legacy workflow
            files = await app_builder.build_from_task_spec(task_spec)
            
            assert len(files) == 2
            assert files[0]["path"] == "index.html"
            assert files[1]["path"] == "app.js"
            mock_legacy.assert_called_once_with(task_spec)
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_json_workflow_vs_legacy_output(self):
        """Test that JSON workflow produces equivalent output to legacy workflow."""
        from unittest.mock import MagicMock
        mock_llm_client = MagicMock()
        app_builder = AppBuilder(mock_llm_client)
        
        task_spec = TaskSpec(
            app_name="ComparisonApp",
            version="1.0.0",
            run_id="COMPARE-001",
            prd_analysis="Compare JSON vs legacy workflow output",
            features=["Comparison feature"],
            constraints={"framework": "vanilla_js"},
            success_criteria=["Equivalent functionality"]
        )
        
        # Mock both workflows
        legacy_files = [
            {"path": "index.html", "content": "<html>Legacy</html>"},
            {"path": "app.js", "content": "console.log('legacy');"}
        ]
        
        json_files = [
            {"path": "index.html", "content": "<html>JSON</html>"},
            {"path": "app.js", "content": "console.log('json');"}
        ]
        
        with patch.object(app_builder, 'build_from_task_spec', return_value=legacy_files), \
             patch.object(app_builder, 'generate_manifest_json') as mock_manifest, \
             patch.object(app_builder, 'generate_files_json', return_value=json_files):
            
            # Test legacy workflow
            legacy_result = await app_builder.build_from_task_spec(task_spec)
            
            # Test JSON workflow
            manifest = BuildManifest(
                architecture={"type": "spa_web_app", "framework": "vanilla_js"},
                files=[{"path": "index.html", "purpose": "Main page", "dependencies": []}],
                deployment={"container": "nginx:alpine", "port": 80}
            )
            mock_manifest.return_value = manifest
            json_result = await app_builder.generate_files_json(task_spec, manifest)
            
            # Both should produce valid output
            assert len(legacy_result) > 0
            assert len(json_result) > 0
            
            # Both should have essential files
            legacy_paths = [f["path"] for f in legacy_result]
            json_paths = [f["path"] for f in json_result]
            
            assert "index.html" in legacy_paths
            assert "index.html" in json_paths
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_both_workflows_coexist(self):
        """Test that both workflows can coexist without interference."""
        from unittest.mock import MagicMock
        mock_llm_client = MagicMock()
        app_builder = AppBuilder(mock_llm_client)
        
        task_spec = TaskSpec(
            app_name="CoexistApp",
            version="1.0.0",
            run_id="COEXIST-001",
            prd_analysis="Test workflow coexistence",
            features=["Coexistence feature"],
            constraints={"framework": "vanilla_js"},
            success_criteria=["Both workflows work"]
        )
        
        with patch.object(app_builder, 'build_from_task_spec') as mock_legacy, \
             patch.object(app_builder, 'generate_manifest_json') as mock_manifest, \
             patch.object(app_builder, 'generate_files_json') as mock_files:
            
            # Mock responses
            mock_legacy.return_value = [{"path": "legacy.html", "content": "legacy"}]
            
            manifest = BuildManifest(
                architecture={"type": "spa_web_app", "framework": "vanilla_js"},
                files=[{"path": "json.html", "purpose": "JSON page", "dependencies": []}],
                deployment={"container": "nginx:alpine", "port": 80}
            )
            mock_manifest.return_value = manifest
            mock_files.return_value = [{"path": "json.html", "content": "json"}]
            
            # Run legacy workflow first
            legacy_result = await app_builder.build_from_task_spec(task_spec)
            
            # Run JSON workflow second
            json_manifest = await app_builder.generate_manifest_json(task_spec)
            json_result = await app_builder.generate_files_json(task_spec, json_manifest)
            
            # Both should complete successfully
            assert len(legacy_result) == 1
            assert len(json_result) == 1
            
            # Verify no interference
            assert legacy_result[0]["path"] == "legacy.html"
            assert json_result[0]["path"] == "json.html"
            
            # Verify all mocks were called
            mock_legacy.assert_called_once()
            mock_manifest.assert_called_once()
            mock_files.assert_called_once()
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_lead_agent_task_sequencing_backward_compatibility(self):
        """Test that LeadAgent task sequencing works with both old and new task formats."""
        lead_agent = LeadAgent("test-lead-agent")
        
        # Test with new four-task sequence
        prd_analysis = {
            "summary": "Test backward compatibility",
            "features": ["Feature 1"],
            "constraints": {"framework": "vanilla_js"},
            "success_criteria": ["Works"]
        }
        
        tasks = lead_agent.create_development_tasks(prd_analysis, "TestApp", "TEST-001")
        
        # Should create 4 tasks
        assert len(tasks) == 4
        assert tasks[0]["requirements"]["action"] == "archive"
        assert tasks[1]["requirements"]["action"] == "design_manifest"
        assert tasks[2]["requirements"]["action"] == "build"
        assert tasks[3]["requirements"]["action"] == "deploy"
        
        # Verify warmboot_state is initialized
        assert hasattr(lead_agent, 'warmboot_state')
        assert lead_agent.warmboot_state['manifest'] is None
        assert lead_agent.warmboot_state['build_files'] == []
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_dev_agent_task_handling_backward_compatibility(self):
        """Test that DevAgent handles both legacy and new task formats."""
        dev_agent = DevAgent("test-dev-agent")
        
        # Mock AppBuilder methods
        dev_agent.app_builder = MagicMock()
        dev_agent.file_manager = MagicMock()
        dev_agent.docker_manager = MagicMock()
        
        # Test legacy build task (no manifest)
        legacy_task = {
            "task_id": "legacy-build-001",
            "type": "development",
            "requirements": {
                "action": "build",
                "task_spec": {
                    "app_name": "LegacyApp",
                    "version": "1.0.0",
                    "run_id": "LEGACY-001",
                    "prd_analysis": "Legacy test",
                    "features": ["Legacy feature"],
                    "constraints": {},
                    "success_criteria": ["Works"]
                }
            }
        }
        
        dev_agent.app_builder.build_from_task_spec.return_value = [
            {"path": "index.html", "content": "<html>Legacy</html>"}
        ]
        
        result = await dev_agent._handle_development_task(legacy_task)
        
        assert result["status"] == "completed"
        assert result["action"] == "build"
        dev_agent.app_builder.build_from_task_spec.assert_called_once()
        
        # Test new build task (with manifest)
        manifest = BuildManifest(
            architecture={"type": "spa_web_app", "framework": "vanilla_js"},
            files=[{"path": "index.html", "purpose": "Main page", "dependencies": []}],
            deployment={"container": "nginx:alpine", "port": 80}
        )
        
        new_task = {
            "task_id": "new-build-001",
            "type": "development",
            "requirements": {
                "action": "build",
                "manifest": manifest.__dict__,
                "task_spec": {
                    "app_name": "NewApp",
                    "version": "1.0.0",
                    "run_id": "NEW-001",
                    "prd_analysis": "New test",
                    "features": ["New feature"],
                    "constraints": {},
                    "success_criteria": ["Works"]
                }
            }
        }
        
        dev_agent.app_builder.generate_files_json.return_value = [
            {"path": "index.html", "content": "<html>New</html>"}
        ]
        
        result = await dev_agent._handle_development_task(new_task)
        
        assert result["status"] == "completed"
        assert result["action"] == "build"
        dev_agent.app_builder.generate_files_json.assert_called_once()


