#!/usr/bin/env python3
"""
Governance Approval Capability Handler
Implements governance.approval capability for processing approval requests and decisions.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class GovernanceApproval:
    """
    Governance Approval - Implements governance.approval capability
    
    Processes approval requests and makes governance decisions based on complexity thresholds.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize GovernanceApproval with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
        # Access agent's escalation_threshold for complexity checks
        self.escalation_threshold = getattr(agent_instance, 'escalation_threshold', 0.7)
    
    async def approve(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process approval request.
        
        Implements the governance.approval capability.
        
        Args:
            request: Request dictionary containing:
                - complexity: Complexity score (0.0-1.0)
                
        Returns:
            Dictionary containing:
            - approved: Boolean approval decision
            - decision: Decision type ('approved' or 'escalated')
            - approval_time: Time taken for decision (in seconds)
        """
        try:
            complexity = request.get('complexity', 0.5)
            
            logger.info(f"{self.name} processing approval request with complexity: {complexity}")
            
            # Check complexity against escalation threshold
            if complexity > self.escalation_threshold:
                result = {
                    'approved': False,
                    'decision': 'escalated',
                    'approval_time': 0.0
                }
                logger.info(f"{self.name} escalated approval request due to high complexity: {complexity} > {self.escalation_threshold}")
            else:
                result = {
                    'approved': True,
                    'decision': 'approved',
                    'approval_time': 0.5
                }
                logger.info(f"{self.name} approved request with complexity: {complexity}")
            
            return result
            
        except Exception as e:
            logger.error(f"{self.name} failed to process approval request: {e}", exc_info=True)
            return {
                'approved': False,
                'decision': 'error',
                'approval_time': 0.0,
                'error': str(e)
            }


