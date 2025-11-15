#!/usr/bin/env python3
"""
Governance Escalation Capability Handler
Implements governance.escalation capability for handling task escalation requests.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class GovernanceEscalation:
    """
    Governance Escalation - Implements governance.escalation capability
    
    Handles task escalation to premium consultation.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize GovernanceEscalation with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
    
    async def escalate(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Escalate task to premium consultation.
        
        Implements the governance.escalation capability.
        
        Args:
            request: Request dictionary containing:
                - task_id: Task identifier
                - task: Task dictionary (optional, will use request if not provided)
                
        Returns:
            Dictionary containing:
            - escalated: Boolean indicating escalation status
            - resolution: Resolution type ('escalated_to_premium')
            - escalation_time: Time taken for escalation (in seconds)
        """
        try:
            task_id = request.get('task_id', 'unknown')
            task = request.get('task', request)
            
            logger.info(f"{self.name} escalating task: {task_id}")
            
            # Call agent's escalate_task method
            await self.agent.escalate_task(task_id, task)
            
            result = {
                'escalated': True,
                'resolution': 'escalated_to_premium',
                'escalation_time': 1.0
            }
            
            logger.info(f"{self.name} successfully escalated task {task_id}")
            return result
            
        except Exception as e:
            logger.error(f"{self.name} failed to escalate task: {e}", exc_info=True)
            return {
                'escalated': False,
                'resolution': 'error',
                'escalation_time': 0.0,
                'error': str(e)
            }


