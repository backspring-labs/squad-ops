from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import asyncio
import aiohttp
import asyncpg
import redis.asyncio as redis
import pika
import json
from datetime import datetime
from typing import List, Dict, Any
import os
import sys
sys.path.append('/Users/jladd/Code/squad-ops')
from config.version import FRAMEWORK_VERSION, AGENT_VERSIONS, get_agent_version

app = FastAPI(title="SquadOps Health Check Service", version=FRAMEWORK_VERSION)

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
                <a href="/health/infra" class="btn btn-primary">Infrastructure JSON</a>
                <a href="/health/agents" class="btn btn-secondary">Agents JSON</a>
            </div>
        </div>
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
