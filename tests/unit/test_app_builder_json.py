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
    async def test_call_llm_json_success(self, app_builder, mock_manifest_response):
        """Test successful LLM JSON call via router."""
        # Mock llm_client.complete() to return JSON string
        json_response = json.dumps(mock_manifest_response)
        app_builder.llm_client.complete = AsyncMock(return_value=json_response)
        app_builder.llm_client.get_token_usage = MagicMock(return_value=None)
        
        result = await app_builder._call_llm_json(
            prompt="Test prompt",
            context="test_context"
        )
        
        assert result == mock_manifest_response
        assert isinstance(result, dict)
        assert "architecture" in result
        assert "files" in result
        assert "deployment" in result
        
        # Verify format='json' was passed
        app_builder.llm_client.complete.assert_called_once()
        call_kwargs = app_builder.llm_client.complete.call_args[1]
        assert call_kwargs.get('format') == 'json'
    
    @pytest.mark.asyncio
    async def test_call_llm_json_timeout(self, app_builder):
        """Test LLM JSON call timeout handling."""
        # Mock llm_client to raise timeout error
        app_builder.llm_client.complete = AsyncMock(side_effect=asyncio.TimeoutError("LLM timeout"))
        
        with pytest.raises(Exception, match="LLM call failed"):
            await app_builder._call_llm_json(
                prompt="Test prompt",
                context="test_context"
            )
    
    @pytest.mark.asyncio
    async def test_call_llm_json_invalid_json(self, app_builder):
        """Test handling of invalid JSON response."""
        # Mock llm_client to return invalid JSON string
        app_builder.llm_client.complete = AsyncMock(return_value="not valid json {")
        app_builder.llm_client.get_token_usage = MagicMock(return_value=None)
        
        with pytest.raises(Exception, match="Invalid JSON response from LLM"):
            await app_builder._call_llm_json(
                prompt="Test prompt",
                context="test_context"
            )
    
    @pytest.mark.asyncio
    async def test_call_llm_json_connection_error(self, app_builder):
        """Test handling of connection errors."""
        # Mock llm_client to raise connection error
        app_builder.llm_client.complete = AsyncMock(side_effect=Exception("Network error"))
        
        with pytest.raises(Exception, match="LLM call failed"):
            await app_builder._call_llm_json(
                prompt="Test prompt",
                context="test_context"
            )
    
    @pytest.mark.asyncio
    async def test_generate_manifest_json_success(self, app_builder, sample_task_spec, mock_manifest_response):
        """Test successful manifest generation via JSON."""
        with patch.object(app_builder, '_call_llm_json', return_value=mock_manifest_response):
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
        
        with patch.object(app_builder, '_call_llm_json', return_value=mock_response):
            manifest = await app_builder.generate_manifest_json(sample_task_spec)
            
            # Verify framework is overridden
            assert manifest.framework == "vanilla_js"
    
    @pytest.mark.asyncio
    async def test_generate_manifest_json_prompt_injection(self, app_builder, sample_task_spec, mock_manifest_response):
        """Test that SquadOps constraints are injected into prompt."""
        with patch.object(app_builder, '_call_llm_json', return_value=mock_manifest_response) as mock_call:
            await app_builder.generate_manifest_json(sample_task_spec)
            
            # Verify prompt contains SquadOps constraints
            call_args = mock_call.call_args
            prompt = call_args.kwargs.get('prompt') or call_args[0][0]  # Support both kwargs and positional
            
            assert "SQUADOPS PLATFORM REQUIREMENTS" in prompt
            assert "vanilla_js" in prompt
            assert "OUTPUT FORMAT: json" in prompt
    
    @pytest.mark.asyncio
    async def test_generate_files_json_success(self, app_builder, sample_task_spec, mock_files_response):
        """Test successful files generation via JSON."""
        manifest = create_sample_build_manifest()
        
        with patch.object(app_builder, '_call_llm_json', return_value=mock_files_response):
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
        
        with patch.object(app_builder, '_call_llm_json', return_value=mock_files_response) as mock_call:
            await app_builder.generate_files_json(sample_task_spec, manifest)
            
            # Verify prompt contains manifest summary and SquadOps constraints
            call_args = mock_call.call_args
            prompt = call_args.kwargs.get('prompt') or call_args[0][0]  # Support both kwargs and positional
            
            assert "type: spa_web_app" in prompt
            assert "files:" in prompt
            assert "SQUADOPS PLATFORM REQUIREMENTS" in prompt
            assert "OUTPUT FORMAT: json" in prompt
    
    @pytest.mark.asyncio
    async def test_generate_files_json_missing_content(self, app_builder, sample_task_spec):
        """Test handling of files response missing content."""
        manifest = create_sample_build_manifest()
        
        # Mock response with missing content field
        mock_response = {
            "files": [
                {"file_path": "index.html"},  # Missing content
                {"file_path": "app.js", "content": "console.log('test');"}
            ]
        }
        
        with patch.object(app_builder, '_call_llm_json', return_value=mock_response):
            with pytest.raises(Exception, match="File index.html missing content field"):
                await app_builder.generate_files_json(sample_task_spec, manifest)
    
    @pytest.mark.asyncio
    async def test_generate_files_json_empty_response(self, app_builder, sample_task_spec):
        """Test handling of empty files response."""
        manifest = create_sample_build_manifest()
        
        with patch.object(app_builder, '_call_llm_json', return_value={"files": []}):
            files = await app_builder.generate_files_json(sample_task_spec, manifest)
            
            assert isinstance(files, list)
            assert len(files) == 0
    
    @pytest.mark.asyncio
    async def test_generate_files_json_missing_files_key(self, app_builder, sample_task_spec):
        """Test handling of response missing files key."""
        manifest = create_sample_build_manifest()
        
        with patch.object(app_builder, '_call_llm_json', return_value={}):
            with pytest.raises(Exception, match="File generation failed: No 'files' key in LLM response"):
                await app_builder.generate_files_json(sample_task_spec, manifest)
    
    @pytest.mark.asyncio
    async def test_generate_manifest_json_llm_failure(self, app_builder, sample_task_spec):
        """Test handling of LLM call failure during manifest generation."""
        with patch.object(app_builder, '_call_llm_json', side_effect=Exception("LLM failure")):
            with pytest.raises(Exception, match="LLM failure"):
                await app_builder.generate_manifest_json(sample_task_spec)
    
    @pytest.mark.asyncio
    async def test_generate_files_json_llm_failure(self, app_builder, sample_task_spec):
        """Test handling of LLM call failure during files generation."""
        manifest = create_sample_build_manifest()
        
        with patch.object(app_builder, '_call_llm_json', side_effect=Exception("LLM failure")):
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
    
    @pytest.mark.asyncio
    async def test_load_prompt_template_exception_handling(self, app_builder):
        """Test exception handling in _load_prompt method"""
        # Test with invalid template that causes exception
        with patch('builtins.open', side_effect=Exception("File read error")):
            with pytest.raises(Exception, match="File read error"):
                app_builder._load_prompt("nonexistent.txt")
    
    def test_to_kebab_case_conversion(self, app_builder):
        """Test _to_kebab_case method"""
        # Test various naming conventions
        assert app_builder._to_kebab_case("HelloWorld") == "hello-world"
        assert app_builder._to_kebab_case("hello world") == "hello-world"
        assert app_builder._to_kebab_case("hello_world") == "hello_world"
        assert app_builder._to_kebab_case("HelloWorldApp") == "hello-world-app"
        assert app_builder._to_kebab_case("MyApp123") == "my-app123"
    
    @pytest.mark.asyncio
    async def test_generate_files_json_files_not_list(self, app_builder, sample_task_spec):
        """Test handling when files is not a list"""
        manifest = create_sample_build_manifest()
        
        with patch.object(app_builder, '_call_llm_json', return_value={
            'files': "not a list"
        }):
            with pytest.raises(Exception, match="'files' must be a list"):
                await app_builder.generate_files_json(sample_task_spec, manifest)
    
    @pytest.mark.asyncio
    async def test_generate_files_json_skip_non_dict_files(self, app_builder, sample_task_spec):
        """Test skipping file data that is not a dictionary"""
        manifest = create_sample_build_manifest()
        
        with patch.object(app_builder, '_call_llm_json', return_value={
            'files': [
                {"file_path": "valid.html", "content": "<html></html>"},
                "not a dict",  # This should be skipped
                {"file_path": "another.html", "content": "<html></html>"}
            ]
        }):
            files = await app_builder.generate_files_json(sample_task_spec, manifest)
            # Should only process the 2 valid dictionaries
            assert len(files) == 2
    
    @pytest.mark.asyncio
    async def test_generate_files_json_skip_missing_path(self, app_builder, sample_task_spec):
        """Test skipping file data missing file_path/path"""
        manifest = create_sample_build_manifest()
        
        with patch.object(app_builder, '_call_llm_json', return_value={
            'files': [
                {"file_path": "valid.html", "content": "<html></html>"},
                {"content": "<html></html>"},  # Missing file_path - should be skipped
                {"path": "another.html", "content": "<html></html>"}  # Using 'path' instead of 'file_path'
            ]
        }):
            files = await app_builder.generate_files_json(sample_task_spec, manifest)
            # Should process 2 files (one with file_path, one with path)
            assert len(files) == 2
