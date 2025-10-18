"""
Unit tests for AppBuilder JSON workflow methods.
"""
import pytest
import json
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Dict, Any

from agents.roles.dev.app_builder import AppBuilder
from agents.contracts.task_spec import TaskSpec
from agents.contracts.build_manifest import BuildManifest
from tests.utils.mock_helpers import (
    MockOllamaResponse, MockAiohttpSession, MockAiohttpResponse, create_sample_task_spec,
    create_sample_build_manifest, mock_ollama_json_call
)


class TestAppBuilderJSON:
    """Test AppBuilder JSON workflow methods."""
    
    @pytest.fixture
    def app_builder(self):
        """Create AppBuilder instance for testing."""
        from unittest.mock import MagicMock
        mock_llm_client = MagicMock()
        return AppBuilder(mock_llm_client)
    
    @pytest.fixture
    def sample_task_spec(self):
        """Sample TaskSpec for testing."""
        return create_sample_task_spec()
    
    @pytest.fixture
    def mock_manifest_response(self):
        """Mock manifest JSON response."""
        return MockOllamaResponse.manifest_response()
    
    @pytest.fixture
    def mock_files_response(self):
        """Mock files JSON response."""
        return MockOllamaResponse.files_response()
    
    @pytest.mark.asyncio
    async def test_call_ollama_json_success(self, app_builder, mock_manifest_response):
        """Test successful Ollama JSON API call."""
        with patch('aiohttp.ClientSession', return_value=MockAiohttpSession(mock_manifest_response)):
            result = await app_builder._call_ollama_json(
                prompt="Test prompt",
                model="qwen2.5-coder:7b"
            )
            
            assert result == mock_manifest_response
            assert isinstance(result, dict)
            assert "architecture" in result
            assert "files" in result
            assert "deployment" in result
    
    @pytest.mark.asyncio
    async def test_call_ollama_json_timeout(self, app_builder):
        """Test Ollama JSON call timeout handling."""
        with patch('aiohttp.ClientSession', return_value=MockAiohttpSession(should_timeout=True)):
            with pytest.raises(asyncio.TimeoutError):
                await app_builder._call_ollama_json(
                    prompt="Test prompt",
                    model="qwen2.5-coder:7b"
                )
    
    @pytest.mark.asyncio
    async def test_call_ollama_json_invalid_json(self, app_builder):
        """Test handling of invalid JSON response."""
        mock_session = MockAiohttpSession()
        mock_response = MockAiohttpResponse(malformed_json=True)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            mock_session.post = MagicMock(return_value=mock_response)
            
            with pytest.raises(json.JSONDecodeError):
                await app_builder._call_ollama_json(
                    prompt="Test prompt",
                    model="qwen2.5-coder:7b"
                )
    
    @pytest.mark.asyncio
    async def test_call_ollama_json_connection_error(self, app_builder):
        """Test handling of connection errors."""
        with patch('aiohttp.ClientSession', return_value=MockAiohttpSession(should_raise_exception=True)):
            with pytest.raises(Exception):  # Should catch and re-raise as generic Exception
                await app_builder._call_ollama_json(
                    prompt="Test prompt",
                    model="qwen2.5-coder:7b"
                )
    
    @pytest.mark.asyncio
    async def test_generate_manifest_json_success(self, app_builder, sample_task_spec, mock_manifest_response):
        """Test successful manifest generation via JSON."""
        with patch.object(app_builder, '_call_ollama_json', return_value=mock_manifest_response):
            manifest = await app_builder.generate_manifest_json(sample_task_spec)
            
        assert isinstance(manifest, BuildManifest)
        assert manifest.architecture_type == "spa_web_app"
        assert manifest.framework == "vanilla_js"
        assert len(manifest.files) == 3
        assert manifest.deployment["container"] == "nginx:alpine"
    
    @pytest.mark.asyncio
    async def test_generate_manifest_json_framework_override(self, app_builder, sample_task_spec):
        """Test that framework is overridden to vanilla_js."""
        # Mock LLM to return React framework
        mock_response = MockOllamaResponse.manifest_response()
        mock_response["architecture"]["framework"] = "react"
        
        with patch.object(app_builder, '_call_ollama_json', return_value=mock_response):
            manifest = await app_builder.generate_manifest_json(sample_task_spec)
            
            # Verify framework is overridden
            assert manifest.framework == "vanilla_js"
    
    @pytest.mark.asyncio
    async def test_generate_manifest_json_prompt_injection(self, app_builder, sample_task_spec, mock_manifest_response):
        """Test that SquadOps constraints are injected into prompt."""
        with patch.object(app_builder, '_call_ollama_json', return_value=mock_manifest_response) as mock_call:
            await app_builder.generate_manifest_json(sample_task_spec)
            
            # Verify prompt contains SquadOps constraints
            call_args = mock_call.call_args
            prompt = call_args[0][0]  # First positional argument
            
            assert "SQUADOPS PLATFORM REQUIREMENTS" in prompt
            assert "vanilla_js" in prompt
            assert "OUTPUT FORMAT: json" in prompt
    
    @pytest.mark.asyncio
    async def test_generate_files_json_success(self, app_builder, sample_task_spec, mock_files_response):
        """Test successful files generation via JSON."""
        manifest = create_sample_build_manifest()
        
        with patch.object(app_builder, '_call_ollama_json', return_value=mock_files_response):
            files = await app_builder.generate_files_json(sample_task_spec, manifest)
            
            assert isinstance(files, list)
            assert len(files) == 5  # index.html, app.js, styles.css, nginx.conf, Dockerfile
            
            # Verify file structure
            file_paths = [f["file_path"] for f in files]
            assert any("index.html" in path for path in file_paths)
            assert any("app.js" in path for path in file_paths)
            assert any("styles.css" in path for path in file_paths)
            assert any("nginx.conf" in path for path in file_paths)
            assert any("Dockerfile" in path for path in file_paths)
            
            # Verify content is present
            for file_data in files:
                assert "content" in file_data
                assert len(file_data["content"]) > 0
    
    @pytest.mark.asyncio
    async def test_generate_files_json_manifest_context(self, app_builder, sample_task_spec, mock_files_response):
        """Test that manifest context is injected into developer prompt."""
        manifest = create_sample_build_manifest()
        
        with patch.object(app_builder, '_call_ollama_json', return_value=mock_files_response) as mock_call:
            await app_builder.generate_files_json(sample_task_spec, manifest)
            
            # Verify prompt contains manifest summary and SquadOps constraints
            call_args = mock_call.call_args
            prompt = call_args[0][0]  # First positional argument
            
            assert "Type: spa_web_app" in prompt
            assert "Files to generate:" in prompt
            assert "SQUADOPS PLATFORM REQUIREMENTS" in prompt
            assert "OUTPUT FORMAT: json" in prompt
    
    @pytest.mark.asyncio
    async def test_generate_files_json_missing_content(self, app_builder, sample_task_spec):
        """Test handling of files response missing content."""
        manifest = create_sample_build_manifest()
        
        # Mock response with missing content field
        mock_response = {
            "files": [
                {"path": "index.html"},  # Missing content
                {"path": "app.js", "content": "console.log('test');"}
            ]
        }
        
        with patch.object(app_builder, '_call_ollama_json', return_value=mock_response):
            with pytest.raises(Exception, match="File JSON generation failed"):
                await app_builder.generate_files_json(sample_task_spec, manifest)
    
    @pytest.mark.asyncio
    async def test_generate_files_json_empty_response(self, app_builder, sample_task_spec):
        """Test handling of empty files response."""
        manifest = create_sample_build_manifest()
        
        with patch.object(app_builder, '_call_ollama_json', return_value={"files": []}):
            files = await app_builder.generate_files_json(sample_task_spec, manifest)
            
            assert isinstance(files, list)
            assert len(files) == 0
    
    @pytest.mark.asyncio
    async def test_generate_files_json_missing_files_key(self, app_builder, sample_task_spec):
        """Test handling of response missing files key."""
        manifest = create_sample_build_manifest()
        
        with patch.object(app_builder, '_call_ollama_json', return_value={}):
            files = await app_builder.generate_files_json(sample_task_spec, manifest)
            
            assert isinstance(files, list)
            assert len(files) == 0
    
    @pytest.mark.asyncio
    async def test_generate_manifest_json_llm_failure(self, app_builder, sample_task_spec):
        """Test handling of LLM call failure during manifest generation."""
        with patch.object(app_builder, '_call_ollama_json', side_effect=Exception("LLM failure")):
            with pytest.raises(Exception, match="LLM failure"):
                await app_builder.generate_manifest_json(sample_task_spec)
    
    @pytest.mark.asyncio
    async def test_generate_files_json_llm_failure(self, app_builder, sample_task_spec):
        """Test handling of LLM call failure during files generation."""
        manifest = create_sample_build_manifest()
        
        with patch.object(app_builder, '_call_ollama_json', side_effect=Exception("LLM failure")):
            with pytest.raises(Exception, match="LLM failure"):
                await app_builder.generate_files_json(sample_task_spec, manifest)
    
    def test_load_prompt_with_output_format(self, app_builder):
        """Test _load_prompt method with output_format parameter."""
        # Test architect prompt with JSON format
        prompt = app_builder._load_prompt("architect.txt", output_format="json")
        
        assert "OUTPUT FORMAT: json" in prompt
        assert "CRITICAL OUTPUT RULES" in prompt
        assert "Return ONLY valid JSON" in prompt
        
        # Test developer prompt with JSON format
        prompt = app_builder._load_prompt("developer.txt", output_format="json")
        
        assert "OUTPUT FORMAT: json" in prompt
        assert "CRITICAL OUTPUT RULES" in prompt
        assert "Return ONLY valid JSON" in prompt
    
    def test_load_prompt_without_output_format(self, app_builder):
        """Test _load_prompt method without output_format parameter."""
        # Test architect prompt without format (should show template variable)
        prompt = app_builder._load_prompt("architect.txt")
        
        assert "OUTPUT FORMAT: $output_format" in prompt
        assert "Return ONLY valid JSON" in prompt  # Template contains both sections
        
        # Test developer prompt without format (should show template variable)
        prompt = app_builder._load_prompt("developer.txt")
        
        assert "OUTPUT FORMAT: $output_format" in prompt
        assert "Return ONLY valid JSON" in prompt  # Template contains both sections
