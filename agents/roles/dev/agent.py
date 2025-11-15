#!/usr/bin/env python3
"""
Refactored Dev Agent - Dev Role with Specialized Components
Uses composition pattern with specialized managers for different responsibilities
"""

import asyncio
import json
import logging
from typing import Dict, Any, List
from base_agent import BaseAgent, AgentMessage
import sys
import os
import aiohttp

# Add config path first
sys.path.append('/app')

from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse, Error, Timing
from agents.specs.validator import SchemaValidator
from datetime import datetime
from config.deployment_config import get_deployment_config, get_docker_config
from config.version import get_framework_version

logger = logging.getLogger(__name__)

class DevAgent(BaseAgent):
    """Dev Agent using composition with specialized components"""
    
    def __init__(self, identity: str):
        super().__init__(
            name=identity,
            agent_type="developer",
            reasoning_style="deductive"
        )
        
        # Initialize schema validator
        from pathlib import Path
        base_path = Path(__file__).parent.parent.parent.parent
        self.validator = SchemaValidator(base_path)
        
        # Components are now loaded via capabilities - no direct instantiation needed
        
        # Task processing state
        self.current_task_requirements = {}
        self.current_run_id = "run-001"
        self.task_start_times = {}  # Task 3.1: Track task start times for duration calculation
    
    async def emit_reasoning_event(self, task_id: str, ecid: str, reason_step: str, 
                                   summary: str, context: str, 
                                   key_points: List[str] = None, confidence: float = None):
        """
        Emit reasoning event to LeadAgent for telemetry wrap-up
        
        Delegates to comms.reasoning.emit capability.
        
        Args:
            task_id: Task identifier
            ecid: Execution cycle identifier
            reason_step: Type of reasoning step ('decision', 'hypothesis', 'checkpoint')
            summary: Brief summary of reasoning
            context: Operation context ('manifest_generation', 'build', 'deploy', etc.)
            key_points: Optional list of key points
            confidence: Optional confidence level (0.0-1.0)
        """
        if self.capability_loader:
            await self.capability_loader.execute(
                'comms.reasoning.emit', self, task_id, ecid, reason_step, summary, context, key_points, confidence
            )
        else:
            logger.warning(f"{self.name} capability_loader not initialized, cannot emit reasoning event")
    
    # _create_technical_requirements removed - only used in tests, will be updated in test refactoring
    # If needed in production, use build.requirements.generate capability instead
    # _extract_prd_analysis_from_communication_log removed - PRD analysis is passed via task requirements, not extracted from communication log
    
    async def handle_agent_request(self, request: AgentRequest) -> AgentResponse:
        """Handle agent request using capability-based routing"""
        started_at = datetime.utcnow()
        
        try:
            # Validate request
            is_valid, error_msg = self.validator.validate_request(request)
            if not is_valid:
                return AgentResponse.failure(
                    error_code="VALIDATION_ERROR",
                    error_message=error_msg or "Request validation failed",
                    retryable=False,
                    timing=Timing.create(started_at)
                )
            
            # Validate constraints
            is_valid, error_msg = self._validate_constraints(request)
            if not is_valid:
                return AgentResponse.failure(
                    error_code="POLICY_VIOLATION",
                    error_message=error_msg or "Constraint validation failed",
                    retryable=False,
                    timing=Timing.create(started_at)
                )
            
            # Generate idempotency key
            idempotency_key = request.generate_idempotency_key(self.name)
            
            # Route to capability via Loader
            action = request.action
            if not self.capability_loader:
                return AgentResponse.failure(
                    error_code="LOADER_NOT_INITIALIZED",
                    error_message="Capability loader not initialized",
                    retryable=False,
                    timing=Timing.create(started_at)
                )
            
            try:
                # Execute capability via Loader - fully generic routing
                capability_name = action
                
                # Use calling convention metadata to determine how to call the capability
                args = self.capability_loader.prepare_capability_args(capability_name, request.payload)
                result = await self.capability_loader.execute(capability_name, self, *args)
            except ValueError as e:
                # Capability not found in Loader
                return AgentResponse.failure(
                    error_code="UNKNOWN_CAPABILITY",
                    error_message=f"Unknown capability: {action}",
                    retryable=False,
                    timing=Timing.create(started_at)
                )
            except Exception as e:
                logger.error(f"{self.name}: Capability execution error: {e}", exc_info=True)
                return AgentResponse.failure(
                    error_code="CAPABILITY_EXECUTION_ERROR",
                    error_message=str(e),
                    retryable=True,
                    timing=Timing.create(started_at)
                )
            
            # Validate result keys
            is_valid, error_msg = self.validator.validate_result_keys(action, result)
            if not is_valid:
                logger.warning(f"{self.name}: Result validation warning: {error_msg}")
            
            # Create success response
            ended_at = datetime.utcnow()
            return AgentResponse.success(
                result=result,
                idempotency_key=idempotency_key,
                timing=Timing.create(started_at, ended_at)
            )
            
        except Exception as e:
            logger.error(f"{self.name}: Error handling request: {e}", exc_info=True)
            return AgentResponse.failure(
                error_code="INTERNAL_ERROR",
                error_message=str(e),
                retryable=True,
                timing=Timing.create(started_at)
            )
    
    # _handle_build_artifact removed - build.artifact is handled via process_task
    # All build logic is in process_task methods, no duplicate code needed
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process tasks using generic capability routing.
        
        Uses CapabilityLoader.get_capability_for_task() to determine capability
        based on task_type or requirements.action, then executes it generically.
        """
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type', task.get('task_type', 'unknown'))
        
        logger.info(f"DevAgent processing {task_type} task: {task_id}")
        
        try:
            # Check if this is a new SIP-046 AgentRequest format
            if 'action' in task:
                # Let BaseAgent handle the conversion to AgentRequest
                return await super().process_task(task)
            
            # Generic capability routing via loader
            if not self.capability_loader:
                logger.error(f"DevAgent: Capability loader not initialized")
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': 'Capability loader not initialized'
                }
            
            # Determine capability from task structure
            capability_name = self.capability_loader.get_capability_for_task(task)
            if not capability_name:
                logger.warning(f"DevAgent received task with no capability mapping: {task_type}")
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': f'No capability mapping found for task type: {task_type}'
                }
            
            logger.info(f"DevAgent routing task {task_id} to capability: {capability_name}")
            
            # Store requirements for component access (if present)
            requirements = task.get('requirements', {})
            if requirements:
                self.current_task_requirements = requirements
            
            # Generic capability execution - use calling convention metadata
            # This handles all calling conventions: task_dict, requirements_only, task_id_requirements, payload_as_is
            args = self.capability_loader.prepare_capability_args(capability_name, task)
            result = await self.capability_loader.execute(capability_name, self, *args)
            
            # Return result (capabilities return their own result format)
            return result
                
        except ValueError as e:
            # Capability not found
            logger.error(f"DevAgent: Capability not found: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': f'Capability not found: {e}'
            }
        except Exception as e:
            logger.error(f"DevAgent failed to process task {task_id}: {e}", exc_info=True)
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e)
            }
    
    async def handle_message(self, message: AgentMessage) -> None:
        """Handle incoming messages"""
        logger.info(f"DevAgent received message: {message.message_type} from {message.sender}")
        
        if message.message_type == "task_delegation":
            await self._handle_task_delegation(message)
        elif message.message_type == "task_acknowledgment":
            await self._handle_task_acknowledgment(message)
        elif message.message_type == "task_error":
            await self._handle_task_error(message)
        else:
            logger.info(f"DevAgent received unknown message type: {message.message_type}")
    
    async def _handle_task_delegation(self, message: AgentMessage):
        """Handle task delegation messages"""
        try:
            task_payload = message.payload
            task_id = task_payload.get('task_id', 'unknown')
            ecid = task_payload.get('ecid', 'unknown')
            
            logger.info(f"DevAgent received task delegation: {task_id} from {message.sender}")
            
            # Set current ECID for AppBuilder token metrics (Fix: Token aggregation)
            self.current_ecid = ecid
            logger.debug(f"{self.name} set current_ecid: {ecid}")
            
            # Track task start time for duration calculation (Task 3.1)
            from datetime import datetime
            self.task_start_times[task_id] = datetime.utcnow()
            
            # Task already exists (created by Max), just update status to 'in_progress'
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.put(
                        f"{self.task_api_url}/api/v1/tasks/{task_id}",
                        json={"status": "in_progress"}
                    ) as resp:
                        if resp.status == 200:
                            logger.info(f"{self.name} marked task {task_id} as in_progress")
                        elif resp.status == 404:
                            # Task doesn't exist, log it
                            await self.log_task_start(task_id, ecid, 
                                task_payload.get('description', 'Unknown task'),
                                task_payload.get('priority', 'MEDIUM'))
                        else:
                            logger.warning(f"Failed to update task status: {await resp.text()}")
            except Exception as e:
                logger.warning(f"Failed to update task {task_id}: {e}, continuing anyway")
            
            # Process the delegated task
            result = await self.process_task(task_payload)
            
            # Log completion with artifacts
            artifacts = {
                'action': result.get('action'),
                'files_created': result.get('files_created', []),
                'containers_deployed': result.get('containers_deployed', []),
                'status': result.get('status', 'unknown')
            }
            await self.log_task_completion(task_id, artifacts)
            
            # Send acknowledgment back to sender
            await self.send_message(
                message.sender,
                "task_acknowledgment",
                {
                    'task_id': task_id,
                    'status': result.get('status', 'unknown'),
                    'result': result,
                    'processed_by': self.name
                }
            )
            
            # Emit developer completion event (SIP-027 Phase 1)
            if self.capability_loader:
                await self.capability_loader.execute('task.completion.emit', self, task_id, ecid, result)
            
            # Create documentation if requested
            if task_payload.get('create_documentation', False) and self.capability_loader:
                await self.capability_loader.execute('comms.documentation', self, task_id, result)
            
        except Exception as e:
            logger.error(f"DevAgent failed to handle task delegation: {e}")
            
            # Log task failure
            task_id = task_payload.get('task_id', 'unknown')
            await self.log_task_failure(task_id, str(e))
            
            # Send error back to sender
            await self.send_message(
                message.sender,
                "task_error",
                {
                    'task_id': task_id,
                    'error': str(e),
                    'processed_by': self.name
                }
            )
    
    async def _handle_task_acknowledgment(self, message: AgentMessage):
        """Handle task acknowledgment messages"""
        logger.info(f"DevAgent received task acknowledgment from {message.sender}")
    
    async def _handle_task_error(self, message: AgentMessage):
        """Handle task error messages"""
        logger.error(f"DevAgent received task error from {message.sender}: {message.payload}")
    
    # _emit_developer_completion_event removed - now handled by task.completion.emit capability
    # _create_documentation removed - now handled by comms.documentation capability
    
    async def get_component_status(self) -> Dict[str, Any]:
        """Get status of all capabilities"""
        try:
            return {
                'status': 'healthy',
                'capabilities': {
                    'manifest.generate': {
                        'status': 'ready',
                        'description': 'Generate architecture manifests and create initial files'
                    },
                    'docker.build': {
                        'status': 'ready',
                        'description': 'Build Docker images from source'
                    },
                    'docker.deploy': {
                        'status': 'ready',
                        'description': 'Deploy containers'
                    },
                    'version.archive': {
                        'status': 'ready',
                        'description': 'Archive existing versions'
                    },
                    'build.artifact': {
                        'status': 'ready',
                        'description': 'Build application artifacts from specifications'
                    }
                },
                'agent_info': {
                    'name': self.name,
                    'agent_type': self.agent_type,
                    'reasoning_style': self.reasoning_style,
                    'current_run_id': self.current_run_id
                }
            }
            
        except Exception as e:
            logger.error(f"DevAgent failed to get component status: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    # Removed _calculate_total_tokens_used - now handled by task.completion.emit capability
    # Removed _extract_reasoning_summary_for_task - now handled by task.completion.emit capability

async def main():
    """Main entry point for DevAgent"""
    import os
    from config.unified_config import get_config
    config = get_config()
    identity = config.get_agent_id()
    agent = DevAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
