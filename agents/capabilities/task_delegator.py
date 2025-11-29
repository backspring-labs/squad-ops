#!/usr/bin/env python3
"""
Task Delegator Capability Handler
Implements task.delegate and task.determine_target capabilities for delegating tasks to other agents.
"""

import logging
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class TaskDelegator:
    """
    Task Delegator - Implements task.delegate and task.determine_target capabilities
    
    Handles task delegation logic including:
    - Determining which agent should handle a task
    - Delegating tasks to other agents
    - Managing role-to-agent mappings
    """
    
    def __init__(self, agent):
        """
        Initialize TaskDelegator with agent instance.
        
        Args:
            agent: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent
        self.name = agent.name if hasattr(agent, 'name') else 'unknown'
        self.instances_file = agent.instances_file if hasattr(agent, 'instances_file') else "agents/instances/instances.yaml"
        self.task_api_url = agent.task_api_url if hasattr(agent, 'task_api_url') else 'http://localhost:8001'
        self._role_to_agent_cache = None
    
    async def determine_target(self, task_type: str) -> Dict[str, Any]:
        """
        Determine which agent should handle a task based on role.
        
        Implements the task.determine_target capability.
        
        Args:
            task_type: Type of task (e.g., 'development', 'testing', 'strategy')
            
        Returns:
            Dictionary containing target_agent, target_role, and reasoning
        """
        try:
            # Map task types to roles
            task_to_role_map = {
                'code': 'dev',
                'development': 'dev',
                'deployment': 'dev',
                'archive': 'dev',
                'build': 'dev',
                'product': 'strat',
                'strategy': 'strat',
                'data': 'data',
                'analytics': 'data',
                'security': 'qa',
                'testing': 'qa',
                'financial': 'finance',
                'creative': 'creative',
                'design': 'creative',
                'analysis': 'curator',
                'research': 'curator',
                'communication': 'comms',
                'audit': 'audit',
                'warmboot_wrapup': None  # Special case - use capability binding
            }
            
            # Governance tasks should NEVER be delegated
            if task_type.lower() == 'governance':
                raise ValueError(f"Governance tasks should not be delegated - handled by lead directly")
            
            # Special handling for warmboot_wrapup - use capability binding
            if task_type.lower() == 'warmboot_wrapup':
                capability_loader = getattr(self.agent, 'capability_loader', None)
                if capability_loader:
                    try:
                        agent_id = capability_loader.get_agent_for_capability('warmboot.wrapup')
                        if agent_id:
                            logger.debug(f"Task type '{task_type}' → capability 'warmboot.wrapup' → agent '{agent_id}'")
                            return {
                                'target_agent': agent_id,
                                'target_role': None,  # Not role-based
                                'reasoning': f"Task type '{task_type}' resolved via capability binding to agent '{agent_id}'"
                            }
                    except Exception as e:
                        logger.warning(f"Failed to resolve wrap-up agent via capability binding: {e}")
                # Fallback to lead role if capability binding fails
                role_to_agent_map = self._load_role_to_agent_mapping()
                agent_id = role_to_agent_map.get('lead', 'max')
                logger.debug(f"Task type '{task_type}' → fallback to lead role → agent '{agent_id}'")
                return {
                    'target_agent': agent_id,
                    'target_role': 'lead',
                    'reasoning': f"Task type '{task_type}' resolved via fallback to lead role '{agent_id}'"
                }
            
            # Get role for this task type (default to 'dev' for unknown types)
            target_role = task_to_role_map.get(task_type.lower(), 'dev')
            
            # Load role-to-agent mapping from instances.yaml
            role_to_agent_map = self._load_role_to_agent_mapping()
            
            agent_id = role_to_agent_map.get(target_role, 'dev-agent')
            logger.debug(f"Task type '{task_type}' → role '{target_role}' → agent '{agent_id}'")
            
            reasoning = f"Task type '{task_type}' maps to role '{target_role}', which resolves to agent '{agent_id}'"
            
            return {
                'target_agent': agent_id,
                'target_role': target_role,
                'reasoning': reasoning
            }
        except ValueError:
            # Re-raise ValueError (e.g., for governance tasks) - don't catch it
            raise
        except Exception as e:
            logger.error(f"{self.name} failed to determine delegation target: {e}")
            return {
                'target_agent': 'dev-agent',
                'target_role': 'dev',
                'reasoning': f"Failed to determine target: {str(e)}",
                'error': str(e)
            }
    
    async def delegate(self, task: Dict[str, Any], delegation_reason: str = None) -> Dict[str, Any]:
        """
        Delegate a task to another agent.
        
        Implements the task.delegate capability.
        
        Args:
            task: Task dictionary to delegate
            delegation_reason: Optional reason for delegation
            
        Returns:
            Dictionary containing task_id, target_agent, delegation_status, and delegation_time
        """
        try:
            task_id = task.get('task_id', 'unknown')
            task_type = task.get('task_type', 'development')
            
            # Determine target agent
            target_info = await self.determine_target(task_type)
            target_agent = target_info.get('target_agent', 'dev-agent')
            
            # Create delegation reason if not provided
            if not delegation_reason:
                delegation_reason = f"Task type '{task_type}' delegated to {target_agent}"
            
            # Send message to target agent
            await self.agent.send_message(
                recipient=target_agent,
                message_type="task_delegation",
                payload=task,
                context={
                    'delegated_by': self.name,
                    'delegation_reason': delegation_reason,
                    'ecid': task.get('ecid')
                }
            )
            
            delegation_time = datetime.utcnow().isoformat()
            
            logger.info(f"{self.name} delegated task {task_id} to {target_agent}")
            
            return {
                'task_id': task_id,
                'target_agent': target_agent,
                'delegation_status': 'success',
                'delegation_time': delegation_time
            }
        except Exception as e:
            logger.error(f"{self.name} failed to delegate task: {e}")
            return {
                'task_id': task.get('task_id', 'unknown'),
                'target_agent': None,
                'delegation_status': 'failed',
                'delegation_time': datetime.utcnow().isoformat(),
                'error': str(e)
            }
    
    def _load_role_to_agent_mapping(self) -> Dict[str, str]:
        """
        Load role-to-agent mapping from instances.yaml.
        Returns dict mapping role -> agent_id for enabled agents.
        Caches result for performance.
        """
        if self._role_to_agent_cache is not None:
            return self._role_to_agent_cache
        
        try:
            instances_path = Path(self.instances_file)
            if not instances_path.exists():
                logger.warning(f"Instances file not found: {self.instances_file}, using defaults")
                return self._get_default_role_mapping()
            
            with open(instances_path, 'r') as f:
                data = yaml.safe_load(f)
            
            # Build role -> agent_id mapping from enabled instances
            role_to_agent = {}
            for instance in data.get('instances', []):
                if instance.get('enabled', False):
                    role = instance.get('role')
                    agent_id = instance.get('id')
                    if role and agent_id:
                        # If multiple agents have same role, keep first (TODO: add load balancing)
                        if role not in role_to_agent:
                            role_to_agent[role] = agent_id
            
            self._role_to_agent_cache = role_to_agent
            logger.info(f"Loaded role-to-agent mapping: {role_to_agent}")
            return role_to_agent
            
        except Exception as e:
            logger.error(f"Failed to load instances.yaml: {e}, using defaults")
            return self._get_default_role_mapping()
    
    def _get_default_role_mapping(self) -> Dict[str, str]:
        """Fallback role-to-agent mapping if instances.yaml can't be loaded"""
        return {
            'lead': 'max',
            'dev': 'neo',
            'strat': 'nat',
            'qa': 'eve',
            'data': 'data',
            'finance': 'quark',
            'creative': 'glyph',
            'comms': 'joi',
            'curator': 'og',
            'audit': 'hal'
        }

