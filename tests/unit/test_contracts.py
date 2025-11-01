"""
Unit tests for contract definitions.
"""

import pytest
from agents.contracts.task_spec import TaskSpec
from agents.contracts.build_manifest import BuildManifest, FileSpec

def test_task_spec_creation():
    """Test TaskSpec creation and serialization"""
    spec = TaskSpec(
        app_name="TestApp",
        version="1.0.0",
        run_id="run-001",
        prd_analysis="Test application",
        features=["feature1", "feature2"],
        constraints={"max_files": 5},
        success_criteria=["Deploys successfully"]
    )
    
    assert spec.app_name == "TestApp"
    assert len(spec.features) == 2
    
    # Test serialization
    data = spec.to_dict()
    spec2 = TaskSpec.from_dict(data)
    assert spec2.app_name == spec.app_name

def test_build_manifest_validation():
    """Test BuildManifest validation"""
    manifest_yaml = """
architecture:
  type: spa_web_app
  framework: vanilla_js

files:
  - path: index.html
    purpose: Main page
    dependencies: []

deployment:
  container: nginx:alpine
  port: 80
"""
    
    manifest = BuildManifest.from_yaml(manifest_yaml)
    assert manifest.architecture_type == "spa_web_app"
    assert len(manifest.files) == 1
    assert manifest.files[0].path == "index.html"

def test_build_manifest_validation_against_task_spec():
    """Test BuildManifest validation against TaskSpec"""
    task_spec = TaskSpec(
        app_name="TestApp",
        version="1.0.0",
        run_id="run-001",
        prd_analysis="Test app",
        features=[],
        constraints={},
        success_criteria=[]
    )
    
    manifest_yaml = """
architecture:
  type: spa_web_app
  framework: vanilla_js

files:
  - path: index.html
    purpose: Main page
    dependencies: []

deployment:
  container: nginx:alpine
  port: 80
"""
    
    manifest = BuildManifest.from_yaml(manifest_yaml)
    # Should not raise exception
    assert manifest.validate_against_task_spec(task_spec) is True

def test_build_manifest_validation_empty_files():
    """Test BuildManifest validation fails with no files"""
    manifest_yaml = """
architecture:
  type: spa_web_app
  framework: vanilla_js

files: []

deployment:
  container: nginx:alpine
  port: 80
"""
    
    manifest = BuildManifest.from_yaml(manifest_yaml)
    task_spec = TaskSpec(
        app_name="TestApp",
        version="1.0.0",
        run_id="run-001",
        prd_analysis="Test app",
        features=[],
        constraints={},
        success_criteria=[]
    )
    
    with pytest.raises(ValueError, match="BuildManifest has no files"):
        manifest.validate_against_task_spec(task_spec)




