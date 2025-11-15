#!/usr/bin/env python3
"""
Task Completion Handler Capability
Implements task.completion.handle capability for handling task completion events and orchestrating next steps.
"""

import asyncio
import logging
import aiohttp
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TaskCompletionHandler:
    """
    Task Completion Handler - Implements task.completion.handle capability
    
    Handles task completion events from developers and orchestrates the next steps
    in the WarmBoot sequence (design_manifest -> build -> deploy).
    """
    
    def __init__(self, agent_instance):
        """
        Initialize TaskCompletionHandler with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
        self.warmboot_state = getattr(agent_instance, 'warmboot_state', {})
        self.task_delegator = getattr(agent_instance, 'task_delegator', None)
        self.send_message = agent_instance.send_message if hasattr(agent_instance, 'send_message') else None
        self.communication_log = agent_instance.communication_log if hasattr(agent_instance, 'communication_log') else []
        self.record_memory = agent_instance.record_memory if hasattr(agent_instance, 'record_memory') else None
        self.task_api_url = getattr(agent_instance, 'task_api_url', 'http://task-api:8001')
        
        # Load capabilities via capability loader if available
        self.capability_loader = getattr(agent_instance, 'capability_loader', None)
        if self.capability_loader:
            # Load telemetry_collector capability
            try:
                from agents.capabilities.telemetry_collector import TelemetryCollector
                self.telemetry_collector = TelemetryCollector(agent_instance)
            except Exception as e:
                logger.warning(f"{self.name} failed to load TelemetryCollector: {e}")
                self.telemetry_collector = None
            
            # Load warmboot_memory_handler capability
            try:
                from agents.capabilities.warmboot_memory_handler import WarmBootMemoryHandler
                self.warmboot_memory_handler = WarmBootMemoryHandler(agent_instance)
            except Exception as e:
                logger.warning(f"{self.name} failed to load WarmBootMemoryHandler: {e}")
                self.warmboot_memory_handler = None
        else:
            # Fallback to agent attributes (for backward compatibility)
            self.telemetry_collector = getattr(agent_instance, 'telemetry_collector', None)
            self.warmboot_memory_handler = getattr(agent_instance, 'warmboot_memory_handler', None)
    
    async def handle_completion(self, message: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle task completion event.
        
        Implements the task.completion.handle capability.
        
        Args:
            message: Message payload containing task completion data
            context: Message context containing ECID and other metadata
            
        Returns:
            Dictionary containing handled status, next_action, and completion_status
        """
        try:
            task_id = message.get('task_id', 'unknown')
            ecid = context.get('ecid', message.get('ecid', 'unknown'))
            status = message.get('status', 'unknown')
            action = message.get('action', 'unknown')
            
            logger.info(f"{self.name} handling completion: task {task_id}, ECID {ecid}, status {status}, action {action}")
            
            # Route to specific completion handlers based on action
            if action == 'design_manifest':
                await self._handle_design_manifest_completion(message, context)
            elif action == 'build':
                await self._handle_build_completion(message, context)
            elif action == 'deploy':
                await self._handle_deploy_completion(message, context)
            
            # Only generate wrap-up if task was successful
            if status == 'completed' or status == 'success':
                # Wait briefly for any pending reasoning events to be processed
                await asyncio.sleep(0.5)
                
                # Extract reasoning events from communication log for this ECID
                reasoning_events = [
                    entry for entry in self.communication_log
                    if entry.get('ecid') == ecid 
                    and entry.get('message_type') == 'agent_reasoning'
                ]
                
                if len(reasoning_events) > 0:
                    logger.info(f"{self.name} found {len(reasoning_events)} reasoning events for ECID {ecid} before delegating wrap-up")
                else:
                    logger.debug(f"{self.name} no reasoning events found for ECID {ecid} before delegating wrap-up")
                
                logger.info(f"{self.name} delegating WarmBoot wrap-up generation for ECID {ecid}")
                
                # Collect telemetry data
                telemetry = {}
                if self.telemetry_collector:
                    telemetry = await self.telemetry_collector.collect(ecid, task_id)
                
                # Create wrap-up task and delegate to agent with warmboot.wrapup capability
                if self.capability_loader:
                    try:
                        # Determine target agent for wrap-up task
                        delegation_result = await self.capability_loader.execute(
                            'task.determine_target', self.agent, 'warmboot_wrapup'
                        )
                        wrapup_agent = delegation_result.get('target_agent')
                        
                        if wrapup_agent:
                            # Create wrap-up task payload
                            wrapup_task = {
                                'type': 'warmboot_wrapup',
                                'task_id': f"{task_id}-wrapup",
                                'ecid': ecid,
                                'original_task_id': task_id,
                                'completion_payload': message,
                                'reasoning_events': reasoning_events,
                                'telemetry': telemetry
                            }
                            
                            # Delegate wrap-up task
                            await self.agent.send_message(
                                recipient=wrapup_agent,
                                message_type='task_delegation',
                                payload=wrapup_task,
                                context={
                                    'ecid': ecid,
                                    'delegated_by': self.name,
                                    'task_type': 'warmboot_wrapup'
                                }
                            )
                            logger.info(f"{self.name} delegated wrap-up task to {wrapup_agent} for ECID {ecid}")
                        else:
                            logger.warning(f"{self.name} could not determine wrap-up agent, skipping wrap-up generation")
                    except Exception as e:
                        logger.error(f"{self.name} failed to delegate wrap-up task: {e}", exc_info=True)
                else:
                    logger.warning(f"{self.name} capability_loader not available, cannot delegate wrap-up task")
            else:
                logger.warning(f"{self.name} skipping wrap-up for unsuccessful task: {status}")
            
            return {
                'handled': True,
                'next_action': self._determine_next_action(action),
                'completion_status': status
            }
                
        except Exception as e:
            logger.error(f"{self.name} failed to handle completion: {e}")
            return {
                'handled': False,
                'next_action': None,
                'completion_status': 'error',
                'error': str(e)
            }
    
    async def _handle_design_manifest_completion(self, message: Dict[str, Any], context: Dict[str, Any]) -> None:
        """Handle design manifest completion - extract manifest and trigger build task"""
        try:
            task_id = message.get('task_id', 'unknown')
            ecid = context.get('ecid', message.get('ecid', 'unknown'))
            status = message.get('status', 'unknown')
            
            logger.info(f"{self.name} received design manifest completion: task {task_id}, ECID {ecid}, status {status}")
            
            if status == 'completed' and 'manifest' in message:
                # Extract manifest from Neo's response
                manifest = message['manifest']
                self.warmboot_state['manifest'] = manifest
                
                logger.info(f"{self.name} stored manifest for ECID {ecid}: {manifest.get('architecture', {}).get('type', 'unknown')} with {len(manifest.get('files', []))} files")
                
                # Find and delegate the build task with the manifest
                await self._delegate_build_task_with_manifest(ecid, manifest)
            else:
                logger.warning(f"{self.name} design manifest task failed or missing manifest: {status}")
                
        except Exception as e:
            logger.error(f"{self.name} failed to handle design manifest completion: {e}")
    
    async def _handle_build_completion(self, message: Dict[str, Any], context: Dict[str, Any]) -> None:
        """Handle build completion - extract files and trigger deploy task"""
        try:
            task_id = message.get('task_id', 'unknown')
            ecid = context.get('ecid', message.get('ecid', 'unknown'))
            status = message.get('status', 'unknown')
            
            logger.info(f"{self.name} received build completion: task {task_id}, ECID {ecid}, status {status}")
            
            if status == 'completed' and 'created_files' in message:
                # Extract created files from Neo's response
                created_files = message['created_files']
                self.warmboot_state['build_files'] = created_files
                
                logger.info(f"{self.name} stored build files for ECID {ecid}: {len(created_files)} files created")
                
                # Trigger next task in sequence (deploy)
                await self._trigger_next_task(ecid, 'deploy')
            else:
                logger.warning(f"{self.name} build task failed or missing files: {status}")
                
        except Exception as e:
            logger.error(f"{self.name} failed to handle build completion: {e}")
    
    async def _handle_deploy_completion(self, message: Dict[str, Any], context: Dict[str, Any]) -> None:
        """Handle deploy completion - trigger governance logging"""
        try:
            task_id = message.get('task_id', 'unknown')
            ecid = context.get('ecid', message.get('ecid', 'unknown'))
            status = message.get('status', 'unknown')
            
            logger.info(f"{self.name} received deploy completion: task {task_id}, ECID {ecid}, status {status}")
            
            if status == 'completed':
                # Trigger governance logging via capability
                if self.warmboot_memory_handler:
                    await self.warmboot_memory_handler.log_governance(ecid, self.warmboot_state.get('manifest', {}), self.warmboot_state.get('build_files', []))
                
                # Record memory for WarmBoot completion
                if self.record_memory:
                    await self.record_memory(
                        kind="warmboot_completion",
                        payload={
                            'ecid': ecid,
                            'task_id': task_id,
                            'manifest': self.warmboot_state.get('manifest', {}),
                            'build_files_count': len(self.warmboot_state.get('build_files', []))
                        },
                        importance=0.9,
                        task_context={'ecid': ecid, 'pid': message.get('pid')}
                    )
                
                logger.info(f"{self.name} completed three-task sequence for ECID {ecid}")
            else:
                logger.warning(f"{self.name} deploy task failed: {status}")
                
        except Exception as e:
            logger.error(f"{self.name} failed to handle deploy completion: {e}")
    
    async def _trigger_next_task(self, ecid: str, next_action: str) -> None:
        """Trigger the next task in the sequence"""
        try:
            logger.info(f"{self.name} triggering next task: {next_action} for ECID {ecid}")
            # This is a placeholder - in a real implementation, we'd:
            # 1. Find the next task in the sequence
            # 2. Send it to Neo
            # 3. Update warmboot_state
            # For now, we'll rely on the existing task delegation system
        except Exception as e:
            logger.error(f"{self.name} failed to trigger next task: {e}")
    
    async def _delegate_build_task_with_manifest(self, ecid: str, manifest: Dict[str, Any]) -> None:
        """Find the pending build task for this ECID and delegate it with the manifest"""
        try:
            async with aiohttp.ClientSession() as session:
                # Query tasks API for pending build task with this ECID
                async with session.get(
                    f"{self.task_api_url}/api/v1/tasks",
                    params={"ecid": ecid, "status": "pending"}
                ) as resp:
                    if resp.status == 200:
                        tasks = await resp.json()
                        build_task = None
                        for task in tasks:
                            if task.get('requirements', {}).get('action') == 'build':
                                build_task = task
                                break
                        
                        if build_task:
                            # Update task with manifest
                            build_task['requirements']['manifest'] = manifest
                            
                            # Delegate to Neo
                            if self.task_delegator:
                                delegation_result = await self.task_delegator.determine_target('development')
                                delegation_target = delegation_result.get('target_agent', 'dev-agent')
                                
                                if self.send_message:
                                    await self.send_message(
                                        recipient=delegation_target,
                                        message_type="task_delegation",
                                        payload=build_task,
                                        context={
                                            'delegated_by': self.name,
                                            'delegation_reason': f"Build task with manifest from design completion",
                                            'ecid': ecid
                                        }
                                    )
                                
                                logger.info(f"{self.name} delegated build task {build_task['task_id']} with manifest to {delegation_target}")
                        else:
                            logger.warning(f"{self.name} no pending build task found for ECID {ecid}")
                    else:
                        logger.warning(f"{self.name} failed to query tasks API: {resp.status}")
                        
        except Exception as e:
            logger.error(f"{self.name} failed to delegate build task with manifest: {e}", exc_info=True)
    
    def _determine_next_action(self, current_action: str) -> Optional[str]:
        """Determine the next action in the sequence"""
        action_sequence = {
            'design_manifest': 'build',
            'build': 'deploy',
            'deploy': None
        }
        return action_sequence.get(current_action)

