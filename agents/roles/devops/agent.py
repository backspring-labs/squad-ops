#!/usr/bin/env python3
"""
devops Agent - devops Role
Reasoning Style: systematic
Memory Structure: Task state log
Task Model: devops processing
Local Model: LLaMA 3 13B (mocked)
Premium Consultation: DevOps Engineer - Infrastructure automation and deployment
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from agents.base_agent import AgentMessage, BaseAgent
from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse, Timing
from agents.specs.validator import SchemaValidator

logger = logging.getLogger(__name__)

class DevopsAgent(BaseAgent):
    """DevopsAgent - The {{ROLE_NAME.title()}} Role"""
    
    def __init__(self, identity: str):
        super().__init__(
            name=identity,
            agent_type="devops",
            reasoning_style="systematic"
        )
        self.task_state_log = []
        self.specialized_memory = {}
        self.processing_queue = []
        
        # Initialize schema validator
        base_path = Path(__file__).parent.parent.parent.parent
        self.validator = SchemaValidator(base_path)
    
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
            
            # Route to capability handler
            action = request.action
            if action == "devops.infrastructure":
                result = await self._handle_infrastructure(request)
            elif action == "devops.deployment":
                result = await self._handle_deployment(request)
            else:
                return AgentResponse.failure(
                    error_code="UNKNOWN_CAPABILITY",
                    error_message=f"Unknown capability: {action}",
                    retryable=False,
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
    
    async def _handle_infrastructure(self, request: AgentRequest) -> dict[str, Any]:
        """Handle devops.infrastructure capability"""
        
        # Map existing infrastructure logic to new capability format
        return {
            'infrastructure_status': 'operational',
            'deployment_uri': f'/deployments/{task_id}',
            'configuration': {}
        }
    
    async def _handle_deployment(self, request: AgentRequest) -> dict[str, Any]:
        """Handle devops.deployment capability"""
        
        # Map existing deployment logic to new capability format
        return {
            'deployment_status': 'success',
            'deployment_uri': f'/deployments/{task_id}',
            'version': '1.0.0'
        }
    
    async def process_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """Process devops tasks with systematic reasoning"""
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type', 'unknown')
        complexity = task.get('complexity', 0.5)
        
        logger.info(f"DevopsAgent processing devops task: {task_id}")
        
        # Log task state
        self.task_state_log.append({
            'task_id': task_id,
            'timestamp': task.get('timestamp'),
            'type': task_type,
            'complexity': complexity,
            'status': 'processing'
        })
        
        # Update task status
        await self.update_task_status(task_id, "Active-Non-Blocking", 25.0)
        
        # Process based on task type
        if task_type == "devops_task":
            result = await self._process_devops_task(task)
        else:
            result = await self._process_generic_task(task)
        
        # Update task status
        await self.update_task_status(task_id, "Completed", 100.0)
        
        # Log to communication log (deprecated log_activity may fail in integration tests)
        self.communication_log.append({
            'event': 'devops_task_completed',
            'task_id': task_id,
            'result': result,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Try deprecated log_activity (gracefully handles missing table)
        await self.log_activity(
            f"Processed devops task: {task_id}",
            {"task_id": task_id, "result": result}
        )
        
        return result
    
    async def _process_devops_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """Process specialized devops tasks"""
        # Generate mock response using the base agent's mock_llm_response
        prompt = f"Process devops task: {task.get('description', 'No description')}"
        response = await self.mock_llm_response(prompt, "devops")
        
        return {
            "task_id": task.get('task_id'),
            "status": "completed",
            "result": response,
            "processing_time": 1.5,
            "confidence": 0.85
        }
    
    async def _process_generic_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """Process generic tasks"""
        prompt = f"Process generic task: {task.get('description', 'No description')}"
        response = await self.mock_llm_response(prompt, "generic")
        
        return {
            "task_id": task.get('task_id'),
            "status": "completed",
            "result": response,
            "processing_time": 1.0,
            "confidence": 0.75
        }
    
    async def handle_message(self, message: AgentMessage) -> None:
        """Handle incoming messages"""
        logger.info(f"DevopsAgent received message from {message.sender}: {message.content}")
        
        # Process message based on type
        if message.message_type == "task_request":
            await self._handle_task_request(message)
        elif message.message_type == "coordination":
            await self._handle_coordination(message)
        elif message.message_type == "status_update":
            await self._handle_status_update(message)
        else:
            await self._handle_generic_message(message)
    
    async def _handle_task_request(self, message: AgentMessage) -> None:
        """Handle task request messages"""
        logger.info(f"DevopsAgent handling task request from {message.sender}")
        
        # Generate response
        response_content = await self.mock_llm_response(
            f"Respond to task request: {message.content}",
            "devops"
        )
        
        # Send response back
        await self.send_message(
            message.sender,
            "task_response",
            response_content,
            {"original_message_id": message.message_id}
        )
    
    async def _handle_coordination(self, message: AgentMessage) -> None:
        """Handle coordination messages"""
        logger.info(f"DevopsAgent handling coordination from {message.sender}")
        
        # Process coordination request
        response_content = await self.mock_llm_response(
            f"Coordinate on: {message.content}",
            "coordination"
        )
        
        # Send coordination response
        await self.send_message(
            message.sender,
            "coordination_response",
            response_content,
            {"coordination_type": "devops"}
        )
    
    async def _handle_status_update(self, message: AgentMessage) -> None:
        """Handle status update messages"""
        logger.info(f"DevopsAgent received status update from {message.sender}")
        
        # Update internal state based on status
        self.specialized_memory[f"status_{message.sender}"] = {
            "timestamp": message.timestamp,
            "status": message.content,
            "metadata": message.metadata
        }
    
    async def _handle_generic_message(self, message: AgentMessage) -> None:
        """Handle generic messages"""
        logger.info(f"DevopsAgent handling generic message from {message.sender}")
        
        # Generate generic response
        response_content = await self.mock_llm_response(
            f"Respond to: {message.content}",
            "generic"
        )
        
        # Send response
        await self.send_message(
            message.sender,
            "generic_response",
            response_content,
            {"response_type": "devops"}
        )
    
    async def get_status(self) -> dict[str, Any]:
        """Get current agent status"""
        return {
            "agent_name": self.name,
            "agent_type": "devops",
            "reasoning_style": "systematic",
            "status": self.status,
            "task_state_log_count": len(self.task_state_log),
            "specialized_memory_count": len(self.specialized_memory),
            "processing_queue_count": len(self.processing_queue)
        }

async def main():
    """Main entry point for {{ROLE_NAME.title()}} agent"""
    from config.unified_config import get_config
    config = get_config()
    identity = config.get_agent_id()
    agent = DevopsAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
