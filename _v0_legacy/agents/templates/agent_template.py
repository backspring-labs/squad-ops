#!/usr/bin/env python3
"""
{{ROLE_NAME}} Agent - {{ROLE_NAME}} Role
Reasoning Style: {{REASONING_STYLE}}
Memory Structure: Task state log
Task Model: {{AGENT_TYPE}} processing
Local Model: LLaMA 3 13B (mocked)
Premium Consultation: {{DESCRIPTION}}
"""

import asyncio
import json
import logging
from typing import Dict, Any
from base_agent import BaseAgent, AgentMessage

logger = logging.getLogger(__name__)

class {{CLASS_NAME}}(BaseAgent):
    """{{CLASS_NAME}} - The {{ROLE_NAME.title()}} Role"""
    
    def __init__(self, identity: str):
        super().__init__(
            name=identity,
            agent_type="{{AGENT_TYPE}}",
            reasoning_style="{{REASONING_STYLE}}"
        )
        self.task_state_log = []
        self.specialized_memory = {}
        self.processing_queue = []
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process {{AGENT_TYPE}} tasks with {{REASONING_STYLE}} reasoning"""
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type', 'unknown')
        complexity = task.get('complexity', 0.5)
        
        logger.info(f"{{CLASS_NAME}} processing {{AGENT_TYPE}} task: {task_id}")
        
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
        if task_type == "{{AGENT_TYPE}}_task":
            result = await self._process_{{AGENT_TYPE}}_task(task)
        else:
            result = await self._process_generic_task(task)
        
        # Update task status
        await self.update_task_status(task_id, "Completed", 100.0)
        
        # Log activity
        await self.log_activity(
            f"Processed {{AGENT_TYPE}} task: {task_id}",
            "task_completion",
            {"task_id": task_id, "result": result}
        )
        
        return result
    
    async def _process_{{AGENT_TYPE}}_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process specialized {{AGENT_TYPE}} tasks"""
        # Generate mock response using the base agent's mock_llm_response
        prompt = f"Process {{AGENT_TYPE}} task: {task.get('description', 'No description')}"
        response = await self.mock_llm_response(prompt, "{{AGENT_TYPE}}")
        
        return {
            "task_id": task.get('task_id'),
            "status": "completed",
            "result": response,
            "processing_time": 1.5,
            "confidence": 0.85
        }
    
    async def _process_generic_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
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
        logger.info(f"{{CLASS_NAME}} received message from {message.sender}: {message.content}")
        
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
        logger.info(f"{{CLASS_NAME}} handling task request from {message.sender}")
        
        # Generate response
        response_content = await self.mock_llm_response(
            f"Respond to task request: {message.content}",
            "{{AGENT_TYPE}}"
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
        logger.info(f"{{CLASS_NAME}} handling coordination from {message.sender}")
        
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
            {"coordination_type": "{{AGENT_TYPE}}"}
        )
    
    async def _handle_status_update(self, message: AgentMessage) -> None:
        """Handle status update messages"""
        logger.info(f"{{CLASS_NAME}} received status update from {message.sender}")
        
        # Update internal state based on status
        self.specialized_memory[f"status_{message.sender}"] = {
            "timestamp": message.timestamp,
            "status": message.content,
            "metadata": message.metadata
        }
    
    async def _handle_generic_message(self, message: AgentMessage) -> None:
        """Handle generic messages"""
        logger.info(f"{{CLASS_NAME}} handling generic message from {message.sender}")
        
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
            {"response_type": "{{AGENT_TYPE}}"}
        )
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current agent status"""
        return {
            "agent_name": self.name,
            "agent_type": "{{AGENT_TYPE}}",
            "reasoning_style": "{{REASONING_STYLE}}",
            "status": self.status,
            "task_state_log_count": len(self.task_state_log),
            "specialized_memory_count": len(self.specialized_memory),
            "processing_queue_count": len(self.processing_queue)
        }

async def main():
    """Main entry point for {{ROLE_NAME.title()}} agent"""
    import os
    identity = os.getenv('AGENT_ID', '{{ROLE_NAME}}_agent')
    agent = {{CLASS_NAME}}(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
