#!/usr/bin/env python3
"""
CycleDataStore - Canonical cycle data storage (SIP-0047)

Provides a consistent interface for reading and writing execution cycle artifacts
and telemetry in the canonical cycle_data/<project_id>/<ECID>/ layout.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CycleDataStore:
    """
    Manages cycle data storage for execution cycles.
    
    Provides read/write operations for artifacts and telemetry in the
    canonical cycle_data/<project_id>/<ECID>/ structure.
    """
    
    # Valid areas for cycle data
    VALID_AREAS = {'meta', 'shared', 'agents', 'artifacts', 'tests', 'telemetry'}
    
    def __init__(self, cycle_data_root: Path, project_id: str, cycle_id: str):  # SIP-0048: renamed from ecid
        """
        Initialize CycleDataStore for a specific cycle.
        
        Args:
            cycle_data_root: Base path for cycle data (e.g., repo_root/cycle_data)
            project_id: Project identifier (must exist in projects table)
            cycle_id: Execution cycle identifier (SIP-0048: renamed from ecid)
        """
        self.cycle_data_root = Path(cycle_data_root)
        self.project_id = project_id
        self.cycle_id = cycle_id  # SIP-0048: renamed from ecid
        self._cycle_path = None
        self._directory_created = False
    
    def get_cycle_path(self) -> Path:
        """
        Get the full path to this cycle's data directory.
        
        Returns:
            Path to cycle_data/<project_id>/<cycle_id>/
        """
        if self._cycle_path is None:
            self._cycle_path = self.cycle_data_root / self.project_id / self.cycle_id  # SIP-0048: renamed from ecid
        return self._cycle_path
    
    def _ensure_directory_structure(self):
        """Create the directory structure for this cycle if it doesn't exist."""
        if self._directory_created:
            return
        
        cycle_path = self.get_cycle_path()
        
        # Create all area directories
        for area in self.VALID_AREAS:
            area_path = cycle_path / area
            area_path.mkdir(parents=True, exist_ok=True)
        
        self._directory_created = True
        logger.debug(f"Created cycle data directory structure: {cycle_path}")
    
    def _get_area_path(self, area: str, agent_name: str | None = None) -> Path:
        """
        Get the path for a specific area, optionally with agent subdirectory.
        
        Args:
            area: One of the valid areas (meta, shared, agents, artifacts, tests, telemetry)
            agent_name: Optional agent name for agent-specific subdirectories
            
        Returns:
            Path to the area directory
        """
        if area not in self.VALID_AREAS:
            raise ValueError(f"Invalid area: {area}. Must be one of {self.VALID_AREAS}")
        
        self._ensure_directory_structure()
        cycle_path = self.get_cycle_path()
        area_path = cycle_path / area
        
        # For agents and telemetry areas, create agent-specific subdirectory if provided
        if agent_name and area in ('agents', 'telemetry'):
            area_path = area_path / agent_name
            area_path.mkdir(parents=True, exist_ok=True)
        
        return area_path
    
    def write_text_artifact(
        self,
        area: str,
        relative_path: str,
        content: str,
        agent_name: str | None = None
    ) -> bool:
        """
        Write a text artifact to the cycle data store.
        
        Args:
            area: Area name (meta, shared, agents, artifacts, tests, telemetry)
            relative_path: Relative path within the area (e.g., 'plan.md', 'prd/v1_prd.md')
            content: Text content to write
            agent_name: Optional agent name for agent-specific areas
            
        Returns:
            True if successful, False otherwise
        """
        try:
            area_path = self._get_area_path(area, agent_name)
            file_path = area_path / relative_path
            
            # Create intermediate directories
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            file_path.write_text(content, encoding='utf-8')
            logger.debug(f"Wrote text artifact: {file_path}")
            return True
            
        except ValueError:
            # Re-raise ValueError (invalid area) so callers can handle it
            raise
        except Exception as e:
            logger.error(f"Failed to write text artifact {area}/{relative_path}: {e}")
            return False
    
    def write_binary_artifact(
        self,
        area: str,
        relative_path: str,
        data: bytes,
        agent_name: str | None = None
    ) -> bool:
        """
        Write a binary artifact to the cycle data store.
        
        Args:
            area: Area name (meta, shared, agents, artifacts, tests, telemetry)
            relative_path: Relative path within the area
            data: Binary data to write
            agent_name: Optional agent name for agent-specific areas
            
        Returns:
            True if successful, False otherwise
        """
        try:
            area_path = self._get_area_path(area, agent_name)
            file_path = area_path / relative_path
            
            # Create intermediate directories
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            file_path.write_bytes(data)
            logger.debug(f"Wrote binary artifact: {file_path}")
            return True
            
        except ValueError:
            # Re-raise ValueError (invalid area) so callers can handle it
            raise
        except Exception as e:
            logger.error(f"Failed to write binary artifact {area}/{relative_path}: {e}")
            return False
    
    def read_text_artifact(
        self,
        area: str,
        relative_path: str,
        agent_name: str | None = None
    ) -> str | None:
        """
        Read a text artifact from the cycle data store.
        
        Args:
            area: Area name (meta, shared, agents, artifacts, tests, telemetry)
            relative_path: Relative path within the area
            agent_name: Optional agent name for agent-specific areas
            
        Returns:
            File content as string, or None if file doesn't exist
        """
        try:
            area_path = self._get_area_path(area, agent_name)
            file_path = area_path / relative_path
            
            if not file_path.exists():
                logger.debug(f"Text artifact not found: {file_path}")
                return None
            
            content = file_path.read_text(encoding='utf-8')
            logger.debug(f"Read text artifact: {file_path}")
            return content
            
        except Exception as e:
            logger.error(f"Failed to read text artifact {area}/{relative_path}: {e}")
            return None
    
    def read_binary_artifact(
        self,
        area: str,
        relative_path: str,
        agent_name: str | None = None
    ) -> bytes | None:
        """
        Read a binary artifact from the cycle data store.
        
        Args:
            area: Area name (meta, shared, agents, artifacts, tests, telemetry)
            relative_path: Relative path within the area
            agent_name: Optional agent name for agent-specific areas
            
        Returns:
            File content as bytes, or None if file doesn't exist
        """
        try:
            area_path = self._get_area_path(area, agent_name)
            file_path = area_path / relative_path
            
            if not file_path.exists():
                logger.debug(f"Binary artifact not found: {file_path}")
                return None
            
            data = file_path.read_bytes()
            logger.debug(f"Read binary artifact: {file_path}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to read binary artifact {area}/{relative_path}: {e}")
            return None
    
    def append_telemetry_event(
        self,
        event: dict[str, Any],
        agent_name: str | None = None
    ) -> bool:
        """
        Append a telemetry event as a JSON line to the telemetry stream.
        
        Args:
            event: Event dictionary to append
            agent_name: Optional agent name for agent-specific telemetry streams
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Determine telemetry file path
            if agent_name:
                telemetry_file = self._get_area_path('telemetry', agent_name) / f"{agent_name}.jsonl"
            else:
                telemetry_file = self._get_area_path('telemetry') / "events.jsonl"
            
            # Ensure directory exists
            telemetry_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Append JSON line
            json_line = json.dumps(event, ensure_ascii=False)
            with telemetry_file.open('a', encoding='utf-8') as f:
                f.write(json_line + '\n')
            
            logger.debug(f"Appended telemetry event to: {telemetry_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to append telemetry event: {e}")
            return False

