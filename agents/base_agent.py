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
from typing import Dict, Any, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from agents.specs.agent_request import AgentRequest
    from agents.specs.agent_response import AgentResponse
import aio_pika
import asyncpg
import redis.asyncio as redis
import aiohttp
from dataclasses import dataclass, asdict

# Telemetry abstraction - no direct OpenTelemetry imports needed
# TelemetryClient handles all telemetry backends (OpenTelemetry, AWS, Azure, GCP, Null)

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
        self.db_pool = None  # Deprecated: Keep for legacy reads, will be removed in future
        self.redis_client = None
        
        # Memory providers (SIP-042)
        self.memory_provider = None  # Mem0Adapter for agent-level memory
        self.sql_adapter = None  # SqlAdapter for Squad Memory Pool promotion
        
        # Initialize unified configuration
        from config.unified_config import get_config
        self.config = get_config()
        
        # Configuration from unified config manager
        self.rabbitmq_url = self.config.get_rabbitmq_url()
        self.postgres_url = self.config.get_postgres_url()
        self.redis_url = self.config.get_redis_url()
        self.task_api_url = self.config.get_task_api_url()
        
        # Initialize LLM client
        self.llm_client = self._initialize_llm_client()
        
        # Initialize communication log for telemetry
        self.communication_log = []
        
        # Initialize telemetry client (abstraction layer)
        self.telemetry_client = self._initialize_telemetry_client()
        
        # Initialize capability system (SIP-046)
        self._load_capability_config()
    
    def _initialize_llm_client(self):
        """Initialize LLM client from router"""
        from agents.llm.router import LLMRouter
        router = LLMRouter.from_config('config/llm_config.yaml')
        return router.get_default_client()
    
    def _initialize_telemetry_client(self):
        """Initialize telemetry client from router (platform-aware)"""
        # Handle both Docker (flattened) and local (nested) import structures
        try:
            # Try local development structure first
            from agents.telemetry.router import TelemetryRouter
        except ImportError:
            try:
                # Try Docker flattened structure
                from telemetry.router import TelemetryRouter
            except ImportError:
                # Fallback to NullTelemetryClient if telemetry not available
                logger.warning(f"{self.name}: TelemetryRouter not found, using NullTelemetryClient")
                try:
                    from agents.telemetry.providers.null_client import NullTelemetryClient
                    return NullTelemetryClient({})
                except ImportError:
                    try:
                        from telemetry.providers.null_client import NullTelemetryClient
                        return NullTelemetryClient({})
                    except ImportError:
                        logger.error(f"{self.name}: No telemetry client available")
                        return None
        
        # Get agent version and config for telemetry client
        try:
            agent_version = get_agent_version(self.name)
            agent_config = get_agent_config(self.name)
        except Exception as e:
            logger.warning(f"{self.name}: Failed to get agent version/config: {e}")
            agent_version = "0.3.0"
            agent_config = {"llm": "unknown"}
        
        # Build telemetry config
        telemetry_config = {
            'service_name': f"squadops-{self.name.lower()}",
            'service_version': agent_version,
            'agent_name': self.name,
            'agent_type': self.agent_type,
            'agent_llm': agent_config.get("llm", "unknown"),
        }
        
        # Initialize via router (handles platform selection)
        telemetry_client = TelemetryRouter.from_config()
        
        # Update client config if it's OpenTelemetryClient
        if hasattr(telemetry_client, 'config'):
            telemetry_client.config.update(telemetry_config)
            # Re-initialize with updated config if needed
            if hasattr(telemetry_client, '_setup_telemetry'):
                telemetry_client._setup_telemetry()
        
        logger.info(f"{self.name}: Telemetry client initialized ({type(telemetry_client).__name__})")
        return telemetry_client
    
    def get_tracer(self, name: str = None):
        """Get telemetry tracer instance via TelemetryClient"""
        if name is None:
            name = f"squadops.{self.name.lower()}"
        return self.telemetry_client.get_tracer(name) if self.telemetry_client else None
    
    def get_meter(self, name: str = None):
        """Get telemetry meter instance via TelemetryClient"""
        if name is None:
            name = f"squadops.{self.name.lower()}"
        return self.telemetry_client.get_meter(name) if self.telemetry_client else None
    
    def create_span(self, span_name: str, attributes: Dict[str, Any] = None, kind: Optional[str] = None):
        """Create a telemetry span context manager via TelemetryClient"""
        if not self.telemetry_client:
            from contextlib import nullcontext
            return nullcontext()
        
        return self.telemetry_client.create_span(span_name, attributes, kind)
    
    def record_counter(self, metric_name: str, value: float = 1.0, labels: Dict[str, str] = None):
        """Record a counter metric via TelemetryClient"""
        if not self.telemetry_client:
            return
        
        try:
            self.telemetry_client.record_counter(metric_name, int(value), labels)
        except Exception as e:
            logger.debug(f"{self.name}: Failed to record counter {metric_name}: {e}")
    
    def record_gauge(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """Record a gauge metric via TelemetryClient"""
        if not self.telemetry_client:
            return
        
        try:
            self.telemetry_client.record_gauge(metric_name, value, labels)
        except Exception as e:
            logger.debug(f"{self.name}: Failed to record gauge {metric_name}: {e}")
    
    def record_histogram(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """Record a histogram metric via TelemetryClient"""
        if not self.telemetry_client:
            return
        
        try:
            self.telemetry_client.record_histogram(metric_name, value, labels)
        except Exception as e:
            logger.debug(f"{self.name}: Failed to record histogram {metric_name}: {e}")
        
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
            
            # Initialize memory providers (SIP-042)
            await self._initialize_memory_providers()
            
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
    
    async def _initialize_memory_providers(self):
        """Initialize memory providers (SIP-042)"""
        try:
            from agents.memory.lancedb_adapter import LanceDBAdapter
            from agents.memory.sql_adapter import SqlAdapter
            
            # Initialize LanceDBAdapter for agent-level memory
            self.memory_provider = LanceDBAdapter(self.name)
            
            # Initialize SqlAdapter for Squad Memory Pool promotion
            if self.db_pool:
                self.sql_adapter = SqlAdapter(self.db_pool)
            
            logger.info(f"{self.name}: Memory providers initialized")
        except Exception as e:
            logger.warning(f"{self.name}: Failed to initialize memory providers: {e}")
            # Continue without memory if initialization fails
    
    def _extract_memory_context(self, task: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract PID and ECID from task context.
        Handles various task formats (agent_task_log, message payload, etc.)
        
        Args:
            task: Task dictionary (may be from various sources)
        
        Returns:
            Dictionary with 'pid' and 'ecid' keys
        """
        pid = None
        ecid = None
        
        # Try direct keys first
        if 'pid' in task:
            pid = task['pid']
        if 'ecid' in task:
            ecid = task['ecid']
        
        # Try context dict
        if 'context' in task and isinstance(task['context'], dict):
            pid = pid or task['context'].get('pid')
            ecid = ecid or task['context'].get('ecid')
        
        # Try payload
        if 'payload' in task and isinstance(task['payload'], dict):
            pid = pid or task['payload'].get('pid')
            ecid = ecid or task['payload'].get('ecid')
        
        return {
            'pid': pid or 'unknown',
            'ecid': ecid or 'unknown'
        }
    
    async def record_memory(self, kind: str, payload: Any, importance: float = 0.7, ns: str = "role", 
                           task_context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Record a memory after successful agent action (SIP-042).
        Agent-level memories go to LanceDB, Squad-level go to PostgreSQL.
        
        Args:
            kind: Type of memory (e.g., 'task_delegation', 'build_success', 'governance_decision')
            payload: Memory payload (can be dict or object with to_dict() method)
            importance: Importance score (0.0 to 1.0)
            ns: Namespace ('role' for agent-level, 'squad' for promoted)
            task_context: Optional task context dict for extracting PID/ECID
        
        Returns:
            Memory ID if successful, None otherwise
        """
        # Agent-level memories use Mem0 (SQLite), Squad-level use SQL adapter
        if ns == "squad":
            if not self.sql_adapter:
                logger.debug(f"{self.name}: SQL adapter not initialized, skipping squad memory recording")
                return None
            adapter = self.sql_adapter
        else:
            if not self.memory_provider:
                logger.debug(f"{self.name}: Memory provider not initialized, skipping memory recording")
                return None
            adapter = self.memory_provider
        
        try:
            # Extract PID and ECID from context
            context = task_context or self.current_task or {}
            context_info = self._extract_memory_context(context)
            pid = context_info.get('pid', 'unknown')
            ecid = context_info.get('ecid', 'unknown')
            
            # Convert payload to dict if needed
            if hasattr(payload, 'to_dict'):
                payload_dict = payload.to_dict()
            elif isinstance(payload, dict):
                payload_dict = payload
            else:
                payload_dict = {'data': str(payload)}
            
            # Create tags
            tags = [
                f"pid:{pid}",
                kind,
                f"agent:{self.name.lower()}"
            ]
            if ecid != 'unknown':
                tags.append(f"ecid:{ecid}")
            
            # Create memory content
            memory_content = {
                'action': kind,
                'result': payload_dict,
                'timestamp': datetime.utcnow().isoformat(),
                'ecid': ecid,
                'pid': pid
            }
            
            # Create memory item
            memory_item = {
                'ns': ns,
                'agent': self.name,
                'tags': tags,
                'content': memory_content,
                'importance': importance,
                'pid': pid if pid != 'unknown' else None,
                'ecid': ecid if ecid != 'unknown' else None
            }
            
            # Add status/validator for SQL adapter
            if ns == "squad":
                memory_item['status'] = 'pending'
                memory_item['validator'] = None
            
            # Store memory via appropriate adapter
            # Instrument memory operation with telemetry span
            span_name = f"memory.{'promote' if ns == 'squad' else 'store'}"
            span_attrs = {
                'agent.name': self.name,
                'memory.kind': kind,
                'memory.namespace': ns,
                'memory.importance': importance,
                'ecid': ecid if ecid != 'unknown' else None,
                'pid': pid if pid != 'unknown' else None,
                'storage': 'squad_pool' if ns == 'squad' else 'lancedb'
            }
            
            import time
            start_time = time.time()
            
            with self.create_span(span_name, span_attrs):
                mem_id = await adapter.put(memory_item)
                latency_ms = (time.time() - start_time) * 1000
                
                # Record latency histogram
                self.record_histogram('memory_operation_latency_ms', latency_ms, {
                    'operation': 'put',
                    'namespace': ns,
                    'agent': self.name
                })
                
                if mem_id:
                    # Record success metrics
                    self.record_counter('memory_operations_total', 1, {
                        'operation': 'put',
                        'kind': kind,
                        'namespace': ns,
                        'agent': self.name,
                        'status': 'success'
                    })
                    
                    storage = "Squad Memory Pool" if ns == "squad" else "LanceDB"
                    logger.info(f"{self.name}: Recorded memory {kind} (ID: {mem_id[:8] if mem_id else 'None'}...) for ECID {ecid} in {storage} ({latency_ms:.2f}ms)")
                else:
                    # Record failure metrics
                    self.record_counter('memory_operations_total', 1, {
                        'operation': 'put',
                        'kind': kind,
                        'namespace': ns,
                        'agent': self.name,
                        'status': 'failed'
                    })
                    logger.warning(f"{self.name}: Failed to record memory {kind} - adapter returned None")
                
                return mem_id
            
        except Exception as e:
            # Record failure telemetry
            self.record_counter('memory_operations_total', 1, {
                'operation': 'put',
                'kind': kind,
                'namespace': ns,
                'agent': self.name,
                'status': 'error'
            })
            logger.error(f"{self.name}: Failed to record memory: {e}")
            return None
    
    async def retrieve_memories(self, query: str = "", k: int = 8, ns: str = "role", **kwargs) -> List[dict]:
        """
        Retrieve memories with telemetry instrumentation.
        
        Args:
            query: Search query string
            k: Maximum number of results
            ns: Namespace ('role' for agent-level, 'squad' for Squad Memory Pool)
            **kwargs: Additional filters (tags, agent, pid, ecid, etc.)
        
        Returns:
            List of memory dictionaries
        """
        # Select appropriate adapter
        if ns == "squad":
            if not self.sql_adapter:
                logger.debug(f"{self.name}: SQL adapter not initialized, cannot retrieve squad memories")
                return []
            adapter = self.sql_adapter
        else:
            if not self.memory_provider:
                logger.debug(f"{self.name}: Memory provider not initialized, cannot retrieve memories")
                return []
            adapter = self.memory_provider
        
        # Instrument memory retrieval with telemetry span
        span_name = f"memory.{'retrieve_squad' if ns == 'squad' else 'retrieve'}"
        span_attrs = {
            'agent.name': self.name,
            'memory.namespace': ns,
            'memory.query_length': len(query),
            'memory.max_results': k
        }
        
        import time
        start_time = time.time()
        
        try:
            with self.create_span(span_name, span_attrs):
                memories = await adapter.get(query, k, **kwargs)
                latency_ms = (time.time() - start_time) * 1000
                
                # Record latency histogram
                self.record_histogram('memory_operation_latency_ms', latency_ms, {
                    'operation': 'get',
                    'namespace': ns,
                    'agent': self.name
                })
                
                # Record retrieval metrics
                self.record_counter('memory_operations_total', 1, {
                    'operation': 'get',
                    'namespace': ns,
                    'agent': self.name,
                    'status': 'success'
                })
                
                # Record results count as gauge
                self.record_gauge('memory_retrieval_results_count', len(memories), {
                    'namespace': ns,
                    'agent': self.name
                })
                
                logger.debug(f"{self.name}: Retrieved {len(memories)} memories from {ns} namespace ({latency_ms:.2f}ms)")
                return memories
                
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            
            # Record error metrics
            self.record_counter('memory_operations_total', 1, {
                'operation': 'get',
                'namespace': ns,
                'agent': self.name,
                'status': 'error'
            })
            
            logger.error(f"{self.name}: Failed to retrieve memories: {e}")
            return []
    
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
        """Update task status via Task API (replaces direct database writes)"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.task_api_url}/api/v1/task-status",
                    json={
                        "task_id": task_id,
                        "agent_name": self.name,
                        "status": status,
                        "progress": progress,
                        "eta": eta
                    }
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Failed to update task status: {error_text}")
                    else:
                        logger.debug(f"{self.name} updated task status via API: {task_id}")
                        return await resp.json()
        except Exception as e:
            logger.error(f"{self.name} failed to update task status via API: {e}")
            raise
    
    async def log_activity(self, activity: str, details: Dict[str, Any] = None):
        """
        DEPRECATED: Log agent activity
        
        This method writes to deprecated agent_task_logs table.
        Use Task API endpoints (log_task_start, log_task_completion) instead.
        
        Now gracefully handles missing table (for integration tests).
        """
        import warnings
        warnings.warn(
            f"log_activity() is deprecated for {self.name}. "
            "Use Task API endpoints (log_task_start, log_task_completion) instead.",
            DeprecationWarning,
            stacklevel=2
        )
        # Keep legacy implementation but mark as deprecated
        # Gracefully handle missing table (for integration tests)
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO agent_task_logs (task_id, agent_name, task_name, task_status, start_time, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6)
                    """, f"{self.name}_{activity}_{int(time.time() * 1000)}", self.name, activity, "completed", datetime.utcnow(), datetime.utcnow())
            except Exception as e:
                # Gracefully handle missing table (integration tests, etc.)
                logger.debug(f"{self.name} log_activity failed (table may not exist): {e}")
                # Still log to communication log as fallback
                self.communication_log.append({
                    'activity': activity,
                    'details': details or {},
                    'timestamp': datetime.utcnow().isoformat()
                })
        else:
            # No db_pool - just log to communication log
            self.communication_log.append({
                'activity': activity,
                'details': details or {},
                'timestamp': datetime.utcnow().isoformat()
            })
    
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
        try:
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
                        error_text = await resp.text()
                        logger.error(f"Failed to log task start: {error_text}")
                        # Return None instead of raising - allow task creation to continue
                        return None
                    try:
                        return await resp.json()
                    except Exception as e:
                        logger.warning(f"Failed to parse task start response: {e}")
                        return None
        except Exception as e:
            # If Task API is unavailable, log warning but don't fail
            logger.warning(f"Task API unavailable for log_task_start: {e}")
            return None

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
        """Send heartbeat via Health-Check API (agent health management)"""
        try:
            # Get memory count if memory provider is available
            memory_count = 0
            if self.memory_provider and hasattr(self.memory_provider, 'count'):
                try:
                    memory_count = await self.memory_provider.count()
                except Exception as e:
                    logger.debug(f"{self.name} failed to get memory count: {e}")
            
            # Use health-check service URL (defaults to health-check:8000 if HEALTH_CHECK_URL not set)
            health_check_url = os.getenv('HEALTH_CHECK_URL', 'http://health-check:8000')
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{health_check_url}/health/agents/status",
                    json={
                        "agent_name": self.name,
                        "status": self.status,
                        "current_task_id": self.current_task or None,
                        "version": get_agent_version(self.name),
                        "tps": 0,  # Mock TPS for now
                        "memory_count": memory_count
                    }
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Failed to send heartbeat: {error_text}")
                    else:
                        logger.debug(f"{self.name} heartbeat sent via Health-Check API (memory_count: {memory_count})")
                        return await resp.json()
        except Exception as e:
            logger.error(f"{self.name} heartbeat failed via Health-Check API: {e}")
            raise
    
    def _load_capability_config(self):
        """Load capability configuration from config.yaml"""
        try:
            from agents.capabilities.loader import CapabilityLoader
            from pathlib import Path
            
            # Determine role from agent_type (e.g., "governance" -> "lead")
            role_map = {
                "governance": "lead",
                "developer": "dev",
                "strategy": "strat",
                "quality_assurance": "qa",
                "data_analyst": "data",
                "financial_analyst": "finance",
                "communications": "comms",
                "research_curator": "curator",
                "creative_designer": "creative",
                "auditor": "audit",
                "devops": "devops"
            }
            
            role = role_map.get(self.agent_type, self.agent_type)
            
            # Load capability config
            base_path = Path(__file__).parent.parent.parent
            loader = CapabilityLoader(base_path)
            self.capability_config = loader.load_agent_config(role)
            self.capability_loader = loader
            self.implemented_capabilities = loader.get_agent_capabilities(role) if self.capability_config else []
            
            logger.info(f"{self.name}: Loaded capability config for role {role}, implements {len(self.implemented_capabilities)} capabilities")
            
        except Exception as e:
            logger.warning(f"{self.name}: Failed to load capability config: {e}")
            self.capability_config = None
            self.capability_loader = None
            self.implemented_capabilities = []
    
    def _validate_constraints(self, request: 'AgentRequest') -> tuple[bool, Optional[str]]:
        """Validate request against agent constraints"""
        if not self.capability_config:
            return True, None  # No constraints if config not loaded
        
        constraints = self.capability_config.constraints
        
        # Validate repo_allow
        if 'repo_allow' in constraints:
            repo_allow = constraints['repo_allow']
            payload_repo = request.payload.get('repo', request.payload.get('project', ''))
            if repo_allow and not any(repo_allow_pattern in payload_repo for repo_allow_pattern in repo_allow):
                return False, f"Repository not allowed: {payload_repo}"
        
        # Validate max_runtime_s (will be checked during execution)
        # Validate network_allow (will be checked during execution)
        
        return True, None
    
    @abstractmethod
    async def handle_agent_request(self, request: 'AgentRequest') -> 'AgentResponse':
        """Handle agent request - must be implemented by each agent"""
        pass
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task - DEPRECATED: Use handle_agent_request instead"""
        # Convert old task format to AgentRequest for compatibility
        try:
            from agents.specs.agent_request import AgentRequest
            from agents.specs.agent_response import AgentResponse
            
            # Try to convert task to AgentRequest
            if 'action' in task:
                request = AgentRequest.from_dict(task)
                response = await self.handle_agent_request(request)
                return response.to_dict()
            else:
                # Fallback for old format
                logger.warning(f"{self.name}: Received old format task, converting...")
                # Create minimal AgentRequest from old task
                request = AgentRequest(
                    action=task.get('type', 'unknown'),
                    payload=task,
                    metadata={
                        'pid': task.get('pid', 'unknown'),
                        'ecid': task.get('ecid', 'unknown')
                    }
                )
                response = await self.handle_agent_request(request)
                return response.to_dict()
        except Exception as e:
            logger.error(f"{self.name}: Failed to process task: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'task_id': task.get('task_id', 'unknown')
            }
    
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
        """Execute LLM call via configured provider with telemetry span and token tracking (Task 1.3)"""
        from datetime import datetime
        
        # Create telemetry span for LLM call (Task 1.1: Link Ollama logs to telemetry)
        span_name = f"llm_call.{context.lower().replace(' ', '_')}"
        span_ctx = self.create_span(span_name, {
            'agent.name': self.name,
            'llm.operation': context,
            'llm.prompt_length': len(prompt),
            'ecid': getattr(self, 'current_ecid', None)
        })
        
        # Extract trace ID before entering span context (Task 1.1)
        trace_id = None
        try:
            # Try to get trace ID from current active span if available
            from opentelemetry import trace
            current_span = trace.get_current_span()
            if current_span and hasattr(current_span, 'get_span_context'):
                span_context = current_span.get_span_context()
                if span_context and span_context.trace_id:
                    trace_id = format(span_context.trace_id, '032x')
        except Exception:
            pass
        
        with span_ctx:
            try:
                response = await self.llm_client.complete(
                    prompt=prompt,
                    temperature=0.7,
                    max_tokens=4000
                )
                
                # Try to get trace ID again after span is active (Task 1.1)
                if not trace_id:
                    try:
                        from opentelemetry import trace
                        active_span = trace.get_current_span()
                        if active_span and hasattr(active_span, 'get_span_context'):
                            span_context = active_span.get_span_context()
                            if span_context and span_context.trace_id:
                                trace_id = format(span_context.trace_id, '032x')
                    except Exception:
                        pass
                
                # Track token usage from LLM call (Task 1.3)
                token_usage = None
                total_tokens = 0
                try:
                    # Try to get token usage from LLM client (if supported)
                    if hasattr(self.llm_client, 'get_token_usage'):
                        token_usage = self.llm_client.get_token_usage()
                        if token_usage:
                            total_tokens = token_usage.get('total_tokens', 0)
                            
                            # Record token usage metric via telemetry client (Task 1.3)
                            ecid = getattr(self, 'current_ecid', None)
                            labels = {
                                'agent': self.name,
                                'operation': context.lower().replace(' ', '_'),
                            }
                            if ecid:
                                labels['ecid'] = ecid
                            
                            self.record_counter('agent_tokens_used_total', total_tokens, labels)
                            logger.debug(f"{self.name} LLM call used {total_tokens} tokens ({token_usage.get('prompt_tokens', 0)} prompt + {token_usage.get('completion_tokens', 0)} completion)")
                except Exception as e:
                    logger.debug(f"{self.name} Failed to track token usage: {e}")
                
                # Log to communication log for telemetry with prompt and response (Task 1.1)
                log_entry = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'agent': self.name,
                    'message_type': 'llm_reasoning',
                    'description': f"LLM {context}: {response[:500]}...",
                    'ecid': getattr(self, 'current_ecid', None),
                    'prompt': prompt,  # Task 1.1: Capture prompt
                    'full_response': response,
                    'trace_id': trace_id  # Task 1.1: Link to telemetry trace
                }
                
                # Include token usage in communication log (Task 1.3)
                if token_usage:
                    log_entry['token_usage'] = token_usage
                
                self.communication_log.append(log_entry)
                
                return response
            except Exception as e:
                error_msg = str(e) if e else f"{type(e).__name__}: {repr(e)}"
                logger.error(f"{self.name} LLM call failed: {error_msg}")
                logger.debug(f"{self.name} LLM call exception details:", exc_info=True)
                raise
    
    async def _ollama_response(self, prompt: str, context: str, model: str) -> str:
        """
        DEPRECATED: Use llm_response() instead which uses the LLM router abstraction.
        
        This method is kept for backward compatibility but should not be used.
        It bypasses the LLM router and makes direct HTTP calls to Ollama.
        """
        logger.warning(
            f"{self.name} is using deprecated _ollama_response(). "
            "Use llm_response() instead which respects USE_LOCAL_LLM and provider abstraction."
        )
        
        # Delegate to llm_response which uses the router
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        return await self.llm_response(full_prompt, context)
    
    async def run(self):
        """Main agent loop"""
        logger.info(f"{self.name} starting up...")
        
        try:
            await self.initialize()
            
            # Start metrics HTTP server if telemetry client supports it (Task 0.12)
            self.metrics_server = None
            if self.telemetry_client and hasattr(self.telemetry_client, 'get_prometheus_reader'):
                try:
                    prometheus_reader = self.telemetry_client.get_prometheus_reader()
                    if prometheus_reader:
                        # Handle both Docker (flattened) and local (nested) import structures
                        try:
                            from agents.telemetry.metrics_server import start_metrics_server
                        except ImportError:
                            try:
                                from telemetry.metrics_server import start_metrics_server
                            except ImportError:
                                logger.warning(f"{self.name}: Metrics server module not found")
                                start_metrics_server = None
                        
                        if start_metrics_server:
                            prometheus_port = int(os.getenv('PROMETHEUS_METRICS_PORT', '8888'))
                            self.metrics_server = await start_metrics_server(
                                port=prometheus_port,
                                meter_provider=getattr(self.telemetry_client, 'meter_provider', None),
                                prometheus_reader=prometheus_reader
                            )
                            logger.info(f"{self.name} started metrics HTTP server on port {prometheus_port}")
                except Exception as e:
                    logger.warning(f"{self.name} failed to start metrics server: {e}")
            
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
        # Stop metrics server if running
        if hasattr(self, 'metrics_server') and self.metrics_server:
            try:
                await self.metrics_server.stop()
                logger.info(f"{self.name} stopped metrics HTTP server")
            except Exception as e:
                logger.warning(f"{self.name} error stopping metrics server: {e}")
        
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
