#!/usr/bin/env python3
"""
Documentation Creator Capability Handler
Implements comms.documentation capability for creating documentation and written content.
"""

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class DocumentationCreator:
    """
    Documentation Creator - Implements comms.documentation capability
    
    Creates task documentation files in markdown format.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize DocumentationCreator with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
    
    async def create(self, task_id: str, result: dict[str, Any]) -> dict[str, Any]:
        """
        Create documentation for the task.
        
        Implements the comms.documentation capability.
        
        Args:
            task_id: Task identifier
            result: Task result dictionary containing:
                - status: Task status
                - action: Task action
                - app_name: Application name (optional)
                - version: Application version (optional)
                - created_files: List of created files (optional)
                - image: Docker image name (optional)
                - container_name: Container name (optional)
                - archived_version: Archived version (optional)
                
        Returns:
            Dictionary containing:
            - documentation_uri: URI to documentation file
            - content: Documentation content
            - format: Documentation format ('markdown')
        """
        try:
            # Create runs directory if it doesn't exist
            runs_dir = "warm-boot/runs"
            await self.agent.write_file(f"{runs_dir}/.gitkeep", "")
            
            # Create task-specific directory
            task_dir = f"{runs_dir}/{task_id}"
            
            # Generate documentation content
            doc_content = f"""# Task Documentation: {task_id}

**Processed by**: {self.name} (DevAgent)
**Timestamp**: {asyncio.get_event_loop().time()}
**Status**: {result.get('status', 'unknown')}

## Task Details
- **Task ID**: {task_id}
- **Action**: {result.get('action', 'unknown')}
- **App Name**: {result.get('app_name', 'N/A')}
- **Version**: {result.get('version', 'N/A')}

## Results
{json.dumps(result, indent=2)}

## Capabilities Used
- **manifest.generate**: {result.get('created_files', [])}
- **docker.build**: {result.get('image', 'N/A')}
- **docker.deploy**: {result.get('container_name', 'N/A')}
- **version.archive**: {result.get('archived_version', 'N/A')}

## Notes
This task was processed using the refactored Dev Agent with capabilities.
Each capability handles a specific aspect of the development workflow.
"""
            
            # Write documentation file
            doc_file = f"{task_dir}/task-summary.md"
            await self.agent.write_file(doc_file, doc_content)
            
            logger.info(f"{self.name} created documentation: {doc_file}")
            
            return {
                'documentation_uri': doc_file,
                'content': doc_content,
                'format': 'markdown'
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to create documentation: {e}", exc_info=True)
            return {
                'documentation_uri': None,
                'content': None,
                'format': 'markdown',
                'error': str(e)
            }


