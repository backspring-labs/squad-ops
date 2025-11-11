"""
Comprehensive unit tests for DevAgent - covering JSON workflow and all methods.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, Any

from agents.roles.dev.agent import DevAgent
from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse
from tests.utils.mock_helpers import (
    create_sample_build_artifact_request,
    create_sample_agent_response,
    MockFileManager, MockDockerManager, MockOllamaResponse
)


class TestDevAgent:
    """Comprehensive tests for DevAgent covering JSON workflow and all methods."""
    
    @pytest.fixture
    def dev_agent(self, mock_unified_config):
        """Create DevAgent instance for testing."""
        with patch('config.unified_config.get_config', return_value=mock_unified_config):
            agent = DevAgent("test-dev-agent")
            # Mock capability_loader.execute to avoid real capability execution
            agent.capability_loader = MagicMock()
            agent.capability_loader.execute = AsyncMock()
            return agent
    
    # ============================================================================
    # JSON WORKFLOW TESTS (from test_dev_agent_json_handlers.py)
    # ============================================================================
    
    @pytest.fixture
    def design_manifest_task(self):
        """Sample design_manifest task with flattened requirements."""
        return {
            "task_id": "test-design-001",
            "type": "development",
            "requirements": {
                "action": "design_manifest",
                "app_name": "TestApp",
                "version": "1.0.0",
                "run_id": "TEST-001",
                "prd_analysis": "Test application",
                "features": ["Feature 1", "Feature 2"],
                "constraints": {"framework": "vanilla_js"},
                "success_criteria": ["Application loads"]
            }
        }
    
    @pytest.fixture
    def build_task_with_manifest(self):
        """Sample build task with manifest and flattened requirements."""
        return {
            "task_id": "test-build-001",
            "type": "development",
            "requirements": {
                "action": "build",
                "app_name": "TestApp",
                "version": "1.0.0",
                "run_id": "TEST-001",
                "manifest": {
                    "architecture_type": "spa_web_app",
                    "framework": "vanilla_js",
                    "files": []
                }
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
    async def test_handle_agent_request_build_artifact(self, dev_agent):
        """Test handle_agent_request for build.artifact capability"""
        request = create_sample_build_artifact_request(task_id="test-001")
        
        # Mock capability_loader.execute to return build.artifact result
        dev_agent.capability_loader.execute.return_value = {
            "artifact_uri": "/artifacts/TestApp/test-001",
            "commit": "mock_commit_hash",
            "files_generated": [{"type": "file", "path": "index.html", "content": "<html></html>"}],
            "manifest_uri": "/artifacts/TestApp/test-001/manifest.json"
        }
        
        response = await dev_agent.handle_agent_request(request)
        
        assert isinstance(response, AgentResponse)
        assert response.status == "ok"
        assert "artifact_uri" in response.result
        assert "commit" in response.result
        assert "files_generated" in response.result
        assert "manifest_uri" in response.result
        assert response.idempotency_key is not None
        assert response.timing is not None
        dev_agent.capability_loader.execute.assert_called_once_with('build.artifact', dev_agent, request.payload.get('requirements', request.payload))
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_agent_request_unknown_capability(self, dev_agent):
        """Test handle_agent_request with unknown capability"""
        request = AgentRequest(
            action="test.run",  # Valid format but not in Dev's capabilities
            payload={},
            metadata={"pid": "PID-001", "ecid": "ECID-001"}
        )
        
        # Mock capability_loader.execute to raise ValueError for unknown capability
        dev_agent.capability_loader.execute.side_effect = ValueError("Capability 'test.run' not found in capability map")
        
        response = await dev_agent.handle_agent_request(request)
        
        assert isinstance(response, AgentResponse)
        assert response.status == "error"
        assert response.error is not None
        assert response.error.code == "UNKNOWN_CAPABILITY"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_design_manifest_task_success(self, dev_agent, design_manifest_task):
        """Test successful design_manifest task handling via capability."""
        # Mock capability_loader.execute to return manifest.generate result
        mock_result = {
            "status": "completed",
            "task_id": "test-design-001",
            "action": "design_manifest",
            "manifest": {
                "architecture_type": "spa_web_app",
                "framework": "vanilla_js",
                "files": []
            },
            "created_files": ["index.html"]
        }
        dev_agent.capability_loader.execute.return_value = mock_result
        
        result = await dev_agent.process_task(design_manifest_task)
        
        assert result["status"] == "completed"
        assert result["task_id"] == "test-design-001"
        assert result["action"] == "design_manifest"
        assert "manifest" in result
        dev_agent.capability_loader.execute.assert_called_once_with('manifest.generate', dev_agent, "test-design-001", design_manifest_task["requirements"])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_design_manifest_task_missing_requirements(self, dev_agent):
        """Test design_manifest task with missing build requirements via capability."""
        task = {
            "task_id": "test-001",
            "type": "development",
            "requirements": {
                "action": "design_manifest"
                # Missing app_name, features, etc. (will use defaults)
            }
        }
        
        # Mock capability_loader.execute to return success with defaults
        dev_agent.capability_loader.execute.return_value = {
            "status": "completed",
            "task_id": "test-001",
            "action": "design_manifest",
            "manifest": {"architecture_type": "spa_web_app"},
            "created_files": []
        }
        
        result = await dev_agent.process_task(task)
        
        # Should succeed with default values
        assert result["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_handle_design_manifest_task_exception(self, dev_agent):
        """Test design_manifest task exception handling via capability"""
        task = {
            'task_id': 'test-task-001',
            'type': 'development',
            'requirements': {
                'action': 'design_manifest',
                'app_name': 'TestApp',
                'version': '1.0.0',
                'run_id': 'test-run',
                'prd_analysis': 'Test analysis',
                'features': ['feature1'],
                'constraints': {},
                'success_criteria': ['Task completes']
            }
        }
        
        # Mock capability_loader.execute to raise exception
        dev_agent.capability_loader.execute.side_effect = Exception("Manifest generation failed")
        
        result = await dev_agent.process_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert 'error' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_build_task_with_manifest_json_workflow(self, dev_agent, build_task_with_manifest):
        """Test build task with manifest using JSON workflow via capability."""
        # Mock capability_loader.execute to return docker.build result
        mock_result = {
            "status": "completed",
            "task_id": "test-build-001",
            "action": "build",
            "created_files": ["app.py", "index.html"],
            "image": "test-app",
            "image_version": "test-app:1.0.0"
        }
        dev_agent.capability_loader.execute.return_value = mock_result
        
        result = await dev_agent.process_task(build_task_with_manifest)
        
        assert result["status"] == "completed"
        assert result["task_id"] == "test-build-001"
        assert result["action"] == "build"
        assert "created_files" in result
        assert len(result["created_files"]) == 2
        dev_agent.capability_loader.execute.assert_called_once_with('docker.build', dev_agent, "test-build-001", build_task_with_manifest["requirements"])
    
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_build_task_file_creation(self, dev_agent, build_task_with_manifest):
        """Test that build task creates files correctly via capability."""
        # Mock capability_loader.execute to return docker.build result with created files
        mock_result = {
            "status": "completed",
            "task_id": "test-build-001",
            "action": "build",
            "created_files": ["app.py", "index.html"],
            "image": "test-app",
            "image_version": "test-app:1.0.0"
        }
        dev_agent.capability_loader.execute.return_value = mock_result
        
        result = await dev_agent.process_task(build_task_with_manifest)
        
        # Check that files were created (returned in result)
        assert "created_files" in result
        assert len(result["created_files"]) == 2
        assert "app.py" in result["created_files"]
        assert "index.html" in result["created_files"]
    
    @pytest.mark.asyncio
    async def test_handle_build_task_missing_manifest(self, dev_agent):
        """Test build task with missing manifest via capability"""
        task = {
            'task_id': 'test-task-001',
            'type': 'development',
            'requirements': {
                'action': 'build',
                'application': 'TestApp',
                'version': '1.0.0'
                # Missing manifest
            }
        }
        
        # Mock capability_loader.execute to return error for missing manifest
        dev_agent.capability_loader.execute.return_value = {
            'task_id': 'test-task-001',
            'status': 'error',
            'action': 'build',
            'error': 'Manifest is required for build task'
        }
        
        result = await dev_agent.process_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert result['action'] == 'build'
        assert 'Manifest is required' in result['error']
    
    @pytest.mark.asyncio
    async def test_handle_build_task_exception(self, dev_agent):
        """Test build task exception handling via capability"""
        task = {
            'task_id': 'test-task-001',
            'type': 'development',
            'requirements': {
                'action': 'build',
                'application': 'TestApp',
                'version': '1.0.0',
                'manifest': {
                    'app_name': 'TestApp',
                    'version': '1.0.0',
                    'features': ['Feature1']
                }
            }
        }
        
        # Mock capability_loader.execute to raise exception
        dev_agent.capability_loader.execute.side_effect = Exception("File generation failed")
        
        result = await dev_agent.process_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert 'error' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_deploy_task_with_source_dir(self, dev_agent, deploy_task):
        """Test deploy task with source directory via capability."""
        # Mock capability_loader.execute to return docker.deploy result
        mock_result = {
            "status": "completed",
            "task_id": "test-deploy-001",
            "action": "deploy",
            "container_name": "test-app-container",
            "image": "test-app:1.0.0"
        }
        dev_agent.capability_loader.execute.return_value = mock_result
        
        result = await dev_agent.process_task(deploy_task)
        
        assert result["status"] == "completed"
        assert result["task_id"] == "test-deploy-001"
        assert result["action"] == "deploy"
        dev_agent.capability_loader.execute.assert_called_once_with('docker.deploy', dev_agent, "test-deploy-001", deploy_task["requirements"])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_deploy_task_with_source_fallback(self, dev_agent, deploy_task):
        """Test deploy task with source fallback via capability."""
        # Mock capability_loader.execute to return docker.deploy result
        mock_result = {
            "status": "completed",
            "task_id": "test-deploy-001",
            "action": "deploy",
            "container_name": "test-app-container",
            "image": "test-app:1.0.0"
        }
        dev_agent.capability_loader.execute.return_value = mock_result
        
        result = await dev_agent.process_task(deploy_task)
        
        assert result["status"] == "completed"
        assert result["task_id"] == "test-deploy-001"
        assert result["action"] == "deploy"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_deploy_task_missing_source(self, dev_agent):
        """Test deploy task with missing source via capability."""
        task = {
            "task_id": "test-deploy-003",
            "type": "development",
            "requirements": {
                "action": "deploy",
                "app_name": "test-app"
                # Missing source_dir
            }
        }
        
        # Mock capability_loader.execute to return success (capability handles missing source)
        dev_agent.capability_loader.execute.return_value = {
            "status": "completed",
            "task_id": "test-deploy-003",
            "action": "deploy",
            "container_name": "test-app-container"
        }
        
        result = await dev_agent.process_task(task)
        
        assert result["status"] == "completed"
        assert result["task_id"] == "test-deploy-003"
        assert result["action"] == "deploy"
    
    @pytest.mark.asyncio
    async def test_handle_deploy_task_with_features(self, dev_agent):
        """Test deploy task with features but no manifest via capability"""
        task = {
            'task_id': 'test-task-001',
            'type': 'development',
            'requirements': {
                'action': 'deploy',
                'application': 'TestApp',
                'version': '1.0.0',
                'features': ['Feature1', 'Feature2'],
                'prd_analysis': 'Test analysis'
            }
        }
        
        # Mock capability_loader.execute to return success
        dev_agent.capability_loader.execute.return_value = {
            'task_id': 'test-task-001',
            'status': 'completed',
            'action': 'deploy',
            'container_name': 'test-app-container'
        }
        
        result = await dev_agent.process_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'completed'
        assert result['action'] == 'deploy'
    
    @pytest.mark.asyncio
    async def test_handle_deploy_task_build_failure(self, dev_agent):
        """Test deploy task with Docker build failure via capability"""
        task = {
            'task_id': 'test-task-001',
            'type': 'development',
            'requirements': {
                'action': 'deploy',
                'application': 'TestApp',
                'version': '1.0.0',
                'source_dir': '/path/to/source'
            }
        }
        
        # Mock capability_loader.execute to return build failure
        dev_agent.capability_loader.execute.return_value = {
            'task_id': 'test-task-001',
            'status': 'error',
            'action': 'deploy',
            'error': 'Docker build failed'
        }
        
        result = await dev_agent.process_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert result['action'] == 'deploy'
        assert 'Docker build failed' in result['error']
    
    @pytest.mark.asyncio
    async def test_handle_deploy_task_deploy_failure(self, dev_agent):
        """Test deploy task with Docker deploy failure via capability"""
        task = {
            'task_id': 'test-task-001',
            'type': 'development',
            'requirements': {
                'action': 'deploy',
                'application': 'TestApp',
                'version': '1.0.0',
                'source_dir': '/path/to/source'
            }
        }
        
        # Mock capability_loader.execute to return deploy failure
        dev_agent.capability_loader.execute.return_value = {
            'task_id': 'test-task-001',
            'status': 'error',
            'action': 'deploy',
            'error': 'Container deployment failed'
        }
        
        result = await dev_agent.process_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert result['action'] == 'deploy'
        assert 'Container deployment failed' in result['error']
    
    @pytest.mark.asyncio
    async def test_handle_deploy_task_exception(self, dev_agent):
        """Test deploy task exception handling via capability"""
        task = {
            'task_id': 'test-task-001',
            'type': 'development',
            'requirements': {
                'action': 'deploy',
                'application': 'TestApp',
                'version': '1.0.0',
                'source_dir': '/path/to/source'
            }
        }
        
        # Mock capability_loader.execute to raise exception
        dev_agent.capability_loader.execute.side_effect = Exception("Docker operation failed")
        
        result = await dev_agent.process_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert 'error' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_task_routing_unknown_action(self, dev_agent):
        """Test task routing for unknown action via capability."""
        task = {
            "task_id": "test-unknown-001",
            "type": "development",
            "requirements": {
                "action": "unknown_action",
                "description": "Test unknown action"
            }
        }
        
        # Mock capability_loader.execute to return error for unknown action
        dev_agent.capability_loader.execute.return_value = {
            "status": "error",
            "task_id": "test-unknown-001",
            "error": "Unknown action: unknown_action"
        }
        
        result = await dev_agent.process_task(task)
        
        assert result["status"] == "error"
        assert "Unknown action" in result["error"]
    
    # ============================================================================
    # COMPREHENSIVE TESTS (from test_dev_agent_comprehensive.py)
    # ============================================================================
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_archive_task_success(self, dev_agent):
        """Test successful archive task handling via capability."""
        task = {
            "task_id": "test-archive-001",
            "type": "development",
            "requirements": {
                "action": "archive",
                "application": "TestApp",
                "version": "1.0.0"
            }
        }
        
        # Mock capability_loader.execute to return version.archive result
        mock_result = {
            'status': 'completed',
            'task_id': 'test-archive-001',
            'action': 'archive',
            'app_name': 'TestApp',
            'archived_version': '1.0.0',
            'archive_dir': '/archive/testapp-1.0.0'
        }
        dev_agent.capability_loader.execute.return_value = mock_result
        
        result = await dev_agent.process_task(task)
        
        assert result["status"] == "completed"
        assert result["task_id"] == "test-archive-001"
        assert result["action"] == "archive"
        assert result["app_name"] == "TestApp"
        dev_agent.capability_loader.execute.assert_called_once_with('version.archive', dev_agent, "test-archive-001", task["requirements"])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_archive_task_failure(self, dev_agent):
        """Test archive task handling with failure via capability."""
        task = {
            "task_id": "test-archive-002",
            "type": "development",
            "requirements": {
                "action": "archive",
                "application": "TestApp",
                "version": "1.0.0"
            }
        }
        
        # Mock capability_loader.execute to return failure
        dev_agent.capability_loader.execute.return_value = {
            'status': 'error',
            'task_id': 'test-archive-002',
            'action': 'archive',
            'error': 'Archive failed'
        }
        
        result = await dev_agent.process_task(task)
        
        assert result["status"] == "error"
        assert result["task_id"] == "test-archive-002"
        assert "Archive failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_handle_archive_task_exception(self, dev_agent):
        """Test archive task exception handling via capability"""
        task = {
            'task_id': 'test-task-001',
            'type': 'development',
            'requirements': {
                'action': 'archive',
                'application': 'TestApp',
                'version': '1.0.0'
            }
        }
        
        # Mock capability_loader.execute to raise exception
        dev_agent.capability_loader.execute.side_effect = Exception("Archive failed")
        
        result = await dev_agent.process_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert 'error' in result
    
    # Removed test_handle_technical_task_success - _handle_technical_task method removed
    # Technical tasks are not currently supported via capabilities
    
    # Removed test_handle_technical_task_failure - _handle_technical_task method removed
    # Technical tasks are not currently supported via capabilities
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_technical_requirements_success_legacy(self, dev_agent):
        """Test successful technical requirements creation (legacy test name)."""
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
        
        tech_requirements = await dev_agent._create_technical_requirements(requirements)
        
        assert isinstance(tech_requirements, dict)
        assert tech_requirements.get("app_name") == "TechnicalTask"
        assert tech_requirements.get("version") == "1.0.0"
        assert len(tech_requirements.get("features", [])) == 2
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_technical_requirements_fallback_legacy(self, dev_agent):
        """Test technical requirements creation with fallback (legacy test name)."""
        requirements = {
            "description": "Test technical task",
            "complexity": 0.5
        }
        
        # Mock LLM client to fail
        dev_agent.llm_client = AsyncMock()
        dev_agent.llm_client.complete.side_effect = Exception("LLM failed")
        
        tech_requirements = await dev_agent._create_technical_requirements(requirements)
        
        assert isinstance(tech_requirements, dict)
        assert tech_requirements.get("app_name") == "TechnicalTask"  # Fallback name
        assert "Technical task" in tech_requirements.get("prd_analysis", "")
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_development_task(self, dev_agent):
        """Test processing development task via capability."""
        task = {
            "task_id": "test-dev-001",
            "type": "development",
            "requirements": {
                "action": "archive",
                "app_name": "TestApp"
            }
        }
        
        # Mock capability_loader.execute to return success
        dev_agent.capability_loader.execute.return_value = {
            "status": "completed",
            "task_id": "test-dev-001",
            "action": "archive"
        }
        
        result = await dev_agent.process_task(task)
        
        assert result["status"] == "completed"
        dev_agent.capability_loader.execute.assert_called_once_with('version.archive', dev_agent, "test-dev-001", task["requirements"])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_unknown_type(self, dev_agent):
        """Test processing unknown task type."""
        task = {
            "task_id": "test-unknown-001",
            "type": "unknown",
            "requirements": {}
        }
        
        result = await dev_agent.process_task(task)
        
        assert result["status"] == "error"
        assert "Unknown task type" in result["error"]
    
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
        """Test development task routing to archive via capability."""
        task = {
            "task_id": "test-archive-001",
            "requirements": {
                "action": "archive",
                "app_name": "TestApp"
            }
        }
        
        # Mock capability_loader.execute to return success
        dev_agent.capability_loader.execute.return_value = {
            "status": "completed",
            "task_id": "test-archive-001",
            "action": "archive"
        }
        
        result = await dev_agent._handle_development_task(task)
        
        assert result["status"] == "completed"
        dev_agent.capability_loader.execute.assert_called_once_with('version.archive', dev_agent, "test-archive-001", task["requirements"])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_development_task_design_manifest(self, dev_agent):
        """Test development task routing to design_manifest via capability."""
        task = {
            "task_id": "test-design-001",
            "requirements": {
                "action": "design_manifest",
                "app_name": "TestApp"
            }
        }
        
        # Mock capability_loader.execute to return success
        dev_agent.capability_loader.execute.return_value = {
            "status": "completed",
            "task_id": "test-design-001",
            "action": "design_manifest"
        }
        
        result = await dev_agent._handle_development_task(task)
        
        assert result["status"] == "completed"
        dev_agent.capability_loader.execute.assert_called_once_with('manifest.generate', dev_agent, "test-design-001", task["requirements"])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_development_task_build(self, dev_agent):
        """Test development task routing to build via capability."""
        task = {
            "task_id": "test-build-001",
            "requirements": {
                "action": "build",
                "app_name": "TestApp"
            }
        }
        
        # Mock capability_loader.execute to return success
        dev_agent.capability_loader.execute.return_value = {
            "status": "completed",
            "task_id": "test-build-001",
            "action": "build"
        }
        
        result = await dev_agent._handle_development_task(task)
        
        assert result["status"] == "completed"
        dev_agent.capability_loader.execute.assert_called_once_with('docker.build', dev_agent, "test-build-001", task["requirements"])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_development_task_deploy(self, dev_agent):
        """Test development task routing to deploy via capability."""
        task = {
            "task_id": "test-deploy-001",
            "requirements": {
                "action": "deploy",
                "app_name": "TestApp"
            }
        }
        
        # Mock capability_loader.execute to return success
        dev_agent.capability_loader.execute.return_value = {
            "status": "completed",
            "task_id": "test-deploy-001",
            "action": "deploy"
        }
        
        result = await dev_agent._handle_development_task(task)
        
        assert result["status"] == "completed"
        dev_agent.capability_loader.execute.assert_called_once_with('docker.deploy', dev_agent, "test-deploy-001", task["requirements"])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_development_task_unknown_action(self, dev_agent):
        """Test development task routing to unknown action via capability."""
        task = {
            "task_id": "test-technical-001",
            "requirements": {
                "action": "unknown_action",
                "app_name": "TestApp"
            }
        }
        
        # Mock capability_loader.execute to return error for unknown action
        dev_agent.capability_loader.execute.return_value = {
            "status": "error",
            "task_id": "test-technical-001",
            "error": "Unknown action: unknown_action"
        }
        
        result = await dev_agent._handle_development_task(task)
        
        assert result["status"] == "error"
        assert "Unknown action" in result["error"]
    
    @pytest.mark.unit
    def test_dev_agent_initialization(self):
        """Test DevAgent initialization."""
        agent = DevAgent("test-dev-agent")
        
        assert agent.name == "test-dev-agent"
        assert agent.agent_type == "developer"
        assert agent.reasoning_style == "deductive"
        # Components are now loaded via capabilities - no direct attributes
        assert hasattr(agent, 'capability_loader')
        assert agent.capability_loader is not None
    
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
    
    # Removed tests for _handle_code_generation_task - method removed
    # Removed tests for _handle_docker_task - method removed
    # Removed tests for _handle_version_task - method removed
    # Removed tests for _handle_technical_task - method removed
    # These methods are no longer part of DevAgent - capabilities handle these operations
    
    @pytest.mark.asyncio
    async def test_create_technical_requirements_success(self, dev_agent):
        """Test _create_technical_requirements success path"""
        requirements = {
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
        
        result = await dev_agent._create_technical_requirements(requirements)
        
        # Should return a dict (requirements)
        assert isinstance(result, dict)
        assert result.get('app_name') == 'DatabaseTask'
        assert result.get('version') == '1.0.0'
        assert len(result.get('features', [])) == 2
    
    @pytest.mark.asyncio
    async def test_create_technical_requirements_exception(self, dev_agent):
        """Test _create_technical_requirements exception handling"""
        requirements = {
            'technical_type': 'database',
            'action': 'create_table',
            'specification': 'CREATE TABLE test (id INT)'
        }
        
        # Mock LLM client to raise exception
        dev_agent.llm_client = AsyncMock()
        dev_agent.llm_client.complete.side_effect = Exception("LLM call failed")
        
        result = await dev_agent._create_technical_requirements(requirements)
        
        # Should return a dict (fallback requirements)
        assert isinstance(result, dict)
        assert result.get('app_name') == 'TechnicalTask'
        assert result.get('version') == '1.0.0'
        assert isinstance(result.get('features'), list)
    
    @pytest.mark.asyncio
    async def test_create_technical_requirements_fallback(self, dev_agent):
        """Test _create_technical_requirements fallback when LLM fails"""
        requirements = {
            'technical_type': 'database',
            'action': 'create_table',
            'specification': 'CREATE TABLE test (id INT)'
        }
        
        # Mock LLM client to return None
        dev_agent.llm_client = AsyncMock()
        dev_agent.llm_client.complete.return_value = None
        
        result = await dev_agent._create_technical_requirements(requirements)
        
        # Should return a dict (fallback requirements)
        assert isinstance(result, dict)
        assert result.get('app_name') == 'TechnicalTask'
        assert result.get('version') == '1.0.0'
        assert isinstance(result.get('features'), list)
    
    # Removed tests for process_task with code_generation, docker_operations, version_management task types
    # These task types are no longer supported - only "development" task type is supported
    # Removed test_handle_generic_task_governance_rejection - _handle_generic_task method removed
        
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
    
    # ============================================================================
    # REASONING SHARING TESTS
    # ============================================================================
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_emit_reasoning_event_success(self, dev_agent):
        """Test successful reasoning event emission"""
        dev_agent.send_message = AsyncMock()
        
        await dev_agent.emit_reasoning_event(
            task_id='test-task-001',
            ecid='ECID-WB-001',
            reason_step='decision',
            summary='Selected FastAPI architecture',
            context='manifest_generation',
            key_points=['FastAPI chosen', 'Async support needed'],
            confidence=0.85
        )
        
        # Verify send_message was called
        dev_agent.send_message.assert_called_once()
        
        # Get call arguments - call_args is a call() object
        call_args = dev_agent.send_message.call_args
        
        # Extract keyword arguments (send_message uses keyword args)
        kw_args = call_args.kwargs
        
        # Verify recipient
        assert kw_args['recipient'] == 'max'  # DevAgent sends to 'max' (instance name)
        
        # Verify message type
        assert kw_args['message_type'] == 'agent_reasoning'
        
        # Verify payload structure
        payload = kw_args['payload']
        assert payload['schema'] == 'reasoning.v1'
        assert payload['task_id'] == 'test-task-001'
        assert payload['ecid'] == 'ECID-WB-001'
        assert payload['reason_step'] == 'decision'
        assert payload['summary'] == 'Selected FastAPI architecture'
        assert payload['context'] == 'manifest_generation'
        assert payload['key_points'] == ['FastAPI chosen', 'Async support needed']
        assert payload['confidence'] == 0.85
        assert payload['raw_reasoning_included'] is False
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_emit_reasoning_event_minimal(self, dev_agent):
        """Test reasoning event emission with minimal fields"""
        dev_agent.send_message = AsyncMock()
        
        await dev_agent.emit_reasoning_event(
            task_id='test-task-002',
            ecid='ECID-WB-002',
            reason_step='checkpoint',
            summary='Build completed',
            context='build'
        )
        
        # Verify send_message was called
        dev_agent.send_message.assert_called_once()
        call_args = dev_agent.send_message.call_args
        payload = call_args.kwargs['payload']
        
        # Verify required fields
        assert payload['task_id'] == 'test-task-002'
        assert payload['ecid'] == 'ECID-WB-002'
        assert payload['reason_step'] == 'checkpoint'
        assert payload['summary'] == 'Build completed'
        assert payload['context'] == 'build'
        
        # Verify optional fields are not present
        assert 'key_points' not in payload or payload.get('key_points') is None
        assert 'confidence' not in payload or payload.get('confidence') is None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_emit_reasoning_event_exception(self, dev_agent):
        """Test reasoning event emission with exception handling"""
        dev_agent.send_message = AsyncMock(side_effect=Exception("Send failed"))
        
        # Should not raise exception
        await dev_agent.emit_reasoning_event(
            task_id='test-task-003',
            ecid='ECID-WB-003',
            reason_step='decision',
            summary='Test decision',
            context='test'
        )
        
        # Should have attempted to send
        dev_agent.send_message.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_design_manifest_emits_reasoning(self, dev_agent, design_manifest_task):
        """Test that design_manifest task emits reasoning events via capability"""
        dev_agent.send_message = AsyncMock()
        dev_agent.current_ecid = 'ECID-WB-001'
        
        # Mock capability_loader.execute to return success
        # Note: Reasoning events are emitted by the capability, not the agent
        dev_agent.capability_loader.execute.return_value = {
            "status": "completed",
            "task_id": "test-design-001",
            "action": "design_manifest",
            "manifest": {"architecture_type": "spa_web_app"},
            "created_files": ["index.html"]
        }
        
        result = await dev_agent.process_task(design_manifest_task)
        
        # Verify capability was called
        dev_agent.capability_loader.execute.assert_called_once_with('manifest.generate', dev_agent, "test-design-001", design_manifest_task["requirements"])
        
        # Note: Reasoning events are now emitted by the capability, not the agent
        # To verify reasoning events, we would need to test the capability directly
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_build_task_emits_reasoning(self, dev_agent, build_task_with_manifest):
        """Test that build task emits reasoning events via capability"""
        dev_agent.send_message = AsyncMock()
        dev_agent.current_ecid = 'ECID-WB-001'
        
        # Mock capability_loader.execute to return success
        # Note: Reasoning events are emitted by the capability, not the agent
        dev_agent.capability_loader.execute.return_value = {
            "status": "completed",
            "task_id": "test-build-001",
            "action": "build",
            "created_files": ["app.py"],
            "image": "test-app",
            "image_version": "test-app:1.0.0"
        }
        
        result = await dev_agent.process_task(build_task_with_manifest)
        
        # Verify capability was called
        dev_agent.capability_loader.execute.assert_called_once_with('docker.build', dev_agent, "test-build-001", build_task_with_manifest["requirements"])
        
        # Note: Reasoning events are now emitted by the capability, not the agent
        # To verify reasoning events, we would need to test the capability directly
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_deploy_task_emits_reasoning(self, dev_agent, deploy_task):
        """Test that deploy task emits reasoning events via capability"""
        dev_agent.send_message = AsyncMock()
        dev_agent.current_ecid = 'ECID-WB-001'
        
        # Mock capability_loader.execute to return success
        # Note: Reasoning events are emitted by the capability, not the agent
        dev_agent.capability_loader.execute.return_value = {
            "status": "completed",
            "task_id": "test-deploy-001",
            "action": "deploy",
            "container_name": "test-app-container",
            "image": "test-app:1.0.0"
        }
        
        result = await dev_agent.process_task(deploy_task)
        
        # Verify capability was called
        dev_agent.capability_loader.execute.assert_called_once_with('docker.deploy', dev_agent, "test-deploy-001", deploy_task["requirements"])
        
        # Note: Reasoning events are now emitted by the capability, not the agent
        # To verify reasoning events, we would need to test the capability directly
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_completion_event_includes_reasoning_summary(self, dev_agent):
        """Test that completion event includes reasoning summary"""
        dev_agent.send_message = AsyncMock()
        dev_agent.current_ecid = 'ECID-WB-001'
        
        # Add reasoning entries to communication log
        dev_agent.communication_log = [
            {
                'ecid': 'ECID-WB-001',
                'message_type': 'llm_reasoning',
                'description': 'AppBuilder manifest_generation: Selected FastAPI architecture',
                'timestamp': '2025-01-01T12:00:00Z'
            },
            {
                'ecid': 'ECID-WB-001',
                'message_type': 'llm_reasoning',
                'description': 'AppBuilder build: Generated 5 files',
                'timestamp': '2025-01-01T12:05:00Z'
            }
        ]
        
        result = {
            'action': 'build',
            'status': 'completed',
            'created_files': ['app.py', 'index.html']
        }
        
        await dev_agent._emit_developer_completion_event('test-task-001', 'ECID-WB-001', result)
        
        # Verify send_message was called
        dev_agent.send_message.assert_called_once()
        call_args = dev_agent.send_message.call_args
        
        # Verify it's a completion event
        assert call_args.kwargs['recipient'] == 'max'  # DevAgent sends to 'max' (instance name)
        assert call_args.kwargs['message_type'] == 'task.developer.completed'
        
        # Verify payload includes reasoning_summary
        payload = call_args.kwargs['payload']
        assert 'reasoning_summary' in payload
        reasoning_summary = payload['reasoning_summary']
        assert reasoning_summary['context'] == 'build'
        assert reasoning_summary['reasoning_available'] is True
        assert len(reasoning_summary.get('key_decisions', [])) > 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_extract_reasoning_summary_for_task(self, dev_agent):
        """Test reasoning summary extraction from communication log"""
        dev_agent.communication_log = [
            {
                'ecid': 'ECID-WB-001',
                'message_type': 'llm_reasoning',
                'description': 'AppBuilder manifest_generation: Selected architecture',
                'timestamp': '2025-01-01T12:00:00Z'
            },
            {
                'ecid': 'ECID-WB-001',
                'message_type': 'llm_reasoning',
                'description': 'AppBuilder build: Generated files',
                'timestamp': '2025-01-01T12:05:00Z'
            },
            {
                'ecid': 'ECID-WB-002',  # Different ECID - should be filtered out
                'message_type': 'llm_reasoning',
                'description': 'AppBuilder build: Other task',
                'timestamp': '2025-01-01T12:10:00Z'
            },
            {
                'ecid': 'ECID-WB-001',
                'message_type': 'llm_reasoning',
                'description': 'AppBuilder deploy: Deployed container',
                'timestamp': '2025-01-01T12:10:00Z'
            }
        ]
        
        summary = dev_agent._extract_reasoning_summary_for_task('ECID-WB-001', 'build')
        
        assert summary['context'] == 'build'
        assert summary['reasoning_available'] is True
        assert summary['event_count'] == 1  # Only one build entry for ECID-WB-001 (filtered by ECID and context)
        assert len(summary['key_decisions']) > 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_extract_reasoning_summary_no_events(self, dev_agent):
        """Test reasoning summary extraction when no events found"""
        dev_agent.communication_log = []
        
        summary = dev_agent._extract_reasoning_summary_for_task('ECID-WB-001', 'build')
        
        assert summary['context'] == 'build'
        assert summary['reasoning_available'] is False
        assert summary['event_count'] == 0
        assert len(summary['key_decisions']) == 0
        assert 'note' in summary