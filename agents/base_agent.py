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
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, List
import aio_pika
import asyncpg
import redis.asyncio as redis
from dataclasses import dataclass, asdict
import aiofiles
import shutil
from pathlib import Path

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
                INSERT INTO agent_logs (agent_name, activity, details, timestamp)
                VALUES ($1, $2, $3, $4)
            """, self.name, activity, json.dumps(details or {}), datetime.utcnow().isoformat())
    
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
                self.current_task,
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
    # FILE MODIFICATION CAPABILITIES
    # ============================================================================
    
    async def read_file(self, file_path: str) -> str:
        """Read a file and return its contents"""
        try:
            # Ensure path is relative to warm-boot directory
            if not file_path.startswith('/'):
                file_path = f"/app/{file_path}"
            
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                logger.info(f"{self.name} read file: {file_path}")
                return content
        except Exception as e:
            logger.error(f"{self.name} failed to read file {file_path}: {e}")
            raise
    
    async def write_file(self, file_path: str, content: str) -> bool:
        """Write content to a file"""
        try:
            # Ensure path is relative to warm-boot directory
            if not file_path.startswith('/'):
                file_path = f"/app/{file_path}"
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(content)
                logger.info(f"{self.name} wrote file: {file_path}")
                return True
        except Exception as e:
            logger.error(f"{self.name} failed to write file {file_path}: {e}")
            return False
    
    async def modify_file(self, file_path: str, modifications: List[Dict[str, Any]]) -> bool:
        """Apply modifications to a file (replace, insert, delete)"""
        try:
            # Read current content
            current_content = await self.read_file(file_path)
            lines = current_content.split('\n')
            
            # Apply modifications in reverse order to maintain line numbers
            modifications.sort(key=lambda x: x.get('line_number', 0), reverse=True)
            
            for mod in modifications:
                mod_type = mod.get('type', 'replace')
                line_number = mod.get('line_number', 0)
                content = mod.get('content', '')
                
                if mod_type == 'replace' and 0 <= line_number < len(lines):
                    lines[line_number] = content
                elif mod_type == 'insert' and 0 <= line_number <= len(lines):
                    lines.insert(line_number, content)
                elif mod_type == 'delete' and 0 <= line_number < len(lines):
                    lines.pop(line_number)
            
            # Write modified content
            new_content = '\n'.join(lines)
            return await self.write_file(file_path, new_content)
            
        except Exception as e:
            logger.error(f"{self.name} failed to modify file {file_path}: {e}")
            return False
    
    async def create_directory(self, dir_path: str) -> bool:
        """Create a directory"""
        try:
            if not dir_path.startswith('/'):
                dir_path = f"/app/{dir_path}"
            
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"{self.name} created directory: {dir_path}")
            return True
        except Exception as e:
            logger.error(f"{self.name} failed to create directory {dir_path}: {e}")
            return False
    
    async def list_files(self, dir_path: str) -> List[str]:
        """List files in a directory"""
        try:
            if not dir_path.startswith('/'):
                dir_path = f"/app/{dir_path}"
            
            files = []
            for item in os.listdir(dir_path):
                item_path = os.path.join(dir_path, item)
                if os.path.isfile(item_path):
                    files.append(item)
            logger.info(f"{self.name} listed files in: {dir_path}")
            return files
        except Exception as e:
            logger.error(f"{self.name} failed to list files in {dir_path}: {e}")
            return []
    
    async def file_exists(self, file_path: str) -> bool:
        """Check if a file exists"""
        try:
            if not file_path.startswith('/'):
                file_path = f"/app/{file_path}"
            
            exists = os.path.isfile(file_path)
            logger.info(f"{self.name} checked file existence: {file_path} = {exists}")
            return exists
        except Exception as e:
            logger.error(f"{self.name} failed to check file existence {file_path}: {e}")
            return False
    
    # ============================================================================
    # DEPLOYMENT CAPABILITIES
    # ============================================================================
    
    async def build_docker_image(self, context_path: str, image_name: str, build_args: Dict[str, str] = None) -> bool:
        """Build a Docker image with enhanced capabilities"""
        try:
            import subprocess
            import os
            
            # Ensure we're in the right directory
            if not context_path.startswith('/'):
                context_path = f"/app/{context_path}"
            
            # Validate context path exists
            if not os.path.exists(context_path):
                logger.error(f"{self.name} Docker context path does not exist: {context_path}")
                return False
            
            cmd = ["docker", "build", "-t", image_name]
            
            # Add build args
            if build_args:
                for key, value in build_args.items():
                    cmd.extend(["--build-arg", f"{key}={value}"])
            
            cmd.append(context_path)
            
            logger.info(f"{self.name} building Docker image: {image_name} from {context_path}")
            result = subprocess.run(cmd, capture_output=True, text=True, cwd="/app")
            
            if result.returncode == 0:
                logger.info(f"{self.name} successfully built Docker image: {image_name}")
                return True
            else:
                logger.error(f"{self.name} failed to build Docker image: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"{self.name} failed to build Docker image: {e}")
            return False
    
    async def deploy_service(self, service_name: str, image_name: str, ports: List[str] = None, env_vars: Dict[str, str] = None) -> bool:
        """Deploy a service using docker-compose with enhanced capabilities"""
        try:
            import subprocess
            import os
            
            # First, try to stop and remove existing container
            try:
                subprocess.run(["docker", "stop", service_name], capture_output=True, text=True)
                subprocess.run(["docker", "rm", service_name], capture_output=True, text=True)
            except:
                pass  # Container might not exist
            
            # Build docker run command
            cmd = ["docker", "run", "-d", "--name", service_name]
            
            # Add port mappings
            if ports:
                for port in ports:
                    cmd.extend(["-p", port])
            
            # Add environment variables
            if env_vars:
                for key, value in env_vars.items():
                    cmd.extend(["-e", f"{key}={value}"])
            
            # Add network (use existing squadnet)
            cmd.extend(["--network", "squad-ops_squadnet"])
            
            cmd.append(image_name)
            
            logger.info(f"{self.name} deploying service: {service_name} with image: {image_name}")
            result = subprocess.run(cmd, capture_output=True, text=True, cwd="/app")
            
            if result.returncode == 0:
                logger.info(f"{self.name} successfully deployed service: {service_name}")
                return True
            else:
                logger.error(f"{self.name} failed to deploy service: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"{self.name} failed to deploy service: {e}")
            return False
    
    async def update_docker_compose(self, service_config: Dict[str, Any]) -> bool:
        """Update docker-compose.yml with new service configuration"""
        try:
            import yaml
            import os
            
            compose_file = "/app/docker-compose.yml"
            
            # Read existing docker-compose.yml
            if os.path.exists(compose_file):
                with open(compose_file, 'r') as f:
                    compose_data = yaml.safe_load(f) or {}
            else:
                compose_data = {}
            
            # Ensure services section exists
            if 'services' not in compose_data:
                compose_data['services'] = {}
            
            # Add or update service
            service_name = service_config.get('name')
            if service_name:
                compose_data['services'][service_name] = service_config.get('config', {})
                
                # Write updated docker-compose.yml
                with open(compose_file, 'w') as f:
                    yaml.dump(compose_data, f, default_flow_style=False)
                
                logger.info(f"{self.name} updated docker-compose.yml with service: {service_name}")
                return True
            else:
                logger.error(f"{self.name} service config missing 'name' field")
                return False
                
        except Exception as e:
            logger.error(f"{self.name} failed to update docker-compose: {e}")
            return False
    
    async def restart_service(self, service_name: str) -> bool:
        """Restart a Docker service"""
        try:
            import subprocess
            
            # Stop the service
            stop_result = subprocess.run(["docker", "stop", service_name], capture_output=True, text=True)
            
            # Start the service
            start_result = subprocess.run(["docker", "start", service_name], capture_output=True, text=True)
            
            if start_result.returncode == 0:
                logger.info(f"{self.name} successfully restarted service: {service_name}")
                return True
            else:
                logger.error(f"{self.name} failed to restart service: {start_result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"{self.name} failed to restart service: {e}")
            return False
    
    async def check_service_status(self, service_name: str) -> Dict[str, Any]:
        """Check the status of a Docker service"""
        try:
            import subprocess
            
            # Get container status
            result = subprocess.run(
                ["docker", "inspect", service_name], 
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                import json
                container_info = json.loads(result.stdout)[0]
                
                status = {
                    "name": service_name,
                    "running": container_info["State"]["Running"],
                    "status": container_info["State"]["Status"],
                    "ports": container_info["NetworkSettings"]["Ports"],
                    "image": container_info["Config"]["Image"]
                }
                
                logger.info(f"{self.name} checked service status: {service_name} - {status['status']}")
                return status
            else:
                logger.error(f"{self.name} failed to check service status: {result.stderr}")
                return {"name": service_name, "error": "Service not found"}
                
        except Exception as e:
            logger.error(f"{self.name} failed to check service status: {e}")
            return {"name": service_name, "error": str(e)}
    
    # ============================================================================
    # DOCUMENTATION CAPABILITIES
    # ============================================================================
    
    async def create_documentation(self, doc_path: str, content: str, doc_type: str = "markdown") -> bool:
        """Create documentation file with enhanced capabilities"""
        try:
            # Ensure proper file extension
            if not doc_path.endswith('.md') and doc_type == "markdown":
                doc_path += '.md'
            
            # Add timestamp and agent attribution
            timestamp = datetime.utcnow().isoformat()
            header = f"<!-- Generated by {self.name} on {timestamp} -->\n\n"
            full_content = header + content
            
            success = await self.write_file(doc_path, full_content)
            if success:
                logger.info(f"{self.name} created documentation: {doc_path}")
            return success
        except Exception as e:
            logger.error(f"{self.name} failed to create documentation: {e}")
            return False
    
    async def update_documentation(self, doc_path: str, updates: List[Dict[str, Any]]) -> bool:
        """Update existing documentation with enhanced capabilities"""
        try:
            if await self.file_exists(doc_path):
                # Add update timestamp
                timestamp = datetime.utcnow().isoformat()
                update_note = f"<!-- Updated by {self.name} on {timestamp} -->\n"
                
                # Read current content
                current_content = await self.read_file(doc_path)
                
                # Apply updates
                success = await self.modify_file(doc_path, updates)
                
                if success:
                    # Add update note to the end
                    updated_content = await self.read_file(doc_path)
                    await self.write_file(doc_path, updated_content + "\n" + update_note)
                    logger.info(f"{self.name} updated documentation: {doc_path}")
                
                return success
            else:
                logger.warning(f"{self.name} documentation file not found: {doc_path}")
                return False
        except Exception as e:
            logger.error(f"{self.name} failed to update documentation: {e}")
            return False
    
    async def create_run_summary(self, run_id: str, summary_data: Dict[str, Any]) -> bool:
        """Create WarmBoot run summary documentation"""
        try:
            doc_path = f"warm-boot/runs/{run_id}-summary.md"
            
            content = f"""# WarmBoot {run_id} Summary

**Run ID:** {run_id}  
**Date:** {summary_data.get('date', datetime.utcnow().isoformat())}  
**Status:** {summary_data.get('status', 'Completed')}  
**Agent Work:** {summary_data.get('agent_work_percentage', 'Unknown')}% Real

## Executive Summary

{summary_data.get('summary', 'No summary provided')}

## Agent Collaboration

{summary_data.get('collaboration_details', 'No collaboration details')}

## Technical Implementation

{summary_data.get('technical_details', 'No technical details')}

## Verification Results

{summary_data.get('verification_results', 'No verification results')}

## Files Modified

{summary_data.get('files_modified', 'No files modified')}

## Next Steps

{summary_data.get('next_steps', 'No next steps defined')}

---
*Generated by {self.name} on {datetime.utcnow().isoformat()}*
"""
            
            return await self.create_documentation(doc_path, content)
        except Exception as e:
            logger.error(f"{self.name} failed to create run summary: {e}")
            return False
    
    async def create_run_logs(self, run_id: str, log_data: Dict[str, Any]) -> bool:
        """Create WarmBoot run logs in JSON format"""
        try:
            import json
            
            doc_path = f"warm-boot/runs/{run_id}-logs.json"
            
            # Add metadata
            log_data['generated_by'] = self.name
            log_data['generated_at'] = datetime.utcnow().isoformat()
            
            content = json.dumps(log_data, indent=2)
            
            return await self.write_file(doc_path, content)
        except Exception as e:
            logger.error(f"{self.name} failed to create run logs: {e}")
            return False
    
    async def create_release_manifest(self, run_id: str, manifest_data: Dict[str, Any]) -> bool:
        """Create release manifest for WarmBoot run"""
        try:
            doc_path = f"warm-boot/runs/{run_id}/release_manifest.yaml"
            
            # Ensure directory exists
            await self.create_directory(f"warm-boot/runs/{run_id}")
            
            content = f"""# WarmBoot {run_id} Release Manifest

**Release ID:** {run_id}  
**Release Date:** {manifest_data.get('release_date', datetime.utcnow().isoformat())}  
**Status:** {manifest_data.get('status', 'Deployed')}

## Infrastructure Versions

{manifest_data.get('infrastructure_versions', 'No infrastructure details')}

## Code Versions

{manifest_data.get('code_versions', 'No code details')}

## Configuration

{manifest_data.get('configuration', 'No configuration details')}

## Deployment Details

{manifest_data.get('deployment_details', 'No deployment details')}

## Verification

{manifest_data.get('verification', 'No verification details')}

---
*Generated by {self.name} on {datetime.utcnow().isoformat()}*
"""
            
            return await self.create_documentation(doc_path, content)
        except Exception as e:
            logger.error(f"{self.name} failed to create release manifest: {e}")
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
