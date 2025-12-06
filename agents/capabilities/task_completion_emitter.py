#!/usr/bin/env python3
"""
Task Completion Emitter Capability Handler
Implements task.completion.emit capability for emitting developer completion events to LeadAgent.
"""

import hashlib
import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class TaskCompletionEmitter:
    """
    Task Completion Emitter - Implements task.completion.emit capability
    
    Emits developer completion events for WarmBoot wrap-up generation.
    Handles task duration calculation, artifact hashing, and reasoning summary extraction.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize TaskCompletionEmitter with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
        self.communication_log = getattr(agent_instance, 'communication_log', [])
        self.task_start_times = getattr(agent_instance, 'task_start_times', {})
        self._role_to_agent_cache = None
    
    def _calculate_total_tokens_used(self) -> int:
        """
        Calculate total tokens used from communication log entries.
        
        Returns:
            Total number of tokens used across all LLM calls in the communication log
        """
        total_tokens = 0
        for entry in self.communication_log:
            if 'token_usage' in entry and isinstance(entry['token_usage'], dict):
                token_usage = entry['token_usage']
                total_tokens += token_usage.get('total_tokens', 0)
        return total_tokens
    
    def _load_role_to_agent_mapping(self) -> dict[str, str]:
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
            
            # Find instances.yaml
            base_path = Path(__file__).parent.parent.parent
            instances_path = base_path / 'config' / 'instances.yaml'
            
            if instances_path.exists():
                with open(instances_path) as f:
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
    
    def _extract_reasoning_summary_for_task(self, cycle_id: str, action: str) -> dict[str, Any]:
        """
        Extract reasoning summary from communication log for a specific task/action.
        
        Args:
            cycle_id: Execution cycle identifier
            action: Task action (manifest_generation, build, deploy)
            
        Returns:
            Dictionary with reasoning summary for the task
        """
        reasoning_events = []
        
        # Map action to context
        context_map = {
            'archive': 'archive',
            'design_manifest': 'manifest_generation',
            'build': 'build',
            'deploy': 'deploy'
        }
        
        target_context = context_map.get(action, action)
        
        # Find reasoning events in communication log for this cycle_id and context
        for entry in self.communication_log:
            entry_cycle_id = entry.get('cycle_id')
            entry_type = entry.get('message_type', '')
            
            # Check for LLM reasoning entries
            if entry_cycle_id == cycle_id and entry_type == 'llm_reasoning':
                description = entry.get('description', '')
                # Match context more precisely - check for context word in description
                description_lower = description.lower()
                context_patterns = [
                    f"{target_context}:",  # "build:" or "manifest_generation:"
                    f"appbuilder {target_context}",  # "appbuilder build"
                    f"{target_context} "  # "build " (space after)
                ]
                if any(pattern in description_lower for pattern in context_patterns):
                    reasoning_events.append({
                        'timestamp': entry.get('timestamp'),
                        'summary': description[:200] + ('...' if len(description) > 200 else ''),
                        'context': target_context
                    })
        
        # Build summary
        if reasoning_events:
            return {
                'context': target_context,
                'event_count': len(reasoning_events),
                'key_decisions': [event['summary'] for event in reasoning_events[:3]],  # Top 3
                'reasoning_available': True
            }
        else:
            return {
                'context': target_context,
                'event_count': 0,
                'key_decisions': [],
                'reasoning_available': False,
                'note': 'No reasoning events found for this task'
            }
    
    async def emit(self, task_id: str, cycle_id: str, result: dict[str, Any]) -> dict[str, Any]:
        """
        Emit developer completion event for WarmBoot wrap-up.
        
        Implements the task.completion.emit capability.
        
        Args:
            task_id: Task identifier
            cycle_id: Execution cycle identifier
            result: Task result dictionary containing:
                - action: Task action (archive, build, deploy, etc.)
                - created_files: List of created file paths
                - status: Task status
                - tests_passed: Number of tests passed (optional)
                - tests_failed: Number of tests failed (optional)
                
        Returns:
            Dictionary containing:
            - event_sent: Boolean indicating if event was sent successfully
            - task_id: Task identifier
            - cycle_id: Execution cycle identifier
        """
        try:
            # Calculate task duration
            duration_seconds = 0
            if task_id in self.task_start_times:
                start_time = self.task_start_times[task_id]
                duration_seconds = (datetime.utcnow() - start_time).total_seconds()
                # Clean up start time after calculation
                del self.task_start_times[task_id]
            
            # Build list of artifacts with actual hashes
            artifacts = []
            if 'created_files' in result:
                for file_path in result['created_files']:
                    artifact_hash = "sha256:no_hash"
                    try:
                        if os.path.exists(file_path):
                            with open(file_path, 'rb') as f:
                                file_hash = hashlib.sha256(f.read()).hexdigest()
                                artifact_hash = f"sha256:{file_hash}"
                    except Exception as e:
                        logger.debug(f"{self.name} failed to hash artifact {file_path}: {e}")
                    
                    artifacts.append({
                        'path': file_path,
                        'hash': artifact_hash
                    })
            
            # Determine tasks completed based on action
            action = result.get('action', 'unknown')
            tasks_completed = []
            if action == 'archive':
                tasks_completed = ['archive']
            elif action == 'build':
                tasks_completed = ['scaffold', 'implement', 'test']
            elif action == 'deploy':
                tasks_completed = ['deploy']
            else:
                tasks_completed = [action]
            
            # Extract reasoning summary from communication log for this task/cycle_id
            reasoning_summary = self._extract_reasoning_summary_for_task(cycle_id, action)
            
            # Create completion event payload
            completion_event = {
                'event_type': 'task.developer.completed',
                'sender_agent': self.name,
                'sender_role': 'developer',
                'cycle_id': cycle_id,
                'timestamp': datetime.utcnow().isoformat(),
                'payload': {
                    'task_id': task_id,
                    'task_group': 'code_generation',
                    'tasks_completed': tasks_completed,
                    'artifacts': artifacts,
                    'metrics': {
                        'duration_seconds': round(duration_seconds, 2),
                        'tokens_used': self._calculate_total_tokens_used(),
                        'tests_passed': result.get('tests_passed', 0),
                        'tests_failed': result.get('tests_failed', 0)
                    },
                    'reasoning_summary': reasoning_summary,
                    'status': result.get('status', 'unknown')
                }
            }
            
            # Determine lead agent dynamically for event aggregation
            lead_agent_id = self._get_lead_agent_id()
            
            # Send completion event to lead agent (will handle wrap-up task delegation)
            await self.agent.send_message(
                recipient=lead_agent_id,
                message_type='task.developer.completed',
                payload=completion_event['payload'],
                context={
                    'event_type': completion_event['event_type'],
                    'sender_role': completion_event['sender_role'],
                    'cycle_id': cycle_id
                }
            )
            
            logger.info(f"{self.name} emitted developer completion event for task {task_id}, cycle_id {cycle_id}")
            
            return {
                'event_sent': True,
                'task_id': task_id,
                'cycle_id': cycle_id
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to emit developer completion event: {e}", exc_info=True)
            return {
                'event_sent': False,
                'task_id': task_id,
                'cycle_id': cycle_id,
                'error': str(e)
            }

