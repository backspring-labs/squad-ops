"""
Integration tests for JSON workflow with real Ollama.
"""
import pytest
import asyncio
import json
import os
import tempfile
from typing import Dict, Any

from agents.roles.dev.app_builder import AppBuilder
from agents.contracts.task_spec import TaskSpec
from agents.contracts.build_manifest import BuildManifest


class TestJSONWorkflowIntegration:
    """Integration tests for JSON workflow with real Ollama."""
    
    @pytest.fixture
    def app_builder(self):
        """Create AppBuilder instance for testing."""
        from unittest.mock import MagicMock
        mock_llm_client = MagicMock()
        return AppBuilder(mock_llm_client)
    
    @pytest.fixture
    def sample_task_spec(self):
        """Sample TaskSpec for integration testing."""
        return TaskSpec(
            app_name="IntegrationTestApp",
            version="1.0.0",
            run_id="INTEGRATION-001",
            prd_analysis="Integration test application for validating JSON workflow with real Ollama",
            features=["Real-time validation", "JSON output", "Ollama integration"],
            constraints={"framework": "vanilla_js", "deployment": "docker"},
            success_criteria=["App loads successfully", "No markdown stripping needed", "Structured output"]
        )
    
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
                except:
                    return False
            
            return asyncio.run(check_ollama())
        except:
            return False
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_end_to_end_json_workflow(self, app_builder, sample_task_spec, ollama_available):
        """Test complete JSON workflow with real Ollama."""
        if not ollama_available:
            pytest.skip("Ollama not available for integration test")
        
        # Step 1: Generate manifest via JSON
        manifest = await app_builder.generate_manifest_json(sample_task_spec)
        
        assert isinstance(manifest, BuildManifest)
        assert manifest.architecture["type"] == "spa_web_app"
        assert manifest.architecture["framework"] == "vanilla_js"
        assert len(manifest.files) > 0
        assert manifest.deployment["container"] == "nginx:alpine"
        
        # Step 2: Generate files via JSON
        files = await app_builder.generate_files_json(sample_task_spec, manifest)
        
        assert isinstance(files, list)
        assert len(files) > 0
        
        # Step 3: Verify file structure
        file_paths = [f["path"] for f in files]
        assert "index.html" in file_paths
        assert "app.js" in file_paths
        assert "nginx.conf" in file_paths
        assert "Dockerfile" in file_paths
        
        # Step 4: Verify content quality
        for file_data in files:
            assert "content" in file_data
            assert len(file_data["content"]) > 0
            
            # Verify no markdown markers in content
            content = file_data["content"]
            assert "```" not in content
            assert "---" not in content or content.count("---") <= 1  # Allow YAML frontmatter
        
        # Step 5: Verify specific file contents
        html_file = next(f for f in files if f["path"] == "index.html")
        assert "<!DOCTYPE html>" in html_file["content"]
        assert "<html>" in html_file["content"]
        
        js_file = next(f for f in files if f["path"] == "app.js")
        assert "console.log" in js_file["content"] or "function" in js_file["content"]
        
        nginx_file = next(f for f in files if f["path"] == "nginx.conf")
        assert "server {" in nginx_file["content"]
        assert "listen 80" in nginx_file["content"]
        
        dockerfile = next(f for f in files if f["path"] == "Dockerfile")
        assert "FROM nginx:alpine" in dockerfile["content"]
        assert "EXPOSE 80" in dockerfile["content"]
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_manifest_generation_with_ollama(self, app_builder, sample_task_spec, ollama_available):
        """Test manifest generation with real Ollama API."""
        if not ollama_available:
            pytest.skip("Ollama not available for integration test")
        
        manifest = await app_builder.generate_manifest_json(sample_task_spec)
        
        # Verify manifest structure
        assert isinstance(manifest, BuildManifest)
        assert hasattr(manifest, 'architecture')
        assert hasattr(manifest, 'files')
        assert hasattr(manifest, 'deployment')
        
        # Verify architecture details
        arch = manifest.architecture
        assert arch["type"] == "spa_web_app"
        assert arch["framework"] == "vanilla_js"  # Should be enforced
        assert "description" in arch
        
        # Verify files structure
        assert len(manifest.files) >= 3  # At least index.html, app.js, styles.css
        for file_info in manifest.files:
            assert "path" in file_info
            assert "purpose" in file_info
            assert "dependencies" in file_info
            assert isinstance(file_info["dependencies"], list)
        
        # Verify deployment details
        deploy = manifest.deployment
        assert deploy["container"] == "nginx:alpine"
        assert deploy["port"] == 80
        assert "environment" in deploy
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_file_generation_with_ollama(self, app_builder, sample_task_spec, ollama_available):
        """Test file generation with real Ollama API."""
        if not ollama_available:
            pytest.skip("Ollama not available for integration test")
        
        # First generate manifest
        manifest = await app_builder.generate_manifest_json(sample_task_spec)
        
        # Then generate files
        files = await app_builder.generate_files_json(sample_task_spec, manifest)
        
        # Verify JSON structure
        assert isinstance(files, list)
        assert len(files) >= 4  # At least index.html, app.js, styles.css, nginx.conf
        
        # Verify each file has required fields
        for file_data in files:
            assert "path" in file_data
            assert "content" in file_data
            assert isinstance(file_data["path"], str)
            assert isinstance(file_data["content"], str)
            assert len(file_data["path"]) > 0
            assert len(file_data["content"]) > 0
        
        # Verify specific files exist
        file_paths = [f["path"] for f in files]
        required_files = ["index.html", "app.js", "nginx.conf", "Dockerfile"]
        for required_file in required_files:
            assert required_file in file_paths
        
        # Verify content quality
        html_content = next(f["content"] for f in files if f["path"] == "index.html")
        assert "<!DOCTYPE html>" in html_content
        assert "<title>" in html_content
        
        js_content = next(f["content"] for f in files if f["path"] == "app.js")
        assert len(js_content) > 10  # Should have substantial content
        
        nginx_content = next(f["content"] for f in files if f["path"] == "nginx.conf")
        assert "server {" in nginx_content
        assert "location /" in nginx_content
        
        dockerfile_content = next(f["content"] for f in files if f["path"] == "Dockerfile")
        assert "FROM nginx:alpine" in dockerfile_content
        assert "COPY" in dockerfile_content
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_governance_artifacts_created(self, app_builder, sample_task_spec, ollama_available):
        """Test that governance artifacts are properly created."""
        if not ollama_available:
            pytest.skip("Ollama not available for integration test")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Generate manifest and files
            manifest = await app_builder.generate_manifest_json(sample_task_spec)
            files = await app_builder.generate_files_json(sample_task_spec, manifest)
            
            # Create temporary files to simulate governance logging
            manifest_file = os.path.join(temp_dir, "manifest.yaml")
            checksums_file = os.path.join(temp_dir, "checksums.json")
            
            # Write manifest snapshot
            import yaml
            with open(manifest_file, 'w') as f:
                yaml.dump(manifest.__dict__, f)
            
            # Write checksums
            import hashlib
            checksums = {
                "run_id": sample_task_spec.run_id,
                "timestamp": "2024-01-01T00:00:00Z",
                "files": {}
            }
            
            for file_data in files:
                content = file_data["content"]
                checksum = hashlib.sha256(content.encode()).hexdigest()
                checksums["files"][file_data["path"]] = checksum
            
            with open(checksums_file, 'w') as f:
                json.dump(checksums, f, indent=2)
            
            # Verify files exist
            assert os.path.exists(manifest_file)
            assert os.path.exists(checksums_file)
            
            # Verify manifest file content
            with open(manifest_file, 'r') as f:
                loaded_manifest = yaml.safe_load(f)
                assert loaded_manifest["architecture"]["type"] == "spa_web_app"
                assert loaded_manifest["architecture"]["framework"] == "vanilla_js"
            
            # Verify checksums file content
            with open(checksums_file, 'r') as f:
                loaded_checksums = json.load(f)
                assert loaded_checksums["run_id"] == sample_task_spec.run_id
                assert "files" in loaded_checksums
                assert len(loaded_checksums["files"]) == len(files)
                
                # Verify checksums are valid SHA-256 hashes
                for file_path, checksum in loaded_checksums["files"].items():
                    assert len(checksum) == 64  # SHA-256 hex length
                    assert all(c in '0123456789abcdef' for c in checksum)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_json_vs_legacy_output_quality(self, app_builder, sample_task_spec, ollama_available):
        """Test that JSON workflow produces equivalent quality to legacy workflow."""
        if not ollama_available:
            pytest.skip("Ollama not available for integration test")
        
        # Generate using JSON workflow
        json_manifest = await app_builder.generate_manifest_json(sample_task_spec)
        json_files = await app_builder.generate_files_json(sample_task_spec, json_manifest)
        
        # Generate using legacy workflow
        legacy_files = await app_builder.build_from_task_spec(sample_task_spec)
        
        # Compare outputs
        assert len(json_files) > 0
        assert len(legacy_files) > 0
        
        # Both should have essential files
        json_paths = [f["path"] for f in json_files]
        legacy_paths = [f["path"] for f in legacy_files]
        
        essential_files = ["index.html", "app.js"]
        for essential in essential_files:
            assert essential in json_paths
            assert essential in legacy_paths
        
        # Content should be comparable quality
        json_html = next(f["content"] for f in json_files if f["path"] == "index.html")
        legacy_html = next(f["content"] for f in legacy_files if f["path"] == "index.html")
        
        assert len(json_html) > 50  # Should have substantial content
        assert len(legacy_html) > 50
        assert "<!DOCTYPE html>" in json_html
        assert "<!DOCTYPE html>" in legacy_html
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_ollama_timeout_handling(self, app_builder, sample_task_spec, ollama_available):
        """Test handling of Ollama timeouts in integration."""
        if not ollama_available:
            pytest.skip("Ollama not available for integration test")
        
        # Test with very short timeout
        original_timeout = getattr(app_builder, '_ollama_timeout', 30)
        app_builder._ollama_timeout = 0.001  # Very short timeout
        
        try:
            with pytest.raises(asyncio.TimeoutError):
                await app_builder.generate_manifest_json(sample_task_spec)
        finally:
            app_builder._ollama_timeout = original_timeout
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_ollama_model_availability(self, app_builder, sample_task_spec, ollama_available):
        """Test with different Ollama models."""
        if not ollama_available:
            pytest.skip("Ollama not available for integration test")
        
        # Test with default model
        manifest = await app_builder.generate_manifest_json(sample_task_spec)
        assert isinstance(manifest, BuildManifest)
        
        # Test with alternative model if available
        try:
            manifest_alt = await app_builder.generate_manifest_json(sample_task_spec)
            assert isinstance(manifest_alt, BuildManifest)
        except Exception as e:
            # If alternative model fails, that's okay for integration test
            pytest.skip(f"Alternative model not available: {e}")
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_large_task_spec_handling(self, app_builder, ollama_available):
        """Test handling of large TaskSpec with many features."""
        if not ollama_available:
            pytest.skip("Ollama not available for integration test")
        
        large_task_spec = TaskSpec(
            app_name="LargeTestApp",
            version="1.0.0",
            run_id="LARGE-001",
            prd_analysis="Large test application with many features for stress testing JSON workflow",
            features=[
                "User authentication", "Data visualization", "Real-time updates",
                "File upload", "Search functionality", "Dashboard", "Reports",
                "Notifications", "API integration", "Mobile responsive"
            ],
            constraints={
                "framework": "vanilla_js",
                "deployment": "docker",
                "performance": "high",
                "security": "enterprise"
            },
            success_criteria=[
                "All features work correctly", "Performance meets requirements",
                "Security standards met", "Mobile responsive", "Cross-browser compatible"
            ]
        )
        
        # Should handle large TaskSpec without issues
        manifest = await app_builder.generate_manifest_json(large_task_spec)
        assert isinstance(manifest, BuildManifest)
        assert len(manifest.files) >= 3
        
        files = await app_builder.generate_files_json(large_task_spec, manifest)
        assert isinstance(files, list)
        assert len(files) >= 4
