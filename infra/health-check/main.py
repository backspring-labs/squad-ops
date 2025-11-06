from fastapi import FastAPI, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import asyncio
import aiohttp
import asyncpg
import redis.asyncio as redis
import pika
import json
import logging
import yaml
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import os
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Reduce verbosity of pika (RabbitMQ client) logging - silence all pika loggers
pika_loggers = ['pika', 'pika.connection', 'pika.channel', 'pika.adapters', 'pika.adapters.utils', 
                'pika.adapters.utils.connection_workflow', 'pika.adapters.utils.io_services_utils',
                'pika.adapters.blocking_connection', 'pika.select_connection']
for logger_name in pika_loggers:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

sys.path.append('/Users/jladd/Code/squad-ops')
from config.version import SQUADOPS_VERSION, AGENT_VERSIONS, get_agent_version

app = FastAPI(title="SquadOps Health Check Service", version=SQUADOPS_VERSION)

# Pydantic models for WarmBoot requests
class WarmBootRequest(BaseModel):
    run_id: str
    application: str
    request_type: str
    agents: List[str]
    priority: str
    description: str
    requirements: Optional[str] = None
    prd_path: Optional[str] = None

# Pydantic models for Agent Status
class AgentStatusCreate(BaseModel):
    agent_name: str
    status: str
    current_task_id: Optional[str] = None
    version: Optional[str] = None
    tps: int = 0
    memory_count: Optional[int] = None

class AgentStatusUpdate(BaseModel):
    status: Optional[str] = None
    current_task_id: Optional[str] = None
    version: Optional[str] = None
    tps: Optional[int] = None
    memory_count: Optional[int] = None

# Configuration
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://squadops:squadops123@rabbitmq:5672/")
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://squadops:squadops123@postgres:5432/squadops")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
PREFECT_URL = os.getenv("PREFECT_URL", "http://prefect-server:4200/api")

class HealthChecker:
    def __init__(self):
        self.redis_client = None
        self.pg_pool = None
        self._instances_cache = None
        self.instances_file = os.getenv('INSTANCES_FILE', 'agents/instances/instances.yaml')
    
    def _load_instances(self) -> Dict[str, Dict[str, Any]]:
        """
        Load agent instances from instances.yaml.
        Returns dict mapping agent_id -> {display_name, role, description}
        Caches result for performance.
        """
        if self._instances_cache is not None:
            return self._instances_cache
        
        try:
            instances_path = Path(self.instances_file)
            if not instances_path.exists():
                logger.warning(f"Instances file not found: {self.instances_file}, using defaults")
                return self._get_default_instances()
            
            with open(instances_path, 'r') as f:
                data = yaml.safe_load(f)
            
            # Build agent_id -> instance info mapping
            instances = {}
            for instance in data.get('instances', []):
                if instance.get('enabled', False):
                    agent_id = instance.get('id')
                    if agent_id:
                        instances[agent_id] = {
                            'display_name': instance.get('display_name', agent_id.title()),
                            'role': instance.get('role', 'unknown'),
                            'description': instance.get('description', '')
                        }
            
            self._instances_cache = instances
            logger.info(f"Loaded {len(instances)} agent instances from {self.instances_file}")
            return instances
            
        except Exception as e:
            logger.error(f"Failed to load instances.yaml: {e}, using defaults")
            return self._get_default_instances()
    
    def _get_default_instances(self) -> Dict[str, Dict[str, Any]]:
        """Fallback instances mapping if instances.yaml can't be loaded"""
        return {
            'max': {'display_name': 'Max', 'role': 'lead', 'description': 'Task Lead - Governance and coordination'},
            'neo': {'display_name': 'Neo', 'role': 'dev', 'description': 'Developer - Deductive reasoning'},
            'strat-agent': {'display_name': 'StratAgent', 'role': 'strat', 'description': 'Product Strategy - Abductive reasoning'},
            'creative-agent': {'display_name': 'CreativeAgent', 'role': 'creative', 'description': 'Creative Design - Visual synthesis'},
            'qa-agent': {'display_name': 'QAAgent', 'role': 'qa', 'description': 'QA & Security - Counterfactual reasoning'},
            'data-agent': {'display_name': 'DataAgent', 'role': 'data', 'description': 'Analytics - Inductive reasoning'},
            'finance-agent': {'display_name': 'FinanceAgent', 'role': 'finance', 'description': 'Finance & Ops - Rule-based reasoning'},
            'comms-agent': {'display_name': 'CommsAgent', 'role': 'comms', 'description': 'Communications - Empathetic reasoning'},
            'curator-agent': {'display_name': 'CuratorAgent', 'role': 'curator', 'description': 'R&D & Curation - Pattern detection'},
            'audit-agent': {'display_name': 'AuditAgent', 'role': 'audit', 'description': 'Monitoring & Audit - Continuous monitoring'}
        }
        
    async def init_connections(self):
        """Initialize database connections"""
        try:
            self.redis_client = redis.from_url(REDIS_URL)
            self.pg_pool = await asyncpg.create_pool(POSTGRES_URL)
        except Exception as e:
            print(f"Failed to initialize connections: {e}")
    
    async def check_rabbitmq(self) -> Dict[str, Any]:
        """Check RabbitMQ health"""
        try:
            connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            channel = connection.channel()
            queue_info = channel.queue_declare(queue='health_check', durable=False, auto_delete=True)
            
            # Try to get RabbitMQ version from management API
            version = "Unknown"
            try:
                # RabbitMQ management API endpoint for version info
                import urllib.request
                import json
                import base64
                
                # Extract credentials from RABBITMQ_URL
                url_parts = RABBITMQ_URL.replace("amqp://", "").split("@")
                if len(url_parts) == 2:
                    creds = url_parts[0]
                    host_port = url_parts[1].split("/")[0]
                    mgmt_url = f"http://{host_port.replace(':5672', ':15672')}/api/overview"
                    
                    # Create basic auth header
                    auth_string = base64.b64encode(creds.encode()).decode()
                    headers = {'Authorization': f'Basic {auth_string}'}
                    
                    req = urllib.request.Request(mgmt_url, headers=headers)
                    with urllib.request.urlopen(req, timeout=5) as response:
                        data = json.loads(response.read().decode())
                        version = data.get('rabbitmq_version', 'Unknown')
            except:
                # Fallback: try to get version from connection properties
                try:
                    props = connection.server_properties
                    version = props.get('version', 'Unknown')
                except:
                    pass
            
            connection.close()
            
            return {
                "component": "RabbitMQ",
                "type": "Message Broker",
                "status": "online",
                "version": version,
                "purpose": "Handles inter-agent communication",
                "notes": f"{queue_info.method.message_count} messages in queue"
            }
        except Exception as e:
            return {
                "component": "RabbitMQ",
                "type": "Message Broker",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Handles inter-agent communication",
                "notes": f"Error: {str(e)}"
            }
    
    async def check_postgres(self) -> Dict[str, Any]:
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
                    match = re.search(r'PostgreSQL (\d+\.\d+)', version_result)
                    if match:
                        version = match.group(1)
                
            return {
                "component": "PostgreSQL",
                "type": "Relational DB",
                "status": "online",
                "version": version,
                "purpose": "Persistent data and logs",
                "notes": f"{count} agents registered"
            }
        except Exception as e:
            return {
                "component": "PostgreSQL",
                "type": "Relational DB",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Persistent data and logs",
                "notes": f"Error: {str(e)}"
            }
    
    async def check_redis(self) -> Dict[str, Any]:
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
                "version": info.get('redis_version', 'Unknown'),
                "purpose": "Caching, state sync, pub/sub backbone",
                "notes": f"Memory used: {info.get('used_memory_human', 'Unknown')}"
            }
        except Exception as e:
            return {
                "component": "Redis",
                "type": "Cache & Pub/Sub",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Caching, state sync, pub/sub backbone",
                "notes": f"Error: {str(e)}"
            }
    
    async def check_prefect(self) -> Dict[str, Any]:
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
                        except:
                            pass
                        
                        return {
                            "component": "Prefect Server",
                            "type": "Orchestration Engine",
                            "status": "online",
                            "version": version,
                            "purpose": "Task orchestration and state management",
                            "notes": "API responding"
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
                "notes": f"Error: {str(e)}"
            }
    
    async def check_prometheus(self) -> Dict[str, Any]:
        """Check Prometheus health"""
        try:
            prometheus_url = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
            async with aiohttp.ClientSession() as session:
                # Check health endpoint
                async with session.get(f"{prometheus_url}/-/healthy", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        # Try to get version from API
                        version = "Unknown"
                        try:
                            version_url = f"{prometheus_url}/api/v1/status/buildinfo"
                            async with session.get(version_url, timeout=aiohttp.ClientTimeout(total=5)) as version_response:
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
                            "notes": "Health endpoint responding"
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
                "notes": f"Error: {str(e)}"
            }
    
    async def check_grafana(self) -> Dict[str, Any]:
        """Check Grafana health"""
        try:
            grafana_url = os.getenv("GRAFANA_URL", "http://grafana:3000")
            async with aiohttp.ClientSession() as session:
                # Check health endpoint
                async with session.get(f"{grafana_url}/api/health", timeout=aiohttp.ClientTimeout(total=5)) as response:
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
                            "notes": f"API responding, database: {status}"
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
                "notes": f"Error: {str(e)}"
            }
    
    async def check_otel_collector(self) -> Dict[str, Any]:
        """
        Check OpenTelemetry Collector health
        
        Note: Unlike other services (Prometheus, Grafana, etc.) that expose version via their APIs,
        the OTel Collector health check endpoint doesn't include version metadata in its response,
        even with include_metadata: true. Version must come from deployment configuration.
        This is standard practice - version is a deployment-time concern, not runtime.
        """
        try:
            otel_url = os.getenv("OTEL_COLLECTOR_URL", "http://otel-collector:4318")
            health_check_url = os.getenv("OTEL_COLLECTOR_HEALTH_URL", "http://otel-collector:13133")
            
            version = "Unknown"
            status = "online"
            notes = "OTLP endpoint responding"
            
            async with aiohttp.ClientSession() as session:
                # Check health check endpoint for status (if configured)
                try:
                    async with session.get(f"{health_check_url}/", timeout=aiohttp.ClientTimeout(total=5)) as health_response:
                        if health_response.status == 200:
                            health_data = await health_response.json()
                            if "Server available" in health_data.get("status", "") or health_data.get("status") == "ready":
                                status = "online"
                                notes = "Health check endpoint responding"
                                # Note: Health check response doesn't include version even with include_metadata: true
                                # Version must come from deployment config (env var or container metadata)
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    # Health check endpoint not available - will check OTLP endpoint below
                    logger.debug(f"{health_check_url} health check not available")
                except Exception as e:
                    logger.debug(f"Error checking health endpoint: {e}")
                
                # Get version from zPages diagnostic endpoint (/debug/servicez)
                # This is the OpenTelemetry Collector's built-in diagnostic API, similar to other services
                # This is better than Docker API because it queries the service itself directly
                zpages_url = os.getenv("OTEL_COLLECTOR_ZPAGES_URL", "http://otel-collector:55679")
                try:
                    async with session.get(f"{zpages_url}/debug/servicez", timeout=aiohttp.ClientTimeout(total=5)) as zpages_response:
                        if zpages_response.status == 200:
                            html_content = await zpages_response.text()
                            # Parse version from HTML - zPages /debug/servicez shows version in Build Info table
                            import re
                            # Strategy: Extract Build Info section first, then find Version row
                            # HTML structure: <b>Build Info:</b><table>...<b>Version</b></td><td>|</td><td>0.138.0</td>...
                            version_match = None
                            build_info_section = re.search(r'<b>Build Info:</b>.*?</table>', html_content, re.IGNORECASE | re.DOTALL)
                            if build_info_section:
                                build_html = build_info_section.group(0)
                                # Find Version in bold, then capture version number after separator
                                version_match = re.search(r'<b>Version</b>.*?([0-9]+\.[0-9]+\.[0-9]+)', build_html, re.IGNORECASE | re.DOTALL)
                                if version_match:
                                    parsed_version = version_match.group(1).strip()
                                    # Verify it's a valid version number (X.Y.Z format)
                                    if re.match(r'^\d+\.\d+\.\d+$', parsed_version):
                                        version = parsed_version
                                        logger.debug(f"Got OTel Collector version from zPages: {version}")
                                    else:
                                        version_match = None
                            else:
                                # Fallback: search entire HTML for Version + version pattern
                                version_match = re.search(r'<b>Version</b>.*?([0-9]+\.[0-9]+\.[0-9]+)', html_content, re.IGNORECASE | re.DOTALL)
                                if version_match:
                                    parsed_version = version_match.group(1).strip()
                                    if re.match(r'^\d+\.\d+\.\d+$', parsed_version):
                                        version = parsed_version
                                        logger.debug(f"Got OTel Collector version from zPages (fallback): {version}")
                            
                            # Fall back to environment variable only if version parsing failed
                            if not version_match or version == "Unknown":
                                env_version = os.getenv("OTEL_COLLECTOR_VERSION")
                                if env_version:
                                    version = env_version
                                else:
                                    if version == "Unknown":
                                        logger.debug("Could not parse version from zPages response")
                        else:
                            # zPages unavailable - fall back to environment variable
                            env_version = os.getenv("OTEL_COLLECTOR_VERSION")
                            if env_version:
                                version = env_version
                            else:
                                version = "Unknown"
                                logger.debug(f"zPages endpoint returned HTTP {zpages_response.status}")
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    # zPages endpoint not available - fall back to environment variable
                    logger.debug(f"Could not query zPages endpoint for OTel Collector version: {e}")
                    env_version = os.getenv("OTEL_COLLECTOR_VERSION")
                    if env_version:
                        version = env_version
                    else:
                        version = "Unknown"
                
                # Verify OTLP endpoint is responding
                async with session.post(
                    f"{otel_url}/v1/metrics",
                    json={},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    # Even if it returns 400/405, that means the service is responding
                    if response.status in [200, 400, 405]:
                        return {
                            "component": "OpenTelemetry Collector",
                            "type": "Telemetry Gateway",
                            "status": status,
                            "version": version,
                            "purpose": "Collect, process, and export telemetry data (OTLP)",
                            "notes": notes
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
                "notes": "Cannot connect to OTLP endpoint - check container status"
            }
        except Exception as e:
            return {
                "component": "OpenTelemetry Collector",
                "type": "Telemetry Gateway",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Collect, process, and export telemetry data (OTLP)",
                "notes": f"Error: {str(e)}"
            }
    
    async def get_agent_status(self) -> List[Dict[str, Any]]:
        """Get agent status from database"""
        try:
            if not self.pg_pool:
                await self.init_connections()
            
            # Load instances.yaml to filter out obsolete agents
            instances = self._load_instances()
            valid_agent_ids = set(instances.keys())
            
            async with self.pg_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT agent_name, status, version, tps, memory_count, last_heartbeat, current_task_id
                    FROM agent_status
                    ORDER BY agent_name
                """)
                
                agents = []
                for row in rows:
                    # Skip agents not in instances.yaml (obsolete/stale entries)
                    agent_name = row['agent_name']
                    if agent_name not in valid_agent_ids:
                        logger.debug(f"Skipping obsolete agent entry: {agent_name}")
                        continue
                    
                    # Handle memory_count - asyncpg.Record uses dict-like access
                    memory_count = row['memory_count'] if row['memory_count'] is not None else 0
                    
                    # Use config/version.py as source of truth for agent version
                    # Database version may be stale if agent hasn't sent heartbeat recently
                    agent_version = get_agent_version(agent_name)
                    
                    agents.append({
                        "agent": self._get_display_name(agent_name),
                        "role": self._get_agent_role(agent_name),
                        "status": row['status'],
                        "version": agent_version,  # Use version from config/version.py
                        "tps": row['tps'],
                        "memory_count": memory_count,
                        "last_heartbeat": row['last_heartbeat'].isoformat() if row['last_heartbeat'] else None,
                        "current_task": row['current_task_id']
                    })
                
                return agents
        except Exception as e:
            logger.error(f"Failed to get agent status from database: {e}", exc_info=True)
            # Return mock data if database is unavailable - use instances.yaml as fallback
            instances = self._load_instances()
            mock_agents = []
            for agent_id, instance_info in instances.items():
                mock_agents.append({
                    "agent": instance_info['display_name'],
                    "role": instance_info['description'].split(' - ')[0] if ' - ' in instance_info['description'] else instance_info['description'],
                    "status": "offline",
                    "version": get_agent_version(agent_id),
                    "tps": 0,
                    "memory_count": 0
                })
            return mock_agents
    
    def _get_display_name(self, agent_id: str) -> str:
        """Get agent display name from agent ID using instances.yaml"""
        instances = self._load_instances()
        instance = instances.get(agent_id)
        if instance:
            return instance['display_name']
        # Fallback: title case the agent_id
        return agent_id.title()
    
    def _get_agent_role(self, agent_name: str) -> str:
        """Get agent role description using instances.yaml"""
        instances = self._load_instances()
        instance = instances.get(agent_name)
        if instance:
            # Use description field from instances.yaml, or map role to description
            description = instance.get('description', '')
            if description:
                # Extract role description from description field (e.g., "Task Lead - Governance..." -> "Task Lead")
                role_desc = description.split(' - ')[0] if ' - ' in description else description
                return role_desc
            # Fallback: map role to description
            role_to_desc = {
                'lead': 'Task Lead',
                'dev': 'Developer',
                'strat': 'Product Strategy',
                'creative': 'Creative Design',
                'qa': 'QA & Security',
                'data': 'Analytics',
                'finance': 'Finance & Ops',
                'comms': 'Communications',
                'curator': 'R&D & Curation',
                'audit': 'Monitoring & Audit'
            }
            return role_to_desc.get(instance.get('role', ''), 'Unknown')
        return "Unknown"
    
    async def update_agent_status_in_db(self, agent_status: Dict[str, Any]) -> Dict[str, Any]:
        """Update agent status in database"""
        try:
            if not self.pg_pool:
                await self.init_connections()
            
            async with self.pg_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO agent_status 
                    (agent_name, status, last_heartbeat, current_task_id, version, tps, memory_count, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (agent_name) 
                    DO UPDATE SET 
                        status = $2,
                        last_heartbeat = $3,
                        current_task_id = $4,
                        version = $5,
                        tps = $6,
                        memory_count = $7,
                        updated_at = $8
                """, agent_status['agent_name'], agent_status['status'], datetime.utcnow(),
                    agent_status.get('current_task_id'), agent_status.get('version'),
                    agent_status.get('tps', 0), agent_status.get('memory_count', 0) or 0,
                    datetime.utcnow())
                return {"status": "updated", "agent_name": agent_status['agent_name']}
        except Exception as e:
            logger.error(f"Failed to update agent status: {e}")
            raise

    async def submit_warmboot_request(self, request: WarmBootRequest) -> Dict[str, Any]:
        """Submit WarmBoot request to agents via RabbitMQ"""
        try:
            # Initialize connections if needed
            if not self.pg_pool:
                await self.init_connections()
            
            # Create ECID for this warmboot (Max will create the execution cycle)
            ecid = f"ECID-WB-{request.run_id.replace('run-', '')}"
            
            # Send messages to agents via RabbitMQ
            connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            channel = connection.channel()
            
            # Send to Max (lead agent) first
            max_message = {
                "task_id": f"{ecid}-main",
                "type": "governance",
                "ecid": ecid,
                "application": request.application,
                "request_type": request.request_type,
                "agents": request.agents,
                "priority": request.priority,
                "description": request.description,
                "requirements": request.requirements,
                "prd_path": request.prd_path,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            channel.basic_publish(
                exchange='',
                routing_key='max_tasks',
                body=json.dumps(max_message),
                properties=pika.BasicProperties(
                    content_type='application/json',
                    delivery_mode=2  # Make message persistent
                )
            )
            
            # NOTE: Max (Lead Agent) handles all task creation and delegation
            # The health check app only sends the governance task to Max
            # Max then processes the PRD and creates/delegates proper tasks to other agents
            # This ensures proper task orchestration through Max's governance layer
            
            connection.close()
            
            # Insert WarmBoot run into database for persistence and sequence tracking
            try:
                async with self.pg_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO warmboot_runs 
                        (run_id, run_name, squad_config, benchmark_target, start_time, status, metrics, scorecard)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (run_id) DO NOTHING
                    """, 
                    request.run_id,
                    request.application or "Unknown",
                    json.dumps({
                        "agents": request.agents,
                        "request_type": request.request_type,
                        "priority": request.priority,
                        "prd_path": request.prd_path,
                        "description": request.description,
                        "requirements": request.requirements
                    }),
                    request.application,
                    datetime.utcnow(),
                    "submitted",
                    json.dumps({}),
                    json.dumps({})
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
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to submit WarmBoot request: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get_warmboot_status(self, run_id: str) -> Dict[str, Any]:
        """Get status of WarmBoot request"""
        try:
            if not self.pg_pool:
                await self.init_connections()
            
            async with self.pg_pool.acquire() as conn:
                # Get task statuses from task_status table (like successful WarmBoot runs)
                task_statuses = await conn.fetch("""
                    SELECT task_id, agent_name, status, progress, updated_at
                    FROM task_status
                    WHERE task_id LIKE $1
                    ORDER BY agent_name
                """, f"{run_id}%")
                
                if not task_statuses:
                    return {
                        "run_id": run_id,
                        "status": "submitted",
                        "message": f"WarmBoot run {run_id} submitted to agents",
                        "task_statuses": [],
                        "timestamp": datetime.utcnow().isoformat()
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
                            "updated_at": task["updated_at"].isoformat() if task["updated_at"] else None
                        }
                        for task in task_statuses
                    ],
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to get WarmBoot status: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get_available_prds(self) -> List[Dict[str, Any]]:
        """Get available PRDs from warm-boot/prd/ directory"""
        try:
            import os
            import re
            
            prds = []
            prd_dir = "warm-boot/prd/"
            
            if not os.path.exists(prd_dir):
                return prds
            
            for filename in os.listdir(prd_dir):
                if filename.endswith('.md'):
                    file_path = os.path.join(prd_dir, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Extract PRD metadata
                        title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
                        pid_match = re.search(r'PID-(\d+)', content)
                        description_match = re.search(r'## Summary\s*\n(.+?)(?=\n##|\n#|$)', content, re.DOTALL)
                        
                        title = title_match.group(1) if title_match else filename.replace('.md', '')
                        pid = f"PID-{pid_match.group(1)}" if pid_match else "Unknown"
                        description = description_match.group(1).strip() if description_match else "No description available"
                        
                        prds.append({
                            "file_path": file_path,
                            "filename": filename,
                            "title": title,
                            "pid": pid,
                            "description": description[:200] + "..." if len(description) > 200 else description
                        })
                    except Exception as e:
                        # Skip files that can't be read
                        continue
            
            return prds
            
        except Exception as e:
            return []
    
    async def get_next_run_id(self) -> str:
        """Get next sequential run ID from database"""
        try:
            # Initialize connections if needed
            if not self.pg_pool:
                await self.init_connections()
            
            # Query database for highest run number
            async with self.pg_pool.acquire() as conn:
                result = await conn.fetchval("""
                    SELECT run_id FROM warmboot_runs 
                    WHERE run_id LIKE 'run-%'
                    ORDER BY 
                        CAST(SUBSTRING(run_id FROM 'run-([0-9]+)') AS INTEGER) DESC 
                    LIMIT 1
                """)
                
                if result:
                    # Extract number and increment
                    run_num = int(result.split("-")[1])
                    next_num = run_num + 1
                else:
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
                                except:
                                    continue
                    
                    next_num = max(existing_runs) + 1 if existing_runs else 1
                
                return f"run-{next_num:03d}"
            
        except Exception as e:
            logger.error(f"Error getting next run ID: {e}")
            return "run-001"
    
    async def get_agent_messages(self, since: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent agent messages for live communication feed"""
        try:
            if not self.pg_pool:
                await self.init_connections()
            
            async with self.pg_pool.acquire() as conn:
                # Get recent messages (last 50 or since timestamp)
                if since:
                    messages = await conn.fetch("""
                        SELECT timestamp, message_type, sender, recipient, payload, context, message_id
                        FROM squadcomms_messages
                        WHERE timestamp > $1
                        ORDER BY timestamp DESC
                        LIMIT 50
                    """, since)
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
                    if msg['payload']:
                        if isinstance(msg['payload'], dict):
                            content = msg['payload'].get('description', msg['payload'].get('content', 'Message sent'))
                        else:
                            content = str(msg['payload'])
                    
                    formatted_messages.append({
                        'timestamp': msg['timestamp'],
                        'message_type': msg['message_type'],
                        'sender': msg['sender'],
                        'recipient': msg['recipient'],
                        'content': content,
                        'metadata': msg['context'] or {}
                    })
                
                # Return in chronological order (oldest first)
                return list(reversed(formatted_messages))
                
        except Exception as e:
            return []

# Initialize health checker
health_checker = HealthChecker()

@app.on_event("startup")
async def startup_event():
    await health_checker.init_connections()

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
        health_checker.check_otel_collector()
    )
    return infra_checks

@app.get("/health/agents")
async def health_agents():
    """Get agent health status"""
    agents = await health_checker.get_agent_status()
    return agents

@app.post("/health/agents/status")
async def create_or_update_agent_status(agent_status: AgentStatusCreate):
    """Create or update agent status (heartbeat endpoint)"""
    try:
        result = await health_checker.update_agent_status_in_db({
            'agent_name': agent_status.agent_name,
            'status': agent_status.status,
            'current_task_id': agent_status.current_task_id,
            'version': agent_status.version,
            'tps': agent_status.tps,
            'memory_count': agent_status.memory_count
        })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update agent status: {str(e)}")

@app.put("/health/agents/status/{agent_name}")
async def update_agent_status(agent_name: str, update: AgentStatusUpdate):
    """Update agent status fields"""
    try:
        if not health_checker.pg_pool:
            await health_checker.init_connections()
        
        updates = []
        params = []
        param_count = 1
        
        if update.status:
            updates.append(f"status = ${param_count}")
            params.append(update.status)
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
        
        params.append(agent_name)
        query = f"UPDATE agent_status SET {', '.join(updates)} WHERE agent_name = ${param_count}"
        
        async with health_checker.pg_pool.acquire() as conn:
            result = await conn.execute(query, *params)
            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail=f"Agent status {agent_name} not found")
        
        return {"status": "updated", "agent_name": agent_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update agent status: {str(e)}")

@app.get("/health/agents/status/{agent_name}")
async def get_agent_status_by_name(agent_name: str):
    """Get agent status by agent_name"""
    try:
        if not health_checker.pg_pool:
            await health_checker.init_connections()
        
        async with health_checker.pg_pool.acquire() as conn:
            status = await conn.fetchrow("""
                SELECT * FROM agent_status WHERE agent_name = $1
            """, agent_name)
            
            if not status:
                raise HTTPException(status_code=404, detail=f"Agent status {agent_name} not found")
            
            return {
                "agent_name": status['agent_name'],
                "status": status['status'],
                "version": status['version'],
                "tps": status['tps'],
                "memory_count": status.get('memory_count', 0) or 0,
                "last_heartbeat": status['last_heartbeat'].isoformat() if status['last_heartbeat'] else None,
                "current_task_id": status['current_task_id']
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent status: {str(e)}")

@app.get("/health")
async def health_dashboard():
    """Get health dashboard HTML"""
    infra_status = await health_infra()
    agent_status = await health_agents()
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>SquadOps Health Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        <meta http-equiv="refresh" content="60">
        <style>
            .table th, .table td {{
                white-space: nowrap;
                padding: 8px 12px;
            }}
            .table th:nth-child(1), .table td:nth-child(1) {{ width: 15%; }}
            .table th:nth-child(2), .table td:nth-child(2) {{ width: 20%; }}
            .table th:nth-child(3), .table td:nth-child(3) {{ width: 15%; }}
            .table th:nth-child(4), .table td:nth-child(4) {{ width: 15%; }}
            .table th:nth-child(5), .table td:nth-child(5) {{ width: 10%; }}
            .table th:nth-child(6), .table td:nth-child(6) {{ width: 10%; }}
        </style>
    </head>
    <body>
        <div class="container mt-4">
            <h1 class="mb-4">🚀 SquadOps Health Dashboard</h1>
            <p class="text-muted">Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <div class="row">
                <div class="col-12">
                    <h2>Infrastructure Status</h2>
                    <div class="table-responsive">
                        <table class="table table-striped">
                            <thead>
                                <tr>
                                    <th>Component</th>
                                    <th>Type</th>
                                    <th>Status</th>
                                    <th>Version</th>
                                    <th>Notes</th>
                                </tr>
                            </thead>
                            <tbody>
    """
    
    for component in infra_status:
        status_icon = "✅" if component["status"] == "online" else "❌"
        status_class = "table-success" if component["status"] == "online" else "table-danger"
        
        html_content += f"""
                                <tr class="{status_class}">
                                    <td>{component['component']}</td>
                                    <td>{component['type']}</td>
                                    <td>{status_icon} {component['status']}</td>
                                    <td>{component['version']}</td>
                                    <td>{component['notes']}</td>
                                </tr>
        """
    
    html_content += """
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <div class="row mt-4">
                <div class="col-12">
                    <h2>Agent Status</h2>
                    <div class="table-responsive">
                        <table class="table table-striped">
                            <thead>
                                <tr>
                                    <th>Agent</th>
                                    <th>Role</th>
                                    <th>Status</th>
                                    <th>Version</th>
                                    <th>TPS</th>
                                    <th>Memories</th>
                                </tr>
                            </thead>
                            <tbody>
    """
    
    for agent in agent_status:
        status_icon = "✅" if agent["status"] == "online" else "❌"
        status_class = "table-success" if agent["status"] == "online" else "table-danger"
        
        html_content += f"""
                                <tr class="{status_class}">
                                    <td>{agent['agent']}</td>
                                    <td>{agent['role']}</td>
                                    <td>{status_icon} {agent['status']}</td>
                                    <td>{agent['version']}</td>
                                    <td>{agent['tps']}</td>
                                    <td>{agent.get('memory_count', 0)}</td>
                                </tr>
        """
    
    html_content += """
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <div class="mt-4">
                <h3>Quick Actions</h3>
                <a href="/warmboot/form" class="btn btn-success">🚀 Submit WarmBoot Request</a>
                <a href="/health/infra" class="btn btn-primary">Infrastructure JSON</a>
                <a href="/health/agents" class="btn btn-secondary">Agents JSON</a>
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

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
async def get_agent_messages(since: Optional[str] = None):
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
        row_agents = agents_list[i:i+3]
        row_class = 'row mt-2' if i > 0 else 'row'
        row_html = f'                        <div class="{row_class}">\n'
        for agent_id, instance_info in row_agents:
            display_name = instance_info['display_name']
            role = instance_info['role']
            # Check max and neo by default
            checked = 'checked' if agent_id in ['max', 'neo'] else ''
            row_html += f'''                            <div class="col-md-4">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="agent_{agent_id}" name="agents" value="{agent_id}" {checked}>
                                    <label class="form-check-label" for="agent_{agent_id}">{display_name} ({role.title()})</label>
                                </div>
                            </div>
'''
        row_html += '                        </div>'
        agent_checkboxes_html.append(row_html)
    
    agents_section = '\n'.join(agent_checkboxes_html)
    
    html_content = """
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
""" + agents_section + """
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
                            checkbox.checked = agent.status === 'online' || agent.agent === 'Max';
                            
                            // Disable Max (always required)
                            if (agent.agent === 'Max') {
                                checkbox.disabled = true;
                            }
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
                    media_type=response.headers.get('content-type', 'text/html')
                )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"error": f"HelloSquad application unavailable: {str(e)}"}
        )

@app.get("/hello-squad/")
async def proxy_hello_squad_root():
    """Proxy root request to HelloSquad application"""
    return await proxy_hello_squad("", None)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
