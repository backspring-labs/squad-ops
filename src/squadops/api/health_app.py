import asyncio
import json
import logging
import os
import random
import string
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import aio_pika
import aiohttp
import asyncpg
import pika
import redis.asyncio as redis
import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request as StarletteRequest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Reduce verbosity of pika (RabbitMQ client) logging - silence all pika loggers
pika_loggers = [
    "pika",
    "pika.connection",
    "pika.channel",
    "pika.adapters",
    "pika.adapters.utils",
    "pika.adapters.utils.connection_workflow",
    "pika.adapters.utils.io_services_utils",
    "pika.adapters.blocking_connection",
    "pika.select_connection",
]
for logger_name in pika_loggers:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

from squadops import __version__ as SQUADOPS_VERSION
from squadops.config import load_config, get_config, redact_config, config_fingerprint


# Agent version lookup (simplified - can be enhanced later)
def get_agent_version(agent_name: str) -> str:
    """Get version for a specific agent."""
    return SQUADOPS_VERSION  # All agents use framework version for now


app = FastAPI(title="SquadOps Health Check Service", version=SQUADOPS_VERSION)

# Import modular routes (after app creation to avoid circular imports)
from squadops.api.routes import health as health_routes
from squadops.api.routes import agents as agents_routes
from squadops.api.routes import console as console_routes
from squadops.api.routes import warmboot as warmboot_routes

# Include routers (routes will be initialized at startup)
app.include_router(health_routes.router)
app.include_router(agents_routes.router)
app.include_router(console_routes.router)
app.include_router(warmboot_routes.router)

# Initialize Jinja2 templates
# In Docker: templates are at /app/templates
# Locally: use path relative to this module
_module_dir = Path(__file__).parent
template_dir = _module_dir / "templates"
if not template_dir.exists():
    # Fallback for Docker
    template_dir = Path("templates")
templates = Jinja2Templates(directory=str(template_dir))


# Pydantic models for WarmBoot requests
class WarmBootRequest(BaseModel):
    run_id: str
    application: str
    request_type: str
    agents: list[str]
    priority: str
    description: str
    requirements: str | None = None
    prd_path: str | None = None
    requirements_text: str | None = None


# Pydantic models for Agent Status
# SIP-Agent-Lifecycle: agent_id is the identifier, lifecycle_state is from agent FSM
class AgentStatusCreate(BaseModel):
    agent_id: str  # Renamed from agent_name for consistency with task system
    lifecycle_state: str  # Required - agent FSM state (STARTING, READY, WORKING, etc.)
    current_task_id: str | None = None
    version: str | None = None
    tps: int = 0
    memory_count: int | None = None
    # Deprecated fields (ignored if present)
    agent_name: str | None = None  # Backward compatibility - ignored
    status: str | None = None  # Backward compatibility - ignored
    network_status: str | None = None  # Prohibited - ignored


class AgentStatusUpdate(BaseModel):
    lifecycle_state: str | None = None
    current_task_id: str | None = None
    version: str | None = None
    tps: int | None = None
    memory_count: int | None = None


# Agent Gateway: Console Session Management
@dataclass
class ConsoleSession:
    """Console session for Agent Gateway"""

    session_id: str
    mode: str  # "idle" | "chat"
    bound_agent: str | None = None
    cycle_id: str | None = None  # SIP-0048: renamed from ecid
    created_at: datetime = field(default_factory=datetime.utcnow)
    pending_responses: list[dict[str, Any]] = field(default_factory=list)


# Agent Gateway: In-memory session store
console_sessions: dict[str, ConsoleSession] = {}


def create_console_session() -> str:
    """Create a new console session and return session_id"""
    session_id = str(uuid.uuid4())
    console_sessions[session_id] = ConsoleSession(session_id=session_id, mode="idle")
    logger.info(f"Agent Gateway: Created new console session: {session_id}")
    return session_id


def get_console_session(session_id: str) -> ConsoleSession | None:
    """Get console session by session_id"""
    return console_sessions.get(session_id)


def update_console_session(session_id: str, **kwargs) -> None:
    """Update console session fields"""
    session = console_sessions.get(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    for key, value in kwargs.items():
        if hasattr(session, key):
            setattr(session, key, value)

    logger.debug(f"Agent Gateway: Updated session {session_id}: {kwargs}")


def generate_console_cycle_id() -> str:
    """Generate cycle_id for console chat session"""
    timestamp = int(datetime.utcnow().timestamp())
    random_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"CYCLE-CONSOLE-{timestamp}-{random_suffix}"


# Configuration - Use centralized config system (SIP-051)
strict_mode = os.getenv("SQUADOPS_STRICT_CONFIG", "false").lower() == "true"
config = load_config(strict=strict_mode)
RABBITMQ_URL = config.comms.rabbitmq.url
POSTGRES_URL = config.db.url
REDIS_URL = config.comms.redis.url
# PREFECT_URL uses AppConfig (SIP-051)
PREFECT_URL = config.prefect.api_url

# Log configuration at startup (SIP-051 requirement)
config_dict = config.model_dump()
redacted_config = redact_config(config_dict)
fingerprint = config_fingerprint(redacted_config)
logger.info(f"Configuration profile: {config._profile} (strict={strict_mode})")
logger.info(f"Configuration fingerprint: {fingerprint}")


# Agent Gateway: Command Parser
def parse_command(command: str) -> dict[str, Any]:
    """Parse command line into command name and arguments"""
    command = command.strip()
    if not command:
        return {"command": "", "args": []}

    # Handle quoted strings
    parts = []
    current = ""
    in_quotes = False
    quote_char = None

    for char in command:
        if char in ['"', "'"] and not in_quotes:
            in_quotes = True
            quote_char = char
        elif char == quote_char and in_quotes:
            in_quotes = False
            quote_char = None
        elif char == " " and not in_quotes:
            if current:
                parts.append(current)
                current = ""
        else:
            current += char

    if current:
        parts.append(current)

    if not parts:
        return {"command": "", "args": []}

    return {"command": parts[0].lower(), "args": parts[1:] if len(parts) > 1 else []}


# Agent Gateway: Command Handler
class CommandHandler:
    """Handler for console commands"""

    def __init__(self, health_checker: "HealthChecker"):
        self.health_checker = health_checker

    async def handle_help(self) -> list[str]:
        """Return list of available commands"""
        return [
            "Available commands:",
            "  help                    - Show this help message",
            "  agent list              - List all agents",
            "  agent status            - Show agent status",
            "  agent info <name>       - Show agent details",
            "  agent logs <name> <N>   - Show last N log entries for agent",
            "  chat <name>             - Start chat with agent",
            "  chat end                - End current chat",
            "  whoami                  - Show current session info",
            "  clear                   - Clear console output (client-side)",
        ]

    async def handle_agent_list(self) -> list[str]:
        """Return formatted list of all agents"""
        try:
            agents = await self.health_checker.get_agent_status()
            lines = ["Agents:"]
            for agent in agents:
                network_status = agent.get("network_status", "offline")
                lifecycle_state = agent.get("lifecycle_state", "UNKNOWN")
                agent_name = agent.get("agent_name", agent.get("agent", "unknown"))
                status_icon = "✅" if network_status == "online" else "❌"
                lines.append(
                    f"  {status_icon} {agent_name} ({agent.get('role', 'unknown')}) - Network: {network_status}, Lifecycle: {lifecycle_state}"
                )
            return lines
        except Exception as e:
            logger.error(f"Agent Gateway: Failed to get agent list: {e}")
            return [f"Error: Failed to get agent list: {str(e)}"]

    async def handle_agent_status(self) -> list[str]:
        """Return detailed agent status"""
        try:
            agents = await self.health_checker.get_agent_status()
            lines = ["Agent Status:"]
            for agent in agents:
                network_status = agent.get("network_status", "offline")
                lifecycle_state = agent.get("lifecycle_state", "UNKNOWN")
                agent_name = agent.get("agent_name", agent.get("agent", "unknown"))
                status_icon = "✅" if network_status == "online" else "❌"
                lines.append(f"  {status_icon} {agent_name} ({agent.get('role', 'unknown')})")
                lines.append(f"    Network Status: {network_status}")
                lines.append(f"    Lifecycle State: {lifecycle_state}")
                lines.append(f"    Version: {agent.get('version', 'unknown')}")
                lines.append(f"    TPS: {agent.get('tps', 0)}")
                lines.append(f"    Memories: {agent.get('memory_count', 0)}")
                lines.append("")
            return lines
        except Exception as e:
            logger.error(f"Agent Gateway: Failed to get agent status: {e}")
            return [f"Error: Failed to get agent status: {str(e)}"]

    async def handle_agent_info(self, name: str) -> list[str]:
        """Return agent details from instances.yaml"""
        try:
            instances = self.health_checker._load_instances()
            agent_id = name.lower()

            if agent_id not in instances:
                return [f"Error: Agent '{name}' not found"]

            instance_info = instances[agent_id]
            lines = [f"Agent Info: {instance_info['display_name']}"]
            lines.append(f"  ID: {agent_id}")
            lines.append(f"  Role: {instance_info['role']}")
            lines.append(f"  Description: {instance_info.get('description', 'N/A')}")

            # Try to get status from database
            try:
                agent_status = await self.health_checker.get_agent_status()
                for agent in agent_status:
                    if agent.get("agent_id", "").lower() == agent_id or agent.get("agent_name", "").lower() == agent_id:
                        lines.append(f"  Network Status: {agent.get('network_status', 'unknown')}")
                        lines.append(f"  Lifecycle State: {agent.get('lifecycle_state', 'UNKNOWN')}")
                        lines.append(f"  Version: {agent.get('version', 'unknown')}")
                        break
            except Exception:
                pass

            return lines
        except Exception as e:
            logger.error(f"Agent Gateway: Failed to get agent info: {e}")
            return [f"Error: Failed to get agent info: {str(e)}"]

    async def handle_agent_logs(self, name: str, n: int = 10) -> list[str]:
        """Return last N log entries for agent (placeholder for MVP)"""
        # Placeholder - would need to access agent logs
        return [
            f"Agent logs for {name} (last {n} entries):",
            "  [Log access not yet implemented - MVP placeholder]",
            "  Future: Query agent container logs or centralized log service",
        ]

    async def handle_chat_start(self, session_id: str, agent_name: str) -> dict[str, Any]:
        """Start chat session with agent"""
        try:
            # Check if agent exists and is online
            agents = await self.health_checker.get_agent_status()
            agent_found = False
            agent_online = False

            for agent in agents:
                agent_id = agent.get("agent_id", "").lower()
                agent_name_display = agent.get("agent_name", "").lower()
                if agent_id == agent_name.lower() or agent_name_display == agent_name.lower():
                    agent_found = True
                    agent_online = agent.get("network_status", "offline") == "online"
                    break

            if not agent_found:
                return {
                    "lines": [f"Error: Agent '{agent_name}' not found"],
                    "mode": "idle",
                    "bound_agent": None,
                    "cycle_id": None,
                }

            if not agent_online:
                return {
                    "lines": [f"Error: Agent '{agent_name}' is offline"],
                    "mode": "idle",
                    "bound_agent": None,
                    "cycle_id": None,
                }

            # Create cycle_id and update session
            cycle_id = generate_console_cycle_id()
            update_console_session(
                session_id, mode="chat", bound_agent=agent_name.lower(), cycle_id=cycle_id
            )

            logger.info(
                f"Agent Gateway: Chat started: {agent_name} (session: {session_id}, cycle_id: {cycle_id})"
            )

            return {
                "lines": [f"Chat started with {agent_name}. Type 'chat end' to exit."],
                "mode": "chat",
                "bound_agent": agent_name.lower(),
                "cycle_id": cycle_id,
            }
        except Exception as e:
            logger.error(f"Agent Gateway: Failed to start chat: {e}")
            return {
                "lines": [f"Error: Failed to start chat: {str(e)}"],
                "mode": "idle",
                "bound_agent": None,
                "cycle_id": None,
            }

    async def handle_chat_end(self, session_id: str) -> dict[str, Any]:
        """End chat session"""
        try:
            session = get_console_session(session_id)
            if session and session.mode == "chat":
                agent_name = session.bound_agent
                update_console_session(session_id, mode="idle", bound_agent=None, cycle_id=None)
                logger.info(f"Agent Gateway: Chat ended: {agent_name} (session: {session_id})")
                return {
                    "lines": [f"Chat ended with {agent_name}."],
                    "mode": "idle",
                    "bound_agent": None,
                    "cycle_id": None,
                }
            else:
                return {
                    "lines": ["Not in chat mode."],
                    "mode": "idle",
                    "bound_agent": None,
                    "cycle_id": None,
                }
        except Exception as e:
            logger.error(f"Agent Gateway: Failed to end chat: {e}")
            return {
                "lines": [f"Error: Failed to end chat: {str(e)}"],
                "mode": "idle",
                "bound_agent": None,
                "cycle_id": None,
            }

    async def handle_whoami(self, session_id: str) -> list[str]:
        """Return session info"""
        session = get_console_session(session_id)
        if not session:
            return ["Error: Session not found"]

        lines = [
            "Session Info:",
            f"  Session ID: {session.session_id}",
            f"  Mode: {session.mode}",
            f"  Bound Agent: {session.bound_agent or 'None'}",
            f"  Cycle ID: {session.cycle_id or 'None'}",
            f"  Created: {session.created_at.isoformat()}",
        ]
        return lines

    async def handle_chat_message(self, session_id: str, message: str) -> dict[str, Any]:
        """Send chat message to agent via A2A"""
        session = get_console_session(session_id)
        if not session:
            return {
                "lines": ["Error: Session not found"],
                "mode": "idle",
                "bound_agent": None,
                "cycle_id": None,
            }

        if session.mode != "chat" or not session.bound_agent:
            return {
                "lines": ["Error: Not in chat mode. Use 'chat <agent>' to start."],
                "mode": session.mode,
                "bound_agent": session.bound_agent,
                "cycle_id": session.cycle_id,
            }

        try:
            # Build A2A message and send via RabbitMQ
            agent_name = session.bound_agent
            cycle_id = session.cycle_id

            # Build A2A message
            timestamp = int(datetime.utcnow().timestamp())
            a2a_message = {
                "action": "comms.chat",
                "payload": {"message": message, "session_id": session_id},
                "metadata": {
                    "pid": f"PID-CONSOLE-{timestamp}",
                    "cycle_id": cycle_id,
                    "tags": ["console", "chat"],
                    "response_queue": "console_responses",  # Gateway tells agent where to respond
                    "correlation_id": session_id,  # Gateway uses this to match response
                },
                "request_id": f"{cycle_id}-{timestamp}",
            }

            # Send via RabbitMQ to comms queue (not tasks queue)
            connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            channel = connection.channel()

            routing_key = f"{agent_name}_comms"  # Communication queue
            channel.basic_publish(
                exchange="",
                routing_key=routing_key,
                body=json.dumps(a2a_message),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,  # Make message persistent
                ),
            )

            connection.close()

            logger.info(f"Agent Gateway: Sent chat message to {agent_name} (session: {session_id})")

            return {
                "lines": [f"[You → {agent_name}]: {message}"],
                "mode": session.mode,
                "bound_agent": session.bound_agent,
                "cycle_id": session.cycle_id,
            }
        except Exception as e:
            logger.error(f"Agent Gateway: Failed to send chat message: {e}")
            return {
                "lines": [f"Error: Failed to send message: {str(e)}"],
                "mode": session.mode,
                "bound_agent": session.bound_agent,
                "cycle_id": session.cycle_id,
            }


class HealthChecker:
    def __init__(self):
        self.redis_client = None
        self.pg_pool = None
        self._instances_cache = None
        self._instances_cache_mtime = None  # Track file modification time for cache invalidation
        # Use AppConfig for instances_file
        app_config = get_config()
        self.instances_file = str(app_config.agent.instances_file)
        self.rabbitmq_connection = None
        self.rabbitmq_channel = None
        self.response_queue = None
        self._reconciliation_running = True  # Flag to control reconciliation loop

    def _load_instances(self) -> dict[str, dict[str, Any]]:
        """
        Load agent instances from instances.yaml.
        Returns dict mapping agent_id -> {display_name, role, description}
        Caches result for performance, but automatically reloads if file is modified.
        """
        try:
            instances_path = Path(self.instances_file)
            if not instances_path.exists():
                logger.warning(f"Instances file not found: {self.instances_file}, using defaults")
                return self._get_default_instances()

            # Check if file has been modified since cache was created
            current_mtime = instances_path.stat().st_mtime
            if self._instances_cache is not None and self._instances_cache_mtime == current_mtime:
                # Cache is still valid
                return self._instances_cache

            # File is new or has been modified - reload it
            with open(instances_path) as f:
                data = yaml.safe_load(f)

            # Build agent_id -> instance info mapping
            instances = {}
            for instance in data.get("instances", []):
                if instance.get("enabled", False):
                    agent_id = instance.get("id")
                    if agent_id:
                        instances[agent_id] = {
                            "display_name": instance.get("display_name", agent_id.title()),
                            "role": instance.get("role", "unknown"),
                            "description": instance.get("description", ""),
                        }

            # Update cache and modification time
            was_cached = self._instances_cache is not None
            self._instances_cache = instances
            self._instances_cache_mtime = current_mtime

            if was_cached:
                logger.info(
                    f"Reloaded {len(instances)} agent instances from {self.instances_file} (file modified)"
                )
            else:
                logger.info(f"Loaded {len(instances)} agent instances from {self.instances_file}")

            return instances

        except Exception as e:
            logger.error(f"Failed to load instances.yaml: {e}, using defaults")
            return self._get_default_instances()

    def _get_instances_order(self) -> list[str]:
        """
        Get ordered list of agent_ids from instances.yaml (preserves file order).
        Returns list of agent_ids in the order they appear in instances.yaml.
        """
        try:
            instances_path = Path(self.instances_file)
            if not instances_path.exists():
                return []

            with open(instances_path) as f:
                data = yaml.safe_load(f)

            # Return agent_ids in the order they appear in instances.yaml
            order = []
            for instance in data.get("instances", []):
                if instance.get("enabled", False):
                    agent_id = instance.get("id")
                    if agent_id:
                        order.append(agent_id)

            return order

        except Exception as e:
            logger.error(f"Failed to get instances order: {e}")
            return []

    def _get_default_instances(self) -> dict[str, dict[str, Any]]:
        """Fallback instances mapping if instances.yaml can't be loaded"""
        return {
            "max": {
                "display_name": "Max",
                "role": "lead",
                "description": "Task Lead - Governance and coordination",
            },
            "neo": {
                "display_name": "Neo",
                "role": "dev",
                "description": "Developer - Deductive reasoning",
            },
            "strat-agent": {
                "display_name": "StratAgent",
                "role": "strat",
                "description": "Product Strategy - Abductive reasoning",
            },
            "creative-agent": {
                "display_name": "CreativeAgent",
                "role": "creative",
                "description": "Creative Design - Visual synthesis",
            },
            "qa-agent": {
                "display_name": "QAAgent",
                "role": "qa",
                "description": "QA & Security - Counterfactual reasoning",
            },
            "data-agent": {
                "display_name": "DataAgent",
                "role": "data",
                "description": "Analytics - Inductive reasoning",
            },
            "finance-agent": {
                "display_name": "FinanceAgent",
                "role": "finance",
                "description": "Finance & Ops - Rule-based reasoning",
            },
            "comms-agent": {
                "display_name": "CommsAgent",
                "role": "comms",
                "description": "Communications - Empathetic reasoning",
            },
            "curator-agent": {
                "display_name": "CuratorAgent",
                "role": "curator",
                "description": "R&D & Curation - Pattern detection",
            },
            "audit-agent": {
                "display_name": "AuditAgent",
                "role": "audit",
                "description": "Monitoring & Audit - Continuous monitoring",
            },
        }

    async def init_connections(self):
        """Initialize database connections and RabbitMQ"""
        try:
            self.redis_client = redis.from_url(REDIS_URL)
            self.pg_pool = await asyncpg.create_pool(POSTGRES_URL)

            # Initialize async RabbitMQ connection for console response consumer
            self.rabbitmq_connection = await aio_pika.connect_robust(RABBITMQ_URL)
            self.rabbitmq_channel = await self.rabbitmq_connection.channel()

            # Declare console_responses queue
            self.response_queue = await self.rabbitmq_channel.declare_queue(
                "console_responses", durable=True
            )
            logger.info("Agent Gateway: Declared console_responses queue")

            # Start consumer task
            asyncio.create_task(self._consume_responses())

        except Exception as e:
            logger.error(f"Failed to initialize connections: {e}", exc_info=True)

    async def _consume_responses(self):
        """Consume responses from console_responses queue"""
        try:
            async for message in self.response_queue:
                try:
                    async with message.process():
                        msg_data = json.loads(message.body.decode())

                        # Extract correlation_id from message properties (should match session_id)
                        correlation_id = message.correlation_id or msg_data.get("metadata", {}).get(
                            "correlation_id"
                        )
                        if not correlation_id:
                            logger.warning(
                                "Agent Gateway: Received response without correlation_id"
                            )
                            continue

                        # Extract response data
                        action = msg_data.get("action", "")
                        payload = msg_data.get("payload", {})

                        # For comms.chat.response, extract response fields from AgentResponse structure
                        if action == "comms.chat.response":
                            # AgentResponse structure: {status: 'ok', result: {...}}
                            if payload.get("status") == "ok":
                                result = payload.get("result", {})
                                response_data = {
                                    "response_text": result.get("response_text", ""),
                                    "agent_name": result.get("agent_name", "unknown"),
                                    "timestamp": result.get("timestamp", ""),
                                    "status": result.get("status", "available"),
                                }
                            else:
                                # Error response
                                error = payload.get("error", {})
                                response_data = {
                                    "response_text": f"[Error: {error.get('message', 'Unknown error')}]",
                                    "agent_name": "unknown",
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "status": "error",
                                }
                        else:
                            # Generic response handling
                            response_data = {"action": action, "payload": payload}

                        # Get session and append response
                        session = get_console_session(correlation_id)
                        if session:
                            session.pending_responses.append(response_data)
                            logger.info(
                                f"Agent Gateway: Stored response for session {correlation_id}"
                            )
                        else:
                            logger.warning(
                                f"Agent Gateway: No session found for correlation_id {correlation_id}"
                            )

                except Exception as e:
                    logger.error(
                        f"Agent Gateway: Error processing response message: {e}", exc_info=True
                    )
        except Exception as e:
            logger.error(f"Agent Gateway: Error in response consumer: {e}", exc_info=True)

    async def check_rabbitmq(self) -> dict[str, Any]:
        """Check RabbitMQ health"""
        try:
            connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            channel = connection.channel()
            queue_info = channel.queue_declare(
                queue="health_check", durable=False, auto_delete=True
            )

            # Try to get RabbitMQ version from management API
            version = "Unknown"
            try:
                # RabbitMQ management API endpoint for version info
                import base64
                import json
                import urllib.request

                # Extract credentials from RABBITMQ_URL
                url_parts = RABBITMQ_URL.replace("amqp://", "").split("@")
                if len(url_parts) == 2:
                    creds = url_parts[0]
                    host_port = url_parts[1].split("/")[0]
                    mgmt_url = f"http://{host_port.replace(':5672', ':15672')}/api/overview"

                    # Create basic auth header
                    auth_string = base64.b64encode(creds.encode()).decode()
                    headers = {"Authorization": f"Basic {auth_string}"}

                    req = urllib.request.Request(mgmt_url, headers=headers)
                    with urllib.request.urlopen(req, timeout=5) as response:
                        data = json.loads(response.read().decode())
                        version = data.get("rabbitmq_version", "Unknown")
            except Exception:
                # Fallback: try to get version from connection properties
                try:
                    props = connection.server_properties
                    version = props.get("version", "Unknown")
                except Exception:
                    pass

            connection.close()

            return {
                "component": "RabbitMQ",
                "type": "Message Broker",
                "status": "online",
                "version": version,
                "purpose": "Handles inter-agent communication",
                "notes": f"{queue_info.method.message_count} messages in queue",
            }
        except Exception as e:
            return {
                "component": "RabbitMQ",
                "type": "Message Broker",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Handles inter-agent communication",
                "notes": f"Error: {str(e)}",
            }

    async def check_postgres(self) -> dict[str, Any]:
        """Check PostgreSQL health"""
        try:
            if not self.pg_pool:
                await self.init_connections()

            async with self.pg_pool.acquire() as conn:
                version_result = await conn.fetchval("SELECT version()")
                count = await conn.fetchval("SELECT COUNT(*) FROM agent_status")

                # Extract version number from PostgreSQL version string
                version = "Unknown"
                if version_result:
                    # PostgreSQL version string format: "PostgreSQL 15.3 on x86_64-pc-linux-gnu..."
                    import re

                    match = re.search(r"PostgreSQL (\d+\.\d+)", version_result)
                    if match:
                        version = match.group(1)

            return {
                "component": "PostgreSQL",
                "type": "Relational DB",
                "status": "online",
                "version": version,
                "purpose": "Persistent data and logs",
                "notes": f"{count} agents registered",
            }
        except Exception as e:
            return {
                "component": "PostgreSQL",
                "type": "Relational DB",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Persistent data and logs",
                "notes": f"Error: {str(e)}",
            }

    async def check_redis(self) -> dict[str, Any]:
        """Check Redis health"""
        try:
            if not self.redis_client:
                await self.init_connections()

            await self.redis_client.ping()
            info = await self.redis_client.info()

            return {
                "component": "Redis",
                "type": "Cache & Pub/Sub",
                "status": "online",
                "version": info.get("redis_version", "Unknown"),
                "purpose": "Caching, state sync, pub/sub backbone",
                "notes": f"Memory used: {info.get('used_memory_human', 'Unknown')}",
            }
        except Exception as e:
            return {
                "component": "Redis",
                "type": "Cache & Pub/Sub",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Caching, state sync, pub/sub backbone",
                "notes": f"Error: {str(e)}",
            }

    async def check_prefect(self) -> dict[str, Any]:
        """Check Prefect health"""
        try:
            async with aiohttp.ClientSession() as session:
                # First check health
                async with session.get(f"{PREFECT_URL}/health") as response:
                    if response.status == 200:
                        # Try to get version from version endpoint
                        version = "Unknown"
                        try:
                            version_url = f"{PREFECT_URL}/version"
                            async with session.get(version_url) as version_response:
                                if version_response.status == 200:
                                    version_text = await version_response.text()
                                    # Remove quotes if present
                                    version = version_text.strip('"')
                        except Exception:
                            pass

                        return {
                            "component": "Prefect Server",
                            "type": "Orchestration Engine",
                            "status": "online",
                            "version": version,
                            "purpose": "Task orchestration and state management",
                            "notes": "API responding",
                        }
                    else:
                        raise Exception(f"HTTP {response.status}")
        except Exception as e:
            return {
                "component": "Prefect Server",
                "type": "Orchestration Engine",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Task orchestration and state management",
                "notes": f"Error: {str(e)}",
            }

    async def check_prometheus(self) -> dict[str, Any]:
        """Check Prometheus health"""
        try:
            app_config = get_config()
            prometheus_url = app_config.observability.prometheus.url
            async with aiohttp.ClientSession() as session:
                # Check health endpoint
                async with session.get(
                    f"{prometheus_url}/-/healthy", timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        # Try to get version from API
                        version = "Unknown"
                        try:
                            version_url = f"{prometheus_url}/api/v1/status/buildinfo"
                            async with session.get(
                                version_url, timeout=aiohttp.ClientTimeout(total=5)
                            ) as version_response:
                                if version_response.status == 200:
                                    version_data = await version_response.json()
                                    if version_data.get("data", {}).get("version"):
                                        version = version_data["data"]["version"]
                        except Exception:
                            version = "Unknown"

                        return {
                            "component": "Prometheus",
                            "type": "Metrics Storage",
                            "status": "online",
                            "version": version,
                            "purpose": "Time-series metrics database and query engine",
                            "notes": "Health endpoint responding",
                        }
                    else:
                        raise Exception(f"HTTP {response.status}")
        except Exception as e:
            return {
                "component": "Prometheus",
                "type": "Metrics Storage",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Time-series metrics database and query engine",
                "notes": f"Error: {str(e)}",
            }

    async def check_grafana(self) -> dict[str, Any]:
        """Check Grafana health"""
        try:
            app_config = get_config()
            grafana_url = app_config.observability.grafana.url
            async with aiohttp.ClientSession() as session:
                # Check health endpoint
                async with session.get(
                    f"{grafana_url}/api/health", timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        health_data = await response.json()
                        version = health_data.get("version", "Unknown")
                        status = health_data.get("database", "unknown")

                        return {
                            "component": "Grafana",
                            "type": "Visualization Platform",
                            "status": "online" if status == "ok" else "degraded",
                            "version": version,
                            "purpose": "Metrics visualization and dashboards",
                            "notes": f"API responding, database: {status}",
                        }
                    else:
                        raise Exception(f"HTTP {response.status}")
        except Exception as e:
            return {
                "component": "Grafana",
                "type": "Visualization Platform",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Metrics visualization and dashboards",
                "notes": f"Error: {str(e)}",
            }

    async def check_otel_collector(self) -> dict[str, Any]:
        """
        Check OpenTelemetry Collector health

        Note: Unlike other services (Prometheus, Grafana, etc.) that expose version via their APIs,
        the OTel Collector health check endpoint doesn't include version metadata in its response,
        even with include_metadata: true. Version must come from deployment configuration.
        This is standard practice - version is a deployment-time concern, not runtime.
        """
        app_config = get_config()
        try:
            otel_url = app_config.observability.otel.url
            health_check_url = app_config.observability.otel.health_url

            version = "Unknown"
            status = "online"
            notes = "OTLP endpoint responding"

            async with aiohttp.ClientSession() as session:
                # Check health check endpoint for status (if configured)
                try:
                    async with session.get(
                        f"{health_check_url}/", timeout=aiohttp.ClientTimeout(total=5)
                    ) as health_response:
                        if health_response.status == 200:
                            health_data = await health_response.json()
                            if (
                                "Server available" in health_data.get("status", "")
                                or health_data.get("status") == "ready"
                            ):
                                status = "online"
                                notes = "Health check endpoint responding"
                                # Note: Health check response doesn't include version even with include_metadata: true
                                # Version must come from deployment config (env var or container metadata)
                except (TimeoutError, aiohttp.ClientError):
                    # Health check endpoint not available - will check OTLP endpoint below
                    logger.debug(f"{health_check_url} health check not available")
                except Exception as e:
                    logger.debug(f"Error checking health endpoint: {e}")

                # Get version from zPages diagnostic endpoint (/debug/servicez)
                # This is the OpenTelemetry Collector's built-in diagnostic API, similar to other services
                # This is better than Docker API because it queries the service itself directly
                zpages_url = app_config.observability.otel.zpages_url
                try:
                    async with session.get(
                        f"{zpages_url}/debug/servicez", timeout=aiohttp.ClientTimeout(total=5)
                    ) as zpages_response:
                        if zpages_response.status == 200:
                            html_content = await zpages_response.text()
                            # Parse version from HTML - zPages /debug/servicez shows version in Build Info table
                            import re

                            # Strategy: Extract Build Info section first, then find Version row
                            # HTML structure: <b>Build Info:</b><table>...<b>Version</b></td><td>|</td><td>0.138.0</td>...
                            version_match = None
                            build_info_section = re.search(
                                r"<b>Build Info:</b>.*?</table>",
                                html_content,
                                re.IGNORECASE | re.DOTALL,
                            )
                            if build_info_section:
                                build_html = build_info_section.group(0)
                                # Find Version in bold, then capture version number after separator
                                version_match = re.search(
                                    r"<b>Version</b>.*?([0-9]+\.[0-9]+\.[0-9]+)",
                                    build_html,
                                    re.IGNORECASE | re.DOTALL,
                                )
                                if version_match:
                                    parsed_version = version_match.group(1).strip()
                                    # Verify it's a valid version number (X.Y.Z format)
                                    if re.match(r"^\d+\.\d+\.\d+$", parsed_version):
                                        version = parsed_version
                                        logger.debug(
                                            f"Got OTel Collector version from zPages: {version}"
                                        )
                                    else:
                                        version_match = None
                            else:
                                # Fallback: search entire HTML for Version + version pattern
                                version_match = re.search(
                                    r"<b>Version</b>.*?([0-9]+\.[0-9]+\.[0-9]+)",
                                    html_content,
                                    re.IGNORECASE | re.DOTALL,
                                )
                                if version_match:
                                    parsed_version = version_match.group(1).strip()
                                    if re.match(r"^\d+\.\d+\.\d+$", parsed_version):
                                        version = parsed_version
                                        logger.debug(
                                            f"Got OTel Collector version from zPages (fallback): {version}"
                                        )

                            # Fall back to config version only if version parsing failed
                            if not version_match or version == "Unknown":
                                config_version = app_config.observability.otel.version
                                if config_version:
                                    version = config_version
                                else:
                                    if version == "Unknown":
                                        logger.debug("Could not parse version from zPages response")
                        else:
                            # zPages unavailable - fall back to config
                            config_version = app_config.observability.otel.version
                            if config_version:
                                version = config_version
                            else:
                                version = "Unknown"
                                logger.debug(
                                    f"zPages endpoint returned HTTP {zpages_response.status}"
                                )
                except (TimeoutError, aiohttp.ClientError) as e:
                    # zPages endpoint not available - fall back to config
                    logger.debug(f"Could not query zPages endpoint for OTel Collector version: {e}")
                    config_version = app_config.observability.otel.version
                    if config_version:
                        version = config_version
                    else:
                        version = "Unknown"

                # Verify OTLP endpoint is responding
                async with session.post(
                    f"{otel_url}/v1/metrics", json={}, timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    # Even if it returns 400/405, that means the service is responding
                    if response.status in [200, 400, 405]:
                        return {
                            "component": "OpenTelemetry Collector",
                            "type": "Telemetry Gateway",
                            "status": status,
                            "version": version,
                            "purpose": "Collect, process, and export telemetry data (OTLP)",
                            "notes": notes,
                        }
                    else:
                        raise Exception(f"HTTP {response.status}")
        except aiohttp.ClientError:
            # Try alternative check - see if container is running
            return {
                "component": "OpenTelemetry Collector",
                "type": "Telemetry Gateway",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Collect, process, and export telemetry data (OTLP)",
                "notes": "Cannot connect to OTLP endpoint - check container status",
            }
        except Exception as e:
            return {
                "component": "OpenTelemetry Collector",
                "type": "Telemetry Gateway",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Collect, process, and export telemetry data (OTLP)",
                "notes": f"Error: {str(e)}",
            }

    async def check_langfuse(self) -> dict[str, Any]:
        """Check LangFuse health"""
        try:
            app_config = get_config()
            langfuse_url = app_config.langfuse.host
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{langfuse_url}/api/public/health",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status == 200:
                        health_data = await response.json()
                        version = health_data.get("version", "Unknown")
                        api_status = health_data.get("status", "unknown")
                        return {
                            "component": "LangFuse",
                            "type": "LLM Observability",
                            "status": "online" if api_status == "OK" else "degraded",
                            "version": version,
                            "purpose": "LLM call tracking and tracing (SIP-0061)",
                            "notes": f"API responding, status: {api_status}",
                        }
                    else:
                        raise Exception(f"HTTP {response.status}")
        except Exception as e:
            return {
                "component": "LangFuse",
                "type": "LLM Observability",
                "status": "offline",
                "version": "Unknown",
                "purpose": "LLM call tracking and tracing (SIP-0061)",
                "notes": f"Error: {str(e)}",
            }

    async def check_keycloak(self) -> dict[str, Any]:
        """Check Keycloak OIDC health (SIP-0062).

        Primary: OIDC discovery endpoint.
        Fallback: /health/ready (KC_HEALTH_ENABLED=true).
        """
        try:
            app_config = get_config()
            auth_config = app_config.auth
            if not auth_config.enabled or auth_config.provider == "disabled":
                return {
                    "component": "Keycloak",
                    "type": "Identity Provider",
                    "status": "disabled",
                    "version": "N/A",
                    "purpose": "OIDC authentication (SIP-0062)",
                    "notes": "Auth disabled or provider=disabled",
                }

            if auth_config.oidc is None:
                return {
                    "component": "Keycloak",
                    "type": "Identity Provider",
                    "status": "not configured",
                    "version": "N/A",
                    "purpose": "OIDC authentication (SIP-0062)",
                    "notes": "OIDC config not set",
                }

            issuer_url = auth_config.oidc.issuer_url.rstrip("/")
            discovery_url = f"{issuer_url}/.well-known/openid-configuration"

            async with aiohttp.ClientSession() as session:
                # Primary: OIDC discovery document
                try:
                    async with session.get(
                        discovery_url,
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as response:
                        if response.status == 200:
                            discovery = await response.json()
                            return {
                                "component": "Keycloak",
                                "type": "Identity Provider",
                                "status": "online",
                                "version": "Unknown",
                                "purpose": "OIDC authentication (SIP-0062)",
                                "notes": f"Realm: {discovery.get('issuer', 'unknown')}",
                            }
                except Exception:
                    pass

                # Fallback: Keycloak health endpoint
                # Extract base URL from issuer (remove /realms/xxx)
                base_url = issuer_url.split("/realms/")[0] if "/realms/" in issuer_url else issuer_url
                try:
                    async with session.get(
                        f"{base_url}/health/ready",
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as response:
                        if response.status == 200:
                            return {
                                "component": "Keycloak",
                                "type": "Identity Provider",
                                "status": "online",
                                "version": "Unknown",
                                "purpose": "OIDC authentication (SIP-0062)",
                                "notes": "OIDC discovery failed, health endpoint OK",
                            }
                except Exception:
                    pass

                raise Exception("Both OIDC discovery and health endpoints unreachable")
        except Exception as e:
            return {
                "component": "Keycloak",
                "type": "Identity Provider",
                "status": "offline",
                "version": "Unknown",
                "purpose": "OIDC authentication (SIP-0062)",
                "notes": f"Error: {str(e)}",
            }

    def _compute_network_status(self, last_heartbeat: datetime | None) -> str:
        """Compute network_status from last_heartbeat timestamp
        
        SIP-Agent-Lifecycle: network_status is derived by Health Check from heartbeat timing.
        If last_heartbeat is within timeout window, agent is online; otherwise offline.
        """
        if last_heartbeat is None:
            return "offline"

        # Heartbeat timeout window: 2-3x heartbeat interval (default: 90 seconds for 30s heartbeat)
        app_config = get_config()
        heartbeat_timeout_window = app_config.agent.heartbeat_timeout_window
        
        now = datetime.utcnow()
        time_since_heartbeat = (now - last_heartbeat).total_seconds()
        
        if time_since_heartbeat <= heartbeat_timeout_window:
            return "online"
        else:
            return "offline"

    async def get_agent_status(self) -> list[dict[str, Any]]:
        """Get agent status from database
        
        SIP-Agent-Lifecycle: Returns agent_id, agent_name (display), network_status (derived),
        lifecycle_state (from agent or UNKNOWN if offline), and other fields.
        """
        try:
            if not self.pg_pool:
                await self.init_connections()

            async with self.pg_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT agent_id, lifecycle_state, version, tps, memory_count, last_heartbeat, current_task_id
                    FROM agent_status
                """)

                # Load instances.yaml for display metadata (single source of truth)
                instances = self._load_instances()
                # Get order from instances.yaml to preserve file ordering
                instances_order = self._get_instances_order()

                # Build a dict of agent_id -> row for quick lookup
                rows_by_id = {row["agent_id"]: row for row in rows}

                agents = []
                # First, add agents in instances.yaml order
                for agent_id in instances_order:
                    if agent_id in rows_by_id:
                        row = rows_by_id[agent_id]

                        # Derive network_status from last_heartbeat timing
                        network_status = self._compute_network_status(row["last_heartbeat"])

                        # Get lifecycle_state: use stored value if online, UNKNOWN if offline
                        stored_lifecycle_state = row["lifecycle_state"]
                        if network_status == "offline":
                            lifecycle_state = "UNKNOWN"
                        else:
                            lifecycle_state = stored_lifecycle_state if stored_lifecycle_state else "UNKNOWN"

                        # Handle memory_count - asyncpg.Record uses dict-like access
                        memory_count = row["memory_count"] if row["memory_count"] is not None else 0

                        # Use version from database (reported by agents in heartbeats)
                        agent_version = row["version"] if row["version"] else "0.0.0"

                        # Get display_name and role (description) from instances.yaml (single source of truth)
                        display_name = agent_id.title()  # Default fallback
                        role = "N/A"  # Default fallback
                        if agent_id in instances:
                            display_name = instances[agent_id].get("display_name", agent_id.title())
                            role = instances[agent_id].get("description", "N/A")

                        agents.append(
                            {
                                "agent_id": agent_id,  # Identifier for key references
                                "agent_name": display_name,  # Display name for dashboard
                                "role": role,
                                "network_status": network_status,  # Derived from heartbeat timing
                                "lifecycle_state": lifecycle_state,  # From agent FSM or UNKNOWN
                                "version": agent_version,
                                "tps": row["tps"],
                                "memory_count": memory_count,
                                "last_seen": row["last_heartbeat"].isoformat() + "Z"
                                if row["last_heartbeat"]
                                else None,
                                "current_task_id": row["current_task_id"],
                            }
                        )

                # Then, add any agents in database that aren't in instances.yaml (alphabetically)
                for agent_id in sorted(rows_by_id.keys()):
                    if agent_id not in instances_order:
                        row = rows_by_id[agent_id]
                        agent_id = row["agent_id"]

                        # Derive network_status from last_heartbeat timing
                        network_status = self._compute_network_status(row["last_heartbeat"])

                        # Get lifecycle_state: use stored value if online, UNKNOWN if offline
                        stored_lifecycle_state = row["lifecycle_state"]
                        if network_status == "offline":
                            lifecycle_state = "UNKNOWN"
                        else:
                            lifecycle_state = stored_lifecycle_state if stored_lifecycle_state else "UNKNOWN"

                        # Handle memory_count - asyncpg.Record uses dict-like access
                        memory_count = row["memory_count"] if row["memory_count"] is not None else 0

                        # Use version from database (reported by agents in heartbeats)
                        agent_version = row["version"] if row["version"] else "0.0.0"

                        # Get display_name and role (description) from instances.yaml (single source of truth)
                        display_name = agent_id.title()  # Default fallback
                        role = "N/A"  # Default fallback
                        if agent_id in instances:
                            display_name = instances[agent_id].get("display_name", agent_id.title())
                            role = instances[agent_id].get("description", "N/A")

                        agents.append(
                            {
                                "agent_id": agent_id,  # Identifier for key references
                                "agent_name": display_name,  # Display name for dashboard
                                "role": role,
                                "network_status": network_status,  # Derived from heartbeat timing
                                "lifecycle_state": lifecycle_state,  # From agent FSM or UNKNOWN
                                "version": agent_version,
                                "tps": row["tps"],
                                "memory_count": memory_count,
                                "last_seen": row["last_heartbeat"].isoformat() + "Z"
                                if row["last_heartbeat"]
                                else None,
                                "current_task_id": row["current_task_id"],
                            }
                        )

                return agents
        except Exception as e:
            logger.error(f"Failed to get agent status from database: {e}", exc_info=True)
            # Return mock data if database is unavailable - use instances.yaml as fallback
            instances = self._load_instances()
            mock_agents = []
            for agent_id, instance_info in instances.items():
                mock_agents.append(
                    {
                        "agent_id": agent_id,
                        "agent_name": instance_info["display_name"],
                        "role": instance_info.get("role", "unknown"),
                        "network_status": "offline",
                        "lifecycle_state": "UNKNOWN",
                        "version": get_agent_version(agent_id),
                        "tps": 0,
                        "memory_count": 0,
                        "last_seen": None,
                        "current_task_id": None,
                    }
                )
            return mock_agents

    async def reconciliation_loop(self):
        """Periodic reconciliation loop to recompute network_status and set lifecycle_state=UNKNOWN for offline agents
        
        SIP-Agent-Lifecycle: Runs every 30-60 seconds to:
        1. Recompute network_status based on last_heartbeat timing
        2. Set lifecycle_state = UNKNOWN for agents where network_status = offline
        """
        app_config = get_config()
        reconciliation_interval = app_config.agent.reconciliation_interval
        
        while self._reconciliation_running:
            try:
                await asyncio.sleep(reconciliation_interval)
                
                if not self.pg_pool:
                    await self.init_connections()
                
                async with self.pg_pool.acquire() as conn:
                    # Get all agents with their last_heartbeat timestamps
                    rows = await conn.fetch("""
                        SELECT agent_id, last_heartbeat, lifecycle_state, network_status
                        FROM agent_status
                    """)
                    
                    now = datetime.utcnow()
                    app_config = get_config()
                    heartbeat_timeout_window = app_config.agent.heartbeat_timeout_window
                    
                    updates = []
                    for row in rows:
                        agent_id = row["agent_id"]
                        last_heartbeat = row["last_heartbeat"]
                        stored_network_status = row.get("network_status")  # May be None for new rows
                        current_lifecycle_state = row.get("lifecycle_state")
                        
                        # Compute network_status from timing
                        if last_heartbeat is None:
                            computed_network_status = "offline"
                        else:
                            time_since_heartbeat = (now - last_heartbeat).total_seconds()
                            computed_network_status = "online" if time_since_heartbeat <= heartbeat_timeout_window else "offline"
                        
                        # Determine what needs updating
                        needs_network_status_update = computed_network_status != stored_network_status
                        # Only update lifecycle_state when going offline (set to UNKNOWN)
                        # When coming online, don't update lifecycle_state - let agent update it via heartbeat
                        needs_lifecycle_update = (
                            computed_network_status == "offline" and current_lifecycle_state != "UNKNOWN"
                        )
                        
                        if needs_network_status_update or needs_lifecycle_update:
                            new_network_status = computed_network_status
                            
                            # Log network status change if it changed
                            if needs_network_status_update:
                                logger.info(
                                    f"Agent {agent_id}: network_status changed {stored_network_status or 'unknown'} → {new_network_status}"
                                )
                                # Network status change event logging (can be extended to use telemetry client if available)
                                # Event: agent.network_status.changed
                                # Attributes: agent_id, previous_network_status, new_network_status, timestamp
                            
                            # Only update lifecycle_state when going offline (set to UNKNOWN)
                            # When coming online, don't update lifecycle_state - agent will update it via heartbeat
                            if needs_lifecycle_update:
                                # Going offline - set lifecycle_state to UNKNOWN
                                updates.append((agent_id, new_network_status, "UNKNOWN", True))
                            else:
                                # Only network_status changed (coming online) - don't touch lifecycle_state
                                updates.append((agent_id, new_network_status, None, False))
                    
                    # Batch update all agents that need updates
                    if updates:
                        for agent_id, network_status, lifecycle_state, update_lifecycle in updates:
                            if update_lifecycle:
                                # Update both network_status and lifecycle_state (going offline)
                                await conn.execute("""
                                    UPDATE agent_status
                                    SET network_status = $1,
                                        lifecycle_state = $2,
                                        updated_at = $3
                                    WHERE agent_id = $4
                                """, network_status, lifecycle_state, now, agent_id)
                            else:
                                # Only update network_status (coming online - agent will update lifecycle_state)
                                await conn.execute("""
                                    UPDATE agent_status
                                    SET network_status = $1,
                                        updated_at = $2
                                    WHERE agent_id = $3
                                """, network_status, now, agent_id)
                        
                        logger.debug(f"Reconciliation: Updated {len(updates)} agent(s)")
                        
            except Exception as e:
                logger.error(f"Reconciliation loop error: {e}", exc_info=True)
                # Continue running even if there's an error
                await asyncio.sleep(10)  # Short delay before retrying

    def _get_display_name(self, agent_id: str) -> str:
        """Get agent display name from agent ID using instances.yaml"""
        instances = self._load_instances()
        instance = instances.get(agent_id)
        if instance:
            return instance["display_name"]
        # Fallback: title case the agent_id
        return agent_id.title()

    def _get_agent_role(self, agent_name: str) -> str:
        """Get agent role description using instances.yaml"""
        instances = self._load_instances()
        instance = instances.get(agent_name)
        if instance:
            # Use description field from instances.yaml, or map role to description
            description = instance.get("description", "")
            if description:
                # Extract role description from description field (e.g., "Task Lead - Governance..." -> "Task Lead")
                role_desc = description.split(" - ")[0] if " - " in description else description
                return role_desc
            # Fallback: map role to description
            role_to_desc = {
                "lead": "Task Lead",
                "dev": "Developer",
                "strat": "Product Strategy",
                "creative": "Creative Design",
                "qa": "QA & Security",
                "data": "Analytics",
                "finance": "Finance & Ops",
                "comms": "Communications",
                "curator": "R&D & Curation",
                "audit": "Monitoring & Audit",
            }
            return role_to_desc.get(instance.get("role", ""), "Unknown")
        return "Unknown"

    async def update_agent_status_in_db(self, agent_status: dict[str, Any]) -> dict[str, Any]:
        """Update agent status in database
        
        SIP-Agent-Lifecycle: Stores agent_id, lifecycle_state, and updates last_heartbeat timestamp.
        network_status is derived separately by Health Check service based on heartbeat timing.
        """
        try:
            if not self.pg_pool:
                await self.init_connections()

            async with self.pg_pool.acquire() as conn:
                # Update last_heartbeat timestamp to current time (heartbeat receipt time)
                # SIP-Agent-Lifecycle: Do NOT set network_status here - it's managed by reconciliation loop
                # Database DEFAULT 'offline' will be used for new inserts, reconciliation loop will update it
                now = datetime.utcnow()
                
                await conn.execute(
                    """
                    INSERT INTO agent_status 
                    (agent_id, lifecycle_state, last_heartbeat, current_task_id, version, tps, memory_count, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (agent_id) 
                    DO UPDATE SET 
                        lifecycle_state = $2,
                        last_heartbeat = $3,
                        current_task_id = $4,
                        version = $5,
                        tps = $6,
                        memory_count = $7,
                        updated_at = $8
                    """,
                    agent_status["agent_id"],
                    agent_status["lifecycle_state"],
                    now,  # Heartbeat receipt time
                    agent_status.get("current_task_id"),
                    agent_status.get("version"),
                    agent_status.get("tps", 0),
                    agent_status.get("memory_count", 0) or 0,
                    now,
                )
                return {"status": "updated", "agent_id": agent_status["agent_id"]}
        except Exception as e:
            logger.error(f"Failed to update agent status: {e}")
            raise

    async def submit_warmboot_request(self, request: WarmBootRequest) -> dict[str, Any]:
        """Submit WarmBoot request to agents via RabbitMQ"""
        try:
            # Initialize connections if needed
            if not self.pg_pool:
                await self.init_connections()

            # Create cycle_id for this warmboot (Max will create the execution cycle)
            cycle_id = f"CYCLE-WB-{request.run_id.replace('run-', '')}"

            # Send messages to agents via RabbitMQ
            connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            channel = connection.channel()

            # Send to Max (lead agent) using new SIP-046 AgentRequest format
            # Use validate.warmboot capability for WarmBoot requests
            # Use requirements_text if provided, otherwise use prd_path
            max_message = {
                "action": "validate.warmboot",
                "payload": {
                    "task_id": f"{cycle_id}-main",
                    "application": request.application,
                    "request_type": request.request_type,
                    "agents": request.agents,
                    "priority": request.priority,
                    "description": request.description,
                    "requirements": request.requirements,
                    "prd_path": request.prd_path if not request.requirements_text else None,
                    "requirements_text": request.requirements_text,
                },
                "metadata": {
                    "pid": f"PID-{request.run_id.replace('run-', '')}",
                    "cycle_id": cycle_id,
                    "tags": ["warmboot", request.request_type],
                },
                "request_id": f"{cycle_id}-main-{int(datetime.utcnow().timestamp())}",
            }

            channel.basic_publish(
                exchange="",
                routing_key="max_tasks",
                body=json.dumps(max_message),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,  # Make message persistent
                ),
            )

            # NOTE: Max (Lead Agent) handles all task creation and delegation
            # The health check app only sends the governance task to Max
            # Max then processes the PRD and creates/delegates proper tasks to other agents
            # This ensures proper task orchestration through Max's governance layer

            connection.close()

            # Insert WarmBoot run into database for persistence and sequence tracking
            try:
                async with self.pg_pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO warmboot_runs 
                        (run_id, run_name, squad_config, benchmark_target, start_time, status, metrics, scorecard)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (run_id) DO NOTHING
                    """,
                        request.run_id,
                        request.application or "Unknown",
                        json.dumps(
                            {
                                "agents": request.agents,
                                "request_type": request.request_type,
                                "priority": request.priority,
                                "prd_path": request.prd_path
                                if not request.requirements_text
                                else None,
                                "requirements_text": request.requirements_text,
                                "description": request.description,
                                "requirements": request.requirements,
                            }
                        ),
                        request.application,
                        datetime.utcnow(),
                        "submitted",
                        json.dumps({}),
                        json.dumps({}),
                    )
                    logger.info(f"Recorded WarmBoot run {request.run_id} in database")
            except Exception as db_error:
                logger.warning(f"Failed to record WarmBoot run in database: {db_error}")
                # Don't fail the request if database insert fails

            return {
                "status": "success",
                "message": f"WarmBoot request {request.run_id} submitted successfully",
                "run_id": request.run_id,
                "agents_notified": request.agents,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to submit WarmBoot request: {str(e)}",
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def get_warmboot_status(self, run_id: str) -> dict[str, Any]:
        """Get status of WarmBoot request"""
        try:
            if not self.pg_pool:
                await self.init_connections()

            async with self.pg_pool.acquire() as conn:
                # Get task statuses from task_status table (like successful WarmBoot runs)
                task_statuses = await conn.fetch(
                    """
                    SELECT task_id, agent_name, status, progress, updated_at
                    FROM task_status
                    WHERE task_id LIKE $1
                    ORDER BY agent_name
                """,
                    f"{run_id}%",
                )

                if not task_statuses:
                    return {
                        "run_id": run_id,
                        "status": "submitted",
                        "message": f"WarmBoot run {run_id} submitted to agents",
                        "task_statuses": [],
                        "timestamp": datetime.utcnow().isoformat(),
                    }

                return {
                    "run_id": run_id,
                    "status": "in_progress",
                    "task_statuses": [
                        {
                            "task_id": task["task_id"],
                            "agent_name": task["agent_name"],
                            "status": task["status"],
                            "progress": task["progress"],
                            "updated_at": task["updated_at"].isoformat()
                            if task["updated_at"]
                            else None,
                        }
                        for task in task_statuses
                    ],
                    "timestamp": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to get WarmBoot status: {str(e)}",
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def get_available_prds(self) -> list[dict[str, Any]]:
        """Get available PRDs from warm-boot/prd/ directory"""
        try:
            import os
            import re

            prds = []
            prd_dir = "warm-boot/prd/"

            if not os.path.exists(prd_dir):
                return prds

            for filename in os.listdir(prd_dir):
                if filename.endswith(".md"):
                    file_path = os.path.join(prd_dir, filename)
                    try:
                        with open(file_path, encoding="utf-8") as f:
                            content = f.read()

                        # Extract PRD metadata
                        title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
                        pid_match = re.search(r"PID-(\d+)", content)
                        description_match = re.search(
                            r"## Summary\s*\n(.+?)(?=\n##|\n#|$)", content, re.DOTALL
                        )

                        title = title_match.group(1) if title_match else filename.replace(".md", "")
                        pid = f"PID-{pid_match.group(1)}" if pid_match else "Unknown"
                        description = (
                            description_match.group(1).strip()
                            if description_match
                            else "No description available"
                        )

                        prds.append(
                            {
                                "file_path": file_path,
                                "filename": filename,
                                "title": title,
                                "pid": pid,
                                "description": description[:200] + "..."
                                if len(description) > 200
                                else description,
                            }
                        )
                    except Exception:
                        # Skip files that can't be read
                        continue

            return prds

        except Exception:
            return []

    async def get_next_run_id(self) -> str:
        """Get next sequential run ID from database"""
        try:
            # Initialize connections if needed
            if not self.pg_pool:
                await self.init_connections()

            # Query database for highest run number
            async with self.pg_pool.acquire() as conn:
                # Try to get the highest numeric run ID from database
                result = await conn.fetchval("""
                    SELECT run_id FROM warmboot_runs 
                    WHERE run_id ~ '^run-[0-9]+$'
                    ORDER BY 
                        CAST(SUBSTRING(run_id FROM 'run-([0-9]+)') AS INTEGER) DESC 
                    LIMIT 1
                """)

                if result:
                    # Extract number and increment
                    try:
                        run_num = int(result.split("-")[1])
                        next_num = run_num + 1
                        logger.info(
                            f"Found highest run ID in database: {result}, next will be: run-{next_num:03d}"
                        )
                        return f"run-{next_num:03d}"
                    except (ValueError, IndexError) as e:
                        logger.warning(
                            f"Failed to parse run ID from database: {result}, error: {e}"
                        )
                        # Fall through to filesystem check

                # Fallback: check filesystem for any existing runs
                import os

                runs_dir = "warm-boot/runs/"
                existing_runs = []

                if os.path.exists(runs_dir):
                    for item in os.listdir(runs_dir):
                        if item.startswith("run-") and os.path.isdir(os.path.join(runs_dir, item)):
                            try:
                                run_num = int(item.split("-")[1])
                                existing_runs.append(run_num)
                            except Exception:
                                continue

                if existing_runs:
                    next_num = max(existing_runs) + 1
                    logger.info(
                        f"Found highest run ID in filesystem: run-{max(existing_runs)}, next will be: run-{next_num:03d}"
                    )
                else:
                    next_num = 1
                    logger.info("No existing runs found, starting with run-001")

                return f"run-{next_num:03d}"

        except Exception as e:
            logger.error(f"Error getting next run ID: {e}")
            return "run-001"

    async def get_agent_messages(self, since: str | None = None) -> list[dict[str, Any]]:
        """Get recent agent messages for live communication feed"""
        try:
            if not self.pg_pool:
                await self.init_connections()

            async with self.pg_pool.acquire() as conn:
                # Get recent messages (last 50 or since timestamp)
                if since:
                    messages = await conn.fetch(
                        """
                        SELECT timestamp, message_type, sender, recipient, payload, context, message_id
                        FROM squadcomms_messages
                        WHERE timestamp > $1
                        ORDER BY timestamp DESC
                        LIMIT 50
                    """,
                        since,
                    )
                else:
                    messages = await conn.fetch("""
                        SELECT timestamp, message_type, sender, recipient, payload, context, message_id
                        FROM squadcomms_messages
                        ORDER BY timestamp DESC
                        LIMIT 50
                    """)

                # Convert to format expected by frontend
                formatted_messages = []
                for msg in messages:
                    # Extract content from payload or use message_type as content
                    content = "Message sent"
                    if msg["payload"]:
                        if isinstance(msg["payload"], dict):
                            content = msg["payload"].get(
                                "description", msg["payload"].get("content", "Message sent")
                            )
                        else:
                            content = str(msg["payload"])

                    formatted_messages.append(
                        {
                            "timestamp": msg["timestamp"],
                            "message_type": msg["message_type"],
                            "sender": msg["sender"],
                            "recipient": msg["recipient"],
                            "content": content,
                            "metadata": msg["context"] or {},
                        }
                    )

                # Return in chronological order (oldest first)
                return list(reversed(formatted_messages))

        except Exception:
            return []


# Initialize health checker
health_checker = HealthChecker()


@app.on_event("startup")
async def startup_event():
    await health_checker.init_connections()
    # Start periodic reconciliation loop for network_status
    asyncio.create_task(health_checker.reconciliation_loop())

    # SIP-0062 Phase 3a: Initialize auth for console routes
    auth_dep = None
    auth_config = config.auth
    try:
        if auth_config.provider == "disabled":
            # Protected endpoints return 503 when auth is disabled
            async def _disabled_dependency(request):
                from fastapi import HTTPException

                raise HTTPException(503, "Authentication service unavailable")

            auth_dep = _disabled_dependency
        elif auth_config.enabled and auth_config.provider != "disabled":
            from adapters.auth.factory import create_auth_provider, create_authorization_provider
            from squadops.api.health_deps import set_health_auth_ports
            from squadops.api.middleware.auth import require_auth

            auth_port = create_auth_provider(
                auth_config.provider,
                issuer_url=auth_config.oidc.issuer_url,
                audience=auth_config.oidc.audience,
                jwks_url=auth_config.oidc.jwks_url,
                roles_claim_path=auth_config.oidc.roles_claim_path,
                jwks_cache_ttl_seconds=auth_config.oidc.jwks_cache_ttl_seconds,
                jwks_forced_refresh_min_interval_seconds=auth_config.oidc.jwks_forced_refresh_min_interval_seconds,
                clock_skew_seconds=auth_config.oidc.clock_skew_seconds,
                issuer_public_url=auth_config.oidc.issuer_public_url,
            )
            authz_port = create_authorization_provider(
                auth_config.provider,
                roles_mode=auth_config.roles_mode,
                roles_client_id=auth_config.roles_client_id,
            )
            set_health_auth_ports(auth=auth_port, authz=authz_port)
            from squadops.api.health_deps import get_health_auth_port

            auth_dep = require_auth(get_health_auth_port)
            logger.info("Health app auth initialized (provider=%s)", auth_config.provider)
        # else: auth.enabled=False → auth_dep remains None (no auth on console routes)
    except Exception as e:
        logger.error("Failed to initialize health app auth: %s", e)

    # Initialize modular routes with dependencies
    health_routes.init_routes(health_checker, templates)
    agents_routes.init_routes(health_checker)
    console_routes.init_routes(
        health_checker=health_checker,
        console_sessions=console_sessions,
        parse_command=parse_command,
        create_console_session=create_console_session,
        get_console_session=get_console_session,
        command_handler_cls=CommandHandler,
        auth_dependency=auth_dep,
    )
    warmboot_routes.init_routes(health_checker)


@app.on_event("shutdown")
async def shutdown_event():
    # Cancel reconciliation loop
    health_checker._reconciliation_running = False


@app.get("/health/infra")
async def health_infra():
    """Get infrastructure health status"""
    infra_checks = await asyncio.gather(
        health_checker.check_rabbitmq(),
        health_checker.check_postgres(),
        health_checker.check_redis(),
        health_checker.check_prefect(),
        health_checker.check_prometheus(),
        health_checker.check_grafana(),
        health_checker.check_otel_collector(),
    )
    return infra_checks


@app.get("/health/agents")
async def health_agents():
    """Get agent health status"""
    agents = await health_checker.get_agent_status()
    return agents


@app.post("/health/agents/status")
async def create_or_update_agent_status(agent_status: AgentStatusCreate):
    """Create or update agent status (heartbeat endpoint)
    
    SIP-Agent-Lifecycle: Accepts agent_id and lifecycle_state from agent.
    Ignores any status or network_status fields (agents don't send these).
    """
    try:
        # Use agent_id (required), ignore deprecated agent_name if present
        agent_id = agent_status.agent_id
        if agent_status.agent_name and not agent_id:
            # Backward compatibility: use agent_name if agent_id not provided
            agent_id = agent_status.agent_name.lower()
        
        # Validate lifecycle_state
        valid_states = ['STARTING', 'READY', 'WORKING', 'BLOCKED', 'CRASHED', 'STOPPING']
        if agent_status.lifecycle_state not in valid_states:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid lifecycle_state: {agent_status.lifecycle_state}. Must be one of {valid_states}"
            )
        
        result = await health_checker.update_agent_status_in_db(
            {
                "agent_id": agent_id,
                "lifecycle_state": agent_status.lifecycle_state,
                "current_task_id": agent_status.current_task_id,
                "version": agent_status.version,
                "tps": agent_status.tps,
                "memory_count": agent_status.memory_count,
            }
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update agent status: {str(e)}"
        ) from e


@app.put("/health/agents/status/{agent_id}")
async def update_agent_status(agent_id: str, update: AgentStatusUpdate):
    """Update agent status fields
    
    SIP-Agent-Lifecycle: Uses agent_id instead of agent_name.
    network_status is derived by Health Check, not updated directly.
    """
    try:
        if not health_checker.pg_pool:
            await health_checker.init_connections()

        updates = []
        params = []
        param_count = 1

        if update.lifecycle_state:
            updates.append(f"lifecycle_state = ${param_count}")
            params.append(update.lifecycle_state)
            param_count += 1

        if update.current_task_id is not None:
            updates.append(f"current_task_id = ${param_count}")
            params.append(update.current_task_id)
            param_count += 1

        if update.version:
            updates.append(f"version = ${param_count}")
            params.append(update.version)
            param_count += 1

        if update.tps is not None:
            updates.append(f"tps = ${param_count}")
            params.append(update.tps)
            param_count += 1

        if update.memory_count is not None:
            updates.append(f"memory_count = ${param_count}")
            params.append(update.memory_count)
            param_count += 1

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates.append(f"last_heartbeat = ${param_count}")
        params.append(datetime.utcnow())
        param_count += 1
        updates.append(f"updated_at = ${param_count}")
        params.append(datetime.utcnow())
        param_count += 1

        params.append(agent_id.lower())  # Use lowercase agent_id
        query = f"UPDATE agent_status SET {', '.join(updates)} WHERE agent_id = ${param_count}"

        async with health_checker.pg_pool.acquire() as conn:
            result = await conn.execute(query, *params)
            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail=f"Agent status {agent_id} not found")

        return {"status": "updated", "agent_id": agent_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update agent status: {str(e)}"
        ) from e


@app.get("/health/agents/status/{agent_id}")
async def get_agent_status_by_id(agent_id: str):
    """Get agent status by agent_id
    
    SIP-Agent-Lifecycle: Uses agent_id instead of agent_name.
    Returns network_status (derived) and lifecycle_state.
    """
    try:
        if not health_checker.pg_pool:
            await health_checker.init_connections()

        async with health_checker.pg_pool.acquire() as conn:
            status = await conn.fetchrow(
                """
                SELECT agent_id, lifecycle_state, network_status, version, tps, memory_count, last_heartbeat, current_task_id
                FROM agent_status WHERE agent_id = $1
            """,
                agent_id.lower(),
            )

            if not status:
                raise HTTPException(status_code=404, detail=f"Agent status {agent_id} not found")

            # Derive network_status from last_heartbeat timing
            network_status = health_checker._compute_network_status(status["last_heartbeat"])
            
            # Get lifecycle_state: UNKNOWN if offline, otherwise use stored value
            if network_status == "offline":
                lifecycle_state = "UNKNOWN"
            else:
                lifecycle_state = status["lifecycle_state"] if status["lifecycle_state"] else "UNKNOWN"

            # Get display name from instances.yaml
            agent_name = health_checker._get_display_name(status["agent_id"])

            return {
                "agent_id": status["agent_id"],
                "agent_name": agent_name,
                "network_status": network_status,
                "lifecycle_state": lifecycle_state,
                "version": status["version"],
                "tps": status["tps"],
                "memory_count": status.get("memory_count", 0) or 0,
                "last_seen": status["last_heartbeat"].isoformat() + "Z"
                if status["last_heartbeat"]
                else None,
                "current_task_id": status["current_task_id"],
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent status: {str(e)}") from e


@app.get("/health")
async def health_dashboard(request: StarletteRequest):
    """Get health dashboard HTML"""
    infra_status = await health_infra()
    agent_status = await health_agents()

    return templates.TemplateResponse(
        "health_dashboard.html",
        {
            "request": request,
            "infra_status": infra_status,
            "agent_status": agent_status,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@app.post("/warmboot/submit")
async def submit_warmboot(request: WarmBootRequest):
    """Submit a WarmBoot request to agents"""
    result = await health_checker.submit_warmboot_request(request)
    return JSONResponse(content=result)


@app.get("/warmboot/status/{run_id}")
async def get_warmboot_status(run_id: str):
    """Get status of a WarmBoot request"""
    result = await health_checker.get_warmboot_status(run_id)
    return JSONResponse(content=result)


@app.get("/warmboot/prds")
async def get_available_prds():
    """Get available PRDs from warm-boot/prd/ directory"""
    prds = await health_checker.get_available_prds()
    return JSONResponse(content=prds)


# Agent Gateway: Console Request/Response Models
class ConsoleCommandRequest(BaseModel):
    session_id: str
    command: str


class ConsoleCommandResponse(BaseModel):
    session_id: str
    lines: list[str]
    mode: str
    bound_agent: str | None = None
    cycle_id: str | None = None  # SIP-0048: renamed from ecid


@app.post("/console/command")
async def console_command(request: ConsoleCommandRequest):
    """Agent Gateway: Handle console command"""
    try:
        # Get or create session
        session = get_console_session(request.session_id)
        if not session:
            # Create new session with provided session_id if not found
            console_sessions[request.session_id] = ConsoleSession(
                session_id=request.session_id, mode="idle"
            )
            session = get_console_session(request.session_id)
            if not session:
                raise HTTPException(status_code=500, detail="Failed to create session")

        # Parse command
        parsed = parse_command(request.command)
        cmd = parsed["command"]
        args = parsed["args"]

        logger.info(f"Agent Gateway command: {cmd} (session: {request.session_id})")

        # Initialize command handler
        handler = CommandHandler(health_checker)

        # Route command
        if cmd == "":
            return ConsoleCommandResponse(
                session_id=request.session_id,
                lines=[],
                mode=session.mode,
                bound_agent=session.bound_agent,
                cycle_id=session.cycle_id,
            )
        elif cmd == "help":
            lines = await handler.handle_help()
            return ConsoleCommandResponse(
                session_id=request.session_id,
                lines=lines,
                mode=session.mode,
                bound_agent=session.bound_agent,
                cycle_id=session.cycle_id,
            )
        elif cmd == "agent":
            if len(args) == 0:
                return ConsoleCommandResponse(
                    session_id=request.session_id,
                    lines=["Error: 'agent' command requires subcommand (list, status, info, logs)"],
                    mode=session.mode,
                    bound_agent=session.bound_agent,
                    cycle_id=session.cycle_id,
                )
            subcmd = args[0].lower()
            if subcmd == "list":
                lines = await handler.handle_agent_list()
                return ConsoleCommandResponse(
                    session_id=request.session_id,
                    lines=lines,
                    mode=session.mode,
                    bound_agent=session.bound_agent,
                    cycle_id=session.cycle_id,
                )
            elif subcmd == "status":
                lines = await handler.handle_agent_status()
                return ConsoleCommandResponse(
                    session_id=request.session_id,
                    lines=lines,
                    mode=session.mode,
                    bound_agent=session.bound_agent,
                    cycle_id=session.cycle_id,
                )
            elif subcmd == "info":
                if len(args) < 2:
                    return ConsoleCommandResponse(
                        session_id=request.session_id,
                        lines=["Error: 'agent info' requires agent name"],
                        mode=session.mode,
                        bound_agent=session.bound_agent,
                        cycle_id=session.cycle_id,
                    )
                lines = await handler.handle_agent_info(args[1])
                return ConsoleCommandResponse(
                    session_id=request.session_id,
                    lines=lines,
                    mode=session.mode,
                    bound_agent=session.bound_agent,
                    cycle_id=session.cycle_id,
                )
            elif subcmd == "logs":
                if len(args) < 2:
                    return ConsoleCommandResponse(
                        session_id=request.session_id,
                        lines=["Error: 'agent logs' requires agent name"],
                        mode=session.mode,
                        bound_agent=session.bound_agent,
                        cycle_id=session.cycle_id,
                    )
                n = int(args[2]) if len(args) >= 3 else 10
                lines = await handler.handle_agent_logs(args[1], n)
                return ConsoleCommandResponse(
                    session_id=request.session_id,
                    lines=lines,
                    mode=session.mode,
                    bound_agent=session.bound_agent,
                    cycle_id=session.cycle_id,
                )
            else:
                return ConsoleCommandResponse(
                    session_id=request.session_id,
                    lines=[
                        f"Error: Unknown agent subcommand '{subcmd}'. Use 'help' for available commands."
                    ],
                    mode=session.mode,
                    bound_agent=session.bound_agent,
                    cycle_id=session.cycle_id,
                )
        elif cmd == "chat":
            if len(args) == 0:
                return ConsoleCommandResponse(
                    session_id=request.session_id,
                    lines=["Error: 'chat' command requires agent name or 'end'"],
                    mode=session.mode,
                    bound_agent=session.bound_agent,
                    cycle_id=session.cycle_id,
                )
            if args[0].lower() == "end":
                result = await handler.handle_chat_end(request.session_id)
                return ConsoleCommandResponse(
                    session_id=request.session_id,
                    lines=result["lines"],
                    mode=result["mode"],
                    bound_agent=result["bound_agent"],
                    cycle_id=result["cycle_id"],
                )
            else:
                result = await handler.handle_chat_start(request.session_id, args[0])
                return ConsoleCommandResponse(
                    session_id=request.session_id,
                    lines=result["lines"],
                    mode=result["mode"],
                    bound_agent=result["bound_agent"],
                    cycle_id=result["cycle_id"],
                )
        elif cmd == "whoami":
            lines = await handler.handle_whoami(request.session_id)
            session = get_console_session(request.session_id)
            return ConsoleCommandResponse(
                session_id=request.session_id,
                lines=lines,
                mode=session.mode if session else "idle",
                bound_agent=session.bound_agent if session else None,
                cycle_id=session.cycle_id if session else None,
            )
        elif cmd == "clear":
            # Client-side only command
            return ConsoleCommandResponse(
                session_id=request.session_id,
                lines=["[Console cleared]"],
                mode=session.mode,
                bound_agent=session.bound_agent,
                cycle_id=session.cycle_id,
            )
        else:
            # Check if in chat mode - treat as message
            if session.mode == "chat" and session.bound_agent:
                result = await handler.handle_chat_message(request.session_id, request.command)
                return ConsoleCommandResponse(
                    session_id=request.session_id,
                    lines=result["lines"],
                    mode=result["mode"],
                    bound_agent=result["bound_agent"],
                    cycle_id=result["cycle_id"],
                )
            else:
                return ConsoleCommandResponse(
                    session_id=request.session_id,
                    lines=[f"Error: Unknown command '{cmd}'. Type 'help' for available commands."],
                    mode=session.mode,
                    bound_agent=session.bound_agent,
                    cycle_id=session.cycle_id,
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent Gateway error: {e}", exc_info=True)
        session = get_console_session(request.session_id)
        return ConsoleCommandResponse(
            session_id=request.session_id,
            lines=[f"Error: {str(e)}"],
            mode=session.mode if session else "idle",
            bound_agent=session.bound_agent if session else None,
            cycle_id=session.cycle_id if session else None,
        )


@app.get("/console/session")
async def create_console_session_endpoint():
    """Agent Gateway: Create new console session"""
    session_id = create_console_session()
    return {"session_id": session_id}


@app.get("/console/responses/{session_id}")
async def get_console_responses(session_id: str):
    """Agent Gateway: Get and clear pending responses for session"""
    session = get_console_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Return responses and clear list
    responses = session.pending_responses.copy()
    session.pending_responses.clear()

    return {"session_id": session_id, "responses": responses, "count": len(responses)}


@app.get("/warmboot/next-run-id")
async def get_next_run_id():
    """Get next sequential run ID"""
    run_id = await health_checker.get_next_run_id()
    return JSONResponse(content={"run_id": run_id})


@app.get("/warmboot/agents")
async def get_agent_status_for_form():
    """Get agent status for form checkbox defaults"""
    agents = await health_checker.get_agent_status()
    return JSONResponse(content=agents)


@app.get("/warmboot/messages")
async def get_agent_messages(since: str | None = None):
    """Get recent agent messages for live communication feed"""
    messages = await health_checker.get_agent_messages(since)
    return JSONResponse(content=messages)


@app.get("/warmboot/form")
async def warmboot_form():
    """Get WarmBoot request form HTML"""
    # Load instances for dynamic agent list
    instances = health_checker._load_instances()

    # Build agent checkboxes dynamically
    agent_checkboxes_html = []
    agents_list = list(instances.items())

    # Group agents into rows of 3
    for i in range(0, len(agents_list), 3):
        row_agents = agents_list[i : i + 3]
        row_class = "row mt-2" if i > 0 else "row"
        row_html = f'                        <div class="{row_class}">\n'
        for agent_id, instance_info in row_agents:
            display_name = instance_info["display_name"]
            role = instance_info["role"]
            # Check max and neo by default
            checked = "checked" if agent_id in ["max", "neo"] else ""
            row_html += f'''                            <div class="col-md-4">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="agent_{agent_id}" name="agents" value="{agent_id}" {checked}>
                                    <label class="form-check-label" for="agent_{agent_id}">{display_name} ({role.title()})</label>
                                </div>
                            </div>
'''
        row_html += "                        </div>"
        agent_checkboxes_html.append(row_html)

    agents_section = "\n".join(agent_checkboxes_html)

    html_content = (
        """
    <!DOCTYPE html>
    <html>
    <head>
        <title>SquadOps WarmBoot Request</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        <style>
            .form-container {
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }
            .status-container {
                margin-top: 20px;
                padding: 15px;
                border-radius: 5px;
                display: none;
            }
            .status-success {
                background-color: #d4edda;
                border: 1px solid #c3e6cb;
                color: #155724;
            }
            .status-error {
                background-color: #f8d7da;
                border: 1px solid #f5c6cb;
                color: #721c24;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="form-container">
                <h1 class="mb-4">🚀 SquadOps WarmBoot Request</h1>
                <p class="text-muted">Submit a WarmBoot request directly to agents - no AI scripting, real agent communication only.</p>
                
                <form id="warmbootForm">
                    <div class="row">
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="run_id" class="form-label">Run ID</label>
                                <input type="text" class="form-control" id="run_id" name="run_id" required>
                                <div class="form-text">e.g., run-007, feature-auth, bug-fix-001</div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="application" class="form-label">Application</label>
                                <select class="form-select" id="application" name="application" required>
                                    <option value="">Select Application</option>
                                    <option value="HelloSquad">HelloSquad</option>
                                    <option value="SquadOps-Framework">SquadOps Framework</option>
                                    <option value="Health-Check">Health Check Service</option>
                                    <option value="Custom">Custom Application</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="request_type" class="form-label">Request Type</label>
                                <select class="form-select" id="request_type" name="request_type" required>
                                    <option value="">Select Type</option>
                                    <option value="from-scratch">From-Scratch Build (archive previous, build new)</option>
                                    <option value="feature-update">Feature Update (modify existing)</option>
                                    <option value="bug-fix">Bug Fix (fix existing)</option>
                                    <option value="refactor">Refactor (improve existing)</option>
                                    <option value="deployment">Deployment (deploy existing)</option>
                                    <option value="testing">Testing (test existing)</option>
                                </select>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="priority" class="form-label">Priority</label>
                                <select class="form-select" id="priority" name="priority" required>
                                    <option value="">Select Priority</option>
                                    <option value="HIGH">High</option>
                                    <option value="MEDIUM">Medium</option>
                                    <option value="LOW">Low</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label for="agents" class="form-label">Agents</label>
                        <div class="row">
"""
        + agents_section
        + """
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label for="description" class="form-label">Description</label>
                        <textarea class="form-control" id="description" name="description" rows="4" required placeholder="Describe what you want the agents to build or accomplish..."></textarea>
                    </div>
                    
                    <div class="mb-3">
                        <label for="requirements" class="form-label">Requirements (Optional)</label>
                        <textarea class="form-control" id="requirements" name="requirements" rows="3" placeholder="Additional technical requirements, constraints, or specifications..."></textarea>
                    </div>
                    
                    <div class="d-grid gap-2">
                        <button type="submit" class="btn btn-primary btn-lg">Submit WarmBoot Request</button>
                        <a href="/health" class="btn btn-secondary">Back to Health Dashboard</a>
                    </div>
                </form>
                
                <div class="mt-4">
                    <h4>Live Agent Communication</h4>
                    <div class="agent-chat-container">
                        <textarea id="agentChat" class="form-control" rows="15" readonly 
                                  style="font-family: monospace; font-size: 12px; background-color: #f8f9fa;"
                                  placeholder="Agent communication will appear here after submitting a WarmBoot request..."></textarea>
                        <div class="chat-controls mt-2">
                            <button id="clearChat" class="btn btn-sm btn-outline-secondary">Clear</button>
                            <span id="chatStatus" class="badge bg-secondary ms-2">Waiting</span>
                        </div>
                    </div>
                </div>
                
                <div id="statusContainer" class="status-container">
                    <div id="statusMessage"></div>
                    <div id="statusDetails" class="mt-2"></div>
                </div>
            </div>
        </div>
        
        <script>
            let currentRunId = null;
            let chatRefreshInterval = null;
            let lastMessageTime = null;
            
            // Initialize form on page load
            document.addEventListener('DOMContentLoaded', async function() {
                await initializeForm();
            });
            
            async function initializeForm() {
                // Generate Run ID
                await generateRunId();
                
                // Populate PRD dropdown
                await populatePrdDropdown();
                
                // Set up agent checkboxes
                await setupAgentCheckboxes();
                
                // Set up chat controls
                setupChatControls();
            }
            
            async function generateRunId() {
                try {
                    const response = await fetch('/warmboot/next-run-id');
                    const result = await response.json();
                    document.getElementById('run_id').value = result.run_id;
                    currentRunId = result.run_id;
                } catch (error) {
                    console.error('Failed to generate Run ID:', error);
                    document.getElementById('run_id').value = 'run-001';
                    currentRunId = 'run-001';
                }
            }
            
            async function populatePrdDropdown() {
                try {
                    const response = await fetch('/warmboot/prds');
                    const prds = await response.json();
                    const prdSelect = document.getElementById('application');
                    
                    // Clear existing options except the first one
                    prdSelect.innerHTML = '<option value="">Select Application</option>';
                    
                    // Add PRD options
                    prds.forEach(prd => {
                        const option = document.createElement('option');
                        option.value = prd.file_path;
                        option.textContent = `${prd.title} (${prd.pid})`;
                        option.title = prd.description;
                        prdSelect.appendChild(option);
                    });
                    
                    // Add custom options
                    const customOption = document.createElement('option');
                    customOption.value = 'custom';
                    customOption.textContent = 'Custom Application';
                    prdSelect.appendChild(customOption);
                    
                } catch (error) {
                    console.error('Failed to load PRDs:', error);
                }
            }
            
            async function setupAgentCheckboxes() {
                try {
                    const response = await fetch('/warmboot/agents');
                    const agents = await response.json();
                    
                    agents.forEach(agent => {
                        const checkbox = document.getElementById(`agent_${agent.agent.toLowerCase()}`);
                        if (checkbox) {
                            // Set default selection based on agent status
                            const onlineStatuses = ['online', 'available', 'active-non-blocking'];
                            checkbox.checked = onlineStatuses.includes(agent.status);
                        }
                    });
                } catch (error) {
                    console.error('Failed to load agent status:', error);
                }
            }
            
            function setupChatControls() {
                // Clear chat button
                document.getElementById('clearChat').addEventListener('click', function() {
                    document.getElementById('agentChat').value = '';
                    lastMessageTime = null;
                });
            }
            
            function startChatFeed() {
                if (chatRefreshInterval) {
                    clearInterval(chatRefreshInterval);
                }
                
                const chatStatus = document.getElementById('chatStatus');
                chatStatus.className = 'badge bg-success ms-2';
                chatStatus.textContent = 'Live';
                
                chatRefreshInterval = setInterval(async () => {
                    try {
                        const sinceParam = lastMessageTime ? `?since=${lastMessageTime}` : '';
                        const response = await fetch(`/warmboot/messages${sinceParam}`);
                        const messages = await response.json();
                        
                        if (messages.length > 0) {
                            const chatArea = document.getElementById('agentChat');
                            
                            messages.forEach(msg => {
                                const formattedMsg = formatMessage(msg);
                                chatArea.value += formattedMsg + '\\n';
                            });
                            
                            // Auto-scroll to bottom
                            chatArea.scrollTop = chatArea.scrollHeight;
                            
                            // Update last message time
                            lastMessageTime = messages[messages.length - 1].timestamp;
                        }
                    } catch (error) {
                        console.error('Chat feed error:', error);
                    }
                }, 1000); // Refresh every second
            }
            
            function formatMessage(msg) {
                const timestamp = new Date(msg.timestamp).toLocaleTimeString();
                const icon = getMessageIcon(msg.message_type);
                const direction = msg.sender === 'warmboot-orchestrator' ? '←' : '→';
                
                return `[${timestamp}] ${icon} ${msg.message_type}: ${msg.recipient} ${direction} ${msg.sender}\\n           "${msg.content}"`;
            }
            
            function getMessageIcon(messageType) {
                const icons = {
                    'WARMBOOT_REQUEST': '🚀',
                    'TASK_ASSIGNMENT': '📋', 
                    'TASK_ACKNOWLEDGED': '✅',
                    'TASK_UPDATE': '🔄',
                    'PROGRESS_UPDATE': '📝',
                    'BUILD_START': '🏗️',
                    'TASK_COMPLETED': '✅',
                    'TASK_FAILED': '❌'
                };
                return icons[messageType] || '💬';
            }
            
            // Form submission
            document.getElementById('warmbootForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                
                const formData = new FormData(e.target);
                const agents = Array.from(document.querySelectorAll('input[name="agents"]:checked')).map(cb => cb.value);
                
                const requestData = {
                    run_id: formData.get('run_id'),
                    application: formData.get('application'),
                    request_type: formData.get('request_type'),
                    agents: agents,
                    priority: formData.get('priority'),
                    description: formData.get('description'),
                    requirements: formData.get('requirements') || null
                };
                
                try {
                    const response = await fetch('/warmboot/submit', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(requestData)
                    });
                    
                    const result = await response.json();
                    
                    const statusContainer = document.getElementById('statusContainer');
                    const statusMessage = document.getElementById('statusMessage');
                    const statusDetails = document.getElementById('statusDetails');
                    
                    if (result.status === 'success') {
                        statusContainer.className = 'status-container status-success';
                        statusMessage.innerHTML = '<strong>✅ Success!</strong> ' + result.message;
                        statusDetails.innerHTML = `
                            <strong>Run ID:</strong> ${result.run_id}<br>
                            <strong>Agents Notified:</strong> ${result.agents_notified.join(', ')}<br>
                            <strong>Timestamp:</strong> ${result.timestamp}<br>
                            <a href="/warmboot/status/${requestData.run_id}" class="btn btn-sm btn-outline-success mt-2">View Status</a>
                        `;
                        
                        // Start live chat feed
                        startChatFeed();
                        
                    } else {
                        statusContainer.className = 'status-container status-error';
                        statusMessage.innerHTML = '<strong>❌ Error!</strong> ' + result.message;
                        statusDetails.innerHTML = `<strong>Timestamp:</strong> ${result.timestamp}`;
                    }
                    
                    statusContainer.style.display = 'block';
                    statusContainer.scrollIntoView({ behavior: 'smooth' });
                    
                } catch (error) {
                    const statusContainer = document.getElementById('statusContainer');
                    const statusMessage = document.getElementById('statusMessage');
                    
                    statusContainer.className = 'status-container status-error';
                    statusMessage.innerHTML = '<strong>❌ Network Error!</strong> ' + error.message;
                    statusContainer.style.display = 'block';
                    statusContainer.scrollIntoView({ behavior: 'smooth' });
                }
            });
        </script>
    </body>
    </html>
    """
    )
    return HTMLResponse(content=html_content)


@app.get("/")
async def root():
    return {"message": "SquadOps Health Check Service", "version": SQUADOPS_VERSION}


# Application routing - proxy to deployed applications
@app.get("/hello-squad/{path:path}")
async def proxy_hello_squad(path: str, request: Request):
    """Proxy requests to HelloSquad application"""
    try:
        # Forward request to the HelloSquad container
        target_url = f"http://squadops-hello-squad:80/{path}"

        async with aiohttp.ClientSession() as session:
            # Forward the request
            async with session.get(target_url) as response:
                content = await response.read()

                # Return the response with appropriate headers
                return Response(
                    content=content,
                    status_code=response.status,
                    headers=dict(response.headers),
                    media_type=response.headers.get("content-type", "text/html"),
                )
    except Exception as e:
        return JSONResponse(
            status_code=503, content={"error": f"HelloSquad application unavailable: {str(e)}"}
        )


@app.get("/hello-squad/")
async def proxy_hello_squad_root():
    """Proxy root request to HelloSquad application"""
    return await proxy_hello_squad("", None)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
