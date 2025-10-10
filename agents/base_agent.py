#!/usr/bin/env python3
"""
Base Agent Class for SquadOps
Provides common functionality for all agents in the squad
"""

import asyncio
import json
import logging
import os
import sys
import time
import aiofiles
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, List
import aio_pika
import asyncpg
import redis.asyncio as redis
import aiohttp
from dataclasses import dataclass, asdict

# Import version management
sys.path.append('/app')
try:
    from config.version import get_agent_version, get_agent_config
except ImportError:
    # Fallback for when config module isn't available
    def get_agent_version(agent_name: str) -> str:
        return "1.0.0"
    def get_agent_config(agent_name: str) -> dict:
        return {"llm": "unknown", "config": "unknown", "version": "1.0.0"}

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
        self.status = "online"
        self.current_task = None
        self.connection = None
        self.channel = None
        self.db_pool = None
        self.redis_client = None
        
        # Configuration
        self.rabbitmq_url = os.getenv('RABBITMQ_URL', 'amqp://squadops:squadops123@rabbitmq:5672/')
        self.postgres_url = os.getenv('POSTGRES_URL', 'postgresql://squadops:squadops123@postgres:5432/squadops')
        self.redis_url = os.getenv('REDIS_URL', 'redis://redis:6379')
        self.task_api_url = os.getenv("TASK_API_URL", "http://task-api:8001")
        
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
            """, task_id, self.name, status, progress, eta, datetime.utcnow())
    
    async def log_activity(self, activity: str, details: Dict[str, Any] = None):
        """Log agent activity"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO agent_task_logs (task_id, agent_name, task_name, task_status, start_time, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, f"{self.name}_{activity}_{int(time.time() * 1000)}", self.name, activity, "completed", datetime.utcnow(), datetime.utcnow())
    
    async def create_execution_cycle(self, ecid: str, pid: str, run_type: str, 
                                     title: str, description: str = None):
        """Create execution cycle via API"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.task_api_url}/api/v1/execution-cycles",
                json={
                    "ecid": ecid,
                    "pid": pid,
                    "run_type": run_type,
                    "title": title,
                    "description": description,
                    "initiated_by": self.name
                }
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to create execution cycle: {await resp.text()}")
                return await resp.json()

    async def log_task_start(self, task_id: str, ecid: str, description: str, 
                             priority: str = "MEDIUM", dependencies: List[str] = None,
                             delegated_by: str = None, delegated_to: str = None):
        """Log task start via API"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.task_api_url}/api/v1/tasks/start",
                json={
                    "task_id": task_id,
                    "ecid": ecid,
                    "agent": self.name,
                    "status": "started",
                    "priority": priority,
                    "description": description,
                    "dependencies": dependencies or [],
                    "delegated_by": delegated_by,
                    "delegated_to": delegated_to
                }
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to log task start: {await resp.text()}")
                return await resp.json()

    async def log_task_delegation(self, task_id: str, ecid: str, delegated_to: str, 
                                  description: str):
        """Log task delegation via API - update existing task record"""
        async with aiohttp.ClientSession() as session:
            async with session.put(
                f"{self.task_api_url}/api/v1/tasks/{task_id}",
                json={
                    "status": "delegated",
                    "delegated_by": self.name,
                    "delegated_to": delegated_to
                }
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to log task delegation: {await resp.text()}")
                return await resp.json()

    async def log_task_completion(self, task_id: str, artifacts: Dict[str, Any] = None):
        """Log task completion via API"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.task_api_url}/api/v1/tasks/complete",
                json={
                    "task_id": task_id,
                    "artifacts": artifacts
                }
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to log task completion: {await resp.text()}")
                return await resp.json()

    async def log_task_failure(self, task_id: str, error_log: str):
        """Log task failure via API"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.task_api_url}/api/v1/tasks/fail",
                json={
                    "task_id": task_id,
                    "error_log": error_log
                }
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to log task failure: {await resp.text()}")
                return await resp.json()

    async def update_execution_cycle_status(self, ecid: str, status: str, notes: str = None):
        """Update execution cycle status via API"""
        async with aiohttp.ClientSession() as session:
            async with session.put(
                f"{self.task_api_url}/api/v1/execution-cycles/{ecid}",
                json={
                    "status": status,
                    "notes": notes
                }
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to update execution cycle: {await resp.text()}")
                return await resp.json()
    
    async def send_heartbeat(self):
        """Send heartbeat to health monitoring system"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO agent_status (agent_name, status, version, tps, last_heartbeat, current_task_id, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (agent_name) 
                    DO UPDATE SET 
                        status = $2,
                        tps = $4,
                        last_heartbeat = $5,
                        current_task_id = $6,
                        updated_at = $7
                """, 
                self.name, 
                self.status, 
                get_agent_version(self.name), 
                0,  # Mock TPS for now
                datetime.utcnow(),
                self.current_task or None,
                datetime.utcnow()
                )
                
            logger.debug(f"{self.name} heartbeat sent")
            
        except Exception as e:
            logger.error(f"{self.name} heartbeat failed: {e}")
    
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
    
    async def llm_response(self, prompt: str, context: str = "") -> str:
        """Generate LLM response using Ollama or fallback to mock"""
        try:
            # Check if we should use local LLM
            use_local_llm = os.getenv('USE_LOCAL_LLM', 'false').lower() == 'true'
            model_name = os.getenv('AGENT_MODEL', '')
            
            if use_local_llm and model_name:
                return await self._ollama_response(prompt, context, model_name)
            else:
                return await self.mock_llm_response(prompt, context)
        except Exception as e:
            logger.warning(f"LLM call failed, falling back to mock: {e}")
            return await self.mock_llm_response(prompt, context)
    
    async def _ollama_response(self, prompt: str, context: str, model: str) -> str:
        """Generate response using Ollama API"""
        import aiohttp
        
        ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
        
        # Prepare the full prompt with context
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        
        payload = {
            "model": model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 1000
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{ollama_url}/api/generate", json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('response', 'No response generated')
                else:
                    raise Exception(f"Ollama API error: {response.status}")
    
    async def run(self):
        """Main agent loop"""
        logger.info(f"{self.name} starting up...")
        
        try:
            await self.initialize()
            
            # Send initial heartbeat
            await self.send_heartbeat()
            logger.info(f"{self.name} registered with health monitoring system")
            
            # Start listening for tasks and messages
            task_queue = await self.channel.declare_queue(f"{self.name.lower()}_tasks", durable=True)
            comms_queue = await self.channel.declare_queue(f"{self.name.lower()}_comms", durable=True)
            broadcast_queue = await self.channel.declare_queue("squad_broadcast", durable=True)
            
            async def process_tasks():
                async for message in task_queue:
                    try:
                        logger.debug(f"{self.name} received message: {message.body.decode()}")
                        task_data = json.loads(message.body.decode())
                        logger.debug(f"{self.name} parsed task_data: {task_data}")
                        logger.debug(f"{self.name} about to call process_task")
                        result = await self.process_task(task_data)
                        logger.debug(f"{self.name} process_task completed: {result}")
                        
                        # Update task status
                        logger.debug(f"{self.name} about to call update_task_status")
                        await self.update_task_status(
                            task_data.get('task_id', 'unknown'),
                            'Completed',
                            progress=100.0
                        )
                        logger.debug(f"{self.name} update_task_status completed")
                        
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
            
            async def heartbeat_loop():
                """Send periodic heartbeats"""
                while True:
                    await self.send_heartbeat()
                    await asyncio.sleep(30)  # Send heartbeat every 30 seconds
            
            # Run all processors concurrently
            await asyncio.gather(
                process_tasks(),
                process_comms(),
                process_broadcasts(),
                heartbeat_loop()
            )
            
        except Exception as e:
            logger.error(f"{self.name} runtime error: {e}")
        finally:
            await self.cleanup()
    
    # ============================================================================
    # GENERIC AGENT CAPABILITIES
    # ============================================================================
    
    async def read_file(self, file_path: str) -> str:
        """Read file content asynchronously"""
        try:
            # Handle both absolute and relative paths
            if not os.path.isabs(file_path):
                file_path = os.path.join('/app', file_path)
            
            logger.info(f"{self.name} read file: {file_path}")
            
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                return content
                
        except Exception as e:
            logger.error(f"{self.name} failed to read file {file_path}: {e}")
            raise
    
    async def write_file(self, file_path: str, content: str) -> bool:
        """Write content to file asynchronously"""
        try:
            # Handle both absolute and relative paths
            if not os.path.isabs(file_path):
                file_path = os.path.join('/app', file_path)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            logger.info(f"{self.name} wrote file: {file_path}")
            
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(content)
                return True
                
        except Exception as e:
            logger.error(f"{self.name} failed to write file {file_path}: {e}")
            return False
    
    async def modify_file(self, file_path: str, modifications: List[Dict[str, Any]]) -> bool:
        """Modify file content based on modifications list"""
        try:
            # Read current content
            content = await self.read_file(file_path)
            
            # Apply modifications
            for mod in modifications:
                mod_type = mod.get('type', 'replace')
                
                if mod_type == 'replace':
                    old_text = mod.get('old_text', '')
                    new_text = mod.get('new_text', '')
                    content = content.replace(old_text, new_text)
                    
                elif mod_type == 'insert_after':
                    after_text = mod.get('after_text', '')
                    new_text = mod.get('new_text', '')
                    content = content.replace(after_text, after_text + new_text)
                    
                elif mod_type == 'insert_before':
                    before_text = mod.get('before_text', '')
                    new_text = mod.get('new_text', '')
                    content = content.replace(before_text, new_text + before_text)
            
            # Write modified content
            return await self.write_file(file_path, content)
            
        except Exception as e:
            logger.error(f"{self.name} failed to modify file {file_path}: {e}")
            return False
    
    async def execute_command(self, command: str, cwd: str = None) -> Dict[str, Any]:
        """Execute shell command asynchronously"""
        try:
            if cwd is None:
                cwd = '/app'
            
            logger.info(f"{self.name} executing command: {command}")
            
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            return {
                'success': process.returncode == 0,
                'returncode': process.returncode,
                'stdout': stdout.decode('utf-8') if stdout else '',
                'stderr': stderr.decode('utf-8') if stderr else ''
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to execute command {command}: {e}")
            return {
                'success': False,
                'returncode': -1,
                'stdout': '',
                'stderr': str(e)
            }
    
    async def list_files(self, directory: str, pattern: str = None) -> List[str]:
        """List files in directory"""
        try:
            if not os.path.isabs(directory):
                directory = os.path.join('/app', directory)
            
            files = []
            for root, dirs, filenames in os.walk(directory):
                for filename in filenames:
                    if pattern is None or pattern in filename:
                        files.append(os.path.join(root, filename))
            
            return files
            
        except Exception as e:
            logger.error(f"{self.name} failed to list files in {directory}: {e}")
            return []
    
    async def file_exists(self, file_path: str) -> bool:
        """Check if file exists"""
        try:
            if not os.path.isabs(file_path):
                file_path = os.path.join('/app', file_path)
            return os.path.exists(file_path)
        except Exception as e:
            logger.error(f"{self.name} failed to check file existence {file_path}: {e}")
            return False

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
