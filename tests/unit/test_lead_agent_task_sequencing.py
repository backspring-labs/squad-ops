"""
Unit tests for Max agent task sequencing and coordination.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, Any, List
import json
import os
import tempfile

from agents.roles.lead.agent import LeadAgent
from agents.contracts.task_spec import TaskSpec
from agents.contracts.build_manifest import BuildManifest
from tests.utils.mock_helpers import (
    create_sample_task_spec, create_sample_build_manifest,
    MockAgentMessage
)


class TestLeadAgentTaskSequencing:
    """Test LeadAgent task sequencing and coordination."""
    
    @pytest.fixture
    def lead_agent(self):
        """Create LeadAgent instance for testing."""
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
            
            # Mock the generate_task_spec method to avoid network calls
            async def mock_generate_task_spec(*args, **kwargs):
                return MockTaskSpec(
                    app_name=kwargs.get("app_name", "TestApp"),
                    version=kwargs.get("version", "0.2.0.001"), 
                    run_id=kwargs.get("run_id", "TEST-001"),
                    prd_analysis=kwargs.get("prd_content", "Test application for unit testing"),
                    features=kwargs.get("features", ["Feature 1", "Feature 2"]),
                    constraints={"framework": "vanilla_js"},
                    success_criteria=["Application loads", "No errors"]
                )
            
            agent.generate_task_spec = mock_generate_task_spec
            
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
        manifest = create_sample_build_manifest()
        return MockAgentMessage(
            sender="test-dev-agent",
            recipient="test-lead-agent",
            message_type="task.developer.completed",
            payload={
                "task_id": "test-design-001",
                "status": "completed",
                "action": "design_manifest",
                "manifest": manifest.to_dict()
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
    
    def test_warmboot_state_initialization(self, lead_agent):
        """Test that warmboot_state is properly initialized."""
        assert hasattr(lead_agent, 'warmboot_state')
        assert isinstance(lead_agent.warmboot_state, dict)
        assert lead_agent.warmboot_state.get('manifest') is None
        assert lead_agent.warmboot_state.get('build_files') == []
        assert lead_agent.warmboot_state.get('pending_tasks') == []
    
    @pytest.mark.asyncio
    async def test_create_development_tasks_four_task_sequence(self, lead_agent, sample_prd_analysis):
        """Test that four tasks are created in correct sequence."""
        tasks = await lead_agent.create_development_tasks(sample_prd_analysis, "TestApp", "TEST-001")
        
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
        
        # Verify TaskSpec is included in design_manifest and build tasks
        assert "task_spec" in tasks[1]["requirements"]
        assert "task_spec" in tasks[2]["requirements"]
        
        # Verify build task has manifest placeholder
        assert tasks[2]["requirements"]["manifest"] is None
        
        # Verify deploy task has source_dir
        assert "source_dir" in tasks[3]["requirements"]
    
    @pytest.mark.asyncio
    async def test_create_development_tasks_task_spec_creation(self, lead_agent, sample_prd_analysis):
        """Test that TaskSpec is properly created and included."""
        tasks = await lead_agent.create_development_tasks(sample_prd_analysis, "TestApp", "TEST-001")
        
        # Check design_manifest task
        design_task = tasks[1]
        task_spec_dict = design_task["requirements"]["task_spec"]
        
        assert task_spec_dict["app_name"] == "TestApp"
        assert task_spec_dict["version"] == "0.2.0.001"
        assert task_spec_dict["run_id"] == "TEST-001"
        assert task_spec_dict["prd_analysis"] == sample_prd_analysis["summary"]
        assert task_spec_dict["features"] == sample_prd_analysis["features"]
        assert task_spec_dict["constraints"] == sample_prd_analysis["constraints"]
        assert task_spec_dict["success_criteria"] == sample_prd_analysis["success_criteria"]
        
        # Check build task has same TaskSpec
        build_task = tasks[2]
        build_task_spec_dict = build_task["requirements"]["task_spec"]
        assert build_task_spec_dict == task_spec_dict
    
    @pytest.mark.asyncio
    async def test_design_manifest_completion_handler(self, lead_agent, design_manifest_completion_message):
        """Test handling of design_manifest completion."""
        with patch.object(lead_agent, '_trigger_next_task') as mock_trigger:
            await lead_agent._handle_design_manifest_completion(design_manifest_completion_message)
            
            # Verify manifest is stored in warmboot_state
            assert lead_agent.warmboot_state['manifest'] is not None
            assert lead_agent.warmboot_state['manifest']['architecture']['type'] == "spa_web_app"
            
            # Verify next task is triggered
            mock_trigger.assert_called_once_with("TEST-001", "build")
    
    @pytest.mark.asyncio
    async def test_design_manifest_completion_handler_missing_manifest(self, lead_agent):
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
        
        with patch.object(lead_agent, '_trigger_next_task') as mock_trigger:
            await lead_agent._handle_design_manifest_completion(message)
            
            # Verify manifest is not stored
            assert lead_agent.warmboot_state['manifest'] is None
            
            # Verify next task is NOT triggered (because manifest is missing)
            mock_trigger.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_build_completion_handler(self, lead_agent, build_completion_message):
        """Test handling of build completion."""
        with patch.object(lead_agent, '_trigger_next_task') as mock_trigger:
            await lead_agent._handle_build_completion(build_completion_message)
            
            # Verify build files are stored
            assert len(lead_agent.warmboot_state['build_files']) == 5
            assert "index.html" in lead_agent.warmboot_state['build_files']
            assert "app.js" in lead_agent.warmboot_state['build_files']
            assert "nginx.conf" in lead_agent.warmboot_state['build_files']
            assert "Dockerfile" in lead_agent.warmboot_state['build_files']
            
            # Verify next task is triggered
            mock_trigger.assert_called_once_with("TEST-001", "deploy")
    
    @pytest.mark.asyncio
    async def test_build_completion_handler_missing_files(self, lead_agent):
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
        
        with patch.object(lead_agent, '_trigger_next_task') as mock_trigger:
            await lead_agent._handle_build_completion(message)
            
            # Verify build files are empty
            assert lead_agent.warmboot_state['build_files'] == []
            
            # Verify next task is NOT triggered (because created_files is missing)
            mock_trigger.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_deploy_completion_handler(self, lead_agent, deploy_completion_message):
        """Test handling of deploy completion."""
        # Set up warmboot_state with manifest and files
        manifest = create_sample_build_manifest()
        lead_agent.warmboot_state['manifest'] = manifest.__dict__
        lead_agent.warmboot_state['build_files'] = ["index.html", "app.js", "styles.css"]
        
        with patch.object(lead_agent, '_log_warmboot_governance') as mock_log, \
             patch.object(lead_agent, 'generate_warmboot_wrapup') as mock_wrapup:
            
            await lead_agent._handle_deploy_completion(deploy_completion_message)
            
            # Verify governance logging is called
            mock_log.assert_called_once_with("TEST-001", manifest.__dict__, ["index.html", "app.js", "styles.css"])
            
            # Verify wrap-up generation is called
            mock_wrapup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_governance_logging(self, lead_agent):
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
            
            await lead_agent._log_warmboot_governance("TEST-001", manifest.to_dict(), files)
            
            # Verify manifest snapshot was created
            mock_yaml_dump.assert_called_once()
            yaml_call_args = mock_yaml_dump.call_args[0]
            assert yaml_call_args[0] == manifest.to_dict()
            
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
    
    @pytest.mark.asyncio
    async def test_task_failure_handling(self, lead_agent):
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
        
        with patch.object(lead_agent, '_trigger_next_task') as mock_trigger:
            await lead_agent._handle_design_manifest_completion(failure_message)
            
            # Verify next task is NOT triggered on failure
            mock_trigger.assert_not_called()
            
            # Verify warmboot_state is not updated
            assert lead_agent.warmboot_state['manifest'] is None
    
    @pytest.mark.asyncio
    async def test_trigger_next_task_placeholder(self, lead_agent):
        """Test _trigger_next_task placeholder method."""
        # This is currently a placeholder - should not raise exception
        await lead_agent._trigger_next_task("TEST-001", "build")
        
        # Method should complete without error
        assert True  # If we get here, no exception was raised
    
    @pytest.mark.asyncio
    async def test_create_development_tasks_with_custom_app_name(self, lead_agent, sample_prd_analysis):
        """Test create_development_tasks with custom app name."""
        tasks = await lead_agent.create_development_tasks(sample_prd_analysis, "CustomApp", "CUSTOM-001")
        
        # Verify app name is used in TaskSpec
        design_task = tasks[1]
        task_spec_dict = design_task["requirements"]["task_spec"]
        assert task_spec_dict["app_name"] == "CustomApp"
        assert task_spec_dict["run_id"] == "CUSTOM-001"
    
    @pytest.mark.asyncio
    async def test_create_development_tasks_with_default_values(self, lead_agent, sample_prd_analysis):
        """Test create_development_tasks with default values."""
        tasks = await lead_agent.create_development_tasks(sample_prd_analysis)
        
        # Verify default values are used
        design_task = tasks[1]
        task_spec_dict = design_task["requirements"]["task_spec"]
        assert task_spec_dict["app_name"] == "application"
        assert task_spec_dict["version"] == "0.2.0.001"
        assert task_spec_dict["run_id"] is None  # No ecid provided
    
    @pytest.mark.asyncio
    async def test_multiple_completion_handlers_sequence(self, lead_agent):
        """Test the complete sequence of completion handlers."""
        # Set up messages
        manifest = create_sample_build_manifest()
        design_message = MockAgentMessage(
            sender="neo", recipient="max", message_type="task.developer.completed",
            payload={"task_id": "design-001", "status": "completed", "action": "design_manifest", "manifest": manifest.__dict__},
            context={"ecid": "TEST-001"}
        )
        
        build_message = MockAgentMessage(
            sender="neo", recipient="max", message_type="task.developer.completed",
            payload={"task_id": "build-001", "status": "completed", "action": "build", "created_files": ["index.html", "app.js"]},
            context={"ecid": "TEST-001"}
        )
        
        deploy_message = MockAgentMessage(
            sender="neo", recipient="max", message_type="task.developer.completed",
            payload={"task_id": "deploy-001", "status": "completed", "action": "deploy"},
            context={"ecid": "TEST-001"}
        )
        
        with patch.object(lead_agent, '_trigger_next_task') as mock_trigger, \
             patch.object(lead_agent, '_log_warmboot_governance') as mock_log, \
             patch.object(lead_agent, 'generate_warmboot_wrapup') as mock_wrapup:
            
            # Execute sequence
            await lead_agent._handle_design_manifest_completion(design_message)
            await lead_agent._handle_build_completion(build_message)
            await lead_agent._handle_deploy_completion(deploy_message)
            
            # Verify state progression
            assert lead_agent.warmboot_state['manifest'] is not None
            assert len(lead_agent.warmboot_state['build_files']) == 2
            
            # Verify all handlers were called
            assert mock_trigger.call_count == 2  # build and deploy
            mock_log.assert_called_once()
            mock_wrapup.assert_called_once()
