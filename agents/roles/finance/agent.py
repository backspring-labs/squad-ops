#!/usr/bin/env python3
"""Finance Agent - Finance Role"""

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

class FinanceAgent(BaseAgent):
    """Finance Agent - Finance Role"""
    
    def __init__(self, identity: str):
        super().__init__(
            name=identity,
            agent_type="financial_analyst",
            reasoning_style="rule-based"
        )
        self.ledger = []
        self.rules_engine = {}
        self.constraints = {}
        self.financial_models = {}
        
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
            if action == "finance.analysis":
                result = await self._handle_finance_analysis(request)
            elif action == "finance.budget_planning":
                result = await self._handle_budget_planning(request)
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
    
    async def _handle_finance_analysis(self, request: AgentRequest) -> dict[str, Any]:
        """Handle finance.analysis capability"""
        
        # Map existing finance analysis logic to new capability format
        return {
            'financial_report': f'/reports/finance/{task_id}',
            'cost_breakdown': {},
            'recommendations': []
        }
    
    async def _handle_budget_planning(self, request: AgentRequest) -> dict[str, Any]:
        """Handle finance.budget_planning capability"""
        
        # Map existing budget planning logic to new capability format
        return {
            'budget_plan': {},
            'forecast': {},
            'cost_optimization': []
        }
    
    async def process_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """Process financial tasks using rule-based reasoning"""
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type', 'financial_analysis')
        
        logger.info(f"Quark processing financial task: {task_id}")
        
        # Update task status
        await self.update_task_status(task_id, "Active-Non-Blocking", 20.0)
        
        # Load applicable rules
        rules = await self.load_rules(task)
        
        # Apply constraint solving
        await self.update_task_status(task_id, "Active-Non-Blocking", 40.0)
        
        constraints = await self.define_constraints(task)
        
        # Execute rule-based analysis
        await self.update_task_status(task_id, "Active-Non-Blocking", 60.0)
        
        analysis = await self.execute_rule_based_analysis(rules, constraints, task)
        
        # Update ledger
        await self.update_task_status(task_id, "Active-Non-Blocking", 80.0)
        
        await self.update_ledger(task, analysis)
        
        await self.update_task_status(task_id, "Completed", 100.0)
        
        return {
            'task_id': task_id,
            'status': 'completed',
            'rules_applied': len(rules),
            'constraints': constraints,
            'analysis': analysis,
            'ledger_entries': len(self.ledger),
            'mock_response': await self.mock_llm_response(
                f"Financial analysis for {task_type}",
                f"Rules applied: {len(rules)}"
            )
        }
    
    async def handle_message(self, message: AgentMessage) -> None:
        """Handle financial-related messages"""
        if message.message_type == "financial_model":
            await self.handle_financial_model(message)
        elif message.message_type == "budget_request":
            await self.handle_budget_request(message)
        elif message.message_type == "cost_analysis":
            await self.handle_cost_analysis(message)
        else:
            logger.info(f"Quark received message: {message.message_type} from {message.sender}")
    
    async def load_rules(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        """Load applicable rules for the task"""
        task_type = task.get('type', 'general')
        
        # Mock rule loading based on task type
        rules = []
        
        if 'budget' in task_type.lower():
            rules.extend([
                {'id': 'budget_rule_1', 'condition': 'budget > 0', 'action': 'approve'},
                {'id': 'budget_rule_2', 'condition': 'budget > 10000', 'action': 'require_approval'}
            ])
        
        if 'cost' in task_type.lower():
            rules.extend([
                {'id': 'cost_rule_1', 'condition': 'cost < budget', 'action': 'approve'},
                {'id': 'cost_rule_2', 'condition': 'cost > budget * 1.1', 'action': 'reject'}
            ])
        
        return rules
    
    async def define_constraints(self, task: dict[str, Any]) -> dict[str, Any]:
        """Define constraints for constraint solving"""
        constraints = {
            'budget_limit': task.get('budget_limit', 10000),
            'time_constraint': task.get('time_limit', 30),  # days
            'resource_constraint': task.get('resource_limit', 5),
            'quality_constraint': task.get('quality_threshold', 0.8)
        }
        
        return constraints
    
    async def execute_rule_based_analysis(self, rules: list[dict[str, Any]], constraints: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
        """Execute rule-based analysis"""
        analysis_result = {
            'rules_evaluated': len(rules),
            'constraints_satisfied': 0,
            'recommendations': [],
            'financial_impact': 'neutral'
        }
        
        # Evaluate rules
        for rule in rules:
            condition = rule['condition']
            action = rule['action']
            
            # Mock rule evaluation
            if 'budget > 0' in condition:
                analysis_result['constraints_satisfied'] += 1
                analysis_result['recommendations'].append(f"Rule {rule['id']}: {action}")
        
        # Calculate financial impact
        budget = task.get('budget', 0)
        cost = task.get('estimated_cost', budget * 0.8)
        
        if cost > budget:
            analysis_result['financial_impact'] = 'negative'
        elif cost < budget * 0.9:
            analysis_result['financial_impact'] = 'positive'
        
        return analysis_result
    
    async def update_ledger(self, task: dict[str, Any], analysis: dict[str, Any]):
        """Update financial ledger"""
        ledger_entry = {
            'timestamp': task.get('timestamp'),
            'task_id': task.get('task_id'),
            'transaction_type': task.get('type', 'general'),
            'amount': task.get('budget', 0),
            'analysis': analysis,
            'status': 'recorded'
        }
        
        self.ledger.append(ledger_entry)
    
    async def handle_financial_model(self, message: AgentMessage):
        """Handle financial modeling requests"""
        model_type = message.payload.get('model_type', 'general')
        task_id = message.payload.get('task_id')
        
        logger.info(f"Quark creating financial model: {model_type}")
        
        # Create financial model
        model = {
            'type': model_type,
            'parameters': {
                'revenue': 100000,
                'costs': 75000,
                'profit_margin': 0.25
            },
            'projections': {
                'year_1': {'revenue': 100000, 'profit': 25000},
                'year_2': {'revenue': 120000, 'profit': 30000},
                'year_3': {'revenue': 144000, 'profit': 36000}
            },
            'assumptions': ['steady growth', 'stable costs', 'market expansion']
        }
        
        await self.send_message(
            message.sender,
            "financial_model_response",
            {
                'task_id': task_id,
                'model': model,
                'modeler': 'Quark'
            }
        )
    
    async def handle_budget_request(self, message: AgentMessage):
        """Handle budget requests"""
        budget_type = message.payload.get('budget_type', 'operational')
        task_id = message.payload.get('task_id')
        
        logger.info(f"Quark handling budget request: {budget_type}")
        
        # Calculate budget
        budget = {
            'type': budget_type,
            'total_amount': 50000,
            'breakdown': {
                'personnel': 30000,
                'infrastructure': 15000,
                'tools': 5000
            },
            'approval_status': 'pending',
            'constraints': ['Must stay within 10% variance']
        }
        
        await self.send_message(
            message.sender,
            "budget_response",
            {
                'task_id': task_id,
                'budget': budget,
                'budget_manager': 'Quark'
            }
        )
    
    async def handle_cost_analysis(self, message: AgentMessage):
        """Handle cost analysis requests"""
        analysis_type = message.payload.get('analysis_type', 'total_cost')
        task_id = message.payload.get('task_id')
        
        logger.info(f"Quark performing cost analysis: {analysis_type}")
        
        # Perform cost analysis
        cost_analysis = {
            'type': analysis_type,
            'total_cost': 25000,
            'cost_breakdown': {
                'development': 15000,
                'testing': 5000,
                'deployment': 3000,
                'maintenance': 2000
            },
            'cost_per_unit': 125,
            'break_even_point': 200,
            'recommendations': ['Optimize development costs', 'Consider automation']
        }
        
        await self.send_message(
            message.sender,
            "cost_analysis_response",
            {
                'task_id': task_id,
                'analysis': cost_analysis,
                'analyst': 'Quark'
            }
        )

async def main():
    """Main entry point for Finance agent"""
    from config.unified_config import get_config
    config = get_config()
    identity = config.get_agent_id()
    agent = FinanceAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
