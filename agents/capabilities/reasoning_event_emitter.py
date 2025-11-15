#!/usr/bin/env python3
"""
Reasoning Event Emitter Capability Handler
Implements comms.reasoning.emit capability for emitting agent reasoning events to the lead agent for aggregation.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ReasoningEventEmitter:
    """
    Reasoning Event Emitter - Implements comms.reasoning.emit capability
    
    Emits reasoning events to the lead agent for aggregation in communication log.
    Lead agent stores these events and includes them in wrap-up task payload when delegating.
    Includes actual LLM reasoning from communication log if available.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize ReasoningEventEmitter with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
        self.communication_log = getattr(agent_instance, 'communication_log', [])
        self._role_to_agent_cache = None
    
    def _load_role_to_agent_mapping(self) -> Dict[str, str]:
        """
        Load role-to-agent mapping from instances.yaml.
        
        Returns:
            Dictionary mapping roles to agent IDs (e.g., {'lead': 'max', 'dev': 'neo'})
        """
        if self._role_to_agent_cache is not None:
            return self._role_to_agent_cache
        
        try:
            from pathlib import Path
            import yaml
            
            # Find instances.yaml (same logic as TaskDelegator)
            base_path = Path(__file__).parent.parent.parent
            instances_path = base_path / 'config' / 'instances.yaml'
            
            if instances_path.exists():
                with open(instances_path, 'r') as f:
                    instances = yaml.safe_load(f) or {}
                
                role_map = {}
                for agent_id, agent_data in instances.get('agents', {}).items():
                    role = agent_data.get('role', '').lower()
                    if role:
                        role_map[role] = agent_id
                
                self._role_to_agent_cache = role_map
                return role_map
        except Exception as e:
            logger.warning(f"{self.name} failed to load role-to-agent mapping: {e}")
        
        # Fallback to default mapping
        self._role_to_agent_cache = {'lead': 'max', 'dev': 'neo'}
        return self._role_to_agent_cache
    
    def _get_lead_agent_id(self) -> str:
        """
        Determine the lead agent ID dynamically for event aggregation.
        
        Returns:
            Lead agent ID (e.g., 'max')
        """
        role_map = self._load_role_to_agent_mapping()
        lead_agent = role_map.get('lead', 'max')
        return lead_agent
    
    async def emit(self, task_id: str, ecid: str, reason_step: str, 
                   summary: str, context: str, 
                   key_points: List[str] = None, confidence: float = None) -> Dict[str, Any]:
        """
        Emit reasoning event to lead agent for aggregation.
        
        Lead agent stores events in communication log and includes them in wrap-up task payload when delegating.
        
        Implements the comms.reasoning.emit capability.
        
        Args:
            task_id: Task identifier
            ecid: Execution cycle identifier
            reason_step: Type of reasoning step ('decision', 'hypothesis', 'checkpoint')
            summary: Brief summary of reasoning
            context: Operation context ('manifest_generation', 'build', 'deploy', etc.)
            key_points: Optional list of key points
            confidence: Optional confidence level (0.0-1.0)
            
        Returns:
            Dictionary containing:
            - event_sent: Boolean indicating if event was sent successfully
            - task_id: Task identifier
            - ecid: Execution cycle identifier
        """
        try:
            # Extract actual LLM reasoning from communication_log for this context
            llm_reasoning = None
            for entry in self.communication_log:
                entry_ecid = entry.get('ecid')
                entry_type = entry.get('message_type', '')
                entry_context = entry.get('description', '')
                
                # Match by ECID, llm_reasoning type, and context in description
                if (entry_ecid == ecid and 
                    entry_type == 'llm_reasoning' and 
                    context.lower() in entry_context.lower()):
                    # Found matching LLM reasoning - extract it
                    llm_reasoning = {
                        'prompt': entry.get('prompt', '')[:500],  # First 500 chars of prompt
                        'response': entry.get('full_response', '')[:1000],  # First 1000 chars of response
                        'token_usage': entry.get('token_usage', {}),
                        'timestamp': entry.get('timestamp')
                    }
                    break  # Use first matching entry
            
            reasoning_event = {
                'schema': 'reasoning.v1',
                'task_id': task_id,
                'ecid': ecid,
                'reason_step': reason_step,
                'summary': summary,
                'context': context,
                'timestamp': datetime.utcnow().isoformat(),
                'raw_reasoning_included': llm_reasoning is not None
            }
            
            # Add optional fields
            if key_points:
                reasoning_event['key_points'] = key_points
            if confidence is not None:
                reasoning_event['confidence'] = confidence
            
            # Include actual LLM reasoning if found
            if llm_reasoning:
                reasoning_event['llm_reasoning'] = llm_reasoning
                logger.debug(f"{self.name} included LLM reasoning in reasoning event for {context}")
            
            # Determine lead agent dynamically for event aggregation
            lead_agent_id = self._get_lead_agent_id()
            
            # Send reasoning event to lead agent for aggregation
            await self.agent.send_message(
                recipient=lead_agent_id,
                message_type='agent_reasoning',
                payload=reasoning_event,
                context={
                    'sender_agent': self.name,
                    'sender_role': 'developer',
                    'ecid': ecid
                }
            )
            
            if llm_reasoning:
                logger.info(f"{self.name} emitted reasoning event with LLM reasoning: {reason_step} for {context}")
            else:
                logger.debug(f"{self.name} emitted reasoning event (summary only): {reason_step} for {context}")
            
            return {
                'event_sent': True,
                'task_id': task_id,
                'ecid': ecid,
                'lead_agent': lead_agent_id
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to emit reasoning event: {e}", exc_info=True)
            return {
                'event_sent': False,
                'task_id': task_id,
                'ecid': ecid,
                'error': str(e)
            }

