#!/usr/bin/env python3
"""
Base Agent Class for SquadOps
Provides common functionality for all 9 agents in the squad
"""

import asyncio
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, List
import aio_pika
import asyncpg
import redis.asyncio as redis
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class AgentMessage:
    """Standard message format for inter-agent communication"""
    sender: str
    recipient: str
    message_type: str
    payload: Dict[str, Any]
    context: Dict[str, Any]
    timestamp: str
    message_id: str

@dataclass
class TaskStatus:
    """Task status tracking"""
    task_id: str
    agent_name: str
    status: str  # Available, Active-Non-Blocking, Active-Blocking, Blocked, Completed
    progress: float
    eta: Optional[str]
    dependencies: List[str]
    created_at: str
    updated_at: str

class BaseAgent(ABC):
    """Base class for all SquadOps agents"""
    
    def __init__(self, name: str, agent_type: str, reasoning_style: str):
        self.name = name
        self.agent_type = agent_type
        self.reasoning_style = reasoning_style
        self.status = "Available"
        self.current_task = None
        self.connection = None
        self.channel = None
        self.db_pool = None
        self.redis_client = None
        
        # Configuration
        self.rabbitmq_url = os.getenv('RABBITMQ_URL', 'amqp://squadops:squadops123@rabbitmq:5672/')
        self.postgres_url = os.getenv('POSTGRES_URL', 'postgresql://squadops:squadops123@postgres:5432/squadops')
        self.redis_url = os.getenv('REDIS_URL', 'redis://redis:6379')
        
    async def initialize(self):
        """Initialize agent connections"""
        try:
            # Connect to RabbitMQ
            self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
            self.channel = await self.connection.channel()
            
            # Connect to PostgreSQL
            self.db_pool = await asyncpg.create_pool(self.postgres_url)
            
            # Connect to Redis
            self.redis_client = redis.from_url(self.redis_url)
            
            # Declare queues
            await self._setup_queues()
            
            logger.info(f"{self.name} initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize {self.name}: {e}")
            raise
    
    async def _setup_queues(self):
        """Setup RabbitMQ queues for this agent"""
        # Task queue
        await self.channel.declare_queue(f"{self.name.lower()}_tasks", durable=True)
        
        # Communication queue
        await self.channel.declare_queue(f"{self.name.lower()}_comms", durable=True)
        
        # Broadcast queue for squad-wide messages
        await self.channel.declare_queue("squad_broadcast", durable=True)
    
    async def send_message(self, recipient: str, message_type: str, payload: Dict[str, Any], context: Dict[str, Any] = None):
        """Send a message to another agent"""
        message = AgentMessage(
            sender=self.name,
            recipient=recipient,
            message_type=message_type,
            payload=payload,
            context=context or {},
            timestamp=datetime.utcnow().isoformat(),
            message_id=f"{self.name}_{int(time.time() * 1000)}"
        )
        
        queue_name = f"{recipient.lower()}_comms"
        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(asdict(message)).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key=queue_name
        )
        
        logger.info(f"{self.name} sent {message_type} to {recipient}")
    
    async def broadcast_message(self, message_type: str, payload: Dict[str, Any], context: Dict[str, Any] = None):
        """Broadcast a message to all agents"""
        message = AgentMessage(
            sender=self.name,
            recipient="ALL",
            message_type=message_type,
            payload=payload,
            context=context or {},
            timestamp=datetime.utcnow().isoformat(),
            message_id=f"{self.name}_broadcast_{int(time.time() * 1000)}"
        )
        
        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(asdict(message)).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key="squad_broadcast"
        )
        
        logger.info(f"{self.name} broadcasted {message_type}")
    
    async def update_task_status(self, task_id: str, status: str, progress: float = 0.0, eta: str = None):
        """Update task status in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO task_status (task_id, agent_name, status, progress, eta, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (task_id) 
                DO UPDATE SET status = $3, progress = $4, eta = $5, updated_at = $6
            """, task_id, self.name, status, progress, eta, datetime.utcnow().isoformat())
    
    async def log_activity(self, activity: str, details: Dict[str, Any] = None):
        """Log agent activity"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO agent_logs (agent_name, activity, details, timestamp)
                VALUES ($1, $2, $3, $4)
            """, self.name, activity, json.dumps(details or {}), datetime.utcnow().isoformat())
    
    @abstractmethod
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task - must be implemented by each agent"""
        pass
    
    @abstractmethod
    async def handle_message(self, message: AgentMessage) -> None:
        """Handle incoming messages - must be implemented by each agent"""
        pass
    
    async def mock_llm_response(self, prompt: str, context: str = "") -> str:
        """Generate mock LLM response for testing"""
        # This simulates LLM responses without actual model inference
        responses = {
            "code": f"[MOCK CODE RESPONSE] Generated code for: {prompt[:50]}...",
            "analysis": f"[MOCK ANALYSIS] Analysis of: {prompt[:50]}...",
            "strategy": f"[MOCK STRATEGY] Strategic recommendation: {prompt[:50]}...",
            "creative": f"[MOCK CREATIVE] Creative solution: {prompt[:50]}...",
            "governance": f"[MOCK GOVERNANCE] Governance decision: {prompt[:50]}...",
            "data": f"[MOCK DATA] Data insights: {prompt[:50]}...",
            "security": f"[MOCK SECURITY] Security assessment: {prompt[:50]}...",
            "financial": f"[MOCK FINANCIAL] Financial analysis: {prompt[:50]}...",
            "pattern": f"[MOCK PATTERN] Pattern detected: {prompt[:50]}..."
        }
        
        # Return appropriate mock response based on agent type
        return responses.get(self.agent_type.lower(), f"[MOCK RESPONSE] {prompt[:50]}...")
    
    async def run(self):
        """Main agent loop"""
        logger.info(f"{self.name} starting up...")
        
        try:
            await self.initialize()
            
            # Start listening for tasks and messages
            task_queue = await self.channel.declare_queue(f"{self.name.lower()}_tasks", durable=True)
            comms_queue = await self.channel.declare_queue(f"{self.name.lower()}_comms", durable=True)
            broadcast_queue = await self.channel.declare_queue("squad_broadcast", durable=True)
            
            async def process_tasks():
                async for message in task_queue:
                    try:
                        task_data = json.loads(message.body.decode())
                        result = await self.process_task(task_data)
                        
                        # Update task status
                        await self.update_task_status(
                            task_data.get('task_id', 'unknown'),
                            'Completed',
                            progress=100.0
                        )
                        
                        await message.ack()
                        logger.info(f"{self.name} completed task: {task_data.get('task_id', 'unknown')}")
                        
                    except Exception as e:
                        logger.error(f"{self.name} task processing error: {e}")
                        await message.nack(requeue=False)
            
            async def process_comms():
                async for message in comms_queue:
                    try:
                        msg_data = json.loads(message.body.decode())
                        agent_msg = AgentMessage(**msg_data)
                        await self.handle_message(agent_msg)
                        await message.ack()
                        
                    except Exception as e:
                        logger.error(f"{self.name} message processing error: {e}")
                        await message.nack(requeue=False)
            
            async def process_broadcasts():
                async for message in broadcast_queue:
                    try:
                        msg_data = json.loads(message.body.decode())
                        agent_msg = AgentMessage(**msg_data)
                        
                        # Only process broadcasts not from self
                        if agent_msg.sender != self.name:
                            await self.handle_message(agent_msg)
                        
                        await message.ack()
                        
                    except Exception as e:
                        logger.error(f"{self.name} broadcast processing error: {e}")
                        await message.nack(requeue=False)
            
            # Run all processors concurrently
            await asyncio.gather(
                process_tasks(),
                process_comms(),
                process_broadcasts()
            )
            
        except Exception as e:
            logger.error(f"{self.name} runtime error: {e}")
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.connection:
            await self.connection.close()
        if self.db_pool:
            await self.db_pool.close()
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info(f"{self.name} shut down")

if __name__ == "__main__":
    # This will be overridden by each specific agent
    agent = BaseAgent("test", "test", "test")
    asyncio.run(agent.run())
