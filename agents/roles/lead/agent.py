#!/usr/bin/env python3
"""
Lead Agent - Governance Role
Reasoning Style: Governance
Memory Structure: Task state log
Task Model: Approval/escalation
Local Model: LLaMA 3 13B (mocked)
Premium Consultation: Strategic resolution
"""

import asyncio
import json
import logging
from typing import Dict, Any
from base_agent import BaseAgent, AgentMessage

logger = logging.getLogger(__name__)

class LeadAgent(BaseAgent):
    """Lead Agent - The Governance Role"""
    
    def __init__(self, identity: str):
        super().__init__(
            name=identity,
            agent_type="governance",
            reasoning_style="governance"
        )
        self.task_state_log = []
        self.approval_queue = []
        self.escalation_threshold = 0.8
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process governance tasks with approval/escalation logic"""
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type', 'unknown')
        complexity = task.get('complexity', 0.5)
        
        logger.info(f"Max processing governance task: {task_id}")
        
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
        
        # Governance decision logic
        if complexity > self.escalation_threshold:
            # Escalate to premium consultation
            await self.escalate_task(task_id, task)
            await self.update_task_status(task_id, "Blocked", 50.0, "Escalated to premium consultation")
            
            return {
                'task_id': task_id,
                'status': 'escalated',
                'reason': 'High complexity requires premium consultation',
                'escalation_level': 'strategic_resolution',
                'mock_response': await self.mock_llm_response(
                    f"Strategic governance decision for {task_type}",
                    f"Complexity: {complexity}, Task: {task.get('description', 'N/A')}"
                )
            }
        else:
            # Approve and delegate
            await self.update_task_status(task_id, "Active-Non-Blocking", 75.0)
            
            # Determine delegation target
            delegation_target = await self.determine_delegation_target(task_type)
            
            await self.update_task_status(task_id, "Completed", 100.0)
            
            return {
                'task_id': task_id,
                'status': 'approved',
                'delegation_target': delegation_target,
                'governance_decision': f"Approved {task_type} for delegation",
                'mock_response': await self.mock_llm_response(
                    f"Governance approval for {task_type}",
                    f"Delegating to {delegation_target}"
                )
            }
    
    async def handle_message(self, message: AgentMessage) -> None:
        """Handle governance-related messages"""
        if message.message_type == "approval_request":
            await self.handle_approval_request(message)
        elif message.message_type == "escalation":
            await self.handle_escalation(message)
        elif message.message_type == "status_query":
            await self.handle_status_query(message)
        else:
            logger.info(f"Max received message: {message.message_type} from {message.sender}")
    
    async def escalate_task(self, task_id: str, task: Dict[str, Any]):
        """Escalate task to premium consultation"""
        self.approval_queue.append({
            'task_id': task_id,
            'task': task,
            'escalation_time': task.get('timestamp'),
            'reason': 'High complexity'
        })
        
        await self.log_activity("task_escalated", {
            'task_id': task_id,
            'complexity': task.get('complexity'),
            'reason': 'Premium consultation required'
        })
    
    async def determine_delegation_target(self, task_type: str) -> str:
        """Determine which agent should handle the task"""
        delegation_map = {
            'code': 'Neo',
            'product': 'Nat',
            'data': 'Data',
            'security': 'EVE',
            'financial': 'Quark',
            'creative': 'Glyph',
            'analysis': 'Og',
            'communication': 'Joi'
        }
        
        return delegation_map.get(task_type.lower(), 'Neo')
    
    async def handle_approval_request(self, message: AgentMessage):
        """Handle approval requests from other agents"""
        task_id = message.payload.get('task_id')
        logger.info(f"Max handling approval request for task: {task_id}")
        
        # Mock approval logic
        approved = True  # Simplified for stub
        
        await self.send_message(
            message.sender,
            "approval_response",
            {
                'task_id': task_id,
                'approved': approved,
                'governance_notes': 'Approved by Max governance agent'
            }
        )
    
    async def handle_escalation(self, message: AgentMessage):
        """Handle escalation requests"""
        task_id = message.payload.get('task_id')
        reason = message.payload.get('reason', 'Unknown')
        
        logger.info(f"Max handling escalation for task: {task_id}, reason: {reason}")
        
        await self.log_activity("escalation_received", {
            'task_id': task_id,
            'from_agent': message.sender,
            'reason': reason
        })
    
    async def handle_status_query(self, message: AgentMessage):
        """Handle status queries"""
        await self.send_message(
            message.sender,
            "status_response",
            {
                'agent': 'Max',
                'status': self.status,
                'current_task': self.current_task,
                'task_state_log_count': len(self.task_state_log),
                'approval_queue_count': len(self.approval_queue)
            }
        )

async def main():
    """Main entry point for Lead agent"""
    import os
    identity = os.getenv('AGENT_ID', 'lead_agent')
    agent = LeadAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
