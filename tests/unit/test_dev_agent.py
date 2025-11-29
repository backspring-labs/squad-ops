"""
Comprehensive unit tests for DevAgent - covering JSON workflow and all methods.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from agents.roles.dev.agent import DevAgent
from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse
from tests.utils.mock_helpers import (
    create_sample_build_artifact_request
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
            # Mock get_capability_for_task to return None by default (tests can override)
            agent.capability_loader.get_capability_for_task = MagicMock(return_value=None)
            # Mock prepare_capability_args to return appropriate args based on convention
            def prepare_args_side_effect(name, payload, metadata=None):
                # Handle both task dicts (from process_task) and payload dicts (from handle_agent_request)
                if name == 'build.artifact':
                    return (payload.get('requirements', payload),)
                elif name in ['manifest.generate', 'docker.build', 'docker.deploy', 'version.archive']:
                    # Extract task_id and requirements from payload (could be task dict or payload dict)
                    task_id = payload.get('task_id', 'unknown')
                    requirements = payload.get('requirements', payload)
                    return (task_id, requirements)
                elif name == 'warmboot.wrapup':
                    return (payload,)
                else:
                    return (payload,)
            agent.capability_loader.prepare_capability_args = MagicMock(side_effect=prepare_args_side_effect)
            # Mock accepts_task_dict to return False by default (standard capabilities)
            agent.capability_loader.accepts_task_dict = MagicMock(return_value=False)
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
        
        # Mock validator and constraint validation
        dev_agent.validator = MagicMock()
        dev_agent.validator.validate_request = MagicMock(return_value=(True, None))
        dev_agent.validator.validate_result_keys = MagicMock(return_value=(True, None))
        dev_agent._validate_constraints = MagicMock(return_value=(True, None))
        
        # Mock capability_loader.execute to return build.artifact result
        dev_agent.capability_loader.execute = AsyncMock(return_value={
            "artifact_uri": "/artifacts/TestApp/test-001",
            "commit": "mock_commit_hash",
            "files_generated": [{"type": "file", "path": "index.html", "content": "<html></html>"}],
            "manifest_uri": "/artifacts/TestApp/test-001/manifest.json"
        })
        dev_agent.capability_loader.prepare_capability_args = MagicMock(return_value=(request.payload.get('requirements', request.payload),))
        
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
        
        # Mock validator and constraint validation
        dev_agent.validator = MagicMock()
        dev_agent.validator.validate_request = MagicMock(return_value=(True, None))
        dev_agent._validate_constraints = MagicMock(return_value=(True, None))
        
        # Mock capability_loader.execute to raise ValueError for unknown capability
        dev_agent.capability_loader.prepare_capability_args = MagicMock(side_effect=ValueError("Capability 'test.run' not found in capability map"))
        
        response = await dev_agent.handle_agent_request(request)
        
        assert isinstance(response, AgentResponse)
        assert response.status == "error"
        assert response.error is not None
        assert response.error.code == "UNKNOWN_CAPABILITY"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_design_manifest_task_success(self, dev_agent, design_manifest_task):
        """Test successful design_manifest task handling via capability."""
        # Mock get_capability_for_task to return manifest.generate
        dev_agent.capability_loader.get_capability_for_task.return_value = 'manifest.generate'
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
        # Verify prepare_capability_args was called
        dev_agent.capability_loader.prepare_capability_args.assert_called_once_with('manifest.generate', design_manifest_task)
        # Verify execute was called with unpacked args
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
        
        # Mock get_capability_for_task to return manifest.generate
        dev_agent.capability_loader.get_capability_for_task.return_value = 'manifest.generate'
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
        # Mock get_capability_for_task to return docker.build
        dev_agent.capability_loader.get_capability_for_task.return_value = 'docker.build'
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
        # Verify prepare_capability_args was called
        dev_agent.capability_loader.prepare_capability_args.assert_called_once_with('docker.build', build_task_with_manifest)
        # Verify execute was called with unpacked args
        dev_agent.capability_loader.execute.assert_called_once_with('docker.build', dev_agent, "test-build-001", build_task_with_manifest["requirements"])
    
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_build_task_file_creation(self, dev_agent, build_task_with_manifest):
        """Test that build task creates files correctly via capability."""
        # Mock get_capability_for_task to return docker.build
        dev_agent.capability_loader.get_capability_for_task.return_value = 'docker.build'
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
        
        # Mock get_capability_for_task to return docker.build
        dev_agent.capability_loader.get_capability_for_task.return_value = 'docker.build'
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
        # Mock get_capability_for_task to return docker.deploy
        dev_agent.capability_loader.get_capability_for_task.return_value = 'docker.deploy'
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
        # Verify prepare_capability_args was called
        dev_agent.capability_loader.prepare_capability_args.assert_called_once_with('docker.deploy', deploy_task)
        # Verify execute was called with unpacked args
        dev_agent.capability_loader.execute.assert_called_once_with('docker.deploy', dev_agent, "test-deploy-001", deploy_task["requirements"])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handle_deploy_task_with_source_fallback(self, dev_agent, deploy_task):
        """Test deploy task with source fallback via capability."""
        # Mock get_capability_for_task to return docker.deploy
        dev_agent.capability_loader.get_capability_for_task.return_value = 'docker.deploy'
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
        
        # Mock get_capability_for_task to return docker.deploy
        dev_agent.capability_loader.get_capability_for_task.return_value = 'docker.deploy'
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
        
        # Mock get_capability_for_task to return docker.deploy
        dev_agent.capability_loader.get_capability_for_task.return_value = 'docker.deploy'
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
        
        # Mock get_capability_for_task to return docker.deploy
        dev_agent.capability_loader.get_capability_for_task.return_value = 'docker.deploy'
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
        
        # Mock get_capability_for_task to return docker.deploy
        dev_agent.capability_loader.get_capability_for_task.return_value = 'docker.deploy'
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
        
        # Mock get_capability_for_task to return None (no mapping for unknown action)
        dev_agent.capability_loader.get_capability_for_task.return_value = None
        
        result = await dev_agent.process_task(task)
        
        assert result["status"] == "error"
        assert "No capability mapping" in result["error"]
    
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
        
        # Mock get_capability_for_task to return version.archive
        dev_agent.capability_loader.get_capability_for_task.return_value = 'version.archive'
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
        # Verify prepare_capability_args was called
        dev_agent.capability_loader.prepare_capability_args.assert_called_once_with('version.archive', task)
        # Verify execute was called with unpacked args
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
        
        # Mock get_capability_for_task to return version.archive
        dev_agent.capability_loader.get_capability_for_task.return_value = 'version.archive'
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
    
    # Removed tests for _create_technical_requirements - method removed
    # This functionality is now handled by build.requirements.generate capability
    # Test the capability directly in test_build_requirements_generator.py or similar
    
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
        
        # Mock get_capability_for_task to return version.archive
        dev_agent.capability_loader.get_capability_for_task.return_value = 'version.archive'
        # Mock capability_loader.execute to return success
        dev_agent.capability_loader.execute.return_value = {
            "status": "completed",
            "task_id": "test-dev-001",
            "action": "archive"
        }
        
        result = await dev_agent.process_task(task)
        
        assert result["status"] == "completed"
        # Verify prepare_capability_args was called
        dev_agent.capability_loader.prepare_capability_args.assert_called_once_with('version.archive', task)
        # Verify execute was called with unpacked args
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
        
        # Mock get_capability_for_task to return None (no mapping)
        dev_agent.capability_loader.get_capability_for_task.return_value = None
        
        result = await dev_agent.process_task(task)
        
        assert result["status"] == "error"
        assert "No capability mapping" in result["error"]
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_exception(self, dev_agent):
        """Test processing task with exception."""
        task = {
            "task_id": "test-error-001",
            "task_type": "development",
            "requirements": {}
        }
        
        # Mock get_capability_for_task to return None (no mapping)
        dev_agent.capability_loader.get_capability_for_task.return_value = None
        
        result = await dev_agent.process_task(task)
        
        assert result["status"] == "error"
        assert result["task_id"] == "test-error-001"
        assert "No capability mapping" in result["error"]
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_archive(self, dev_agent):
        """Test generic task routing to archive via capability."""
        task = {
            "task_id": "test-archive-001",
            "task_type": "development",
            "requirements": {
                "action": "archive",
                "app_name": "TestApp"
            }
        }
        
        # Mock get_capability_for_task to return capability
        dev_agent.capability_loader.get_capability_for_task.return_value = 'version.archive'
        # Mock capability_loader.execute to return success
        dev_agent.capability_loader.execute.return_value = {
            "status": "completed",
            "task_id": "test-archive-001",
            "action": "archive"
        }
        
        result = await dev_agent.process_task(task)
        
        assert result["status"] == "completed"
        dev_agent.capability_loader.get_capability_for_task.assert_called_once_with(task)
        dev_agent.capability_loader.execute.assert_called_once_with('version.archive', dev_agent, "test-archive-001", task["requirements"])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_design_manifest(self, dev_agent):
        """Test generic task routing to design_manifest via capability."""
        task = {
            "task_id": "test-design-001",
            "task_type": "development",
            "requirements": {
                "action": "design_manifest",
                "app_name": "TestApp"
            }
        }
        
        # Mock get_capability_for_task to return capability
        dev_agent.capability_loader.get_capability_for_task.return_value = 'manifest.generate'
        # Mock capability_loader.execute to return success
        dev_agent.capability_loader.execute.return_value = {
            "status": "completed",
            "task_id": "test-design-001",
            "action": "design_manifest"
        }
        
        result = await dev_agent.process_task(task)
        
        assert result["status"] == "completed"
        dev_agent.capability_loader.get_capability_for_task.assert_called_once_with(task)
        # Verify prepare_capability_args was called
        dev_agent.capability_loader.prepare_capability_args.assert_called_once_with('manifest.generate', task)
        # Verify execute was called with unpacked args
        dev_agent.capability_loader.execute.assert_called_once_with('manifest.generate', dev_agent, "test-design-001", task["requirements"])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_build(self, dev_agent):
        """Test generic task routing to build via capability."""
        task = {
            "task_id": "test-build-001",
            "task_type": "development",
            "requirements": {
                "action": "build",
                "app_name": "TestApp"
            }
        }
        
        # Mock get_capability_for_task to return capability
        dev_agent.capability_loader.get_capability_for_task.return_value = 'docker.build'
        # Mock capability_loader.execute to return success
        dev_agent.capability_loader.execute.return_value = {
            "status": "completed",
            "task_id": "test-build-001",
            "action": "build"
        }
        
        result = await dev_agent.process_task(task)
        
        assert result["status"] == "completed"
        dev_agent.capability_loader.get_capability_for_task.assert_called_once_with(task)
        # Verify prepare_capability_args was called
        dev_agent.capability_loader.prepare_capability_args.assert_called_once_with('docker.build', task)
        # Verify execute was called with unpacked args
        dev_agent.capability_loader.execute.assert_called_once_with('docker.build', dev_agent, "test-build-001", task["requirements"])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_deploy(self, dev_agent):
        """Test generic task routing to deploy via capability."""
        task = {
            "task_id": "test-deploy-001",
            "task_type": "development",
            "requirements": {
                "action": "deploy",
                "app_name": "TestApp"
            }
        }
        
        # Mock get_capability_for_task to return capability
        dev_agent.capability_loader.get_capability_for_task.return_value = 'docker.deploy'
        # Mock capability_loader.execute to return success
        dev_agent.capability_loader.execute.return_value = {
            "status": "completed",
            "task_id": "test-deploy-001",
            "action": "deploy"
        }
        
        result = await dev_agent.process_task(task)
        
        assert result["status"] == "completed"
        dev_agent.capability_loader.get_capability_for_task.assert_called_once_with(task)
        # Verify prepare_capability_args was called
        dev_agent.capability_loader.prepare_capability_args.assert_called_once_with('docker.deploy', task)
        # Verify execute was called with unpacked args
        dev_agent.capability_loader.execute.assert_called_once_with('docker.deploy', dev_agent, "test-deploy-001", task["requirements"])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_unknown_action(self, dev_agent):
        """Test generic task routing with unknown action (no capability mapping)."""
        task = {
            "task_id": "test-technical-001",
            "task_type": "development",
            "requirements": {
                "action": "unknown_action",
                "app_name": "TestApp"
            }
        }
        
        # Mock get_capability_for_task to return None (no mapping)
        dev_agent.capability_loader.get_capability_for_task.return_value = None
        
        result = await dev_agent.process_task(task)
        
        assert result["status"] == "error"
        assert "No capability mapping" in result["error"]
    
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
    
    # Removed tests for _extract_prd_analysis_from_communication_log - method removed
    # PRD analysis is now passed directly via task requirements, not extracted from communication log
    # Test PRD processing capabilities directly (prd.read, prd.analyze)
    
    # Removed tests for _handle_code_generation_task - method removed
    # Removed tests for _handle_docker_task - method removed
    # Removed tests for _handle_version_task - method removed
    # Removed tests for _handle_technical_task - method removed
    # These methods are no longer part of DevAgent - capabilities handle these operations
    
    # Removed tests for _create_technical_requirements - method removed
    # This functionality is now handled by build.requirements.generate capability
    # Test the capability directly in test_build_requirements_generator.py or similar
    
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
        
        # Mock get_capability_for_task to raise exception
        dev_agent.capability_loader.get_capability_for_task.side_effect = Exception("Capability lookup failed")
        
        result = await dev_agent.process_task(task)
        
        assert result['task_id'] == 'test-task-001'
        assert result['status'] == 'error'
        assert 'error' in result
    
    # ============================================================================
    # REASONING SHARING TESTS
    # ============================================================================
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_emit_reasoning_event_delegates_to_capability(self, dev_agent):
        """Test that emit_reasoning_event delegates to comms.reasoning.emit capability"""
        # Mock capability execution
        dev_agent.capability_loader.execute = AsyncMock()
        
        await dev_agent.emit_reasoning_event(
            task_id='test-task-001',
            ecid='ECID-WB-001',
            reason_step='decision',
            summary='Selected FastAPI architecture',
            context='manifest_generation',
            key_points=['FastAPI chosen', 'Async support needed'],
            confidence=0.85
        )
        
        # Verify capability was called with correct arguments
        dev_agent.capability_loader.execute.assert_called_once_with(
            'comms.reasoning.emit', dev_agent,
            'test-task-001', 'ECID-WB-001', 'decision', 'Selected FastAPI architecture',
            'manifest_generation', ['FastAPI chosen', 'Async support needed'], 0.85
        )
    
    # Note: For detailed testing of reasoning event emission logic, test the
    # ReasoningEventEmitter capability directly in test_reasoning_event_emitter.py
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_design_manifest_emits_reasoning(self, dev_agent, design_manifest_task):
        """Test that design_manifest task routes to capability (reasoning events handled by capability)"""
        # Mock get_capability_for_task to return manifest.generate
        dev_agent.capability_loader.get_capability_for_task.return_value = 'manifest.generate'
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
        dev_agent.capability_loader.prepare_capability_args.assert_called_once_with('manifest.generate', design_manifest_task)
        dev_agent.capability_loader.execute.assert_called_once_with('manifest.generate', dev_agent, "test-design-001", design_manifest_task["requirements"])
        
        # Note: Reasoning events are now emitted by the capability, not the agent
        # To verify reasoning events, test the ReasoningEventEmitter capability directly
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_build_task_emits_reasoning(self, dev_agent, build_task_with_manifest):
        """Test that build task routes to capability (reasoning events handled by capability)"""
        # Mock get_capability_for_task to return docker.build
        dev_agent.capability_loader.get_capability_for_task.return_value = 'docker.build'
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
        dev_agent.capability_loader.prepare_capability_args.assert_called_once_with('docker.build', build_task_with_manifest)
        dev_agent.capability_loader.execute.assert_called_once_with('docker.build', dev_agent, "test-build-001", build_task_with_manifest["requirements"])
        
        # Note: Reasoning events are now emitted by the capability, not the agent
        # To verify reasoning events, test the ReasoningEventEmitter capability directly
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_deploy_task_emits_reasoning(self, dev_agent, deploy_task):
        """Test that deploy task routes to capability (reasoning events handled by capability)"""
        # Mock get_capability_for_task to return docker.deploy
        dev_agent.capability_loader.get_capability_for_task.return_value = 'docker.deploy'
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
        dev_agent.capability_loader.prepare_capability_args.assert_called_once_with('docker.deploy', deploy_task)
        dev_agent.capability_loader.execute.assert_called_once_with('docker.deploy', dev_agent, "test-deploy-001", deploy_task["requirements"])
        
        # Note: Reasoning events are now emitted by the capability, not the agent
        # To verify reasoning events, test the ReasoningEventEmitter capability directly
    
    # Removed tests for _emit_developer_completion_event and _extract_reasoning_summary_for_task
    # These methods are now handled by task.completion.emit capability
    # Test the capability directly in test_task_completion_emitter.py
    # The capability includes reasoning summary extraction and completion event emission
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_process_task_warmboot_wrapup(self, dev_agent):
        """Test generic task routing to warmboot.wrapup capability with task dict."""
        task = {
            "task_id": "test-wrapup-001",
            "task_type": "warmboot_wrapup",
            "ecid": "ECID-WB-001",
            "original_task_id": "test-original-001",
            "completion_payload": {"status": "completed"},
            "telemetry": {"duration": 100},
            "reasoning_events": [{"reason_step": "decision", "summary": "Test"}]
        }
        
        # Mock get_capability_for_task to return warmboot.wrapup
        dev_agent.capability_loader.get_capability_for_task.return_value = 'warmboot.wrapup'
        # Mock prepare_capability_args to return task dict for warmboot.wrapup
        dev_agent.capability_loader.prepare_capability_args.return_value = (task,)
        # Mock capability_loader.execute to return success
        dev_agent.capability_loader.execute.return_value = {
            "wrapup_uri": "/warm-boot/runs/run-001/wrapup.md",
            "wrapup_content": "# Wrap-up",
            "run_number": "001"
        }
        
        result = await dev_agent.process_task(task)
        
        assert result["wrapup_uri"] == "/warm-boot/runs/run-001/wrapup.md"
        # Verify prepare_capability_args was called with correct arguments
        dev_agent.capability_loader.prepare_capability_args.assert_called_once_with('warmboot.wrapup', task)
        # Verify execute was called with task dict (not task_id, requirements)
        dev_agent.capability_loader.execute.assert_called_once_with('warmboot.wrapup', dev_agent, task)