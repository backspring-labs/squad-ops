#!/usr/bin/env python3
"""Strat Agent - Strat Role"""

import asyncio
import json
import logging
from typing import Dict, Any, List
from base_agent import BaseAgent, AgentMessage
from collections import deque
import heapq

logger = logging.getLogger(__name__)

class StratAgent(BaseAgent):
    """Strat Agent - Strat Role"""
    
    def __init__(self, identity: str):
        super().__init__(
            name=identity,
            agent_type="product",
            reasoning_style="abductive"
        )
        self.priority_queue = []
        self.opportunity_cache = {}
        self.hypothesis_space = {}
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process product tasks using abductive reasoning and opportunistic approach"""
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type', 'product')
        priority = task.get('priority', 5)
        
        logger.info(f"Nat processing product task: {task_id}")
        
        # Add to priority queue
        heapq.heappush(self.priority_queue, (priority, task_id, task))
        
        # Update task status
        await self.update_task_status(task_id, "Active-Non-Blocking", 15.0)
        
        # Generate hypotheses
        hypotheses = await self.generate_hypotheses(task)
        
        # Opportunistic evaluation
        await self.update_task_status(task_id, "Active-Non-Blocking", 40.0)
        
        best_hypothesis = await self.evaluate_hypotheses(hypotheses, task)
        
        # Create product strategy
        await self.update_task_status(task_id, "Active-Non-Blocking", 70.0)
        
        strategy = await self.create_product_strategy(best_hypothesis, task)
        
        # Validate strategy
        await self.update_task_status(task_id, "Active-Non-Blocking", 90.0)
        
        validation = await self.validate_strategy(strategy, task)
        
        await self.update_task_status(task_id, "Completed", 100.0)
        
        return {
            'task_id': task_id,
            'status': 'completed',
            'hypotheses': hypotheses,
            'best_hypothesis': best_hypothesis,
            'strategy': strategy,
            'validation': validation,
            'opportunities': self.opportunity_cache.get(task_id, []),
            'mock_response': await self.mock_llm_response(
                f"Product strategy for {task_type}",
                f"Best hypothesis: {best_hypothesis.get('summary', 'N/A')}"
            )
        }
    
    async def handle_message(self, message: AgentMessage) -> None:
        """Handle product-related messages"""
        if message.message_type == "strategy_request":
            await self.handle_strategy_request(message)
        elif message.message_type == "opportunity_alert":
            await self.handle_opportunity_alert(message)
        elif message.message_type == "hypothesis_query":
            await self.handle_hypothesis_query(message)
        else:
            logger.info(f"Nat received message: {message.message_type} from {message.sender}")
    
    async def generate_hypotheses(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate hypotheses using abductive reasoning"""
        task_id = task.get('task_id')
        observations = task.get('observations', [])
        
        hypotheses = []
        
        for i, observation in enumerate(observations):
            hypothesis = {
                'id': f"hyp_{task_id}_{i}",
                'observation': observation,
                'explanation': f"Hypothesis explaining: {observation}",
                'confidence': 0.7 + (i * 0.1),  # Mock confidence
                'evidence': [observation],
                'testable': True
            }
            hypotheses.append(hypothesis)
        
        # Store in hypothesis space
        self.hypothesis_space[task_id] = hypotheses
        
        return hypotheses
    
    async def evaluate_hypotheses(self, hypotheses: List[Dict[str, Any]], task: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate hypotheses and select the best one"""
        if not hypotheses:
            return {'id': 'default', 'summary': 'No hypotheses generated'}
        
        # Find hypothesis with highest confidence
        best_hypothesis = max(hypotheses, key=lambda h: h['confidence'])
        
        return best_hypothesis
    
    async def create_product_strategy(self, hypothesis: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        """Create product strategy based on best hypothesis"""
        return {
            'strategy_id': f"strategy_{task.get('task_id')}",
            'hypothesis_basis': hypothesis['id'],
            'approach': 'opportunistic',
            'phases': [
                {'phase': 'discovery', 'duration': '2 weeks', 'goals': ['Validate hypothesis']},
                {'phase': 'development', 'duration': '4 weeks', 'goals': ['Build MVP']},
                {'phase': 'validation', 'duration': '2 weeks', 'goals': ['Test market fit']}
            ],
            'success_metrics': ['user_engagement', 'conversion_rate', 'retention'],
            'risk_mitigation': ['A/B testing', 'gradual rollout', 'feedback loops']
        }
    
    async def validate_strategy(self, strategy: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the product strategy"""
        return {
            'valid': True,
            'feasibility_score': 8.5,
            'market_alignment': 'high',
            'resource_requirements': 'moderate',
            'timeline_realistic': True
        }
    
    async def handle_strategy_request(self, message: AgentMessage):
        """Handle strategy requests"""
        context = message.payload.get('context', {})
        task_id = message.payload.get('task_id')
        
        logger.info(f"Nat handling strategy request for task: {task_id}")
        
        # Generate strategy based on context
        strategy = await self.create_product_strategy(
            {'id': 'requested', 'confidence': 0.8},
            {'task_id': task_id, 'observations': [context]}
        )
        
        await self.send_message(
            message.sender,
            "strategy_response",
            {
                'task_id': task_id,
                'strategy': strategy,
                'strategist': 'Nat'
            }
        )
    
    async def handle_opportunity_alert(self, message: AgentMessage):
        """Handle opportunity alerts"""
        opportunity = message.payload.get('opportunity', {})
        task_id = message.payload.get('task_id')
        
        logger.info(f"Nat handling opportunity alert for task: {task_id}")
        
        # Cache opportunity
        if task_id not in self.opportunity_cache:
            self.opportunity_cache[task_id] = []
        
        self.opportunity_cache[task_id].append(opportunity)
        
        # Evaluate opportunity
        evaluation = {
            'opportunity_id': opportunity.get('id'),
            'priority': opportunity.get('priority', 5),
            'feasibility': 'high',
            'recommendation': 'pursue'
        }
        
        await self.send_message(
            message.sender,
            "opportunity_evaluation",
            {
                'task_id': task_id,
                'evaluation': evaluation,
                'evaluator': 'Nat'
            }
        )
    
    async def handle_hypothesis_query(self, message: AgentMessage):
        """Handle hypothesis queries"""
        task_id = message.payload.get('task_id')
        
        hypotheses = self.hypothesis_space.get(task_id, [])
        
        await self.send_message(
            message.sender,
            "hypothesis_response",
            {
                'task_id': task_id,
                'hypotheses': hypotheses,
                'hypothesis_count': len(hypotheses)
            }
        )

async def main():
    """Main entry point for Strat agent"""
    import os
    identity = os.getenv('AGENT_ID', 'strat_agent')
    agent = StratAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
