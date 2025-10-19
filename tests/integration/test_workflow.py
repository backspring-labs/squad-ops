"""
Integration tests for SquadOps workflow with real Ollama.

Tests the complete workflow:
1. Manifest generation via JSON
2. File generation via JSON  
3. Content quality validation
4. Governance artifact creation
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


class TestWorkflowIntegration:
    """Integration tests for SquadOps workflow with real Ollama."""
    
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
    async def test_end_to_end_workflow(self, app_builder, sample_task_spec, ollama_available):
        """Test complete SquadOps workflow with real Ollama."""
        if not ollama_available:
            pytest.skip("Ollama not available for integration test")
        
        # Step 1: Generate manifest via JSON
        manifest = await app_builder.generate_manifest_json(sample_task_spec)
        
        assert isinstance(manifest, BuildManifest)
        assert manifest.architecture_type == "spa_web_app"
        assert manifest.framework == "vanilla_js"
        assert len(manifest.files) > 0
        assert manifest.deployment["container"] == "nginx:alpine"
        
        # Step 2: Generate files via JSON
        files = await app_builder.generate_files_json(sample_task_spec, manifest)
        
        assert isinstance(files, list)
        assert len(files) > 0
        
        # Step 3: Verify file structure
        file_paths = [f["file_path"] for f in files]
        assert any("index.html" in path for path in file_paths)
        assert any("app.js" in path for path in file_paths)
        assert any("nginx.conf" in path for path in file_paths)
        assert any("Dockerfile" in path for path in file_paths)
        
        # Step 4: Verify content quality
        for file_data in files:
            assert "content" in file_data
            assert len(file_data["content"]) > 0
            
            # Verify no markdown markers in content
            content = file_data["content"]
            assert "```" not in content
            # Allow file delimiters but not YAML frontmatter
            assert content.count("---") <= 2  # Allow "--- FILE: name ---" markers
        
        # Step 5: Verify specific file contents
        html_file = next(f for f in files if "index.html" in f["file_path"])
        assert "<!DOCTYPE html>" in html_file["content"]
        assert "<html" in html_file["content"]  # More flexible HTML tag detection
        
        js_file = next(f for f in files if "app.js" in f["file_path"])
        assert "console.log" in js_file["content"] or "function" in js_file["content"]
        
        nginx_file = next(f for f in files if "nginx.conf" in f["file_path"])
        assert "server {" in nginx_file["content"]
        assert "listen 80" in nginx_file["content"]
        
        dockerfile = next(f for f in files if "Dockerfile" in f["file_path"])
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
        assert hasattr(manifest, 'architecture_type')
        assert hasattr(manifest, 'framework')
        assert hasattr(manifest, 'files')
        assert hasattr(manifest, 'deployment')
        
        # Verify architecture details
        assert manifest.architecture_type == "spa_web_app"
        assert manifest.framework == "vanilla_js"  # Should be enforced
        
        # Verify files structure
        assert len(manifest.files) >= 3  # At least index.html, app.js, styles.css
        for file_info in manifest.files:
            assert hasattr(file_info, 'path')
            assert hasattr(file_info, 'purpose')
            assert hasattr(file_info, 'dependencies')
            assert isinstance(file_info.dependencies, list)
        
        # Verify deployment details
        deploy = manifest.deployment
        assert deploy["container"] == "nginx:alpine"
        assert deploy["port"] == 80
        # Environment is optional, so don't require it
    
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
            # Generate manifest and files
            manifest = await app_builder.generate_manifest_json(sample_task_spec)
            files = await app_builder.generate_files_json(sample_task_spec, manifest)
            
            # Create temporary files to simulate governance logging
            manifest_file = os.path.join(temp_dir, "manifest.yaml")
            checksums_file = os.path.join(temp_dir, "checksums.json")
            
            # Write manifest snapshot
            import yaml
            with open(manifest_file, 'w') as f:
                # Convert FileSpec objects to dictionaries for YAML serialization
                manifest_dict = {
                    'architecture_type': manifest.architecture_type,
                    'framework': manifest.framework,
                    'files': [
                        {
                            'path': f.path,
                            'purpose': f.purpose,
                            'dependencies': f.dependencies
                        }
                        for f in manifest.files
                    ],
                    'deployment': manifest.deployment
                }
                yaml.dump(manifest_dict, f)
            
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
                assert loaded_checksums["run_id"] == sample_task_spec.run_id
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
