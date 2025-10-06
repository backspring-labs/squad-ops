from fastapi import FastAPI, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import asyncio
import aiohttp
import asyncpg
import redis.asyncio as redis
import pika
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import os
import sys
sys.path.append('/Users/jladd/Code/squad-ops')
from config.version import FRAMEWORK_VERSION, AGENT_VERSIONS, get_agent_version

app = FastAPI(title="SquadOps Health Check Service", version=FRAMEWORK_VERSION)

# Pydantic models for WarmBoot requests
class WarmBootRequest(BaseModel):
    run_id: str
    application: str
    request_type: str
    agents: List[str]
    priority: str
    description: str
    requirements: Optional[str] = None

# Configuration
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://squadops:squadops123@rabbitmq:5672/")
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://squadops:squadops123@postgres:5432/squadops")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
PREFECT_URL = os.getenv("PREFECT_URL", "http://prefect-server:4200/api")

class HealthChecker:
    def __init__(self):
        self.redis_client = None
        self.pg_pool = None
        
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
    
    async def get_agent_status(self) -> List[Dict[str, Any]]:
        """Get agent status from database"""
        try:
            if not self.pg_pool:
                await self.init_connections()
            
            async with self.pg_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT agent_name, status, version, tps, last_heartbeat, current_task_id
                    FROM agent_status
                    ORDER BY agent_name
                """)
                
            agents = []
            for row in rows:
                agents.append({
                    "agent": self._get_display_name(row['agent_name']),
                    "role": self._get_agent_role(row['agent_name']),
                    "status": row['status'],
                    "version": row['version'],
                    "tps": row['tps'],
                    "last_heartbeat": row['last_heartbeat'].isoformat() if row['last_heartbeat'] else None,
                    "current_task": row['current_task_id']
                })
            
            return agents
        except Exception as e:
            # Return mock data if database is unavailable - use config versions as fallback
            return [
                {"agent": "Max", "role": "Task Lead", "status": "offline", "version": get_agent_version("max"), "tps": 0},
                {"agent": "Neo", "role": "Developer", "status": "offline", "version": get_agent_version("neo"), "tps": 0},
                {"agent": "Nat", "role": "Product Strategy", "status": "offline", "version": get_agent_version("nat"), "tps": 0},
                {"agent": "Joi", "role": "Communications", "status": "offline", "version": get_agent_version("joi"), "tps": 0},
                {"agent": "Data", "role": "Analytics", "status": "offline", "version": get_agent_version("data"), "tps": 0},
                {"agent": "EVE", "role": "QA & Security", "status": "offline", "version": get_agent_version("eve"), "tps": 0},
                {"agent": "Quark", "role": "Finance & Ops", "status": "offline", "version": get_agent_version("quark"), "tps": 0},
                {"agent": "HAL", "role": "Monitoring", "status": "offline", "version": get_agent_version("hal"), "tps": 0},
                {"agent": "Og", "role": "R&D & Curation", "status": "offline", "version": get_agent_version("og"), "tps": 0},
                {"agent": "Glyph", "role": "Creative Design", "status": "offline", "version": get_agent_version("glyph"), "tps": 0}
            ]
    
    def _get_display_name(self, agent_id: str) -> str:
        """Get agent display name from agent ID"""
        display_names = {
            "max": "Max",
            "neo": "Neo", 
            "nat": "Nat",
            "joi": "Joi",
            "data": "Data",
            "eve": "EVE",
            "quark": "Quark",
            "hal": "HAL",
            "og": "Og",
            "glyph": "Glyph"
        }
        return display_names.get(agent_id, agent_id.title())
    
    def _get_agent_role(self, agent_name: str) -> str:
        """Get agent role description"""
        # Map lowercase agent IDs to role descriptions
        roles = {
            "max": "Task Lead",
            "neo": "Developer", 
            "nat": "Product Strategy",
            "joi": "Communications",
            "data": "Analytics",
            "eve": "QA & Security",
            "quark": "Finance & Ops",
            "hal": "Monitoring",
            "og": "R&D & Curation",
            "glyph": "Creative Design"
        }
        return roles.get(agent_name, "Unknown")
    
    async def submit_warmboot_request(self, request: WarmBootRequest) -> Dict[str, Any]:
        """Submit WarmBoot request to agents via RabbitMQ"""
        try:
            # Create task in database
            if not self.pg_pool:
                await self.init_connections()
            
            async with self.pg_pool.acquire() as conn:
                # Create main task record
                task_id = await conn.fetchval("""
                    INSERT INTO tasks (task_id, title, description, priority, status, created_at, assignee)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING task_id
                """, 
                f"{request.run_id}-main",
                f"WarmBoot {request.run_id}: {request.application}",
                request.description,
                request.priority,
                "PENDING",
                datetime.utcnow(),
                "max"  # Max is always the lead
                )
                
                # Create subtasks for each agent
                for agent in request.agents:
                    subtask_id = f"{request.run_id}-{agent}-001"
                    await conn.execute("""
                        INSERT INTO tasks (task_id, title, description, priority, status, created_at, assignee, parent_task_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    subtask_id,
                    f"{agent.title()} Task for {request.application}",
                    f"Agent-specific task for {request.description}",
                    request.priority,
                    "PENDING",
                    datetime.utcnow(),
                    agent,
                    task_id
                    )
            
            # Send messages to agents via RabbitMQ
            connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            channel = connection.channel()
            
            # Send to Max (lead agent) first
            max_message = {
                "message_type": "WARMBOOT_REQUEST",
                "run_id": request.run_id,
                "application": request.application,
                "request_type": request.request_type,
                "agents": request.agents,
                "priority": request.priority,
                "description": request.description,
                "requirements": request.requirements,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            channel.basic_publish(
                exchange='',
                routing_key='agent_max_queue',
                body=json.dumps(max_message),
                properties=pika.BasicProperties(
                    content_type='application/json',
                    delivery_mode=2  # Make message persistent
                )
            )
            
            # Send individual tasks to each agent
            for agent in request.agents:
                agent_message = {
                    "message_type": "TASK_ASSIGNMENT",
                    "task_id": f"{request.run_id}-{agent}-001",
                    "run_id": request.run_id,
                    "application": request.application,
                    "request_type": request.request_type,
                    "priority": request.priority,
                    "description": request.description,
                    "requirements": request.requirements,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                channel.basic_publish(
                    exchange='',
                    routing_key=f'agent_{agent}_queue',
                    body=json.dumps(agent_message),
                    properties=pika.BasicProperties(
                        content_type='application/json',
                        delivery_mode=2
                    )
                )
            
            connection.close()
            
            return {
                "status": "success",
                "message": f"WarmBoot request {request.run_id} submitted successfully",
                "task_id": task_id,
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
                # Get main task status
                main_task = await conn.fetchrow("""
                    SELECT task_id, title, status, created_at, updated_at
                    FROM tasks
                    WHERE task_id = $1
                """, f"{run_id}-main")
                
                # Get subtask statuses
                subtasks = await conn.fetch("""
                    SELECT task_id, assignee, status, created_at, updated_at
                    FROM tasks
                    WHERE parent_task_id = (SELECT task_id FROM tasks WHERE task_id = $1)
                    ORDER BY assignee
                """, f"{run_id}-main")
                
                if not main_task:
                    return {"status": "not_found", "message": f"WarmBoot run {run_id} not found"}
                
                return {
                    "run_id": run_id,
                    "main_task": dict(main_task),
                    "subtasks": [dict(task) for task in subtasks],
                    "overall_status": main_task['status'],
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to get WarmBoot status: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }

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
        health_checker.check_prefect()
    )
    return infra_checks

@app.get("/health/agents")
async def health_agents():
    """Get agent health status"""
    agents = await health_checker.get_agent_status()
    return agents

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
            .table th:nth-child(1), .table td:nth-child(1) {{ width: 20%; }}
            .table th:nth-child(2), .table td:nth-child(2) {{ width: 20%; }}
            .table th:nth-child(3), .table td:nth-child(3) {{ width: 15%; }}
            .table th:nth-child(4), .table td:nth-child(4) {{ width: 15%; }}
            .table th:nth-child(5), .table td:nth-child(5) {{ width: 30%; }}
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

@app.get("/warmboot/form")
async def warmboot_form():
    """Get WarmBoot request form HTML"""
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
                                    <option value="from-scratch">From-Scratch Build</option>
                                    <option value="feature-update">Feature Update</option>
                                    <option value="bug-fix">Bug Fix</option>
                                    <option value="refactor">Refactor</option>
                                    <option value="deployment">Deployment</option>
                                    <option value="testing">Testing</option>
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
                            <div class="col-md-4">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="agent_max" name="agents" value="max" checked>
                                    <label class="form-check-label" for="agent_max">Max (Lead)</label>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="agent_neo" name="agents" value="neo" checked>
                                    <label class="form-check-label" for="agent_neo">Neo (Dev)</label>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="agent_eve" name="agents" value="eve">
                                    <label class="form-check-label" for="agent_eve">EVE (QA)</label>
                                </div>
                            </div>
                        </div>
                        <div class="row mt-2">
                            <div class="col-md-4">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="agent_nat" name="agents" value="nat">
                                    <label class="form-check-label" for="agent_nat">Nat (Strategy)</label>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="agent_joi" name="agents" value="joi">
                                    <label class="form-check-label" for="agent_joi">Joi (Comms)</label>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="agent_data" name="agents" value="data">
                                    <label class="form-check-label" for="agent_data">Data (Analytics)</label>
                                </div>
                            </div>
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
                
                <div id="statusContainer" class="status-container">
                    <div id="statusMessage"></div>
                    <div id="statusDetails" class="mt-2"></div>
                </div>
            </div>
        </div>
        
        <script>
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
                            <strong>Task ID:</strong> ${result.task_id}<br>
                            <strong>Agents Notified:</strong> ${result.agents_notified.join(', ')}<br>
                            <strong>Timestamp:</strong> ${result.timestamp}<br>
                            <a href="/warmboot/status/${requestData.run_id}" class="btn btn-sm btn-outline-success mt-2">View Status</a>
                        `;
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
    return {"message": "SquadOps Health Check Service", "version": FRAMEWORK_VERSION}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
