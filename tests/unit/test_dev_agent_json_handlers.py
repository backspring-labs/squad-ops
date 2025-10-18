"""
Unit tests for Neo agent JSON task handlers.
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


class TestDevAgentJSONHandlers:
    """Test DevAgent JSON task handlers."""
    
    @pytest.fixture
    def dev_agent(self):
        """Create DevAgent instance for testing."""
        from unittest.mock import MagicMock
        agent = DevAgent("test-dev-agent")
        agent.app_builder = MagicMock()
        agent.file_manager = MockFileManager()
        agent.docker_manager = MockDockerManager()
        return agent
    
    @pytest.fixture
    def design_manifest_task(self):
        """Sample design_manifest task."""
        task_spec = create_sample_task_spec()
        return {
            "task_id": "test-design-001",
            "type": "development",
            "requirements": {
                "action": "design_manifest",
                "task_spec": task_spec.__dict__
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
                "manifest": manifest.to_dict(),
                "task_spec": task_spec.to_dict()
            }
        }
    
    @pytest.fixture
    def build_task_without_manifest(self):
        """Sample build task without manifest (legacy workflow)."""
        task_spec = create_sample_task_spec()
        return {
            "task_id": "test-build-002",
            "type": "development",
            "requirements": {
                "action": "build",
                "task_spec": task_spec.to_dict()
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
                "source_dir": "/app/test-app",
                "target_url": "http://localhost:8080/test-app"
            }
        }
    
    @pytest.mark.asyncio
    async def test_handle_design_manifest_task_success(self, dev_agent, design_manifest_task):
        """Test successful design_manifest task handling."""
        # Mock AppBuilder to return a manifest
        mock_manifest = create_sample_build_manifest()
        dev_agent.app_builder.generate_manifest_json = AsyncMock(return_value=mock_manifest)
        
        result = await dev_agent._handle_design_manifest_task(
            design_manifest_task["task_id"],
            design_manifest_task["requirements"]
        )
        
        assert result["status"] == "completed"
        assert result["action"] == "design_manifest"
        assert "manifest" in result
        assert result["manifest"]["architecture"]["type"] == "spa_web_app"
        
        # Verify AppBuilder was called correctly
        dev_agent.app_builder.generate_manifest_json.assert_called_once()
        call_args = dev_agent.app_builder.generate_manifest_json.call_args[0]
        assert isinstance(call_args[0], TaskSpec)
        assert call_args[0].app_name == "TestApp"
    
    @pytest.mark.asyncio
    async def test_handle_design_manifest_task_missing_taskspec(self, dev_agent):
        """Test design_manifest task with missing task_spec."""
        requirements = {
            "action": "design_manifest"
            # Missing task_spec
        }
        
        result = await dev_agent._handle_design_manifest_task("test-001", requirements)
        
        assert result["status"] == "error"
        assert "taskspec" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_handle_design_manifest_task_appbuilder_failure(self, dev_agent, design_manifest_task):
        """Test design_manifest task when AppBuilder fails."""
        dev_agent.app_builder.generate_manifest_json.side_effect = Exception("AppBuilder failure")
        
        result = await dev_agent._handle_design_manifest_task(
            design_manifest_task["task_id"],
            design_manifest_task["requirements"]
        )
        
        assert result["status"] == "error"
        assert "AppBuilder failure" in result["error"]
    
    @pytest.mark.asyncio
    async def test_handle_build_task_with_manifest_json_workflow(self, dev_agent, build_task_with_manifest):
        """Test build task using JSON workflow with manifest."""
        # Mock AppBuilder to return files in correct format
        mock_files = [
            {"type": "create_file", "file_path": "/app/test-app/index.html", "content": "<html></html>", "directory": "/app/test-app"},
            {"type": "create_file", "file_path": "/app/test-app/app.js", "content": "console.log('test');", "directory": "/app/test-app"},
            {"type": "create_file", "file_path": "/app/test-app/styles.css", "content": "body { color: red; }", "directory": "/app/test-app"},
            {"type": "create_file", "file_path": "/app/test-app/nginx.conf", "content": "server { listen 80; }", "directory": "/app/test-app"},
            {"type": "create_file", "file_path": "/app/test-app/Dockerfile", "content": "FROM nginx:alpine", "directory": "/app/test-app"}
        ]
        dev_agent.app_builder.generate_files_json = AsyncMock(return_value=mock_files)
        
        result = await dev_agent._handle_build_task(
            build_task_with_manifest["task_id"],
            build_task_with_manifest["requirements"]
        )
        
        assert result["status"] == "completed"
        assert result["action"] == "build"
        assert "created_files" in result
        assert len(result["created_files"]) == 5
        
        # Verify JSON workflow was used
        dev_agent.app_builder.generate_files_json.assert_called_once()
        
        # Verify files were created via file_manager
        assert len(dev_agent.file_manager.create_file_calls) == 5
        file_paths = [call["path"] for call in dev_agent.file_manager.create_file_calls]
        assert any("index.html" in path for path in file_paths)
        assert any("app.js" in path for path in file_paths)
        assert any("nginx.conf" in path for path in file_paths)
        assert any("Dockerfile" in path for path in file_paths)
    
    @pytest.mark.asyncio
    async def test_handle_build_task_without_manifest_legacy_workflow(self, dev_agent, build_task_without_manifest):
        """Test build task using legacy workflow without manifest."""
        # Mock AppBuilder legacy method
        mock_build_result = {
            "files": [
                {"type": "create_file", "file_path": "/app/test-app/index.html", "content": "<html></html>", "directory": "/app/test-app"}
            ],
            "manifest": {"architecture_type": "spa_web_app", "framework": "vanilla_js"},
            "success": True
        }
        dev_agent.app_builder.build_from_task_spec = AsyncMock(return_value=mock_build_result)
        
        result = await dev_agent._handle_build_task(
            build_task_without_manifest["task_id"],
            build_task_without_manifest["requirements"]
        )
        
        assert result["status"] == "completed"
        assert result["action"] == "build"
        assert "created_files" in result
        
        # Verify legacy workflow was used
        dev_agent.app_builder.build_from_task_spec.assert_called_once()
        dev_agent.app_builder.generate_files_json.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_build_task_file_creation(self, dev_agent, build_task_with_manifest):
        """Test that files are properly created during build task."""
        mock_files = [
            {"type": "create_file", "file_path": "/app/test-app/index.html", "content": "<html>Test</html>", "directory": "/app/test-app"},
            {"type": "create_file", "file_path": "/app/test-app/app.js", "content": "console.log('test');", "directory": "/app/test-app"},
            {"type": "create_file", "file_path": "/app/test-app/styles.css", "content": "body { color: red; }", "directory": "/app/test-app"}
        ]
        dev_agent.app_builder.generate_files_json = AsyncMock(return_value=mock_files)
        
        result = await dev_agent._handle_build_task(
            build_task_with_manifest["task_id"],
            build_task_with_manifest["requirements"]
        )
        
        # Verify all files were created
        assert len(dev_agent.file_manager.create_file_calls) == 3
        
        # Verify file contents
        created_files = dev_agent.file_manager.get_created_files()
        assert any("index.html" in path and "<html>Test</html>" in content for path, content in created_files.items())
        assert any("app.js" in path and "console.log('test');" in content for path, content in created_files.items())
        assert any("styles.css" in path and "body { color: red; }" in content for path, content in created_files.items())
    
    @pytest.mark.asyncio
    async def test_handle_build_task_file_creation_failure(self, dev_agent, build_task_with_manifest):
        """Test handling of file creation failures."""
        mock_files = [
            {"type": "create_file", "file_path": "/app/test-app/test.html", "content": "test", "directory": "/app/test-app"}
        ]
        dev_agent.app_builder.generate_files_json = AsyncMock(return_value=mock_files)
        
        # Mock file_manager to fail
        dev_agent.file_manager.create_file = AsyncMock(side_effect=Exception("File creation failed"))
        
        result = await dev_agent._handle_build_task(
            build_task_with_manifest["task_id"],
            build_task_with_manifest["requirements"]
        )
        
        assert result["status"] == "error"
        assert "File creation failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_handle_build_task_appbuilder_failure(self, dev_agent, build_task_with_manifest):
        """Test build task when AppBuilder fails."""
        dev_agent.app_builder.generate_files_json = AsyncMock(side_effect=Exception("AppBuilder failure"))
        
        result = await dev_agent._handle_build_task(
            build_task_with_manifest["task_id"],
            build_task_with_manifest["requirements"]
        )
        
        assert result["status"] == "error"
        assert "AppBuilder failure" in result["error"]
    
    @pytest.mark.asyncio
    async def test_handle_deploy_task_with_source_dir(self, dev_agent, deploy_task):
        """Test deploy task with source_dir parameter."""
        # MockDockerManager already returns correct structure, no need to override
        
        result = await dev_agent._handle_deploy_task(
            deploy_task["task_id"],
            deploy_task["requirements"]
        )
        
        assert result["status"] == "completed"
        assert result["action"] == "deploy"
        assert "container_name" in result
        
        # Verify DockerManager was called correctly
        assert len(dev_agent.docker_manager.build_calls) == 1
        assert len(dev_agent.docker_manager.deploy_calls) == 1
    
    @pytest.mark.asyncio
    async def test_handle_deploy_task_with_source_fallback(self, dev_agent):
        """Test deploy task falling back to source parameter."""
        requirements = {
            "action": "deploy",
            "source": "/app/fallback-app",  # No source_dir
            "target_url": "http://localhost:8080/fallback-app"
        }
        
        # MockDockerManager already returns correct structure, no need to override
        
        result = await dev_agent._handle_deploy_task("test-deploy-002", requirements)
        
        assert result["status"] == "completed"
        
        # Verify source_dir fallback was used
        assert len(dev_agent.docker_manager.build_calls) == 1
        assert dev_agent.docker_manager.build_calls[0]["source_dir"] == "/app/fallback-app"
    
    @pytest.mark.asyncio
    async def test_handle_deploy_task_docker_failure(self, dev_agent, deploy_task):
        """Test deploy task when Docker operations fail."""
        dev_agent.docker_manager.build_image = AsyncMock(side_effect=Exception("Docker build failed"))
        
        result = await dev_agent._handle_deploy_task(
            deploy_task["task_id"],
            deploy_task["requirements"]
        )
        
        assert result["status"] == "error"
        assert "Docker build failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_handle_deploy_task_missing_source(self, dev_agent):
        """Test deploy task with missing source parameters."""
        requirements = {
            "action": "deploy",
            "target_url": "http://localhost:8080/test-app"
            # Missing both source_dir and source
        }
        
        result = await dev_agent._handle_deploy_task("test-deploy-003", requirements)
        
        assert result["status"] == "completed"
        assert result["action"] == "deploy"
        
        # Verify fallback source was used
        assert len(dev_agent.docker_manager.build_calls) == 1
        assert "warm-boot/apps" in dev_agent.docker_manager.build_calls[0]["source_dir"]
    
    @pytest.mark.asyncio
    async def test_task_routing_design_manifest(self, dev_agent, design_manifest_task):
        """Test that design_manifest tasks are routed correctly."""
        dev_agent.app_builder.generate_manifest_json = AsyncMock(return_value=create_sample_build_manifest())
        
        result = await dev_agent._handle_development_task(design_manifest_task)
        
        assert result["status"] == "completed"
        assert result["action"] == "design_manifest"
        dev_agent.app_builder.generate_manifest_json.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_task_routing_build(self, dev_agent, build_task_with_manifest):
        """Test that build tasks are routed correctly."""
        dev_agent.app_builder.generate_files_json = AsyncMock(return_value=[])
        
        result = await dev_agent._handle_development_task(build_task_with_manifest)
        
        assert result["status"] == "completed"
        assert result["action"] == "build"
        dev_agent.app_builder.generate_files_json.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_task_routing_deploy(self, dev_agent, deploy_task):
        """Test that deploy tasks are routed correctly."""
        # MockDockerManager already returns correct structure, no need to override
        
        result = await dev_agent._handle_development_task(deploy_task)
        
        assert result["status"] == "completed"
        assert result["action"] == "deploy"
        
        # Verify Docker operations were called
        assert len(dev_agent.docker_manager.build_calls) == 1
        assert len(dev_agent.docker_manager.deploy_calls) == 1
    
    @pytest.mark.asyncio
    async def test_task_routing_unknown_action(self, dev_agent):
        """Test handling of unknown action types."""
        task = {
            "task_id": "test-unknown-001",
            "type": "development",
            "requirements": {
                "action": "unknown_action"
            }
        }
        
        result = await dev_agent._handle_development_task(task)
        
        assert result["status"] == "completed"
        assert result["action"] == "technical"
        assert "task_spec" in result
