"""
Unit tests for AppBuilder JSON workflow methods.
"""
import pytest
import json
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from agents.tools.app_builder import AppBuilder
from agents.skills.dev.architect_prompt import ArchitectPrompt
from agents.skills.dev.developer_prompt import DeveloperPrompt
from agents.skills.dev.squadops_constraints import SquadOpsConstraints
from tests.utils.mock_helpers import (
    MockOllamaResponse, create_sample_task_spec,
    create_sample_build_manifest
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
        """Sample requirements dict for testing."""
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
        # Load Skills to get prompt
        architect_skill = ArchitectPrompt()
        constraints_skill = SquadOpsConstraints()
        import yaml
        import re
        
        app_name_kebab = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', sample_task_spec.get('app_name', 'application')).lower().replace(' ', '-')
        constraints = constraints_skill.load(
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            app_name_kebab=app_name_kebab
        )
        prompt = architect_skill.load(
            app_name=sample_task_spec.get('app_name', 'unknown'),
            version=sample_task_spec.get('version', '1.0.0'),
            prd_analysis=sample_task_spec.get('prd_analysis', ''),
            features=', '.join(sample_task_spec.get('features', [])) if sample_task_spec.get('features') else 'General web application',
            constraints=yaml.dump(sample_task_spec.get('constraints', {})) if sample_task_spec.get('constraints') else 'None',
            squadops_constraints=constraints,
            output_format='json'
        )
        
        with patch.object(app_builder, '_call_llm_json', return_value=mock_manifest_response):
            manifest = await app_builder.generate_manifest_json(prompt, sample_task_spec)
            
        assert isinstance(manifest, dict)
        # Handle both old and new manifest structures
        arch_type = manifest.get("architecture_type") or manifest.get("architecture", {}).get("type")
        framework = manifest.get("framework") or manifest.get("architecture", {}).get("framework")
        assert arch_type == "spa_web_app"
        assert framework == "vanilla_js"
        files = manifest.get("files", [])
        assert len(files) == 3
        deployment = manifest.get("deployment", {})
        assert deployment.get("container") == "nginx:alpine"
    
    @pytest.mark.asyncio
    async def test_generate_manifest_json_framework_override(self, app_builder, sample_task_spec):
        """Test that framework is overridden to vanilla_js."""
        # Load Skills to get prompt
        architect_skill = ArchitectPrompt()
        constraints_skill = SquadOpsConstraints()
        import yaml
        import re
        
        app_name_kebab = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', sample_task_spec.get('app_name', 'application')).lower().replace(' ', '-')
        constraints = constraints_skill.load(
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            app_name_kebab=app_name_kebab
        )
        prompt = architect_skill.load(
            app_name=sample_task_spec.get('app_name', 'unknown'),
            version=sample_task_spec.get('version', '1.0.0'),
            prd_analysis=sample_task_spec.get('prd_analysis', ''),
            features=', '.join(sample_task_spec.get('features', [])) if sample_task_spec.get('features') else 'General web application',
            constraints=yaml.dump(sample_task_spec.get('constraints', {})) if sample_task_spec.get('constraints') else 'None',
            squadops_constraints=constraints,
            output_format='json'
        )
        
        # Mock LLM to return React framework
        mock_response = MockOllamaResponse.manifest_response()
        mock_response["architecture"]["framework"] = "react"
        
        with patch.object(app_builder, '_call_llm_json', return_value=mock_response):
            manifest = await app_builder.generate_manifest_json(prompt, sample_task_spec)
            
            # Verify framework is overridden
            framework = manifest.get("framework") or manifest.get("architecture", {}).get("framework")
            assert framework == "vanilla_js"
    
    @pytest.mark.asyncio
    async def test_generate_manifest_json_prompt_injection(self, app_builder, sample_task_spec, mock_manifest_response):
        """Test that SquadOps constraints are injected into prompt."""
        # Load Skills to get prompt
        architect_skill = ArchitectPrompt()
        constraints_skill = SquadOpsConstraints()
        import yaml
        import re
        
        app_name_kebab = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', sample_task_spec.get('app_name', 'application')).lower().replace(' ', '-')
        constraints = constraints_skill.load(
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            app_name_kebab=app_name_kebab
        )
        prompt = architect_skill.load(
            app_name=sample_task_spec.get('app_name', 'unknown'),
            version=sample_task_spec.get('version', '1.0.0'),
            prd_analysis=sample_task_spec.get('prd_analysis', ''),
            features=', '.join(sample_task_spec.get('features', [])) if sample_task_spec.get('features') else 'General web application',
            constraints=yaml.dump(sample_task_spec.get('constraints', {})) if sample_task_spec.get('constraints') else 'None',
            squadops_constraints=constraints,
            output_format='json'
        )
        
        with patch.object(app_builder, '_call_llm_json', return_value=mock_manifest_response) as mock_call:
            await app_builder.generate_manifest_json(prompt, sample_task_spec)
            
            # Verify prompt contains SquadOps constraints
            call_args = mock_call.call_args
            passed_prompt = call_args.kwargs.get('prompt') or call_args[0][0]  # Support both kwargs and positional
            
            assert "SQUADOPS PLATFORM REQUIREMENTS" in passed_prompt
            assert "vanilla_js" in passed_prompt
            assert "OUTPUT FORMAT: json" in passed_prompt
    
    @pytest.mark.asyncio
    async def test_generate_files_json_success(self, app_builder, sample_task_spec, mock_files_response):
        """Test successful files generation via JSON."""
        manifest = create_sample_build_manifest()
        
        # Load Skills to get prompt
        developer_skill = DeveloperPrompt()
        constraints_skill = SquadOpsConstraints()
        import yaml
        import re
        
        app_name_kebab = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', sample_task_spec.get('app_name', 'application')).lower().replace(' ', '-')
        constraints = constraints_skill.load(
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            app_name_kebab=app_name_kebab
        )
        prompt = developer_skill.load(
            app_name=sample_task_spec.get('app_name', 'unknown'),
            app_name_kebab=app_name_kebab,
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            prd_analysis=sample_task_spec.get('prd_analysis', ''),
            features=', '.join(sample_task_spec.get('features', [])) if sample_task_spec.get('features') else 'General web application',
            constraints=yaml.dump(sample_task_spec.get('constraints', {})) if sample_task_spec.get('constraints') else 'None',
            manifest_summary=yaml.dump(manifest),
            output_format='json',
            squadops_constraints=constraints
        )
        prompt = prompt.replace('$squadops_constraints', constraints)
        
        with patch.object(app_builder, '_call_llm_json', return_value=mock_files_response):
            files = await app_builder.generate_files_json(prompt, sample_task_spec, manifest)
            
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
        
        # Load Skills to get prompt
        developer_skill = DeveloperPrompt()
        constraints_skill = SquadOpsConstraints()
        import yaml
        import re
        
        app_name_kebab = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', sample_task_spec.get('app_name', 'application')).lower().replace(' ', '-')
        constraints = constraints_skill.load(
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            app_name_kebab=app_name_kebab
        )
        prompt = developer_skill.load(
            app_name=sample_task_spec.get('app_name', 'unknown'),
            app_name_kebab=app_name_kebab,
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            prd_analysis=sample_task_spec.get('prd_analysis', ''),
            features=', '.join(sample_task_spec.get('features', [])) if sample_task_spec.get('features') else 'General web application',
            constraints=yaml.dump(sample_task_spec.get('constraints', {})) if sample_task_spec.get('constraints') else 'None',
            manifest_summary=yaml.dump(manifest),
            output_format='json',
            squadops_constraints=constraints
        )
        prompt = prompt.replace('$squadops_constraints', constraints)
        
        with patch.object(app_builder, '_call_llm_json', return_value=mock_files_response) as mock_call:
            await app_builder.generate_files_json(prompt, sample_task_spec, manifest)
            
            # Verify prompt contains manifest summary and SquadOps constraints
            call_args = mock_call.call_args
            passed_prompt = call_args.kwargs.get('prompt') or call_args[0][0]  # Support both kwargs and positional
            
            assert "type: spa_web_app" in passed_prompt
            assert "files:" in passed_prompt
            assert "SQUADOPS PLATFORM REQUIREMENTS" in passed_prompt
            assert "OUTPUT FORMAT: json" in passed_prompt
    
    @pytest.mark.asyncio
    async def test_generate_files_json_missing_content(self, app_builder, sample_task_spec):
        """Test handling of files response missing content."""
        manifest = create_sample_build_manifest()
        
        # Load Skills to get prompt
        developer_skill = DeveloperPrompt()
        constraints_skill = SquadOpsConstraints()
        import yaml
        import re
        
        app_name_kebab = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', sample_task_spec.get('app_name', 'application')).lower().replace(' ', '-')
        constraints = constraints_skill.load(
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            app_name_kebab=app_name_kebab
        )
        prompt = developer_skill.load(
            app_name=sample_task_spec.get('app_name', 'unknown'),
            app_name_kebab=app_name_kebab,
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            prd_analysis=sample_task_spec.get('prd_analysis', ''),
            features=', '.join(sample_task_spec.get('features', [])) if sample_task_spec.get('features') else 'General web application',
            constraints=yaml.dump(sample_task_spec.get('constraints', {})) if sample_task_spec.get('constraints') else 'None',
            manifest_summary=yaml.dump(manifest),
            output_format='json',
            squadops_constraints=constraints
        )
        prompt = prompt.replace('$squadops_constraints', constraints)
        
        # Mock response with missing content field
        mock_response = {
            "files": [
                {"file_path": "index.html"},  # Missing content
                {"file_path": "app.js", "content": "console.log('test');"}
            ]
        }
        
        with patch.object(app_builder, '_call_llm_json', return_value=mock_response):
            with pytest.raises(Exception, match="File index.html missing content field"):
                await app_builder.generate_files_json(prompt, sample_task_spec, manifest)
    
    @pytest.mark.asyncio
    async def test_generate_files_json_empty_response(self, app_builder, sample_task_spec):
        """Test handling of empty files response."""
        manifest = create_sample_build_manifest()
        
        # Load Skills to get prompt
        developer_skill = DeveloperPrompt()
        constraints_skill = SquadOpsConstraints()
        import yaml
        import re
        
        app_name_kebab = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', sample_task_spec.get('app_name', 'application')).lower().replace(' ', '-')
        constraints = constraints_skill.load(
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            app_name_kebab=app_name_kebab
        )
        prompt = developer_skill.load(
            app_name=sample_task_spec.get('app_name', 'unknown'),
            app_name_kebab=app_name_kebab,
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            prd_analysis=sample_task_spec.get('prd_analysis', ''),
            features=', '.join(sample_task_spec.get('features', [])) if sample_task_spec.get('features') else 'General web application',
            constraints=yaml.dump(sample_task_spec.get('constraints', {})) if sample_task_spec.get('constraints') else 'None',
            manifest_summary=yaml.dump(manifest),
            output_format='json',
            squadops_constraints=constraints
        )
        prompt = prompt.replace('$squadops_constraints', constraints)
        
        with patch.object(app_builder, '_call_llm_json', return_value={"files": []}):
            files = await app_builder.generate_files_json(prompt, sample_task_spec, manifest)
            
            assert isinstance(files, list)
            assert len(files) == 0
    
    @pytest.mark.asyncio
    async def test_generate_files_json_missing_files_key(self, app_builder, sample_task_spec):
        """Test handling of response missing files key."""
        manifest = create_sample_build_manifest()
        
        # Load Skills to get prompt
        developer_skill = DeveloperPrompt()
        constraints_skill = SquadOpsConstraints()
        import yaml
        import re
        
        app_name_kebab = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', sample_task_spec.get('app_name', 'application')).lower().replace(' ', '-')
        constraints = constraints_skill.load(
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            app_name_kebab=app_name_kebab
        )
        prompt = developer_skill.load(
            app_name=sample_task_spec.get('app_name', 'unknown'),
            app_name_kebab=app_name_kebab,
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            prd_analysis=sample_task_spec.get('prd_analysis', ''),
            features=', '.join(sample_task_spec.get('features', [])) if sample_task_spec.get('features') else 'General web application',
            constraints=yaml.dump(sample_task_spec.get('constraints', {})) if sample_task_spec.get('constraints') else 'None',
            manifest_summary=yaml.dump(manifest),
            output_format='json',
            squadops_constraints=constraints
        )
        prompt = prompt.replace('$squadops_constraints', constraints)
        
        with patch.object(app_builder, '_call_llm_json', return_value={}):
            with pytest.raises(Exception, match="File generation failed: No 'files' key in LLM response"):
                await app_builder.generate_files_json(prompt, sample_task_spec, manifest)
    
    @pytest.mark.asyncio
    async def test_generate_manifest_json_llm_failure(self, app_builder, sample_task_spec):
        """Test handling of LLM call failure during manifest generation."""
        # Load Skills to get prompt
        architect_skill = ArchitectPrompt()
        constraints_skill = SquadOpsConstraints()
        import yaml
        import re
        
        app_name_kebab = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', sample_task_spec.get('app_name', 'application')).lower().replace(' ', '-')
        constraints = constraints_skill.load(
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            app_name_kebab=app_name_kebab
        )
        prompt = architect_skill.load(
            app_name=sample_task_spec.get('app_name', 'unknown'),
            version=sample_task_spec.get('version', '1.0.0'),
            prd_analysis=sample_task_spec.get('prd_analysis', ''),
            features=', '.join(sample_task_spec.get('features', [])) if sample_task_spec.get('features') else 'General web application',
            constraints=yaml.dump(sample_task_spec.get('constraints', {})) if sample_task_spec.get('constraints') else 'None',
            squadops_constraints=constraints,
            output_format='json'
        )
        
        with patch.object(app_builder, '_call_llm_json', side_effect=Exception("LLM failure")):
            with pytest.raises(Exception, match="LLM failure"):
                await app_builder.generate_manifest_json(prompt, sample_task_spec)
    
    @pytest.mark.asyncio
    async def test_generate_files_json_llm_failure(self, app_builder, sample_task_spec):
        """Test handling of LLM call failure during files generation."""
        manifest = create_sample_build_manifest()
        
        # Load Skills to get prompt
        developer_skill = DeveloperPrompt()
        constraints_skill = SquadOpsConstraints()
        import yaml
        import re
        
        app_name_kebab = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', sample_task_spec.get('app_name', 'application')).lower().replace(' ', '-')
        constraints = constraints_skill.load(
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            app_name_kebab=app_name_kebab
        )
        prompt = developer_skill.load(
            app_name=sample_task_spec.get('app_name', 'unknown'),
            app_name_kebab=app_name_kebab,
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            prd_analysis=sample_task_spec.get('prd_analysis', ''),
            features=', '.join(sample_task_spec.get('features', [])) if sample_task_spec.get('features') else 'General web application',
            constraints=yaml.dump(sample_task_spec.get('constraints', {})) if sample_task_spec.get('constraints') else 'None',
            manifest_summary=yaml.dump(manifest),
            output_format='json',
            squadops_constraints=constraints
        )
        prompt = prompt.replace('$squadops_constraints', constraints)
        
        with patch.object(app_builder, '_call_llm_json', side_effect=Exception("LLM failure")):
            with pytest.raises(Exception, match="LLM failure"):
                await app_builder.generate_files_json(prompt, sample_task_spec, manifest)
    
    def test_load_prompt_with_output_format(self):
        """Test Skill load method with output_format parameter."""
        # Test architect prompt skill with JSON format
        architect_skill = ArchitectPrompt()
        prompt = architect_skill.load(output_format="json", app_name="TestApp", version="1.0.0", 
                                     prd_analysis="Test", features="Feature1", constraints="None",
                                     squadops_constraints="SQUADOPS PLATFORM REQUIREMENTS:")
        
        assert "OUTPUT FORMAT: json" in prompt
        assert "CRITICAL OUTPUT RULES" in prompt
        assert "Return ONLY valid JSON" in prompt
        
        # Test developer prompt skill with JSON format
        developer_skill = DeveloperPrompt()
        prompt = developer_skill.load(output_format="json", app_name="TestApp", app_name_kebab="test-app",
                                     version="1.0.0", run_id="test-001", prd_analysis="Test",
                                     features="Feature1", constraints="None", manifest_summary="test: manifest",
                                     squadops_constraints="SQUADOPS PLATFORM REQUIREMENTS:")
        
        assert "OUTPUT FORMAT: json" in prompt
        assert "CRITICAL OUTPUT RULES" in prompt
        assert "Return ONLY valid JSON" in prompt
    
    def test_load_prompt_without_output_format(self):
        """Test Skill load method without output_format parameter."""
        # Test architect prompt skill without format (should show template variable)
        architect_skill = ArchitectPrompt()
        prompt = architect_skill.load(app_name="TestApp", version="1.0.0", 
                                     prd_analysis="Test", features="Feature1", constraints="None",
                                     squadops_constraints="SQUADOPS PLATFORM REQUIREMENTS:")
        
        assert "OUTPUT FORMAT: $output_format" in prompt
        assert "Return ONLY valid JSON" in prompt  # Template contains both sections
        
        # Test developer prompt skill without format (should show template variable)
        developer_skill = DeveloperPrompt()
        prompt = developer_skill.load(app_name="TestApp", app_name_kebab="test-app",
                                     version="1.0.0", run_id="test-001", prd_analysis="Test",
                                     features="Feature1", constraints="None", manifest_summary="test: manifest",
                                     squadops_constraints="SQUADOPS PLATFORM REQUIREMENTS:")
        
        assert "OUTPUT FORMAT: $output_format" in prompt
        assert "Return ONLY valid JSON" in prompt  # Template contains both sections
    
    @pytest.mark.asyncio
    async def test_load_prompt_template_exception_handling(self):
        """Test exception handling in Skill load method"""
        # Test with invalid template path
        from pathlib import Path
        architect_skill = ArchitectPrompt()
        original_path = architect_skill.template_path
        architect_skill.template_path = Path(__file__).parent / "nonexistent.txt"
        
        with pytest.raises(Exception):
            architect_skill.load(app_name="Test", version="1.0.0", prd_analysis="", 
                                features="", constraints="", squadops_constraints="")
        
        architect_skill.template_path = original_path
    
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
        
        # Load Skills to get prompt
        developer_skill = DeveloperPrompt()
        constraints_skill = SquadOpsConstraints()
        import yaml
        import re
        
        app_name_kebab = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', sample_task_spec.get('app_name', 'application')).lower().replace(' ', '-')
        constraints = constraints_skill.load(
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            app_name_kebab=app_name_kebab
        )
        prompt = developer_skill.load(
            app_name=sample_task_spec.get('app_name', 'unknown'),
            app_name_kebab=app_name_kebab,
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            prd_analysis=sample_task_spec.get('prd_analysis', ''),
            features=', '.join(sample_task_spec.get('features', [])) if sample_task_spec.get('features') else 'General web application',
            constraints=yaml.dump(sample_task_spec.get('constraints', {})) if sample_task_spec.get('constraints') else 'None',
            manifest_summary=yaml.dump(manifest),
            output_format='json',
            squadops_constraints=constraints
        )
        prompt = prompt.replace('$squadops_constraints', constraints)
        
        with patch.object(app_builder, '_call_llm_json', return_value={
            'files': "not a list"
        }):
            with pytest.raises(Exception, match="'files' must be a list"):
                await app_builder.generate_files_json(prompt, sample_task_spec, manifest)
    
    @pytest.mark.asyncio
    async def test_generate_files_json_skip_non_dict_files(self, app_builder, sample_task_spec):
        """Test skipping file data that is not a dictionary"""
        manifest = create_sample_build_manifest()
        
        # Load Skills to get prompt
        developer_skill = DeveloperPrompt()
        constraints_skill = SquadOpsConstraints()
        import yaml
        import re
        
        app_name_kebab = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', sample_task_spec.get('app_name', 'application')).lower().replace(' ', '-')
        constraints = constraints_skill.load(
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            app_name_kebab=app_name_kebab
        )
        prompt = developer_skill.load(
            app_name=sample_task_spec.get('app_name', 'unknown'),
            app_name_kebab=app_name_kebab,
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            prd_analysis=sample_task_spec.get('prd_analysis', ''),
            features=', '.join(sample_task_spec.get('features', [])) if sample_task_spec.get('features') else 'General web application',
            constraints=yaml.dump(sample_task_spec.get('constraints', {})) if sample_task_spec.get('constraints') else 'None',
            manifest_summary=yaml.dump(manifest),
            output_format='json',
            squadops_constraints=constraints
        )
        prompt = prompt.replace('$squadops_constraints', constraints)
        
        with patch.object(app_builder, '_call_llm_json', return_value={
            'files': [
                {"file_path": "valid.html", "content": "<html></html>"},
                "not a dict",  # This should be skipped
                {"file_path": "another.html", "content": "<html></html>"}
            ]
        }):
            files = await app_builder.generate_files_json(prompt, sample_task_spec, manifest)
            # Should only process the 2 valid dictionaries
            assert len(files) == 2
    
    @pytest.mark.asyncio
    async def test_generate_files_json_skip_missing_path(self, app_builder, sample_task_spec):
        """Test skipping file data missing file_path/path"""
        manifest = create_sample_build_manifest()
        
        # Load Skills to get prompt
        developer_skill = DeveloperPrompt()
        constraints_skill = SquadOpsConstraints()
        import yaml
        import re
        
        app_name_kebab = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', sample_task_spec.get('app_name', 'application')).lower().replace(' ', '-')
        constraints = constraints_skill.load(
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            app_name_kebab=app_name_kebab
        )
        prompt = developer_skill.load(
            app_name=sample_task_spec.get('app_name', 'unknown'),
            app_name_kebab=app_name_kebab,
            version=sample_task_spec.get('version', '1.0.0'),
            run_id=sample_task_spec.get('run_id', 'unknown'),
            prd_analysis=sample_task_spec.get('prd_analysis', ''),
            features=', '.join(sample_task_spec.get('features', [])) if sample_task_spec.get('features') else 'General web application',
            constraints=yaml.dump(sample_task_spec.get('constraints', {})) if sample_task_spec.get('constraints') else 'None',
            manifest_summary=yaml.dump(manifest),
            output_format='json',
            squadops_constraints=constraints
        )
        prompt = prompt.replace('$squadops_constraints', constraints)
        
        with patch.object(app_builder, '_call_llm_json', return_value={
            'files': [
                {"file_path": "valid.html", "content": "<html></html>"},
                {"content": "<html></html>"},  # Missing file_path - should be skipped
                {"path": "another.html", "content": "<html></html>"}  # Using 'path' instead of 'file_path'
            ]
        }):
            files = await app_builder.generate_files_json(prompt, sample_task_spec, manifest)
            # Should process 2 files (one with file_path, one with path)
            assert len(files) == 2
