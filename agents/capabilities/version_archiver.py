#!/usr/bin/env python3
"""
Version Archiver Capability Handler
Implements version.archive capability for archiving existing versions.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class VersionArchiver:
    """
    Version Archiver - Implements version.archive capability
    
    Archives existing versions using VersionManager and AppBuilder.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize VersionArchiver with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
        
        # Import VersionManager and AppBuilder as tools
        from agents.tools.app_builder import AppBuilder
        from agents.tools.version_manager import VersionManager
        
        self.version_manager = VersionManager()
        self.app_builder = AppBuilder(llm_client=agent_instance.llm_client, agent=agent_instance)
    
    async def archive(self, task_id: str, requirements: dict[str, Any]) -> dict[str, Any]:
        """
        Archive existing version.
        
        Implements the version.archive capability.
        
        Args:
            task_id: Task identifier
            requirements: Requirements dictionary containing:
                - application: Application name
                - version: New version to archive for
                - source_dir: Source directory (optional)
                - cycle_id: Execution cycle ID
                - pid: Process ID
                
        Returns:
            Dictionary containing:
            - task_id: Task identifier
            - status: Completion status
            - action: Action type
            - app_name: Application name
            - archived_version: Archived version
            - archive_dir: Archive directory path
        """
        try:
            app_name = requirements.get('application', 'application')
            app_kebab = self.app_builder._to_kebab_case(app_name)
            new_version = requirements.get('version', 'unknown')
            source_dir = requirements.get('source_dir', f"warm-boot/apps/{app_kebab}")
            
            logger.info(f"{self.name} archiving existing version for {app_name}")
            
            # Use VersionManager to archive existing version
            archive_result = await self.version_manager.archive_existing_version(
                app_name, source_dir, new_version
            )
            
            if archive_result['status'] == 'success':
                logger.info(f"{self.name} completed archive task: {task_id}")
                return {
                    'task_id': task_id,
                    'status': 'completed',
                    'action': 'archive',
                    'app_name': app_name,
                    'archived_version': archive_result['archived_version'],
                    'archive_dir': archive_result['archive_dir']
                }
            else:
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': archive_result.get('error', 'Archive failed'),
                    'action': 'archive'
                }
                
        except Exception as e:
            logger.error(f"{self.name} failed to archive version: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e),
                'action': 'archive'
            }

