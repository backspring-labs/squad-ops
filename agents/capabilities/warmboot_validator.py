#!/usr/bin/env python3
"""
WarmBoot Validator Capability Handler
Implements validate.warmboot capability for validating WarmBoot execution and generating wrap-up.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class WarmBootValidator:
    """
    WarmBoot Validator - Implements validate.warmboot capability
    
    Validates WarmBoot execution by processing governance tasks and generating wrap-up results.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize WarmBootValidator with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
    
    async def validate(self, request: Dict[str, Any], metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate WarmBoot execution and generate wrap-up.
        
        Implements the validate.warmboot capability.
        
        Args:
            request: Request dictionary containing:
                - task_id: Task identifier (optional)
                - application: Application name
                - request_type: Request type
                - agents: List of agents
                - priority: Priority level
                - description: Task description
                - requirements: Task requirements
                - prd_path: PRD file path
            metadata: Request metadata containing:
                - ecid: Execution cycle ID
                - pid: Process ID
                
        Returns:
            Dictionary containing:
            - match: Boolean indicating if validation matched expectations
            - diffs: List of differences found
            - wrap_up_uri: URI to wrap-up document
            - metrics: Validation metrics
        """
        try:
            metadata = metadata or {}
            ecid = metadata.get('ecid', 'unknown')
            pid = metadata.get('pid', 'unknown')
            
            logger.info(f"{self.name} validating WarmBoot execution for ECID: {ecid}")
            
            # Convert AgentRequest to old task format for compatibility with process_task
            task = {
                'task_id': request.get('task_id', f"{ecid}-main"),
                'type': 'governance',
                'ecid': ecid,
                'pid': pid,
                'application': request.get('application'),
                'request_type': request.get('request_type'),
                'agents': request.get('agents', []),
                'priority': request.get('priority', 'MEDIUM'),
                'description': request.get('description'),
                'requirements': request.get('requirements'),
                'prd_path': request.get('prd_path')
            }
            
            # Process task via agent's process_task method
            result = await self.agent.process_task(task)
            
            # Convert result to validate.warmboot capability format
            validation_result = {
                'match': result.get('status') == 'completed',
                'diffs': result.get('diffs', []),
                'wrap_up_uri': result.get('wrap_up_uri', f'/warm-boot/runs/{ecid}/wrap-up.md'),
                'metrics': result.get('metrics', {})
            }
            
            logger.info(f"{self.name} completed WarmBoot validation for ECID: {ecid}, match: {validation_result['match']}")
            return validation_result
            
        except Exception as e:
            logger.error(f"{self.name} failed to validate WarmBoot execution: {e}", exc_info=True)
            return {
                'match': False,
                'diffs': [],
                'wrap_up_uri': None,
                'metrics': {},
                'error': str(e)
            }


