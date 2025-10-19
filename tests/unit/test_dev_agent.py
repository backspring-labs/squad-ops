"""
Comprehensive unit tests for DevAgent - covering JSON workflow and all methods.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, Any

from agents.roles.dev.agent import DevAgent
from agents.contracts.task_spec import TaskSpec
from agents.contracts.build_manifest import BuildManifest
from tests.utils.mock_helpers import (
    create_sample_task_spec, create_sample_build_manifest,
    MockFileManager, MockDockerManager, MockOllamaResponse
)


class TestDevAgent:
    """Comprehensive tests for DevAgent covering JSON workflow and all methods."""
    
    @pytest.fixture
    def dev_agent(self):
        """Create DevAgent instance for testing."""
        agent = DevAgent("test-dev-agent")
        # Mock the managers to avoid real file system operations
        agent.file_manager = MockFileManager()
        agent.docker_manager = MockDockerManager()
        agent.version_manager = MagicMock()
        agent.app_builder = MagicMock()
        return agent
    
    # ============================================================================
    # JSON WORKFLOW TESTS (from test_dev_agent_json_handlers.py)
    # ============================================================================
    
    @pytest.fixture
    def design_manifest_task(self):
        """Sample design_manifest task."""
        task_spec = create_sample_task_spec()
        return {
            "task_id": "test-design-001",
            "type": "development",
            "requirements": {
                "action": "design_manifest",
                "task_spec": task_spec.to_dict()
            }
        }
    
    @pytest.fixture
    def build_task_with_manifest(self):
        """Sample build task with manifest."""
        task_spec = create_sample_task_spec()
        manifest = create_sample_build_manifest()
        return {
            "task_id": "test-build-001",
            "type": "development",
            "requirements": {
                "action": "build",
                "task_spec": task_spec.to_dict(),
                "manifest": manifest.to_dict()  # Pass as dict, DevAgent converts to BuildManifest
            }
        }
    
    
    @pytest.fixture
    def deploy_task(self):
        """Sample deploy task."""
        return {
            "task_id": "test-deploy-001",
            "type": "development",
            "requirements": {
                "action": "deploy",
                "app_name": "test-app",
                "target_url": "http://localhost:8080"
            }
        }
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_design_manifest_task_success(self, dev_agent, design_manifest_task):
        """Test successful design_manifest task handling."""
        # Mock AppBuilder manifest generation
        mock_manifest = create_sample_build_manifest()
        dev_agent.app_builder.generate_manifest_json = AsyncMock(return_value=mock_manifest)
        
        result = await dev_agent._handle_design_manifest_task(
            design_manifest_task["task_id"],
            design_manifest_task["requirements"]
        )
        
        assert result["status"] == "completed"
        assert result["task_id"] == "test-design-001"
        assert result["action"] == "design_manifest"
        assert "manifest" in result
        dev_agent.app_builder.generate_manifest_json.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_design_manifest_task_missing_taskspec(self, dev_agent):
        """Test design_manifest task with missing TaskSpec."""
        requirements = {
            "action": "design_manifest"
            # Missing task_spec
        }
        
        result = await dev_agent._handle_design_manifest_task("test-001", requirements)
        
        assert result["status"] == "error"
        assert "taskspec" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_handle_design_manifest_task_exception(self, dev_agent):
        """Test _handle_design_manifest_task exception handling"""
        task_id = 'test-task-001'
        requirements = {
            'task_spec': {
                'app_name': 'TestApp',
                'version': '1.0.0',
                'run_id': 'test-run',
                'prd_analysis': 'Test analysis',
                'features': ['feature1'],
                'constraints': {},
                'success_criteria': ['Task completes']
            }
        }
        
        # Mock app_builder to raise exception
        dev_agent.app_builder = AsyncMock()
        dev_agent.app_builder.generate_manifest_json.side_effect = Exception("Manifest generation failed")
        
        result = await dev_agent._handle_design_manifest_task(task_id, requirements)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert result['action'] == 'design_manifest'
        assert 'error' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_build_task_with_manifest_json_workflow(self, dev_agent, build_task_with_manifest):
        """Test build task with manifest using JSON workflow."""
        # Mock AppBuilder file generation - return list of file dicts as expected
        mock_files = [
            {
                "type": "create_file",
                "file_path": "app.py",
                "content": "print('Hello World')"
            },
            {
                "type": "create_file", 
                "file_path": "index.html",
                "content": "<html><body>Hello</body></html>"
            }
        ]
        dev_agent.app_builder.generate_files_json = AsyncMock(return_value=mock_files)
        
        result = await dev_agent._handle_build_task(
            build_task_with_manifest["task_id"],
            build_task_with_manifest["requirements"]
        )
        
        assert result["status"] == "completed"
        assert result["task_id"] == "test-build-001"
        assert result["action"] == "build"
        assert "created_files" in result  # DevAgent returns created_files, not files
        assert len(result["created_files"]) == 2
        dev_agent.app_builder.generate_files_json.assert_called_once()
    
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_build_task_file_creation(self, dev_agent, build_task_with_manifest):
        """Test that build task creates files correctly."""
        # Mock AppBuilder file generation - return list of file dicts as expected
        mock_files = [
            {
                "type": "create_file",
                "file_path": "app.py",
                "content": "print('Hello World')"
            },
            {
                "type": "create_file",
                "file_path": "index.html",
                "content": "<html><body>Hello</body></html>"
            }
        ]
        dev_agent.app_builder.generate_files_json = AsyncMock(return_value=mock_files)
        
        result = await dev_agent._handle_build_task(
            build_task_with_manifest["task_id"],
            build_task_with_manifest["requirements"]
        )
        
        # Check that files were created
        created_files = dev_agent.file_manager.created_files
        assert len(created_files) == 2
        
        # Check specific files were created
        assert any("index.html" in path and "Hello" in content for path, content in created_files.items())
        assert any("app.py" in path and "print" in content for path, content in created_files.items())
    
    @pytest.mark.asyncio
    async def test_handle_build_task_missing_manifest(self, dev_agent):
        """Test _handle_build_task with missing manifest"""
        task_id = 'test-task-001'
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0'
            # Missing manifest
        }
        
        result = await dev_agent._handle_build_task(task_id, requirements)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert result['action'] == 'build'
        assert 'Manifest is required' in result['error']
    
    @pytest.mark.asyncio
    async def test_handle_build_task_exception(self, dev_agent):
        """Test _handle_build_task exception handling"""
        task_id = 'test-task-001'
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'manifest': {
                'app_name': 'TestApp',
                'version': '1.0.0',
                'features': ['Feature1']
            }
        }
        
        # Mock app_builder to raise exception
        dev_agent.app_builder = AsyncMock()
        dev_agent.app_builder.generate_files_json.side_effect = Exception("File generation failed")
        
        result = await dev_agent._handle_build_task(task_id, requirements)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert result['action'] == 'build'
        assert 'error' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_deploy_task_with_source_dir(self, dev_agent, deploy_task):
        """Test deploy task with source directory."""
        # Mock Docker operations - MockDockerManager already returns proper dict structure
        result = await dev_agent._handle_deploy_task(
            deploy_task["task_id"],
            deploy_task["requirements"]
        )
        
        assert result["status"] == "completed"
        assert result["task_id"] == "test-deploy-001"
        assert result["action"] == "deploy"
        assert len(dev_agent.docker_manager.build_calls) == 1
        assert len(dev_agent.docker_manager.deploy_calls) == 1
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_deploy_task_with_source_fallback(self, dev_agent, deploy_task):
        """Test deploy task with source fallback."""
        # Mock Docker operations - MockDockerManager already returns proper dict structure
        result = await dev_agent._handle_deploy_task(
            deploy_task["task_id"],
            deploy_task["requirements"]
        )
        
        assert result["status"] == "completed"
        assert result["task_id"] == "test-deploy-001"
        assert result["action"] == "deploy"
        assert len(dev_agent.docker_manager.build_calls) == 1
        assert len(dev_agent.docker_manager.deploy_calls) == 1
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_deploy_task_missing_source(self, dev_agent):
        """Test deploy task with missing source."""
        requirements = {
            "action": "deploy",
            "app_name": "test-app"
            # Missing source_dir
        }
        
        result = await dev_agent._handle_deploy_task("test-deploy-003", requirements)
        
        assert result["status"] == "completed"
        assert result["task_id"] == "test-deploy-003"
        assert result["action"] == "deploy"
    
    @pytest.mark.asyncio
    async def test_handle_deploy_task_with_features(self, dev_agent):
        """Test _handle_deploy_task with features but no manifest"""
        task_id = 'test-task-001'
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'features': ['Feature1', 'Feature2'],
            'prd_analysis': 'Test analysis'
        }
        
        result = await dev_agent._handle_deploy_task(task_id, requirements)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'completed'
        assert result['action'] == 'deploy'
    
    @pytest.mark.asyncio
    async def test_handle_deploy_task_build_failure(self, dev_agent):
        """Test _handle_deploy_task with Docker build failure"""
        task_id = 'test-task-001'
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'source_dir': '/path/to/source'
        }
        
        # Mock docker_manager to return build failure
        dev_agent.docker_manager = AsyncMock()
        dev_agent.docker_manager.build_image.return_value = {
            'status': 'failed',
            'error': 'Docker build failed'
        }
        
        result = await dev_agent._handle_deploy_task(task_id, requirements)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert result['action'] == 'deploy'
        assert 'Docker build failed' in result['error']
    
    @pytest.mark.asyncio
    async def test_handle_deploy_task_deploy_failure(self, dev_agent):
        """Test _handle_deploy_task with Docker deploy failure"""
        task_id = 'test-task-001'
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'source_dir': '/path/to/source'
        }
        
        # Mock docker_manager to return build success but deploy failure
        dev_agent.docker_manager = AsyncMock()
        dev_agent.docker_manager.build_image.return_value = {'status': 'success'}
        dev_agent.docker_manager.deploy_container.return_value = {
            'status': 'failed',
            'error': 'Container deployment failed'
        }
        
        result = await dev_agent._handle_deploy_task(task_id, requirements)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert result['action'] == 'deploy'
        assert 'Container deployment failed' in result['error']
    
    @pytest.mark.asyncio
    async def test_handle_deploy_task_exception(self, dev_agent):
        """Test _handle_deploy_task exception handling"""
        task_id = 'test-task-001'
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'source_dir': '/path/to/source'
        }
        
        # Mock docker_manager to raise exception
        dev_agent.docker_manager = AsyncMock()
        dev_agent.docker_manager.build_image.side_effect = Exception("Docker operation failed")
        
        result = await dev_agent._handle_deploy_task(task_id, requirements)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert result['action'] == 'deploy'
        assert 'error' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_task_routing_unknown_action(self, dev_agent):
        """Test task routing for unknown action."""
        requirements = {
            "action": "unknown_action",
            "description": "Test unknown action"
        }
        
        result = await dev_agent._handle_development_task({
            "task_id": "test-unknown-001",
            "requirements": requirements
        })
        
        assert result["status"] == "completed"
        assert result["action"] == "technical"
    
    # ============================================================================
    # COMPREHENSIVE TESTS (from test_dev_agent_comprehensive.py)
    # ============================================================================
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_archive_task_success(self, dev_agent):
        """Test successful archive task handling."""
        task_id = "test-archive-001"
        requirements = {
            "application": "TestApp",
            "version": "1.0.0"
        }
        
        # Mock version manager operations
        dev_agent.version_manager.archive_existing_version = AsyncMock(return_value={
            'status': 'success',
            'archived_version': '1.0.0',
            'archive_dir': '/archive/testapp-1.0.0'
        })
        
        result = await dev_agent._handle_archive_task(task_id, requirements)
        
        assert result["status"] == "completed"
        assert result["task_id"] == task_id
        assert result["action"] == "archive"
        assert result["app_name"] == "TestApp"
        dev_agent.version_manager.archive_existing_version.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_archive_task_failure(self, dev_agent):
        """Test archive task handling with failure."""
        task_id = "test-archive-002"
        requirements = {
            "application": "TestApp",
            "version": "1.0.0"
        }
        
        # Mock version manager to return failure
        dev_agent.version_manager.archive_existing_version = AsyncMock(return_value={
            'status': 'error',
            'error': 'Archive failed'
        })
        
        result = await dev_agent._handle_archive_task(task_id, requirements)
        
        assert result["status"] == "error"
        assert result["task_id"] == task_id
        assert "Archive failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_handle_archive_task_exception(self, dev_agent):
        """Test _handle_archive_task exception handling"""
        task_id = 'test-task-001'
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0'
        }
        
        # Mock version_manager to raise exception
        dev_agent.version_manager = AsyncMock()
        dev_agent.version_manager.archive_existing_version.side_effect = Exception("Archive failed")
        
        result = await dev_agent._handle_archive_task(task_id, requirements)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert result['action'] == 'archive'
        assert 'error' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_technical_task_success(self, dev_agent):
        """Test successful technical task handling."""
        task_id = "test-technical-001"
        requirements = {
            "description": "Test technical task",
            "complexity": 0.5
        }
        
        # Mock TaskSpec creation
        mock_task_spec = TaskSpec(
            app_name="TechnicalTask",
            version="1.0.0",
            run_id="test-run",
            prd_analysis="Technical task analysis",
            features=["feature1"],
            constraints={},
            success_criteria=["Task completes"]
        )
        
        with patch.object(dev_agent, '_create_technical_task_spec', return_value=mock_task_spec):
            result = await dev_agent._handle_technical_task(task_id, requirements)
        
        assert result["status"] == "completed"
        assert result["task_id"] == task_id
        assert "technical task" in result["message"].lower()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_technical_task_failure(self, dev_agent):
        """Test technical task handling with failure."""
        task_id = "test-technical-002"
        requirements = {
            "description": "Test technical task",
            "complexity": 0.5
        }
        
        # Mock TaskSpec creation to fail
        with patch.object(dev_agent, '_create_technical_task_spec', side_effect=Exception("TaskSpec failed")):
            result = await dev_agent._handle_technical_task(task_id, requirements)
        
        assert result["status"] == "error"
        assert result["task_id"] == task_id
        assert "TaskSpec failed" in result["error"]
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_technical_task_spec_success(self, dev_agent):
        """Test successful TaskSpec creation."""
        requirements = {
            "description": "Test technical task",
            "complexity": 0.5
        }
        
        # Mock LLM response
        mock_yaml_response = """
        app_name: TechnicalTask
        version: 1.0.0
        run_id: test-run
        prd_analysis: Test analysis
        features:
          - feature1
          - feature2
        constraints: {}
        success_criteria:
          - Task completes
        """
        
        # Mock the LLM client to avoid network calls
        dev_agent.llm_client.complete = AsyncMock(return_value=mock_yaml_response)
        
        task_spec = await dev_agent._create_technical_task_spec(requirements)
        
        assert isinstance(task_spec, TaskSpec)
        assert task_spec.app_name == "TechnicalTask"
        assert task_spec.version == "1.0.0"
        assert len(task_spec.features) == 2
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_technical_task_spec_fallback(self, dev_agent):
        """Test TaskSpec creation with fallback."""
        requirements = {
            "description": "Test technical task",
            "complexity": 0.5
        }
        
        # Mock LLM response to fail
        with patch.object(dev_agent, 'llm_response', side_effect=Exception("LLM failed")):
            task_spec = await dev_agent._create_technical_task_spec(requirements)
        
        assert isinstance(task_spec, TaskSpec)
        assert task_spec.app_name == "TechnicalTask"  # Fallback name
        assert "Technical task" in task_spec.prd_analysis
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_development_task(self, dev_agent):
        """Test processing development task."""
        task = {
            "task_id": "test-dev-001",
            "task_type": "development",
            "requirements": {
                "action": "archive",
                "app_name": "TestApp"
            }
        }
        
        # Mock the development task handler
        with patch.object(dev_agent, '_handle_development_task', return_value={"status": "completed"}) as mock_handler:
            result = await dev_agent.process_task(task)
        
        assert result["status"] == "completed"
        mock_handler.assert_called_once_with(task)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_unknown_type(self, dev_agent):
        """Test processing unknown task type."""
        task = {
            "task_id": "test-unknown-001",
            "task_type": "unknown",
            "requirements": {}
        }
        
        with patch.object(dev_agent, '_handle_generic_task', return_value={"status": "completed"}) as mock_handler:
            result = await dev_agent.process_task(task)
        
        assert result["status"] == "completed"
        mock_handler.assert_called_once_with(task)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_exception(self, dev_agent):
        """Test processing task with exception."""
        task = {
            "task_id": "test-error-001",
            "task_type": "development",
            "requirements": {}
        }
        
        # Mock handler to raise exception
        with patch.object(dev_agent, '_handle_development_task', side_effect=Exception("Handler failed")):
            result = await dev_agent.process_task(task)
        
        assert result["status"] == "error"
        assert result["task_id"] == "test-error-001"
        assert "Handler failed" in result["error"]
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_development_task_archive(self, dev_agent):
        """Test development task routing to archive."""
        task = {
            "task_id": "test-archive-001",
            "requirements": {
                "action": "archive",
                "app_name": "TestApp"
            }
        }
        
        with patch.object(dev_agent, '_handle_archive_task', return_value={"status": "completed"}) as mock_handler:
            result = await dev_agent._handle_development_task(task)
        
        assert result["status"] == "completed"
        mock_handler.assert_called_once_with("test-archive-001", task["requirements"])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_development_task_design_manifest(self, dev_agent):
        """Test development task routing to design_manifest."""
        task = {
            "task_id": "test-design-001",
            "requirements": {
                "action": "design_manifest",
                "app_name": "TestApp"
            }
        }
        
        with patch.object(dev_agent, '_handle_design_manifest_task', return_value={"status": "completed"}) as mock_handler:
            result = await dev_agent._handle_development_task(task)
        
        assert result["status"] == "completed"
        mock_handler.assert_called_once_with("test-design-001", task["requirements"])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_development_task_build(self, dev_agent):
        """Test development task routing to build."""
        task = {
            "task_id": "test-build-001",
            "requirements": {
                "action": "build",
                "app_name": "TestApp"
            }
        }
        
        with patch.object(dev_agent, '_handle_build_task', return_value={"status": "completed"}) as mock_handler:
            result = await dev_agent._handle_development_task(task)
        
        assert result["status"] == "completed"
        mock_handler.assert_called_once_with("test-build-001", task["requirements"])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_development_task_deploy(self, dev_agent):
        """Test development task routing to deploy."""
        task = {
            "task_id": "test-deploy-001",
            "requirements": {
                "action": "deploy",
                "app_name": "TestApp"
            }
        }
        
        with patch.object(dev_agent, '_handle_deploy_task', return_value={"status": "completed"}) as mock_handler:
            result = await dev_agent._handle_development_task(task)
        
        assert result["status"] == "completed"
        mock_handler.assert_called_once_with("test-deploy-001", task["requirements"])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_development_task_technical(self, dev_agent):
        """Test development task routing to technical."""
        task = {
            "task_id": "test-technical-001",
            "requirements": {
                "action": "unknown_action",
                "app_name": "TestApp"
            }
        }
        
        with patch.object(dev_agent, '_handle_technical_task', return_value={"status": "completed"}) as mock_handler:
            result = await dev_agent._handle_development_task(task)
        
        assert result["status"] == "completed"
        mock_handler.assert_called_once_with("test-technical-001", task["requirements"])
    
    @pytest.mark.unit
    def test_dev_agent_initialization(self):
        """Test DevAgent initialization."""
        agent = DevAgent("test-dev-agent")
        
        assert agent.name == "test-dev-agent"
        assert agent.agent_type == "code"
        assert agent.reasoning_style == "deductive"
        assert hasattr(agent, 'app_builder')
        assert hasattr(agent, 'docker_manager')
        assert hasattr(agent, 'version_manager')
        assert hasattr(agent, 'file_manager')
    
    @pytest.mark.unit
    def test_current_task_requirements_storage(self, dev_agent):
        """Test that current task requirements are stored."""
        requirements = {"action": "build", "app_name": "TestApp"}
        
        # Simulate task processing
        dev_agent.current_task_requirements = requirements
        
        assert dev_agent.current_task_requirements == requirements
        assert dev_agent.current_task_requirements["action"] == "build"
        assert dev_agent.current_task_requirements["app_name"] == "TestApp"
    
    @pytest.mark.asyncio
    async def test_extract_prd_analysis_from_communication_log_success(self, dev_agent):
        """Test _extract_prd_analysis_from_communication_log with successful extraction"""
        # Add PRD analysis to communication log
        dev_agent.communication_log = [
            {
                'message_type': 'llm_reasoning',
                'description': 'Some other message',
                'full_response': 'Other response'
            },
            {
                'message_type': 'llm_reasoning',
                'description': 'PRD Analysis: Test analysis content',
                'full_response': 'Full PRD analysis response'
            }
        ]
        
        result = dev_agent._extract_prd_analysis_from_communication_log()
        assert result == 'Full PRD analysis response'
    
    @pytest.mark.asyncio
    async def test_extract_prd_analysis_from_communication_log_fallback(self, dev_agent):
        """Test _extract_prd_analysis_from_communication_log with fallback to description"""
        # Add PRD analysis to communication log without full_response
        dev_agent.communication_log = [
            {
                'message_type': 'llm_reasoning',
                'description': 'PRD Analysis: Test analysis content'
            }
        ]
        
        result = dev_agent._extract_prd_analysis_from_communication_log()
        assert result == 'PRD Analysis: Test analysis content'
    
    @pytest.mark.asyncio
    async def test_extract_prd_analysis_from_communication_log_not_found(self, dev_agent):
        """Test _extract_prd_analysis_from_communication_log when no PRD analysis found"""
        # Empty communication log
        dev_agent.communication_log = []
        
        result = dev_agent._extract_prd_analysis_from_communication_log()
        assert result == "No PRD analysis available - generating generic application"
    
    @pytest.mark.asyncio
    async def test_extract_prd_analysis_from_communication_log_exception(self, dev_agent):
        """Test _extract_prd_analysis_from_communication_log with exception handling"""
        # Mock communication_log to raise exception
        dev_agent.communication_log = None
        
        result = dev_agent._extract_prd_analysis_from_communication_log()
        assert result == "Error extracting PRD analysis - generating generic application"
    
    @pytest.mark.asyncio
    async def test_handle_code_generation_task_success(self, dev_agent):
        """Test _handle_code_generation_task success path"""
        task = {
            'task_id': 'test-task-001',
            'requirements': {
                'application': 'TestApp',
                'version': '1.0.0',
                'features': ['Feature1', 'Feature2']
            }
        }
        
        # Mock code_generator
        dev_agent.code_generator = AsyncMock()
        dev_agent.code_generator.generate_custom_files.return_value = [
            {'file_path': 'test.html', 'content': '<html></html>', 'directory': None}
        ]
        
        result = await dev_agent._handle_code_generation_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'completed'
        assert result['action'] == 'code_generation'
        assert 'created_files' in result
    
    @pytest.mark.asyncio
    async def test_handle_code_generation_task_exception(self, dev_agent):
        """Test _handle_code_generation_task exception handling"""
        task = {
            'task_id': 'test-task-001',
            'requirements': {
                'application': 'TestApp',
                'version': '1.0.0',
                'features': ['Feature1', 'Feature2']
            }
        }
        
        # Mock code_generator to raise exception
        dev_agent.code_generator = AsyncMock()
        dev_agent.code_generator.generate_custom_files.side_effect = Exception("Code generation failed")
        
        result = await dev_agent._handle_code_generation_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert result['action'] == 'code_generation'
        assert 'error' in result
    
    @pytest.mark.asyncio
    async def test_handle_docker_task_build_success(self, dev_agent):
        """Test _handle_docker_task with build action"""
        task = {
            'task_id': 'test-task-001',
            'requirements': {
                'docker_action': 'build',
                'application': 'TestApp',
                'version': '1.0.0',
                'source_dir': '/path/to/source'
            }
        }
        
        # Mock docker_manager
        dev_agent.docker_manager = AsyncMock()
        dev_agent.docker_manager.build_image.return_value = {'status': 'completed'}
        
        result = await dev_agent._handle_docker_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'completed'
        assert result['action'] == 'docker_build'
        assert 'result' in result
    
    @pytest.mark.asyncio
    async def test_handle_docker_task_deploy_success(self, dev_agent):
        """Test _handle_docker_task with deploy action"""
        task = {
            'task_id': 'test-task-001',
            'requirements': {
                'docker_action': 'deploy',
                'application': 'TestApp',
                'version': '1.0.0'
            }
        }
        
        # Mock docker_manager
        dev_agent.docker_manager = AsyncMock()
        dev_agent.docker_manager.deploy_container.return_value = {'status': 'completed'}
        
        result = await dev_agent._handle_docker_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'completed'
        assert result['action'] == 'docker_deploy'
        assert 'result' in result
    
    @pytest.mark.asyncio
    async def test_handle_docker_task_status_success(self, dev_agent):
        """Test _handle_docker_task with status action"""
        task = {
            'task_id': 'test-task-001',
            'requirements': {
                'docker_action': 'status',
                'container_name': 'test-container'
            }
        }
        
        # Mock docker_manager
        dev_agent.docker_manager = AsyncMock()
        dev_agent.docker_manager.get_container_status.return_value = {'status': 'running'}
        
        result = await dev_agent._handle_docker_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'running'
        assert result['action'] == 'docker_status'
        assert 'result' in result
    
    @pytest.mark.asyncio
    async def test_handle_docker_task_unknown_action(self, dev_agent):
        """Test _handle_docker_task with unknown action"""
        task = {
            'task_id': 'test-task-001',
            'requirements': {
                'docker_action': 'unknown_action',
                'application': 'TestApp',
                'version': '1.0.0'
            }
        }
        
        result = await dev_agent._handle_docker_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert 'error' in result
    
    @pytest.mark.asyncio
    async def test_handle_docker_task_exception(self, dev_agent):
        """Test _handle_docker_task exception handling"""
        task = {
            'task_id': 'test-task-001',
            'requirements': {
                'docker_action': 'build',
                'application': 'TestApp',
                'version': '1.0.0'
            }
        }
        
        # Mock docker_manager to raise exception
        dev_agent.docker_manager = AsyncMock()
        dev_agent.docker_manager.build_image.side_effect = Exception("Docker build failed")
        
        result = await dev_agent._handle_docker_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert result['action'] == 'docker_operations'
        assert 'error' in result
    
    
    @pytest.mark.asyncio
    async def test_handle_version_task_detect_success(self, dev_agent):
        """Test _handle_version_task with detect action"""
        task = {
            'task_id': 'test-task-001',
            'requirements': {
                'version_action': 'detect',
                'source_dir': '/path/to/source'
            }
        }
        
        # Mock version_manager
        dev_agent.version_manager = AsyncMock()
        dev_agent.version_manager.detect_existing_version.return_value = '1.0.0'
        
        result = await dev_agent._handle_version_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'completed'
        assert result['action'] == 'version_detect'
        assert 'detected_version' in result
    
    @pytest.mark.asyncio
    async def test_handle_version_task_calculate_success(self, dev_agent):
        """Test _handle_version_task with calculate action"""
        task = {
            'task_id': 'test-task-001',
            'requirements': {
                'version_action': 'calculate',
                'framework_version': '1.0.0',
                'run_id': 'run-001'
            }
        }
        
        # Mock version_manager
        dev_agent.version_manager = AsyncMock()
        dev_agent.version_manager.calculate_new_version.return_value = '1.0.1'
        
        result = await dev_agent._handle_version_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'completed'
        assert result['action'] == 'version_calculate'
        assert 'new_version' in result
    
    @pytest.mark.asyncio
    async def test_handle_version_task_update_success(self, dev_agent):
        """Test _handle_version_task with update action"""
        task = {
            'task_id': 'test-task-001',
            'requirements': {
                'version_action': 'update',
                'app_dir': '/path/to/app',
                'new_version': '2.0.0'
            }
        }
        
        # Mock version_manager
        dev_agent.version_manager = AsyncMock()
        dev_agent.version_manager.update_version_in_files.return_value = {'status': 'completed'}
        
        result = await dev_agent._handle_version_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'completed'
        assert result['action'] == 'version_update'
        assert 'result' in result
    
    @pytest.mark.asyncio
    async def test_handle_version_task_unknown_action(self, dev_agent):
        """Test _handle_version_task with unknown action"""
        task = {
            'task_id': 'test-task-001',
            'requirements': {
                'version_action': 'unknown_action',
                'application': 'TestApp'
            }
        }
        
        result = await dev_agent._handle_version_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert 'error' in result
    
    @pytest.mark.asyncio
    async def test_handle_version_task_exception(self, dev_agent):
        """Test _handle_version_task exception handling"""
        task = {
            'task_id': 'test-task-001',
            'requirements': {
                'version_action': 'detect',
                'source_dir': '/path/to/source'
            }
        }
        
        # Mock version_manager to raise exception
        dev_agent.version_manager = AsyncMock()
        dev_agent.version_manager.detect_existing_version.side_effect = Exception("Version detect failed")
        
        result = await dev_agent._handle_version_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert result['action'] == 'version_management'
        assert 'error' in result
    
    @pytest.mark.asyncio
    async def test_handle_technical_task_success(self, dev_agent):
        """Test _handle_technical_task success path"""
        task_id = 'test-task-001'
        requirements = {
            'technical_type': 'database',
            'action': 'create_table',
            'specification': 'CREATE TABLE test (id INT)'
        }
        
        # Mock technical task handling
        with patch.object(dev_agent, '_create_technical_task_spec') as mock_create_spec:
            mock_task_spec = MagicMock()
            mock_task_spec.to_dict.return_value = {'app_name': 'TechnicalTask', 'features': []}
            mock_create_spec.return_value = mock_task_spec
            
            result = await dev_agent._handle_technical_task(task_id, requirements)
            
            assert result['task_id'] == 'test-task-001'
            assert result['status'] == 'completed'
            assert result['action'] == 'technical'
            assert 'task_spec' in result
    
    @pytest.mark.asyncio
    async def test_handle_technical_task_exception(self, dev_agent):
        """Test _handle_technical_task exception handling"""
        task_id = 'test-task-001'
        requirements = {
            'technical_type': 'database',
            'action': 'create_table',
            'specification': 'CREATE TABLE test (id INT)'
        }
        
        # Mock technical task handling to raise exception
        with patch.object(dev_agent, '_create_technical_task_spec') as mock_create_spec:
            mock_create_spec.side_effect = Exception("Technical task failed")
            
            result = await dev_agent._handle_technical_task(task_id, requirements)
            
            assert result['task_id'] == 'test-task-001'
            assert result['status'] == 'error'
            assert result['action'] == 'technical'
            assert 'error' in result
    
    @pytest.mark.asyncio
    async def test_create_technical_task_spec_success(self, dev_agent):
        """Test _create_technical_task_spec success path"""
        task_spec = {
            'technical_type': 'database',
            'action': 'create_table',
            'specification': 'CREATE TABLE test (id INT)'
        }
        
        # Mock LLM client to return valid YAML
        dev_agent.llm_client = AsyncMock()
        dev_agent.llm_client.complete.return_value = """
        app_name: DatabaseTask
        version: 1.0.0
        run_id: test-run-001
        prd_analysis: Database task specification
        features:
          - Create table functionality
          - Data validation
        constraints:
          database_type: PostgreSQL
        success_criteria:
          - Table created successfully
          - Data validation works
        """
        
        result = await dev_agent._create_technical_task_spec(task_spec)
        
        # Should return a TaskSpec object
        assert hasattr(result, 'app_name')
        assert hasattr(result, 'version')
        assert hasattr(result, 'features')
        assert result.app_name == 'DatabaseTask'
        assert len(result.features) == 2
    
    @pytest.mark.asyncio
    async def test_create_technical_task_spec_exception(self, dev_agent):
        """Test _create_technical_task_spec exception handling"""
        task_spec = {
            'technical_type': 'database',
            'action': 'create_table',
            'specification': 'CREATE TABLE test (id INT)'
        }
        
        # Mock LLM client to raise exception
        dev_agent.llm_client = AsyncMock()
        dev_agent.llm_client.complete.side_effect = Exception("LLM call failed")
        
        result = await dev_agent._create_technical_task_spec(task_spec)
        
        # Should return a TaskSpec object (fallback)
        assert hasattr(result, 'app_name')
        assert hasattr(result, 'version')
        assert hasattr(result, 'features')
    
    @pytest.mark.asyncio
    async def test_create_technical_task_spec_fallback(self, dev_agent):
        """Test _create_technical_task_spec fallback when LLM fails"""
        task_spec = {
            'technical_type': 'database',
            'action': 'create_table',
            'specification': 'CREATE TABLE test (id INT)'
        }
        
        # Mock LLM client to return None
        dev_agent.llm_client = AsyncMock()
        dev_agent.llm_client.complete.return_value = None
        
        result = await dev_agent._create_technical_task_spec(task_spec)
        
        # Should return a TaskSpec object (fallback)
        assert hasattr(result, 'app_name')
        assert hasattr(result, 'version')
        assert hasattr(result, 'features')
    
    @pytest.mark.asyncio
    async def test_process_task_code_generation_type(self, dev_agent):
        """Test process_task with code_generation task type"""
        task = {
            'task_id': 'test-task-001',
            'task_type': 'code_generation',
            'requirements': {
                'application': 'TestApp',
                'version': '1.0.0',
                'features': ['Feature1']
            }
        }
        
        # Mock code_generator
        dev_agent.code_generator = AsyncMock()
        dev_agent.code_generator.generate_custom_files.return_value = [
            {'file_path': 'test.html', 'content': '<html></html>', 'directory': None}
        ]
        
        result = await dev_agent.process_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'completed'
        assert result['action'] == 'code_generation'
    
    @pytest.mark.asyncio
    async def test_process_task_docker_operations_type(self, dev_agent):
        """Test process_task with docker_operations task type"""
        task = {
            'task_id': 'test-task-001',
            'task_type': 'docker_operations',
            'requirements': {
                'docker_action': 'build',
                'application': 'TestApp',
                'version': '1.0.0'
            }
        }
        
        # Mock docker_manager
        dev_agent.docker_manager = AsyncMock()
        dev_agent.docker_manager.build_image.return_value = {'status': 'success'}
        
        result = await dev_agent.process_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'success'
        assert result['action'] == 'docker_build'
    
    @pytest.mark.asyncio
    async def test_process_task_version_management_type(self, dev_agent):
        """Test process_task with version_management task type"""
        task = {
            'task_id': 'test-task-001',
            'task_type': 'version_management',
            'requirements': {
                'version_action': 'detect',
                'source_dir': '/path/to/source'
            }
        }
        
        # Mock version_manager
        dev_agent.version_manager = AsyncMock()
        dev_agent.version_manager.detect_existing_version.return_value = '1.0.0'
        
        result = await dev_agent.process_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'completed'
        assert result['action'] == 'version_detect'
    
    @pytest.mark.asyncio
    async def test_process_task_unknown_task_type(self, dev_agent):
        """Test process_task with unknown task type"""
        task = {
            'task_id': 'test-task-001',
            'task_type': 'unknown_type',
            'requirements': {}
        }
        
        result = await dev_agent.process_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'completed'
        assert result['action'] == 'generic'
        assert 'message' in result
    
    @pytest.mark.asyncio
    async def test_handle_generic_task_governance_rejection(self, dev_agent):
        """Test _handle_generic_task with governance task rejection"""
        task = {
            'task_id': 'test-task-001',
            'task_type': 'governance',
            'requirements': {}
        }
        
        result = await dev_agent.process_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'rejected'
        assert result['action'] == 'governance_rejection'
        assert 'Development agent cannot handle governance tasks' in result['message']
        
    @pytest.mark.asyncio
    async def test_process_task_exception(self, dev_agent):
        """Test process_task exception handling"""
        task = {
            'task_id': 'test-task-001',
            'task_type': 'development',
            'requirements': {}
        }
        
        # Mock _handle_development_task to raise exception
        with patch.object(dev_agent, '_handle_development_task') as mock_handle:
            mock_handle.side_effect = Exception("Task handling failed")
            
            result = await dev_agent.process_task(task)
            
            assert result['task_id'] == 'test-task-001'
            assert result['status'] == 'error'
            assert 'error' in result
