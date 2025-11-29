#!/usr/bin/env python3
"""
Unit tests for PathResolver utility
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from agents.utils.path_resolver import PathResolver


class TestPathResolver:
    """Test PathResolver utility"""
    
    def setup_method(self):
        """Reset PathResolver cache before each test"""
        PathResolver.reset()
    
    def teardown_method(self):
        """Reset PathResolver cache after each test to ensure cleanup"""
        PathResolver.reset()
    
    def test_env_var_primary(self, tmp_path, monkeypatch):
        """Test that SQUADOPS_BASE_PATH environment variable is used as primary source"""
        # Set environment variable
        monkeypatch.setenv('SQUADOPS_BASE_PATH', str(tmp_path))
        
        # Create required directories to make it valid
        (tmp_path / "agents").mkdir()
        (tmp_path / "config").mkdir()
        
        base_path = PathResolver.get_base_path()
        assert base_path == tmp_path.resolve()
    
    def test_env_var_invalid_path(self, tmp_path, monkeypatch):
        """Test that invalid env var path falls back to detection"""
        # Set environment variable to non-existent path
        monkeypatch.setenv('SQUADOPS_BASE_PATH', '/nonexistent/path')
        
        # Mock detection to return a valid path
        with patch.object(PathResolver, '_detect_base_path') as mock_detect:
            mock_detect.return_value = tmp_path
            base_path = PathResolver.get_base_path()
            # Should fall back to detection
            mock_detect.assert_called_once()
    
    def test_detection_from_base_agent(self, tmp_path, monkeypatch):
        """Test detection from base_agent.py location"""
        # Unset env var
        monkeypatch.delenv('SQUADOPS_BASE_PATH', raising=False)
        
        # Create repo structure
        repo_root = tmp_path
        (repo_root / "agents").mkdir()
        (repo_root / "agents" / "base_agent.py").write_text("# base agent")
        (repo_root / "config").mkdir()
        
        # Mock __file__ to point to utils/path_resolver.py in repo structure
        # Also mock cwd to avoid detecting actual repo root
        with patch('agents.utils.path_resolver.__file__', 
                   str(repo_root / "agents" / "utils" / "path_resolver.py")), \
             patch('pathlib.Path.cwd', return_value=repo_root):
            # Create the utils directory structure
            (repo_root / "agents" / "utils").mkdir(parents=True)
            
            base_path = PathResolver.get_base_path()
            assert base_path == repo_root.resolve()
    
    def test_detection_from_cwd(self, tmp_path, monkeypatch):
        """Test detection from current working directory"""
        # Unset env var
        monkeypatch.delenv('SQUADOPS_BASE_PATH', raising=False)
        
        # Create repo structure
        repo_root = tmp_path
        (repo_root / "agents").mkdir()
        (repo_root / "config").mkdir()
        
        # Mock cwd and __file__ location
        with patch('pathlib.Path.cwd', return_value=repo_root), \
             patch('agents.utils.path_resolver.__file__', 
                   str(repo_root / "some" / "other" / "path.py")):
            base_path = PathResolver.get_base_path()
            assert base_path == repo_root.resolve()
    
    def test_caching(self, tmp_path, monkeypatch):
        """Test that base path is cached"""
        monkeypatch.setenv('SQUADOPS_BASE_PATH', str(tmp_path))
        (tmp_path / "agents").mkdir()
        (tmp_path / "config").mkdir()
        
        # First call
        path1 = PathResolver.get_base_path()
        
        # Change env var (shouldn't affect cached value)
        monkeypatch.setenv('SQUADOPS_BASE_PATH', '/different/path')
        
        # Second call should return cached value
        path2 = PathResolver.get_base_path()
        assert path1 == path2 == tmp_path.resolve()
    
    def test_reset(self, tmp_path, monkeypatch):
        """Test that reset clears cache"""
        monkeypatch.setenv('SQUADOPS_BASE_PATH', str(tmp_path))
        (tmp_path / "agents").mkdir()
        (tmp_path / "config").mkdir()
        
        # First call
        PathResolver.get_base_path()
        
        # Reset
        PathResolver.reset()
        
        # Change env var
        new_path = tmp_path / "new"
        new_path.mkdir()
        (new_path / "agents").mkdir()
        (new_path / "config").mkdir()
        monkeypatch.setenv('SQUADOPS_BASE_PATH', str(new_path))
        
        # Should detect new path after reset
        base_path = PathResolver.get_base_path()
        assert base_path == new_path.resolve()
    
    def test_error_when_no_path_found(self, monkeypatch):
        """Test that RuntimeError is raised when no valid path can be determined"""
        # Unset env var
        monkeypatch.delenv('SQUADOPS_BASE_PATH', raising=False)
        
        # Mock all detection strategies to fail
        with patch('pathlib.Path.cwd', return_value=Path('/invalid')), \
             patch('agents.utils.path_resolver.__file__', '/invalid/path.py'):
            with pytest.raises(RuntimeError, match="Could not determine repository base path"):
                PathResolver.get_base_path()
    
    def test_docker_path_detection(self, tmp_path, monkeypatch):
        """Test Docker path detection (base_agent.py at /app/base_agent.py)"""
        # Unset env var
        monkeypatch.delenv('SQUADOPS_BASE_PATH', raising=False)
        
        # Create Docker-like structure
        docker_app = tmp_path / "app"
        docker_app.mkdir()
        (docker_app / "agents").mkdir()
        (docker_app / "agents" / "base_agent.py").write_text("# base agent")
        (docker_app / "config").mkdir()
        
        # Mock __file__ to be at /app/agents/utils/path_resolver.py
        # Also mock cwd to avoid detecting actual repo root
        with patch('agents.utils.path_resolver.__file__',
                   str(docker_app / "agents" / "utils" / "path_resolver.py")), \
             patch('pathlib.Path.cwd', return_value=docker_app):
            # Create utils directory
            (docker_app / "agents" / "utils").mkdir(parents=True)
            
            base_path = PathResolver.get_base_path()
            assert base_path == docker_app.resolve()

