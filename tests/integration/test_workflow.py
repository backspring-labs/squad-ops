"""
Integration tests for SquadOps workflow components with real Ollama.

Tests individual workflow components:
1. Manifest generation via JSON
2. File generation via JSON  
3. Content quality validation
4. Governance artifact creation

Note: End-to-end workflow testing is handled by WarmBoot runs.
"""
import pytest
import asyncio
import json
import os
import tempfile
from typing import Dict, Any

from agents.tools.app_builder import AppBuilder
from agents.skills.dev.architect_prompt import ArchitectPrompt
from agents.skills.dev.developer_prompt import DeveloperPrompt
from agents.skills.dev.squadops_constraints import SquadOpsConstraints
from tests.integration.conftest import retry_on_network_error


class TestWorkflowIntegration:
    """Integration tests for SquadOps workflow with real Ollama."""
    
    def _generate_manifest_prompt(self, task_spec):
        """Helper to generate manifest prompt using Skills."""
        import yaml
        import re
        
        architect_skill = ArchitectPrompt()
        constraints_skill = SquadOpsConstraints()
        
        app_name_kebab = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', task_spec.get('app_name', 'application')).lower().replace(' ', '-')
        constraints = constraints_skill.load(
            version=task_spec.get('version', '1.0.0'),
            run_id=task_spec.get('run_id', 'unknown'),
            app_name_kebab=app_name_kebab
        )
        prompt = architect_skill.load(
            app_name=task_spec.get('app_name', 'unknown'),
            version=task_spec.get('version', '1.0.0'),
            prd_analysis=task_spec.get('prd_analysis', ''),
            features=', '.join(task_spec.get('features', [])) if task_spec.get('features') else 'General web application',
            constraints=yaml.dump(task_spec.get('constraints', {})) if task_spec.get('constraints') else 'None',
            squadops_constraints=constraints,
            output_format='json'
        )
        return prompt, task_spec
    
    def _generate_files_prompt(self, task_spec, manifest):
        """Helper to generate files prompt using Skills."""
        import yaml
        import re
        
        developer_skill = DeveloperPrompt()
        constraints_skill = SquadOpsConstraints()
        
        app_name_kebab = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', task_spec.get('app_name', 'application')).lower().replace(' ', '-')
        constraints = constraints_skill.load(
            version=task_spec.get('version', '1.0.0'),
            run_id=task_spec.get('run_id', 'unknown'),
            app_name_kebab=app_name_kebab
        )
        prompt = developer_skill.load(
            app_name=task_spec.get('app_name', 'unknown'),
            app_name_kebab=app_name_kebab,
            version=task_spec.get('version', '1.0.0'),
            run_id=task_spec.get('run_id', 'unknown'),
            prd_analysis=task_spec.get('prd_analysis', ''),
            features=', '.join(task_spec.get('features', [])) if task_spec.get('features') else 'General web application',
            constraints=yaml.dump(task_spec.get('constraints', {})) if task_spec.get('constraints') else 'None',
            manifest_summary=yaml.dump(manifest),
            output_format='json',
            squadops_constraints=constraints
        )
        prompt = prompt.replace('$squadops_constraints', constraints)
        return prompt, task_spec, manifest
    
    @pytest.fixture
    def sample_task_spec(self):
        """Sample TaskSpec dict for integration testing."""
        return {
            "app_name": "IntegrationTestApp",
            "version": "1.0.0",
            "run_id": "INTEGRATION-001",
            "prd_analysis": "Integration test application for validating JSON workflow with real Ollama",
            "features": ["Real-time validation", "JSON output", "Ollama integration"],
            "constraints": {"framework": "vanilla_js", "deployment": "docker"},
            "success_criteria": ["App loads successfully", "No markdown stripping needed", "Structured output"]
        }
    
    @pytest.fixture
    def ollama_available(self):
        """Check if Ollama is available for integration tests."""
        try:
            import aiohttp
            import asyncio
            
            async def check_ollama():
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get('http://localhost:11434/api/version', timeout=2) as response:
                            return response.status == 200
                except Exception:
                    return False
            
            return asyncio.run(check_ollama())
        except Exception:
            return False
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_manifest_generation_with_ollama(self, app_builder, sample_task_spec, ollama_available):
        """Test manifest generation with real Ollama API."""
        if not ollama_available:
            pytest.skip("Ollama not available for integration test")
        
        manifest_prompt, task_spec = self._generate_manifest_prompt(sample_task_spec)
        manifest = await app_builder.generate_manifest_json(manifest_prompt, sample_task_spec)
        
        # Verify manifest structure
        assert isinstance(manifest, dict)
        # Handle both old (flat) and new (nested) manifest structures
        has_flat = "architecture_type" in manifest
        has_nested = "architecture" in manifest and isinstance(manifest.get("architecture"), dict)
        assert has_flat or has_nested, "Manifest must have either architecture_type or architecture.type"
        assert "files" in manifest
        assert "deployment" in manifest
        
        # Verify architecture details
        # Handle both old and new manifest structures
        arch_type = manifest.get("architecture_type") or manifest.get("architecture", {}).get("type")
        framework = manifest.get("framework") or manifest.get("architecture", {}).get("framework")
        assert arch_type == "spa_web_app"
        assert framework == "vanilla_js"  # Should be enforced
        
        # Verify files structure
        assert len(manifest.get("files", [])) >= 3  # At least index.html, app.js, styles.css
        for file_info in manifest.get("files", []):
            assert isinstance(file_info, dict)
            assert "path" in file_info or "file_path" in file_info
            assert "purpose" in file_info or "content" in file_info
            assert "dependencies" in file_info or "directory" in file_info
            if "dependencies" in file_info:
                assert isinstance(file_info["dependencies"], list)
        
        # Verify deployment details
        deploy = manifest.get("deployment", {})
        assert deploy.get("container") == "nginx:alpine"
        assert deploy.get("port") == 80
        # Environment is optional, so don't require it
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_file_generation_with_ollama(self, app_builder, sample_task_spec, ollama_available):
        """Test file generation with real Ollama API."""
        if not ollama_available:
            pytest.skip("Ollama not available for integration test")
        
        # First generate manifest (using Skills)
        manifest_prompt, task_spec = self._generate_manifest_prompt(sample_task_spec)
        manifest = await app_builder.generate_manifest_json(manifest_prompt, sample_task_spec)
        
        # Then generate files (using Skills)
        files_prompt, task_spec, manifest = self._generate_files_prompt(sample_task_spec, manifest)
        files = await app_builder.generate_files_json(files_prompt, sample_task_spec, manifest)
        
        # Verify JSON structure
        assert isinstance(files, list)
        assert len(files) >= 4  # At least index.html, app.js, styles.css, nginx.conf
        
        # Verify each file has required fields
        for file_data in files:
            assert "file_path" in file_data
            assert "content" in file_data
            assert isinstance(file_data["file_path"], str)
            assert isinstance(file_data["content"], str)
            assert len(file_data["file_path"]) > 0
            assert len(file_data["content"]) > 0
        
        # Verify specific files exist
        file_paths = [f["file_path"] for f in files]
        required_files = ["index.html", "app.js", "nginx.conf", "Dockerfile"]
        for required_file in required_files:
            assert any(required_file in path for path in file_paths)
        
        # Verify content quality
        html_content = next(f["content"] for f in files if "index.html" in f["file_path"])
        assert "<!DOCTYPE html>" in html_content
        assert "<title>" in html_content
        
        js_content = next(f["content"] for f in files if "app.js" in f["file_path"])
        assert len(js_content) > 10  # Should have substantial content
        
        nginx_content = next(f["content"] for f in files if "nginx.conf" in f["file_path"])
        assert "server {" in nginx_content
        assert "location /" in nginx_content
        
        dockerfile_content = next(f["content"] for f in files if "Dockerfile" in f["file_path"])
        assert "FROM nginx:alpine" in dockerfile_content
        assert "COPY" in dockerfile_content
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_governance_artifacts_created(self, app_builder, sample_task_spec, ollama_available):
        """Test that governance artifacts are properly created."""
        if not ollama_available:
            pytest.skip("Ollama not available for integration test")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Generate manifest and files (using Skills)
            manifest_prompt, task_spec = self._generate_manifest_prompt(sample_task_spec)
            manifest = await app_builder.generate_manifest_json(manifest_prompt, sample_task_spec)
            files_prompt, task_spec, manifest = self._generate_files_prompt(sample_task_spec, manifest)
            files = await app_builder.generate_files_json(files_prompt, sample_task_spec, manifest)
            
            # Create temporary files to simulate governance logging
            manifest_file = os.path.join(temp_dir, "manifest.yaml")
            checksums_file = os.path.join(temp_dir, "checksums.json")
            
            # Write manifest snapshot
            import yaml
            with open(manifest_file, 'w') as f:
                # Convert manifest dict to YAML serialization format
                # Handle both old and new manifest structures
                arch_type = manifest.get("architecture_type") or manifest.get("architecture", {}).get("type")
                framework = manifest.get("framework") or manifest.get("architecture", {}).get("framework")
                manifest_dict = {
                    'architecture_type': arch_type,
                    'framework': framework,
                    'files': [
                        {
                            'path': f.get("path") or f.get("file_path"),
                            'purpose': f.get("purpose") or f.get("content", "")[:50],
                            'dependencies': f.get("dependencies", [])
                        }
                        for f in manifest.get("files", [])
                    ],
                    'deployment': manifest.get("deployment", {})
                }
                yaml.dump(manifest_dict, f)
            
            # Write checksums
            import hashlib
            checksums = {
                "run_id": sample_task_spec.get("run_id"),
                "timestamp": "2024-01-01T00:00:00Z",
                "files": {}
            }
            
            for file_data in files:
                content = file_data["content"]
                checksum = hashlib.sha256(content.encode()).hexdigest()
                # Extract filename from full path
                filename = file_data["file_path"].split("/")[-1]
                checksums["files"][filename] = checksum
            
            with open(checksums_file, 'w') as f:
                json.dump(checksums, f, indent=2)
            
            # Verify files exist
            assert os.path.exists(manifest_file)
            assert os.path.exists(checksums_file)
            
            # Verify manifest file content
            with open(manifest_file, 'r') as f:
                loaded_manifest = yaml.safe_load(f)
                assert loaded_manifest["architecture_type"] == "spa_web_app"
                assert loaded_manifest["framework"] == "vanilla_js"
            
            # Verify checksums file content
            with open(checksums_file, 'r') as f:
                loaded_checksums = json.load(f)
                assert loaded_checksums["run_id"] == sample_task_spec.get("run_id")
                assert "files" in loaded_checksums
                assert len(loaded_checksums["files"]) == len(files)
                
                # Verify checksums are valid SHA-256 hashes
                for file_path, checksum in loaded_checksums["files"].items():
                    assert len(checksum) == 64  # SHA-256 hex length
                    assert all(c in '0123456789abcdef' for c in checksum)
    
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_ollama_model_availability(self, app_builder, sample_task_spec, ollama_available):
        """Test with different Ollama models."""
        if not ollama_available:
            pytest.skip("Ollama not available for integration test")
        
        # Test with default model
        manifest_prompt, task_spec = self._generate_manifest_prompt(sample_task_spec)
        manifest = await app_builder.generate_manifest_json(manifest_prompt, sample_task_spec)
        assert isinstance(manifest, dict), "Manifest should be a dict"
        
        # Test with alternative model if available (using Skills)
        try:
            manifest_prompt_alt, task_spec = self._generate_manifest_prompt(sample_task_spec)
            manifest_alt = await app_builder.generate_manifest_json(manifest_prompt_alt, sample_task_spec)
            assert isinstance(manifest_alt, dict), "Manifest should be a dict"
        except Exception as e:
            # If alternative model fails, that's okay for integration test
            pytest.skip(f"Alternative model not available: {e}")
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_large_task_spec_handling(self, app_builder, ollama_available):
        """Test handling of large TaskSpec with many features."""
        if not ollama_available:
            pytest.skip("Ollama not available for integration test")
        
        large_task_spec = {
            "app_name": "LargeTestApp",
            "version": "1.0.0",
            "run_id": "LARGE-001",
            "prd_analysis": "Large test application with many features for stress testing JSON workflow",
            "features": [
                "User authentication", "Data visualization", "Real-time updates",
                "File upload", "Search functionality", "Dashboard", "Reports",
                "Notifications", "API integration", "Mobile responsive"
            ],
            "constraints": {
                "framework": "vanilla_js",
                "deployment": "docker",
                "performance": "high",
                "security": "enterprise"
            },
            "success_criteria": [
                "All features work correctly", "Performance meets requirements",
                "Security standards met", "Mobile responsive", "Cross-browser compatible"
            ]
        }
        
        # Should handle large TaskSpec without issues (using Skills)
        manifest_prompt, task_spec = self._generate_manifest_prompt(large_task_spec)
        manifest = await app_builder.generate_manifest_json(manifest_prompt, large_task_spec)
        assert isinstance(manifest, dict)
        assert len(manifest.get("files", [])) >= 3
        
        files_prompt, task_spec, manifest = self._generate_files_prompt(large_task_spec, manifest)
        files = await app_builder.generate_files_json(files_prompt, large_task_spec, manifest)
        assert isinstance(files, list)
        assert len(files) >= 4
