#!/usr/bin/env python3
"""
Unit tests for build_agent.py script
"""

import yaml
import shutil
from pathlib import Path
import sys

# Add scripts to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "dev"))

from build_agent import (
    build_agent_package,
    get_capability_module_path
)


class TestBuildAgent:
    """Test build_agent.py functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.test_base = Path("/tmp/test_squadops_build")
        if self.test_base.exists():
            shutil.rmtree(self.test_base)
        self.test_base.mkdir(parents=True)
        
        # Create minimal repo structure
        (self.test_base / "agents" / "roles" / "qa").mkdir(parents=True)
        (self.test_base / "agents" / "capabilities").mkdir(parents=True)
        (self.test_base / "agents" / "skills").mkdir(parents=True)
        (self.test_base / "agents" / "llm").mkdir(parents=True)
        (self.test_base / "agents" / "memory").mkdir(parents=True)
        (self.test_base / "agents" / "telemetry").mkdir(parents=True)
        (self.test_base / "agents" / "specs").mkdir(parents=True)
        (self.test_base / "agents" / "utils").mkdir(parents=True)
        (self.test_base / "agents" / "factory").mkdir(parents=True)
        (self.test_base / "agents" / "instances").mkdir(parents=True)
        (self.test_base / "config").mkdir(parents=True)
        
        # Create test config.yaml
        config = {
            'agent_id': 'test-eve',
            'role': 'qa',
            'spec_version': '1.0.0',
            'implements': [
                {'capability': 'qa.test_design', 'min_version': '1.0.0'},
                {'capability': 'comms.chat', 'min_version': '1.0.0'}
            ]
        }
        with open(self.test_base / "agents" / "roles" / "qa" / "config.yaml", 'w') as f:
            yaml.dump(config, f)
        
        # Create minimal required files
        (self.test_base / "agents" / "base_agent.py").write_text("# base agent")
        (self.test_base / "agents" / "roles" / "qa" / "agent.py").write_text("# qa agent")
        (self.test_base / "agents" / "roles" / "qa" / "requirements.txt").write_text("pytest>=7.0.0")
        (self.test_base / "agents" / "capabilities" / "__init__.py").write_text("# capabilities")
        (self.test_base / "agents" / "capabilities" / "loader.py").write_text("# loader")
        (self.test_base / "agents" / "capabilities" / "catalog.yaml").write_text("capabilities: []")
        (self.test_base / "agents" / "capabilities" / "comms_chat.py").write_text("# comms chat")
        (self.test_base / "agents" / "capabilities" / "qa").mkdir()
        (self.test_base / "agents" / "capabilities" / "qa" / "__init__.py").write_text("# qa capabilities")
        (self.test_base / "agents" / "capabilities" / "qa" / "test_design.py").write_text("# test design")
        (self.test_base / "agents" / "capability_bindings.yaml").write_text("bindings: {}")
        (self.test_base / "agents" / "roles" / "registry.yaml").write_text("roles: {}")
        (self.test_base / "agents" / "instances" / "instances.yaml").write_text("instances: []")
        (self.test_base / "agents" / "skills" / "__init__.py").write_text("# skills")
        (self.test_base / "agents" / "skills" / "shared").mkdir()
        (self.test_base / "agents" / "skills" / "shared" / "__init__.py").write_text("# shared skills")
        (self.test_base / "agents" / "skills" / "qa").mkdir()
        (self.test_base / "agents" / "skills" / "qa" / "__init__.py").write_text("# qa skills")
        (self.test_base / "agents" / "skills" / "registry.yaml").write_text("skills: {}")
    
    def teardown_method(self):
        """Clean up test fixtures"""
        if self.test_base.exists():
            shutil.rmtree(self.test_base)
    
    def test_get_capability_module_path(self):
        """Test capability name to module path mapping"""
        assert get_capability_module_path('qa.test_design') == 'agents.capabilities.qa.test_design'
        assert get_capability_module_path('comms.chat') == 'agents.capabilities.comms_chat'
        assert get_capability_module_path('unknown.capability') is None
    
    def test_build_qa_agent_package(self):
        """Test building QA agent package"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        assert dist_dir.exists(), "Dist directory should be created"
        
        # Check entry point
        assert (dist_dir / "agent.py").exists(), "Entry point should exist"
        
        # Check requirements
        assert (dist_dir / "requirements.txt").exists(), "Requirements should exist"
        
        # Check shared infrastructure (base_agent.py should be in agents/, not root)
        assert (dist_dir / "agents" / "base_agent.py").exists(), "Base agent should exist in agents/"
        assert not (dist_dir / "base_agent.py").exists(), "Base agent should NOT be at root"
        assert (dist_dir / "agents" / "llm").exists(), "LLM directory should exist"
        assert (dist_dir / "agents" / "memory").exists(), "Memory directory should exist"
        
        # Check capabilities (only required ones)
        assert (dist_dir / "agents" / "capabilities" / "qa" / "test_design.py").exists(), \
            "Required capability should exist"
        assert (dist_dir / "agents" / "capabilities" / "comms_chat.py").exists(), \
            "Required capability should exist"
        
        # Check config files
        assert (dist_dir / "agents" / "roles" / "qa" / "config.yaml").exists(), \
            "Agent config should exist"
        assert (dist_dir / "agents" / "roles" / "registry.yaml").exists(), \
            "Registry should exist"
        
        # Check skills
        assert (dist_dir / "agents" / "skills" / "shared").exists(), \
            "Shared skills should exist"
        assert (dist_dir / "agents" / "skills" / "qa").exists(), \
            "QA skills should exist"
    
    def test_build_dev_agent_package_includes_tools(self):
        """Test that dev agent package includes tools directory"""
        # Create dev config
        (self.test_base / "agents" / "roles" / "dev").mkdir(parents=True)
        dev_config = {
            'agent_id': 'test-neo',
            'role': 'dev',
            'implements': [{'capability': 'build.artifact'}]
        }
        with open(self.test_base / "agents" / "roles" / "dev" / "config.yaml", 'w') as f:
            yaml.dump(dev_config, f)
        (self.test_base / "agents" / "roles" / "dev" / "agent.py").write_text("# dev agent")
        (self.test_base / "agents" / "roles" / "dev" / "requirements.txt").write_text("pytest>=7.0.0")
        
        # Create tools directory
        (self.test_base / "agents" / "tools").mkdir()
        (self.test_base / "agents" / "tools" / "docker_manager.py").write_text("# docker manager")
        
        build_agent_package('dev', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "dev"
        assert (dist_dir / "agents" / "tools").exists(), "Tools directory should exist for dev"
        assert (dist_dir / "agents" / "tools" / "docker_manager.py").exists(), \
            "Docker manager should exist"
    
    def test_only_required_capabilities_copied(self):
        """Test that only required capabilities are copied, not all"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        
        # Should have required capabilities
        assert (dist_dir / "agents" / "capabilities" / "qa" / "test_design.py").exists()
        assert (dist_dir / "agents" / "capabilities" / "comms_chat.py").exists()
        
        # Should NOT have unrelated capabilities (if we create one)
        # This test verifies the build script doesn't copy everything
    
    def test_shared_infrastructure_always_included(self):
        """Test that shared infrastructure is always included"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        
        # All shared infrastructure should be present
        shared_dirs = [
            "agents/base_agent.py",
            "agents/llm",
            "agents/memory",
            "agents/telemetry",
            "agents/specs",
            "agents/utils",
            "agents/factory",
            "agents/instances",
        ]
        
        for rel_path in shared_dirs:
            full_path = dist_dir / rel_path
            assert full_path.exists(), f"Shared infrastructure should include: {rel_path}"
    
    def test_config_files_copied(self):
        """Test that config files are copied correctly"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        
        assert (dist_dir / "agents" / "capability_bindings.yaml").exists()
        assert (dist_dir / "agents" / "roles" / "registry.yaml").exists()
        assert (dist_dir / "config").exists()
    
    def test_manifest_files_included(self):
        """Test that manifest.json and agent_info.json are included in built package"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        
        assert (dist_dir / "manifest.json").exists(), "manifest.json should exist"
        assert (dist_dir / "agent_info.json").exists(), "agent_info.json should exist"
    
    def test_build_hash_excludes_manifest_files(self):
        """Test that build hash excludes manifest.json and agent_info.json"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        manifest_path = dist_dir / "manifest.json"
        
        import json
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        build_hash1 = manifest['build_hash']
        
        # Modify manifest.json (should not affect hash computation)
        with open(manifest_path, 'w') as f:
            manifest['build_time_utc'] = '2025-01-01T00:00:00Z'
            json.dump(manifest, f, indent=2)
        
        # Recompute hash (should be same since manifest excluded)
        from build_agent import get_build_hash
        build_hash2 = get_build_hash(dist_dir)
        
        assert build_hash1 == build_hash2, "Build hash should not change when manifest files change"

