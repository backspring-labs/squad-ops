#!/usr/bin/env python3
"""
Unified Path Resolver for SquadOps Agents
Provides a single source of truth for determining the repository base path
"""

import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PathResolver:
    """
    Unified path resolution for SquadOps agents.
    
    Uses environment variable SQUADOPS_BASE_PATH as primary source (set in Dockerfiles),
    with fallback detection logic for local development.
    """
    
    _base_path: Optional[Path] = None
    
    @classmethod
    def get_base_path(cls) -> Path:
        """
        Get repository base path with caching.
        
        Returns:
            Path object pointing to the repository root directory
        """
        if cls._base_path is None:
            cls._base_path = cls._detect_base_path()
        return cls._base_path
    
    @classmethod
    def _detect_base_path(cls) -> Path:
        """
        Detect base path using multiple strategies:
        1. Environment variable SQUADOPS_BASE_PATH (primary, set in Dockerfiles)
        2. Detection from base_agent.py location
        3. Detection from current working directory
        4. Detection from common file locations
        
        Returns:
            Path object pointing to the repository root directory
            
        Raises:
            RuntimeError: If base path cannot be determined
        """
        # Strategy 1: Check environment variable (set in Dockerfiles)
        env_path = os.getenv('SQUADOPS_BASE_PATH')
        if env_path:
            env_path_obj = Path(env_path)
            if env_path_obj.exists():
                logger.debug(f"PathResolver: Using SQUADOPS_BASE_PATH={env_path}")
                return env_path_obj.resolve()
            else:
                logger.warning(f"PathResolver: SQUADOPS_BASE_PATH={env_path} does not exist, trying fallback")
        
        # Strategy 2: Detect from base_agent.py location
        # In repo: agents/base_agent.py -> parent.parent.parent is repo root
        # In Docker: /app/base_agent.py -> parent is /app
        try:
            base_agent_path = Path(__file__).parent.parent / "base_agent.py"
            if base_agent_path.exists():
                # base_agent.py exists, check if we're in repo structure
                potential_base = base_agent_path.parent.parent.parent
                if (potential_base / "agents").exists() and (potential_base / "config").exists():
                    logger.debug(f"PathResolver: Detected base path from base_agent.py: {potential_base}")
                    return potential_base.resolve()
                
                # Check if we're in Docker (base_agent.py at /app/base_agent.py)
                potential_docker_base = base_agent_path.parent
                if (potential_docker_base / "agents").exists() and (potential_docker_base / "config").exists():
                    logger.debug(f"PathResolver: Detected Docker base path: {potential_docker_base}")
                    return potential_docker_base.resolve()
        except Exception as e:
            logger.debug(f"PathResolver: Could not detect from base_agent.py: {e}")
        
        # Strategy 3: Detect from current working directory
        cwd = Path.cwd()
        if (cwd / "agents").exists() and (cwd / "config").exists():
            logger.debug(f"PathResolver: Detected base path from CWD: {cwd}")
            return cwd.resolve()
        
        # Strategy 4: Try parent directories from current file location
        current_file = Path(__file__)
        for parent in [current_file.parent.parent.parent, current_file.parent.parent]:
            if (parent / "agents").exists() and (parent / "config").exists():
                logger.debug(f"PathResolver: Detected base path from file location: {parent}")
                return parent.resolve()
        
        # If all strategies fail, raise an error
        error_msg = (
            "PathResolver: Could not determine repository base path. "
            "Set SQUADOPS_BASE_PATH environment variable or ensure you're running from the repository root."
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    @classmethod
    def reset(cls):
        """
        Reset the cached base path (useful for testing).
        """
        cls._base_path = None

