#!/usr/bin/env python3
"""Comms Agent - Comms Role"""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime
from agents.base_agent import BaseAgent, AgentMessage
from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse, Timing
from agents.specs.validator import SchemaValidator
from pathlib import Path
from collections import deque
import time

logger = logging.getLogger(__name__)

class CommsAgent(BaseAgent):
    """Comms Agent - Comms Role"""
    
    def __init__(self, identity: str):
        super().__init__(
            name=identity,
            agent_type="communications",
            reasoning_style="empathetic"
        )
        self.conversation_history = deque(maxlen=100)
        self.emotional_context = {}
        self.interrupt_queue = deque()
        
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
            if action == "comms.documentation":
                result = await self._handle_documentation(request)
            elif action == "comms.stakeholder_update":
                result = await self._handle_stakeholder_update(request)
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
    
    async def _handle_documentation(self, request: AgentRequest) -> Dict[str, Any]:
        """Handle comms.documentation capability"""
        
        # Map existing documentation logic to new capability format
        return {
            'documentation_uri': f'/docs/{task_id}',
            'content': '',
            'format': 'markdown'
        }
    
    async def _handle_stakeholder_update(self, request: AgentRequest) -> Dict[str, Any]:
        """Handle comms.stakeholder_update capability"""
        
        # Map existing stakeholder update logic to new capability format
        return {
            'update_content': '',
            'recipients': [],
            'delivery_status': 'pending'
        }
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process communication tasks with empathetic reasoning"""
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type', 'communication')
        
        logger.info(f"Joi processing communication task: {task_id}")
        
        # Check for interrupts first
        if self.interrupt_queue:
            await self.handle_interrupts()
        
        # Update task status
        await self.update_task_status(task_id, "Active-Non-Blocking", 20.0)
        
        # Analyze emotional context
        emotional_analysis = await self.analyze_emotional_context(task)
        
        # Generate empathetic response
        await self.update_task_status(task_id, "Active-Non-Blocking", 60.0)
        
        response = await self.generate_empathetic_response(task, emotional_analysis)
        
        # Update conversation history
        await self.update_task_status(task_id, "Active-Non-Blocking", 80.0)
        
        await self.update_conversation_history(task, response)
        
        await self.update_task_status(task_id, "Completed", 100.0)
        
        return {
            'task_id': task_id,
            'status': 'completed',
            'emotional_analysis': emotional_analysis,
            'response': response,
            'conversation_context': self.get_conversation_context(),
            'mock_response': await self.mock_llm_response(
                f"Empathetic communication for {task_type}",
                f"Emotional tone: {emotional_analysis.get('tone', 'neutral')}"
            )
        }
    
    async def handle_message(self, message: AgentMessage) -> None:
        """Handle communication-related messages"""
        if message.message_type == "interrupt":
            await self.handle_interrupt(message)
        elif message.message_type == "emotional_support":
            await self.handle_emotional_support(message)
        elif message.message_type == "communication_request":
            await self.handle_communication_request(message)
        else:
            logger.info(f"Joi received message: {message.message_type} from {message.sender}")
    
    async def analyze_emotional_context(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze emotional context of the task"""
        content = task.get('content', '')
        
        # Mock emotional analysis
        emotional_indicators = {
            'urgency': 'high' if 'urgent' in content.lower() else 'normal',
            'tone': 'positive' if any(word in content.lower() for word in ['great', 'excellent', 'good']) else 'neutral',
            'stress_level': 'high' if 'problem' in content.lower() else 'low',
            'sentiment': 'positive' if content.count('!') > content.count('.') else 'neutral'
        }
        
        return {
            'indicators': emotional_indicators,
            'recommended_approach': self.get_recommended_approach(emotional_indicators),
            'empathy_level': 'high' if emotional_indicators['stress_level'] == 'high' else 'normal'
        }
    
    def get_recommended_approach(self, indicators: Dict[str, str]) -> str:
        """Get recommended communication approach based on emotional indicators"""
        if indicators['stress_level'] == 'high':
            return 'supportive'
        elif indicators['urgency'] == 'high':
            return 'direct'
        else:
            return 'collaborative'
    
    async def generate_empathetic_response(self, task: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate empathetic response based on analysis"""
        approach = analysis['recommended_approach']
        
        response_templates = {
            'supportive': {
                'tone': 'understanding',
                'message': "I understand this is challenging. Let's work through this together.",
                'actions': ['acknowledge_concerns', 'offer_support', 'suggest_solutions']
            },
            'direct': {
                'tone': 'clear',
                'message': "I'll help you resolve this quickly and efficiently.",
                'actions': ['prioritize_task', 'provide_clear_steps', 'follow_up']
            },
            'collaborative': {
                'tone': 'friendly',
                'message': "Great! I'm excited to work on this with you.",
                'actions': ['brainstorm', 'gather_input', 'build_consensus']
            }
        }
        
        template = response_templates.get(approach, response_templates['collaborative'])
        
        return {
            'approach': approach,
            'tone': template['tone'],
            'message': template['message'],
            'actions': template['actions'],
            'emotional_support': analysis['empathy_level']
        }
    
    async def update_conversation_history(self, task: Dict[str, Any], response: Dict[str, Any]):
        """Update conversation history with decay"""
        conversation_entry = {
            'timestamp': time.time(),
            'task_id': task.get('task_id'),
            'sender': task.get('sender'),
            'content': task.get('content'),
            'response': response,
            'emotional_context': task.get('emotional_context', {})
        }
        
        self.conversation_history.append(conversation_entry)
    
    def get_conversation_context(self) -> Dict[str, Any]:
        """Get current conversation context"""
        if not self.conversation_history:
            return {'context': 'no_history', 'count': 0}
        
        recent_entries = list(self.conversation_history)[-5:]  # Last 5 entries
        
        return {
            'context': 'active_conversation',
            'count': len(self.conversation_history),
            'recent_topics': [entry.get('content', '')[:50] for entry in recent_entries],
            'emotional_trend': 'stable'  # Mock trend
        }
    
    async def handle_interrupt(self, message: AgentMessage):
        """Handle interrupt messages"""
        interrupt_data = message.payload
        self.interrupt_queue.append(interrupt_data)
        
        logger.info(f"Joi received interrupt: {interrupt_data.get('type', 'unknown')}")
    
    async def handle_interrupts(self):
        """Process pending interrupts"""
        while self.interrupt_queue:
            interrupt = self.interrupt_queue.popleft()
            
            # Handle interrupt based on type
            interrupt_type = interrupt.get('type', 'general')
            
            if interrupt_type == 'urgent_communication':
                await self.handle_urgent_communication(interrupt)
            elif interrupt_type == 'emotional_crisis':
                await self.handle_emotional_crisis(interrupt)
            else:
                logger.info(f"Joi handled interrupt: {interrupt_type}")
    
    async def handle_urgent_communication(self, interrupt: Dict[str, Any]):
        """Handle urgent communication interrupts"""
        logger.info("Joi handling urgent communication interrupt")
        # Mock urgent communication handling
    
    async def handle_emotional_crisis(self, interrupt: Dict[str, Any]):
        """Handle emotional crisis interrupts"""
        logger.info("Joi handling emotional crisis interrupt")
        # Mock emotional crisis handling
    
    async def handle_emotional_support(self, message: AgentMessage):
        """Handle emotional support requests"""
        requester = message.sender
        support_type = message.payload.get('support_type', 'general')
        
        logger.info(f"Joi providing emotional support to {requester}: {support_type}")
        
        support_response = {
            'support_type': support_type,
            'message': "I'm here to help and support you through this.",
            'resources': ['encouragement', 'practical_advice', 'emotional_validation'],
            'follow_up': True
        }
        
        await self.send_message(
            requester,
            "emotional_support_response",
            support_response
        )
    
    async def handle_communication_request(self, message: AgentMessage):
        """Handle communication requests"""
        task_id = message.payload.get('task_id')
        communication_type = message.payload.get('type', 'general')
        
        logger.info(f"Joi handling communication request: {communication_type}")
        
        # Generate appropriate communication
        communication = await self.generate_empathetic_response(
            {'content': f"Communication request: {communication_type}"},
            {'recommended_approach': 'collaborative', 'empathy_level': 'normal'}
        )
        
        await self.send_message(
            message.sender,
            "communication_response",
            {
                'task_id': task_id,
                'communication': communication,
                'communicator': 'Joi'
            }
        )

async def main():
    """Main entry point for Comms agent"""
    from config.unified_config import get_config
    config = get_config()
    identity = config.get_agent_id()
    agent = CommsAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
