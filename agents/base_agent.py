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
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles

if TYPE_CHECKING:
    from agents.specs.agent_request import AgentRequest
    from agents.specs.agent_response import AgentResponse
from dataclasses import asdict, dataclass

import aio_pika
import aiohttp
import asyncpg
import redis.asyncio as redis

from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse

# Telemetry abstraction - no direct OpenTelemetry imports needed
# TelemetryClient handles all telemetry backends (OpenTelemetry, AWS, Azure, GCP, Null)

# Import version management
sys.path.append('/app')
try:
    from config.version import get_agent_config, get_agent_version
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
    payload: dict[str, Any]
    context: dict[str, Any]
    timestamp: str
    message_id: str

@dataclass
class TaskStatus:
    """Task status tracking"""
    task_id: str
    agent_name: str
    status: str  # Available, Active-Non-Blocking, Active-Blocking, Blocked, Completed
    progress: float
    eta: str | None
    dependencies: list[str]
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
        self.agent_info = None  # Store agent_info.json data for metadata in heartbeats
        
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
        
        # Initialize capability system (SIP-046) - must be before LLM client to get model config
        self._load_capability_config()
        
        # Initialize LLM client (uses model from capability_config if available)
        self.llm_client = self._initialize_llm_client()
        
        # Initialize communication log for telemetry
        self.communication_log = []
        
        # Initialize telemetry client (abstraction layer)
        self.telemetry_client = self._initialize_telemetry_client()
    
    def _initialize_llm_client(self):
        """Initialize LLM client from router, using model from config.yaml if available"""
        from agents.llm.router import LLMRouter
        
        # Try to get model from agent's config.yaml defaults.model
        model_from_config = None
        if self.capability_config and self.capability_config.defaults:
            model_config = self.capability_config.defaults.get('model', '')
            if model_config:
                # Parse format: "ollama:model-name" -> "model-name"
                if ':' in model_config:
                    parts = model_config.split(':', 1)
                    if len(parts) == 2:
                        provider, model = parts
                        if provider.lower() == 'ollama':
                            model_from_config = model
                else:
                    # Direct model name
                    model_from_config = model_config
        
        # Initialize router
        router = LLMRouter.from_config('config/llm_config.yaml')
        
        # If we have a model from config.yaml, use it
        if model_from_config:
            # Create new client with model from config.yaml
            from agents.llm.providers.ollama import OllamaClient
            provider_config = router.config['providers'].get('ollama', {})
            return OllamaClient(
                url=provider_config.get('url'),
                model=model_from_config,
                timeout=provider_config.get('timeout', 180)
            )
        
        # No model configured - fail with informative error
        role = getattr(self, 'agent_type', 'unknown')
        raise ValueError(
            f"❌ LLM model not configured for agent '{self.name}' (role: {role})!\n\n"
            f"💡 To fix:\n"
            f"  1. Configure model in {role}/config.yaml:\n"
            f"     defaults:\n"
            f"       model: ollama:<model-name>\n"
            f"  2. Example: defaults.model: ollama:llama3.1:8b\n"
            f"  3. Ensure the model is available in Ollama: ollama list\n"
            f"  4. If model doesn't exist, pull it: ollama pull <model-name>\n\n"
            f"📖 See agents/roles/{role}/config.yaml for examples"
        )
    
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
    
    def create_span(self, span_name: str, attributes: dict[str, Any] = None, kind: str | None = None):
        """Create a telemetry span context manager via TelemetryClient"""
        if not self.telemetry_client:
            from contextlib import nullcontext
            return nullcontext()
        
        return self.telemetry_client.create_span(span_name, attributes, kind)
    
    def record_counter(self, metric_name: str, value: float = 1.0, labels: dict[str, str] = None):
        """Record a counter metric via TelemetryClient"""
        if not self.telemetry_client:
            return
        
        try:
            self.telemetry_client.record_counter(metric_name, int(value), labels)
        except Exception as e:
            logger.debug(f"{self.name}: Failed to record counter {metric_name}: {e}")
    
    def record_gauge(self, metric_name: str, value: float, labels: dict[str, str] = None):
        """Record a gauge metric via TelemetryClient"""
        if not self.telemetry_client:
            return
        
        try:
            self.telemetry_client.record_gauge(metric_name, value, labels)
        except Exception as e:
            logger.debug(f"{self.name}: Failed to record gauge {metric_name}: {e}")
    
    def record_histogram(self, metric_name: str, value: float, labels: dict[str, str] = None):
        """Record a histogram metric via TelemetryClient"""
        if not self.telemetry_client:
            return
        
        try:
            self.telemetry_client.record_histogram(metric_name, value, labels)
        except Exception as e:
            logger.debug(f"{self.name}: Failed to record histogram {metric_name}: {e}")
        
    def _load_agent_info(self) -> dict[str, Any] | None:
        """
        Load agent_info.json from package.
        
        Tries Docker path (/app/agent_info.json) first, then local path (./agent_info.json).
        
        Returns:
            Agent info dictionary or None if file doesn't exist
        """
        # Try Docker path first
        docker_path = Path("/app/agent_info.json")
        if docker_path.exists():
            try:
                with open(docker_path) as f:
                    agent_info = json.load(f)
                    logger.debug(f"{self.name}: Loaded agent_info.json from {docker_path}")
                    return agent_info
            except Exception as e:
                logger.warning(f"{self.name}: Failed to load agent_info.json from {docker_path}: {e}")
        
        # Try local path
        local_path = Path("./agent_info.json")
        if local_path.exists():
            try:
                with open(local_path) as f:
                    agent_info = json.load(f)
                    logger.debug(f"{self.name}: Loaded agent_info.json from {local_path}")
                    return agent_info
            except Exception as e:
                logger.warning(f"{self.name}: Failed to load agent_info.json from {local_path}: {e}")
        
        # File not found - backward compatibility
        logger.warning(f"{self.name}: agent_info.json not found, continuing without metadata (backward compatibility)")
        return None
    
    def _detect_runtime_env(self) -> dict[str, Any]:
        """
        Detect runtime environment information.
        
        Returns:
            Dictionary with python_version, prefect_version, cuda_enabled
        """
        runtime_env = {
            "python_version": sys.version.split()[0]
        }
        
        # Try to detect Prefect version
        try:
            import prefect
            runtime_env["prefect_version"] = prefect.__version__
        except ImportError:
            runtime_env["prefect_version"] = None
        
        # Try to detect CUDA availability
        cuda_enabled = False
        try:
            import torch
            cuda_enabled = torch.cuda.is_available()
        except ImportError:
            # Try checking for CUDA libraries directly
            try:
                import ctypes.util
                cuda_lib = ctypes.util.find_library("cuda")
                if cuda_lib:
                    cuda_enabled = True
            except Exception:
                pass
        
        runtime_env["cuda_enabled"] = cuda_enabled
        
        return runtime_env
    
    def _get_container_hash(self) -> str | None:
        """
        Get container identifier/hash.
        
        Tries HOSTNAME env var (set by Docker), then /etc/hostname.
        
        Returns:
            Container identifier or None if not in container
        """
        # Try HOSTNAME (set by Docker)
        hostname = os.getenv('HOSTNAME')
        if hostname:
            return hostname
        
        # Try reading /etc/hostname
        try:
            hostname_path = Path("/etc/hostname")
            if hostname_path.exists():
                with open(hostname_path) as f:
                    hostname = f.read().strip()
                    if hostname:
                        return hostname
        except Exception:
            pass
        
        # Not in container or can't determine
        return None
    
    def _fill_agent_info(self, agent_info: dict[str, Any]) -> dict[str, Any]:
        """
        Fill runtime fields in agent_info.json.
        
        Args:
            agent_info: Agent info dictionary template
            
        Returns:
            Updated agent info dictionary with runtime fields filled
        """
        # Fill agent_id from self.name if not set
        if not agent_info.get('agent_id'):
            agent_info['agent_id'] = self.name
        
        # Fill runtime environment
        agent_info['runtime_env'] = self._detect_runtime_env()
        
        # Fill startup time
        agent_info['startup_time_utc'] = datetime.utcnow().isoformat() + "Z"
        
        # Fill container hash
        agent_info['container_hash'] = self._get_container_hash()
        
        return agent_info
    
    async def _announce_agent_online(self, agent_info: dict[str, Any]):
        """
        Broadcast agent_online message to squad.
        
        Args:
            agent_info: Complete agent info dictionary
        """
        try:
            payload = {
                "agent_id": agent_info.get('agent_id', self.name),
                "role": agent_info.get('role', 'unknown'),
                "build_hash": agent_info.get('build_hash'),
                "container_hash": agent_info.get('container_hash'),
                "capabilities": agent_info.get('capabilities', []),
                "startup_time_utc": agent_info.get('startup_time_utc')
            }
            
            await self.broadcast_message(
                message_type="agent_online",
                payload=payload,
                context={"source": "agent_startup"}
            )
            
            logger.info(f"{self.name}: Announced agent_online with build_hash={agent_info.get('build_hash')}")
        except Exception as e:
            logger.warning(f"{self.name}: Failed to announce agent_online: {e}")
    
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
            
            # Store role context in memory
            await self._store_role_context()
            
            # Load and process agent_info.json (if available)
            agent_info = self._load_agent_info()
            if agent_info:
                # Fill runtime fields
                agent_info = self._fill_agent_info(agent_info)
                
                # Store agent_info for use in heartbeats
                self.agent_info = agent_info
                
                # Structured logging for agent identity (Recommended enhancement)
                logger.info(
                    "agent_runtime_identity",
                    extra={"agent_info": agent_info}
                )
                
                # Also log formatted version for readability
                logger.info(f"{self.name}: Agent info loaded: {json.dumps(agent_info, indent=2)}")
                
                # Announce agent online
                await self._announce_agent_online(agent_info)
            
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
    
    async def _store_role_context(self):
        """Load role definition from registry and store in memory"""
        try:
            from agents.factory.role_factory import RoleFactory
            from agents.utils.path_resolver import PathResolver
            
            # Get role name from capability_config
            role_name = None
            if self.capability_config:
                role_name = getattr(self.capability_config, 'role', None)
            
            # Fallback: map agent_type to role name (reuse existing mapping)
            if not role_name:
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
                    "auditor": "audit"
                }
                role_name = role_map.get(self.agent_type, self.agent_type)
            
            # Resolve registry file path using PathResolver
            base_path = PathResolver.get_base_path()
            registry_path = str(base_path / "agents" / "roles" / "registry.yaml")
            
            # Load role definition
            role_factory = RoleFactory(registry_file=registry_path)
            role_definition = role_factory.get_role(role_name)
            
            # Create formatted context string
            if role_definition:
                capabilities_str = "\n".join(f"- {cap}" for cap in role_definition.capabilities[:5])
                reasoning_explanation = self._get_reasoning_explanation(role_definition.reasoning_style)
                
                role_context = f"""You are {self.name}, the {role_definition.display_name} agent in SquadOps.

Your role: {role_definition.description}

Key responsibilities:
{capabilities_str}

Your reasoning style is {role_definition.reasoning_style}. {reasoning_explanation}

"""
            else:
                # Fallback to simple context
                role_context = f"You are {self.name}, a {self.agent_type} agent in the SquadOps system.\n\n"
            
            # Store in memory provider
            if self.memory_provider:
                try:
                    await self.record_memory(
                        kind="role_identity",
                        payload={
                            "role_name": role_name,
                            "display_name": role_definition.display_name if role_definition else self.agent_type,
                            "description": role_definition.description if role_definition else f"{self.agent_type} agent",
                            "reasoning_style": role_definition.reasoning_style if role_definition else self.reasoning_style,
                            "capabilities": role_definition.capabilities if role_definition else [],
                            "role_context": role_context
                        },
                        importance=1.0,  # Highest importance - core identity
                        ns="role",
                        task_context=None
                    )
                    logger.info(f"{self.name}: Stored role context in memory for {role_name}")
                except Exception as e:
                    logger.warning(f"{self.name}: Failed to store role context in memory: {e}")
            else:
                logger.warning(f"{self.name}: Memory provider not available, skipping role context storage")
                
        except Exception as e:
            logger.warning(f"{self.name}: Failed to initialize role context: {e}")
    
    def _get_reasoning_explanation(self, reasoning_style: str) -> str:
        """Get human-readable explanation of reasoning style"""
        explanations = {
            "counterfactual": "This means you think by exploring alternative scenarios and 'what if' questions, which helps you identify potential issues and edge cases.",
            "deductive": "This means you reason from general principles to specific conclusions, which helps you build systematic solutions.",
            "abductive": "This means you form the best explanation from available evidence, which helps you make strategic decisions.",
            "inductive": "This means you reason from specific observations to general patterns, which helps you identify trends.",
            "governance": "This means you focus on coordination, decision-making, and ensuring proper workflows.",
            "pattern_detection": "This means you identify patterns and relationships in data, which helps you discover insights."
        }
        return explanations.get(reasoning_style, "This shapes how you approach problems and make decisions.")
    
    def _extract_memory_context(self, task: dict[str, Any]) -> dict[str, str]:
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
                           task_context: dict[str, Any] | None = None) -> str | None:
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
                # For role_identity, use put_if_not_exists to prevent duplicates
                if kind == "role_identity" and ns == "role" and adapter == self.memory_provider:
                    # Use singleton storage for role identity
                    mem_id = await adapter.put_if_not_exists(memory_item)
                    if mem_id:
                        logger.info(f"{self.name}: Stored {kind} memory {mem_id}")
                    else:
                        logger.debug(f"{self.name}: {kind} memory already exists, skipped storage")
                else:
                    # Regular storage for other memory types
                    mem_id = await adapter.put(memory_item)
                
                latency_ms = (time.time() - start_time) * 1000
                
                # Record latency histogram
                self.record_histogram('memory_operation_latency_ms', latency_ms, {
                    'operation': 'put_if_not_exists' if (kind == "role_identity" and ns == "role" and adapter == self.memory_provider) else 'put',
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
    
    async def retrieve_memories(self, query: str = "", k: int = 8, ns: str = "role", **kwargs) -> list[dict]:
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
    
    async def send_message(self, recipient: str, message_type: str, payload: dict[str, Any], context: dict[str, Any] = None):
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
    
    async def broadcast_message(self, message_type: str, payload: dict[str, Any], context: dict[str, Any] = None):
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
    
    async def log_activity(self, activity: str, details: dict[str, Any] = None):
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
                             priority: str = "MEDIUM", dependencies: list[str] = None,
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

    async def log_task_completion(self, task_id: str, artifacts: dict[str, Any] = None):
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
            
            # Send only operational data - health-check will use instances.yaml for display metadata
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
            from agents.utils.path_resolver import PathResolver
            
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
            
            # Load capability config using unified path resolver
            base_path = PathResolver.get_base_path()
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
    
    def _validate_constraints(self, request: 'AgentRequest') -> tuple[bool, str | None]:
        """Validate request against agent constraints"""
        if not self.capability_config:
            return True, None  # No constraints if config not loaded
        
        constraints = self.capability_config.constraints
        
        # Validate repo_allow
        if 'repo_allow' in constraints:
            repo_allow = constraints['repo_allow']
            payload_repo = request.payload.get('repo', request.payload.get('project', ''))
            # Only validate if a repository is actually specified
            if payload_repo and repo_allow and not any(repo_allow_pattern in payload_repo for repo_allow_pattern in repo_allow):
                return False, f"Repository not allowed: {payload_repo}"
        
        # Validate max_runtime_s (will be checked during execution)
        # Validate network_allow (will be checked during execution)
        
        return True, None
    
    @abstractmethod
    async def handle_agent_request(self, request: 'AgentRequest') -> 'AgentResponse':
        """Handle agent request - must be implemented by each agent"""
        pass
    
    async def process_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """Process a task - DEPRECATED: Use handle_agent_request instead"""
        # Convert old task format to AgentRequest for compatibility
        try:
            from agents.specs.agent_request import AgentRequest
            
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
    
    async def handle_task_acknowledgment(self, message: AgentMessage) -> None:
        """Handle task acknowledgment from delegated agents"""
        payload = message.payload
        task_id = payload.get('task_id', 'unknown')
        understanding = payload.get('understanding', '')
        
        logger.info(f"{self.name} received task acknowledgment: {task_id} from {message.sender}")
        logger.info(f"Agent understanding: {understanding[:200]}...")
        
        # Log the successful communication
        self.communication_log.append({
            'task_id': task_id,
            'from_agent': message.sender,
            'to_agent': self.name,
            'message_type': 'task_acknowledgment',
            'timestamp': message.timestamp,
            'status': 'success',
            'understanding': understanding
        })

    async def handle_task_error(self, message: AgentMessage) -> None:
        """Handle task error from delegated agents"""
        payload = message.payload
        task_id = payload.get('task_id', 'unknown')
        error = payload.get('error', 'Unknown error')
        
        logger.error(f"{self.name} received task error: {task_id} from {message.sender}: {error}")
        
        # Log the error
        self.communication_log.append({
            'task_id': task_id,
            'from_agent': message.sender,
            'to_agent': self.name,
            'message_type': 'task_error',
            'timestamp': message.timestamp,
            'status': 'error',
            'error': error
        })
    
    async def handle_reasoning_event(self, message: AgentMessage) -> None:
        """
        Handle reasoning event from other agents (DevAgent, etc.)
        Stores reasoning events in communication log for wrap-up generation
        """
        try:
            payload = message.payload
            context = message.context
            sender = message.sender
            
            # Extract reasoning event data
            reasoning_data = {
                'timestamp': message.timestamp,
                'sender': sender,
                'agent': context.get('sender_agent', sender),
                'message_type': 'agent_reasoning',
                'ecid': payload.get('ecid', context.get('ecid', 'unknown')),
                'task_id': payload.get('task_id', 'unknown'),
                'reason_step': payload.get('reason_step', 'unknown'),
                'summary': payload.get('summary', ''),
                'context': payload.get('context', 'unknown'),
                'key_points': payload.get('key_points', []),
                'confidence': payload.get('confidence'),
                'schema': payload.get('schema', 'reasoning.v1'),
                'raw_reasoning_included': payload.get('raw_reasoning_included', False)
            }
            
            # Store in communication log for wrap-up extraction
            self.communication_log.append(reasoning_data)
            
            logger.info(f"{self.name} received reasoning event from {sender}: {payload.get('reason_step', 'unknown')} for {payload.get('context', 'unknown')} (ECID: {payload.get('ecid', 'unknown')})")
            
        except Exception as e:
            logger.warning(f"{self.name} failed to handle reasoning event: {e}")
    
    async def handle_status_query(self, message: AgentMessage) -> None:
        """Handle status queries"""
        await self.send_message(
            message.sender,
            "status_response",
            {
                'agent': self.name,
                'status': self.status,
                'current_task': self.current_task,
                'task_state_log_count': len(getattr(self, 'task_state_log', [])),
                'approval_queue_count': len(getattr(self, 'approval_queue', []))
            }
        )
    
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
                    task_id = None
                    try:
                        logger.debug(f"{self.name} received message: {message.body.decode()}")
                        task_data = json.loads(message.body.decode())
                        logger.debug(f"{self.name} parsed task_data: {task_data}")
                        
                        # Set busy status before processing
                        task_id = task_data.get('task_id', 'unknown')
                        self.status = "Active-Non-Blocking"
                        self.current_task = task_id
                        logger.debug(f"{self.name} set status to Active-Non-Blocking for task {task_id}")
                        
                        logger.debug(f"{self.name} about to call process_task")
                        result = await self.process_task(task_data)
                        logger.debug(f"{self.name} process_task completed: {result}")
                        
                        # Update task status
                        logger.debug(f"{self.name} about to call update_task_status")
                        await self.update_task_status(
                            task_id,
                            'Completed',
                            progress=100.0
                        )
                        logger.debug(f"{self.name} update_task_status completed")
                        
                        # Clear busy status after successful completion
                        self.status = "Available"
                        self.current_task = None
                        logger.debug(f"{self.name} cleared busy status after task completion")
                        
                        await message.ack()
                        logger.info(f"{self.name} completed task: {task_id}")
                        
                    except Exception as e:
                        logger.error(f"{self.name} task processing error: {e}")
                        # Clear busy status on error
                        self.status = "Available"
                        self.current_task = None
                        logger.debug(f"{self.name} cleared busy status after task error")
                        await message.nack(requeue=False)
            
            async def process_comms():
                async for message in comms_queue:
                    try:
                        msg_data = json.loads(message.body.decode())
                        
                        # Check if this is an AgentRequest (capability invocation) or AgentMessage (inter-agent comms)
                        if 'action' in msg_data:
                            # AgentRequest format - route to capability system
                            request = AgentRequest.from_dict(msg_data)
                            response = await self.handle_agent_request(request)
                            
                            # Generic response routing - check for response_queue in metadata
                            response_queue = msg_data.get('metadata', {}).get('response_queue')
                            if response_queue:
                                correlation_id = msg_data.get('metadata', {}).get('correlation_id')
                                action = msg_data.get('action', 'unknown')
                                
                                # Prepare response message
                                if hasattr(response, 'to_dict'):
                                    response_payload = response.to_dict()
                                elif isinstance(response, dict):
                                    response_payload = {"result": response}
                                else:
                                    response_payload = {"result": response}
                                
                                response_message = {
                                    "action": f"{action}.response",
                                    "payload": response_payload,
                                    "metadata": {
                                        "correlation_id": correlation_id,
                                        "original_action": action,
                                        "agent_name": self.name
                                    }
                                }
                                
                                await self.channel.default_exchange.publish(
                                    aio_pika.Message(
                                        body=json.dumps(response_message).encode(),
                                        correlation_id=correlation_id
                                    ),
                                    routing_key=response_queue
                                )
                                logger.info(f"{self.name} sent response to {response_queue} for {action}")
                        else:
                            # AgentMessage format - route to message handlers
                            agent_msg = AgentMessage(**msg_data)
                            await self.handle_message(agent_msg)
                        
                        await message.ack()
                        
                    except Exception as e:
                        logger.error(f"{self.name} comms processing error: {e}", exc_info=True)
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
            
            async with aiofiles.open(file_path, encoding='utf-8') as f:
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
    
    async def modify_file(self, file_path: str, modifications: list[dict[str, Any]]) -> bool:
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
    
    async def execute_command(self, command: str, cwd: str = None) -> dict[str, Any]:
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
    
    async def list_files(self, directory: str, pattern: str = None) -> list[str]:
        """List files in directory"""
        try:
            if not os.path.isabs(directory):
                directory = os.path.join('/app', directory)
            
            files = []
            for root, _dirs, filenames in os.walk(directory):
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
