#!/usr/bin/env python3
"""Data Agent - Data Role"""

import asyncio
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
from agents.base_agent import BaseAgent, AgentMessage
from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse, Error, Timing
from agents.specs.validator import SchemaValidator
from pathlib import Path
import time

logger = logging.getLogger(__name__)

class DataAgent(BaseAgent):
    """Data Agent - Data Role"""
    
    def __init__(self, identity: str):
        super().__init__(
            name=identity,
            agent_type="data_analyst",
            reasoning_style="inductive"
        )
        self.time_series_cache = {}
        self.batch_queue = []
        self.patterns_discovered = {}
        
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
            if action == "data.analysis":
                result = await self._handle_data_analysis(request)
            elif action == "data.modeling":
                result = await self._handle_data_modeling(request)
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
    
    async def _handle_data_analysis(self, request: AgentRequest) -> Dict[str, Any]:
        """Handle data.analysis capability"""
        payload = request.payload
        task_id = payload.get('task_id', 'unknown')
        
        # Map existing data analysis logic to new capability format
        return {
            'insights': [],
            'metrics': {},
            'visualization_uri': f'/visualizations/{task_id}'
        }
    
    async def _handle_data_modeling(self, request: AgentRequest) -> Dict[str, Any]:
        """Handle data.modeling capability"""
        payload = request.payload
        task_id = payload.get('task_id', 'unknown')
        
        # Map existing data modeling logic to new capability format
        return {
            'model_uri': f'/models/{task_id}',
            'accuracy': 0.0,
            'predictions': []
        }
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process data tasks using inductive reasoning and batch processing"""
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type', 'data_analysis')
        
        logger.info(f"Data processing data task: {task_id}")
        
        # Add to batch queue
        self.batch_queue.append(task)
        
        # Process batch if ready
        if len(self.batch_queue) >= 3:  # Batch size threshold
            await self.process_batch()
        
        # Update task status
        await self.update_task_status(task_id, "Active-Non-Blocking", 30.0)
        
        # Collect data points
        data_points = await self.collect_data_points(task)
        
        # Store in time-series
        await self.update_task_status(task_id, "Active-Non-Blocking", 50.0)
        
        await self.store_time_series_data(task_id, data_points)
        
        # Inductive analysis
        await self.update_task_status(task_id, "Active-Non-Blocking", 70.0)
        
        patterns = await self.inductive_analysis(data_points, task)
        
        # Generate insights
        await self.update_task_status(task_id, "Active-Non-Blocking", 90.0)
        
        insights = await self.generate_insights(patterns, task)
        
        await self.update_task_status(task_id, "Completed", 100.0)
        
        return {
            'task_id': task_id,
            'status': 'completed',
            'data_points': len(data_points),
            'patterns': patterns,
            'insights': insights,
            'time_series_length': len(self.time_series_cache.get(task_id, [])),
            'mock_response': await self.mock_llm_response(
                f"Data analysis for {task_type}",
                f"Patterns found: {len(patterns)}"
            )
        }
    
    async def handle_message(self, message: AgentMessage) -> None:
        """Handle data-related messages"""
        if message.message_type == "data_query":
            await self.handle_data_query(message)
        elif message.message_type == "pattern_request":
            await self.handle_pattern_request(message)
        elif message.message_type == "analytics_request":
            await self.handle_analytics_request(message)
        else:
            logger.info(f"Data received message: {message.message_type} from {message.sender}")
    
    async def collect_data_points(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect data points for analysis"""
        data_source = task.get('data_source', 'mock')
        
        # Mock data collection
        data_points = []
        for i in range(10):  # Mock 10 data points
            data_points.append({
                'timestamp': time.time() - (i * 3600),  # Mock hourly data
                'value': 100 + (i * 5) + (i % 3),  # Mock trend with noise
                'category': task.get('category', 'general'),
                'metadata': {'source': data_source, 'quality': 'high'}
            })
        
        return data_points
    
    async def store_time_series_data(self, task_id: str, data_points: List[Dict[str, Any]]):
        """Store data in time-series format"""
        if task_id not in self.time_series_cache:
            self.time_series_cache[task_id] = []
        
        self.time_series_cache[task_id].extend(data_points)
    
    async def inductive_analysis(self, data_points: List[Dict[str, Any]], task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Perform inductive analysis to find patterns"""
        patterns = []
        
        if len(data_points) >= 3:
            # Mock pattern detection
            values = [dp['value'] for dp in data_points]
            
            # Trend pattern
            if values[-1] > values[0]:
                patterns.append({
                    'type': 'trend',
                    'direction': 'increasing',
                    'confidence': 0.8,
                    'description': 'Upward trend detected'
                })
            
            # Seasonal pattern (mock)
            if len(values) >= 4:
                patterns.append({
                    'type': 'seasonal',
                    'period': 4,
                    'confidence': 0.6,
                    'description': 'Possible seasonal pattern'
                })
        
        return patterns
    
    async def generate_insights(self, patterns: List[Dict[str, Any]], task: Dict[str, Any]) -> Dict[str, Any]:
        """Generate insights from patterns"""
        return {
            'summary': f"Found {len(patterns)} patterns in the data",
            'key_findings': [p['description'] for p in patterns],
            'recommendations': ['Monitor trend continuation', 'Investigate seasonal factors'],
            'confidence_score': sum(p.get('confidence', 0) for p in patterns) / max(len(patterns), 1)
        }
    
    async def process_batch(self):
        """Process batch of tasks"""
        if not self.batch_queue:
            return
        
        logger.info(f"Data processing batch of {len(self.batch_queue)} tasks")
        
        # Process batch
        batch_results = []
        for task in self.batch_queue:
            result = await self.process_task(task)
            batch_results.append(result)
        
        # Clear batch queue
        self.batch_queue = []
        
        # Store batch patterns
        self.patterns_discovered[f"batch_{int(time.time())}"] = batch_results
    
    async def handle_data_query(self, message: AgentMessage):
        """Handle data queries"""
        query_type = message.payload.get('query_type', 'general')
        task_id = message.payload.get('task_id')
        
        logger.info(f"Data handling data query: {query_type}")
        
        # Mock data query response
        response_data = {
            'query_type': query_type,
            'data_available': True,
            'time_range': 'last_24_hours',
            'data_points': 100,
            'quality': 'high'
        }
        
        await self.send_message(
            message.sender,
            "data_query_response",
            {
                'task_id': task_id,
                'data': response_data,
                'analyst': 'Data'
            }
        )
    
    async def handle_pattern_request(self, message: AgentMessage):
        """Handle pattern requests"""
        task_id = message.payload.get('task_id')
        
        # Get relevant patterns
        relevant_patterns = []
        for patterns in self.patterns_discovered.values():
            if isinstance(patterns, list):
                relevant_patterns.extend(patterns)
        
        await self.send_message(
            message.sender,
            "pattern_response",
            {
                'task_id': task_id,
                'patterns': relevant_patterns[-10:],  # Last 10 patterns
                'pattern_count': len(relevant_patterns)
            }
        )
    
    async def handle_analytics_request(self, message: AgentMessage):
        """Handle analytics requests"""
        analytics_type = message.payload.get('analytics_type', 'summary')
        task_id = message.payload.get('task_id')
        
        logger.info(f"Data handling analytics request: {analytics_type}")
        
        # Generate analytics
        analytics = {
            'type': analytics_type,
            'summary': 'Data shows positive trends with seasonal variations',
            'metrics': {
                'total_data_points': sum(len(ts) for ts in self.time_series_cache.values()),
                'patterns_discovered': len(self.patterns_discovered),
                'data_quality': 'high'
            }
        }
        
        await self.send_message(
            message.sender,
            "analytics_response",
            {
                'task_id': task_id,
                'analytics': analytics,
                'analyst': 'Data'
            }
        )

async def main():
    """Main entry point for Data agent"""
    import os
    from config.unified_config import get_config
    config = get_config()
    identity = config.get_agent_id()
    agent = DataAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
