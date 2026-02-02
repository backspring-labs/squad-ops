#!/usr/bin/env python3
"""
Unified Path Resolver for SquadOps.

Provides a single source of truth for determining the repository base path.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class PathResolver:
    """
    Unified path resolution for SquadOps.

    Uses environment variable SQUADOPS_BASE_PATH as primary source (set in Dockerfiles),
    with fallback detection logic for local development.
    """

    _base_path: Path | None = None

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
        2. Detection from pyproject.toml location
        3. Detection from current working directory
        4. Detection from common file locations

        Returns:
            Path object pointing to the repository root directory

        Raises:
            RuntimeError: If base path cannot be determined
        """
        # Strategy 1: Check environment variable (set in Dockerfiles)
        env_path = os.getenv("SQUADOPS_BASE_PATH")
        if env_path:
            env_path_obj = Path(env_path)
            if env_path_obj.exists():
                logger.debug(f"PathResolver: Using SQUADOPS_BASE_PATH={env_path}")
                return env_path_obj.resolve()
            else:
                logger.warning(
                    f"PathResolver: SQUADOPS_BASE_PATH={env_path} does not exist, trying fallback"
                )

        # Strategy 2: Detect from this file's location
        # In repo: src/squadops/config/path_resolver.py -> parent.parent.parent.parent is repo root
        try:
            current_file = Path(__file__).resolve()
            # Go up from src/squadops/config/ to repo root
            potential_base = current_file.parent.parent.parent.parent
            if (potential_base / "pyproject.toml").exists():
                logger.debug(f"PathResolver: Detected base path from file location: {potential_base}")
                return potential_base

            # Try /app for Docker
            if (Path("/app") / "config").exists():
                logger.debug("PathResolver: Detected Docker base path: /app")
                return Path("/app")
        except Exception as e:
            logger.debug(f"PathResolver: Could not detect from file location: {e}")

        # Strategy 3: Detect from current working directory
        cwd = Path.cwd()
        if (cwd / "pyproject.toml").exists():
            logger.debug(f"PathResolver: Detected base path from CWD: {cwd}")
            return cwd.resolve()

        # Strategy 4: Check if config directory exists
        if (cwd / "config").exists():
            logger.debug(f"PathResolver: Detected base path from config dir in CWD: {cwd}")
            return cwd.resolve()

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
