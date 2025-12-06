#!/usr/bin/env python3
"""
Governance Task Coordination Capability Handler
Implements governance.task_coordination capability for coordinating and delegating tasks across squad.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class GovernanceTaskCoordination:
    """
    Governance Task Coordination - Implements governance.task_coordination capability
    
    Coordinates task delegation across squad by determining target agents and sending delegation messages.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize GovernanceTaskCoordination with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
        # Access capability loader for determining delegation targets
        self.capability_loader = getattr(agent_instance, 'capability_loader', None)
    
    async def coordinate(self, request: dict[str, Any], metadata: dict[str, Any] = None) -> dict[str, Any]:
        """
        Coordinate task delegation across squad.
        
        Implements the governance.task_coordination capability.
        
        Args:
            request: Request dictionary containing:
                - type: Task type
                - payload: Task payload (optional, will use request if not provided)
            metadata: Request metadata (optional)
                
        Returns:
            Dictionary containing:
            - tasks_created: Number of tasks created
            - tasks_delegated: Number of tasks delegated
            - coordination_log: Log of coordination actions
        """
        try:
            task_type = request.get('type', 'unknown')
            payload = request.get('payload', request)
            metadata = metadata or {}
            
            logger.info(f"{self.name} coordinating task delegation for type: {task_type}")
            
            # Determine delegation target via capability loader
            if not self.capability_loader:
                logger.error(f"{self.name}: Capability loader not initialized")
                delegation_target = 'dev-agent'  # Fallback
            else:
                try:
                    delegation_result = await self.capability_loader.execute(
                        'task.determine_target', self.agent, task_type
                    )
                    delegation_target = delegation_result.get('target_agent', 'dev-agent')
                except Exception as e:
                    logger.error(f"{self.name}: Failed to determine delegation target: {e}")
                    delegation_target = 'dev-agent'  # Fallback
            
            # Send message to delegation target
            await self.agent.send_message(
                recipient=delegation_target,
                message_type="task_delegation",
                payload=payload,
                context=metadata
            )
            
            result = {
                'tasks_created': 1,
                'tasks_delegated': 1,
                'coordination_log': f"Delegated {task_type} to {delegation_target}"
            }
            
            logger.info(f"{self.name} successfully coordinated delegation of {task_type} to {delegation_target}")
            return result
            
        except Exception as e:
            logger.error(f"{self.name} failed to coordinate task delegation: {e}", exc_info=True)
            return {
                'tasks_created': 0,
                'tasks_delegated': 0,
                'coordination_log': f"Coordination failed: {str(e)}",
                'error': str(e)
            }


