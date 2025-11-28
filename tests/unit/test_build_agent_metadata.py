#!/usr/bin/env python3
"""
Unit tests for build_agent.py metadata generation
"""

import pytest
import yaml
import json
import shutil
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import os

# Add scripts to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "dev"))

from build_agent import (
    build_agent_package,
    get_git_commit,
    get_build_hash,
    get_skills_list,
    get_files_list,
    generate_manifest,
    generate_agent_info
)


class TestBuildAgentMetadata:
    """Test metadata artifact generation"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.test_base = Path("/tmp/test_squadops_build_metadata")
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
        (self.test_base / "agents" / "skills" / "shared" / "text_match.py").write_text("# text match")
        (self.test_base / "agents" / "skills" / "qa").mkdir()
        (self.test_base / "agents" / "skills" / "qa" / "__init__.py").write_text("# qa skills")
        (self.test_base / "agents" / "skills" / "qa" / "test_runner.py").write_text("# test runner")
        (self.test_base / "agents" / "skills" / "registry.yaml").write_text("skills: {}")
        
        # Create config/version.py
        (self.test_base / "config" / "__init__.py").write_text("")
        (self.test_base / "config" / "version.py").write_text('SQUADOPS_VERSION = "0.6.4"')
    
    def teardown_method(self):
        """Clean up test fixtures"""
        if self.test_base.exists():
            shutil.rmtree(self.test_base)
    
    def test_manifest_json_created(self):
        """Test that manifest.json is created"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        manifest_path = dist_dir / "manifest.json"
        
        assert manifest_path.exists(), "manifest.json should exist"
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        # Verify schema
        assert 'role' in manifest
        assert 'capabilities' in manifest
        assert 'skills' in manifest
        assert 'shared_dependencies' in manifest
        assert 'files_included' in manifest
        assert 'build_hash' in manifest
        assert 'git_commit' in manifest
        assert 'build_time_utc' in manifest
        assert 'squadops_version' in manifest
        assert 'build_script_version' in manifest
        
        assert manifest['role'] == 'qa'
        assert isinstance(manifest['capabilities'], list)
        assert isinstance(manifest['skills'], list)
        assert isinstance(manifest['files_included'], list)
        assert manifest['build_hash'].startswith('sha256:')
        assert manifest['build_script_version'] == '1.0'
    
    def test_agent_info_json_created(self):
        """Test that agent_info.json is created"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        agent_info_path = dist_dir / "agent_info.json"
        manifest_path = dist_dir / "manifest.json"
        
        assert agent_info_path.exists(), "agent_info.json should exist"
        
        with open(agent_info_path, 'r') as f:
            agent_info = json.load(f)
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        # Verify build_hash matches
        assert agent_info['build_hash'] == manifest['build_hash']
        
        # Verify schema
        assert 'role' in agent_info
        assert 'agent_id' in agent_info
        assert 'capabilities' in agent_info
        assert 'skills' in agent_info
        assert 'build_hash' in agent_info
        assert 'container_hash' in agent_info
        assert 'runtime_env' in agent_info
        assert 'startup_time_utc' in agent_info
        
        assert agent_info['role'] == 'qa'
        assert agent_info['agent_id'] is None  # Will be filled at runtime
        assert agent_info['container_hash'] is None  # Will be filled at runtime
        assert agent_info['runtime_env'] is None  # Will be filled at runtime
        assert agent_info['startup_time_utc'] is None  # Will be filled at runtime
    
    def test_manifest_deterministic(self):
        """Test that identical builds produce identical manifests"""
        build_agent_package('qa', self.test_base)
        
        dist_dir1 = self.test_base / "dist" / "agents" / "qa"
        manifest_path1 = dist_dir1 / "manifest.json"
        
        with open(manifest_path1, 'r') as f:
            manifest1 = json.load(f)
        
        build_hash1 = manifest1['build_hash']
        
        # Rebuild
        build_agent_package('qa', self.test_base)
        
        dist_dir2 = self.test_base / "dist" / "agents" / "qa"
        manifest_path2 = dist_dir2 / "manifest.json"
        
        with open(manifest_path2, 'r') as f:
            manifest2 = json.load(f)
        
        build_hash2 = manifest2['build_hash']
        
        # Build hashes should match
        assert build_hash1 == build_hash2, "Identical builds should produce identical hashes"
        
        # Manifest ordering should be identical
        assert manifest1['capabilities'] == manifest2['capabilities']
        assert manifest1['skills'] == manifest2['skills']
    
    def test_build_hash_changes_with_file_change(self):
        """Test that build hash changes when files change"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        manifest_path = dist_dir / "manifest.json"
        
        with open(manifest_path, 'r') as f:
            manifest1 = json.load(f)
        
        build_hash1 = manifest1['build_hash']
        
        # Modify a file in source
        (self.test_base / "agents" / "base_agent.py").write_text("# base agent modified")
        
        # Rebuild
        build_agent_package('qa', self.test_base)
        
        with open(manifest_path, 'r') as f:
            manifest2 = json.load(f)
        
        build_hash2 = manifest2['build_hash']
        
        # Build hash should change
        assert build_hash1 != build_hash2, "Build hash should change when files change"
    
    def test_manifest_includes_all_capabilities(self):
        """Test that manifest includes all capabilities"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        manifest_path = dist_dir / "manifest.json"
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        expected_capabilities = ['comms.chat', 'qa.test_design']
        assert sorted(manifest['capabilities']) == sorted(expected_capabilities)
    
    def test_manifest_includes_skills(self):
        """Test that manifest includes skills"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        manifest_path = dist_dir / "manifest.json"
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        # Should include shared and qa skills
        assert len(manifest['skills']) > 0
        assert 'shared.text_match' in manifest['skills']
        assert 'qa.test_runner' in manifest['skills']
    
    def test_git_commit_handles_missing_git(self):
        """Test that get_git_commit handles missing git gracefully"""
        # Test in non-git directory
        result = get_git_commit(self.test_base)
        # Should return None without exception
        assert result is None or isinstance(result, str)
    
    def test_git_commit_uses_build_arg(self):
        """Test that get_git_commit uses build arg when provided"""
        build_arg = "abc123def456"
        result = get_git_commit(self.test_base, build_arg=build_arg)
        assert result == build_arg
    
    def test_build_hash_excludes_manifest_files(self):
        """Test that build hash excludes manifest.json and agent_info.json"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        manifest_path = dist_dir / "manifest.json"
        agent_info_path = dist_dir / "agent_info.json"
        
        with open(manifest_path, 'r') as f:
            manifest1 = json.load(f)
        
        build_hash1 = manifest1['build_hash']
        
        # Modify manifest.json (should not affect hash)
        with open(manifest_path, 'w') as f:
            manifest1['build_time_utc'] = '2025-01-01T00:00:00Z'
            json.dump(manifest1, f, indent=2)
        
        # Recompute hash (should be same)
        build_hash2 = get_build_hash(dist_dir)
        
        assert build_hash1 == build_hash2, "Build hash should not change when manifest files change"
    
    def test_get_skills_list(self):
        """Test get_skills_list function"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        skills = get_skills_list(dist_dir, 'qa')
        
        assert isinstance(skills, list)
        assert 'shared.text_match' in skills
        assert 'qa.test_runner' in skills
        assert skills == sorted(skills)  # Should be sorted
    
    def test_get_files_list(self):
        """Test get_files_list function"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        files = get_files_list(dist_dir)
        
        assert isinstance(files, list)
        assert 'agent.py' in files
        assert 'manifest.json' in files
        assert 'agent_info.json' in files
        assert files == sorted(files)  # Should be sorted
    
    def test_manifest_has_version_field(self):
        """Test that manifest.json includes manifest_version field (Mandatory)"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        manifest_path = dist_dir / "manifest.json"
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        assert 'manifest_version' in manifest, "manifest_version field is mandatory"
        assert manifest['manifest_version'] == '1.0'
    
    def test_agent_info_has_version_field(self):
        """Test that agent_info.json includes agent_info_version field (Mandatory)"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        agent_info_path = dist_dir / "agent_info.json"
        
        with open(agent_info_path, 'r') as f:
            agent_info = json.load(f)
        
        assert 'agent_info_version' in agent_info, "agent_info_version field is mandatory"
        assert agent_info['agent_info_version'] == '1.0'
    
    def test_manifest_includes_shared_modules(self):
        """Test that manifest.json includes shared_modules field (Recommended)"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        manifest_path = dist_dir / "manifest.json"
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        assert 'shared_modules' in manifest, "shared_modules field is recommended"
        assert isinstance(manifest['shared_modules'], list)
        expected_modules = ["llm", "memory", "telemetry", "specs", "utils", "factory", "instances"]
        assert set(manifest['shared_modules']) == set(expected_modules)
    
    def test_manifest_has_resolver_graph(self):
        """Test that manifest.json includes resolver_graph structure (Recommended)"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        manifest_path = dist_dir / "manifest.json"
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        assert 'resolver_graph' in manifest, "resolver_graph field is recommended"
        assert isinstance(manifest['resolver_graph'], dict)
        assert 'capabilities' in manifest['resolver_graph']
        # Can be empty for MVP
        assert isinstance(manifest['resolver_graph']['capabilities'], dict)
    
    def test_agent_info_has_entrypoint(self):
        """Test that agent_info.json includes agent_entrypoint field (Recommended)"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        agent_info_path = dist_dir / "agent_info.json"
        
        with open(agent_info_path, 'r') as f:
            agent_info = json.load(f)
        
        assert 'agent_entrypoint' in agent_info, "agent_entrypoint field is recommended"
        assert agent_info['agent_entrypoint'] == 'agent.py'
    
    def test_build_hash_propagation(self):
        """Test that build_hash propagates correctly through both artifacts (Important)"""
        build_agent_package('qa', self.test_base)
        
        dist_dir = self.test_base / "dist" / "agents" / "qa"
        manifest_path = dist_dir / "manifest.json"
        agent_info_path = dist_dir / "agent_info.json"
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        with open(agent_info_path, 'r') as f:
            agent_info = json.load(f)
        
        # Verify build_hash exists in both
        assert 'build_hash' in manifest
        assert 'build_hash' in agent_info
        
        # Verify they match
        assert manifest['build_hash'] == agent_info['build_hash'], \
            "build_hash must be identical in manifest.json and agent_info.json"
        
        # Verify format (SHA256)
        build_hash = manifest['build_hash']
        assert build_hash.startswith('sha256:'), "build_hash must be SHA256 format"
        assert len(build_hash) > 10, "build_hash must be non-empty"

