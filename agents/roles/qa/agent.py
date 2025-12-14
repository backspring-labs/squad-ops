#!/usr/bin/env python3
"""QA Agent - QA Role"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from agents.base_agent import AgentMessage, BaseAgent
from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse, Timing
from agents.specs.validator import SchemaValidator

logger = logging.getLogger(__name__)

class QAAgent(BaseAgent):
    """QA Agent - Quality Assurance Role"""
    
    def __init__(self, identity: str):
        super().__init__(
            name=identity,
            agent_type="quality_assurance",
            reasoning_style="counterfactual"
        )
        
        # Initialize schema validator using unified path resolver
        from agents.utils.path_resolver import PathResolver
        base_path = PathResolver.get_base_path()
        self.validator = SchemaValidator(base_path)
    
    async def handle_agent_request(self, request: AgentRequest) -> AgentResponse:
        """Handle agent request using generic capability routing"""
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
                # Use calling convention metadata to determine how to call the capability
                args = self.capability_loader.prepare_capability_args(action, request.payload, request.metadata)
                result = await self.capability_loader.execute(action, self, *args)
            except ValueError:
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
    
    async def process_task(self, task: dict[str, Any] | Any) -> dict[str, Any]:
        """
        Process tasks using generic capability routing.
        
        Uses CapabilityLoader.get_capability_for_task() to determine capability
        based on task_type or requirements.action, then executes it generically.
        
        ACI v0.8: Accepts TaskEnvelope (delegates to BaseAgent) or legacy dict format.
        """
        from agents.tasks.models import TaskEnvelope
        
        # ACI v0.8: If TaskEnvelope, delegate to BaseAgent.process_task
        if isinstance(task, TaskEnvelope):
            return await super().process_task(task)
        
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type', task.get('task_type', 'unknown'))
        
        logger.info(f"{self.name} processing {task_type} task: {task_id}")
        
        try:
            # Check if this is a new SIP-046 AgentRequest format
            if 'action' in task:
                # Let BaseAgent handle the conversion to AgentRequest
                return await super().process_task(task)
            
            # Generic capability routing via loader
            if not self.capability_loader:
                logger.error(f"{self.name}: Capability loader not initialized")
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': 'Capability loader not initialized'
                }
            
            # Determine capability from task structure
            capability_name = self.capability_loader.get_capability_for_task(task)
            if not capability_name:
                logger.warning(f"{self.name} received task with no capability mapping: {task_type}")
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': f'No capability mapping found for task type: {task_type}'
                }
            
            logger.info(f"{self.name} routing task {task_id} to capability: {capability_name}")
            
            # Update task status to in_progress
            await self.update_task_status(task_id, "Active-Non-Blocking", 25.0)
            
            try:
                # Generic capability execution - use calling convention metadata
                # This handles all calling conventions: task_dict, requirements_only, task_id_requirements, payload_as_is
                args = self.capability_loader.prepare_capability_args(capability_name, task)
                result = await self.capability_loader.execute(capability_name, self, *args)
                
                # Update task status to completed
                await self.update_task_status(task_id, "Completed", 100.0)
                
                # Return result (capabilities return their own result format)
                return result
                    
            except ValueError as e:
                # Capability not found
                logger.error(f"{self.name}: Capability not found: {e}")
                await self.update_task_status(task_id, "Failed", 0.0, str(e))
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': f'Capability not found: {e}'
                }
            except Exception as e:
                logger.error(f"{self.name}: Capability execution error: {e}", exc_info=True)
                await self.update_task_status(task_id, "Failed", 0.0, str(e))
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': str(e)
                }
                
        except Exception as e:
            logger.error(f"{self.name}: Error processing task: {e}", exc_info=True)
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e)
            }
    
    async def handle_message(self, message: AgentMessage) -> None:
        """Handle generic messages"""
        logger.info(f"{self.name} received message: {message.message_type} from {message.sender}")
        # Generic message handling - no business logic, just logging
        # Business logic should be in capabilities if needed

async def main():
    """Main entry point for QA agent"""
    from config.unified_config import get_config
    config = get_config()
    identity = config.get_agent_id()
    agent = QAAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
