"""
Integration test configuration for SquadOps
Uses testcontainers to provide real services for integration testing
"""

import pytest
import asyncio
import os
import sys
import time
import requests
from typing import AsyncGenerator, Dict, Any
from testcontainers.postgres import PostgresContainer
# from testcontainers.rabbitmq import RabbitMQContainer  # TODO: Fix testcontainers version
from testcontainers.redis import RedisContainer
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, '/app')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'agents'))

# Import agent manager for container management
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from agent_manager import AgentManager

def load_test_config():
    """Load integration test configuration from file"""
    config_file = Path(__file__).parent / 'test_config.env'
    config = {}
    
    if config_file.exists():
        with open(config_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key] = value
    else:
        # Fallback to environment variables
        config = {
            'POSTGRES_URL': os.getenv('POSTGRES_URL', 'postgresql://squadops:squadops123@localhost:5432/squadops'),
            'RABBITMQ_USER': os.getenv('RABBITMQ_USER', 'squadops'),
            'RABBITMQ_PASSWORD': os.getenv('RABBITMQ_PASSWORD', 'squadops123'),
            'RABBITMQ_HOST': os.getenv('RABBITMQ_HOST', 'localhost'),
            'RABBITMQ_PORT': os.getenv('RABBITMQ_PORT', '5672'),
            'REDIS_URL': os.getenv('REDIS_URL', 'redis://localhost:6379'),
            'OLLAMA_URL': os.getenv('OLLAMA_URL', 'http://localhost:11434'),
            'TASK_API_URL': os.getenv('TASK_API_URL', 'http://localhost:8001'),
            'LOG_LEVEL': os.getenv('LOG_LEVEL', 'INFO'),
            'USE_LOCAL_LLM': os.getenv('USE_LOCAL_LLM', 'true')
        }
    
    return config

def check_service_health(service_name: str, host: str, port: int, timeout: int = 30) -> bool:
    """Check if a service is healthy and accepting connections"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                print(f"✅ {service_name} is healthy on {host}:{port}")
                return True
        except Exception as e:
            pass
        time.sleep(1)
    
    print(f"❌ {service_name} failed health check on {host}:{port} after {timeout}s")
    return False

def check_rabbitmq_management(host: str, port: int, timeout: int = 30) -> bool:
    """Check RabbitMQ management interface"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"http://{host}:{port}/api/overview", timeout=5)
            if response.status_code == 200:
                print(f"✅ RabbitMQ management is healthy on {host}:{port}")
                return True
        except Exception as e:
            pass
        time.sleep(1)
    
    print(f"❌ RabbitMQ management failed health check on {host}:{port} after {timeout}s")
    return False

def check_agent_containers(agents: list = ['max', 'neo']) -> bool:
    """Check that agent containers are running and healthy"""
    print(f"🤖 Checking agent containers: {agents}")
    
    manager = AgentManager()
    
    # Get container info
    container_info = manager.get_agent_container_info()
    
    all_healthy = True
    for agent in agents:
        if agent not in container_info:
            print(f"❌ Agent {agent} not found in configuration")
            all_healthy = False
            continue
            
        info = container_info[agent]
        if not info['running']:
            print(f"❌ Agent {agent} ({info['container_name']}) is not running: {info['status']}")
            all_healthy = False
        else:
            print(f"✅ Agent {agent} ({info['container_name']}) is running: {info['status']}")
    
    return all_healthy

async def ensure_agents_running(agents: list = ['max', 'neo']) -> bool:
    """Ensure agent containers are running and healthy"""
    print(f"🚀 Ensuring agents are running: {agents}")
    
    manager = AgentManager()
    
    # Check if agents need rebuild (code is newer than image)
    needs_rebuild = []
    for agent in agents:
        if await manager.check_code_freshness(agent):
            print(f"🔄 Agent {agent} needs rebuild (code is newer than image)")
            needs_rebuild.append(agent)
    
    # Rebuild if needed
    if needs_rebuild:
        print(f"🔨 Rebuilding agents: {needs_rebuild}")
        if not await manager.rebuild_agents(needs_rebuild):
            print(f"❌ Failed to rebuild agents: {needs_rebuild}")
            return False
    
    # Ensure all agents are running
    if not await manager.ensure_agents_running(agents):
        print(f"❌ Failed to ensure agents are running: {agents}")
        return False
    
    print(f"✅ All agents are running and healthy: {agents}")
    return True

@pytest.fixture(scope="session", autouse=True)
def check_required_services():
    """Check that all required services are running before integration tests"""
    print("🔍 Checking required services for integration tests...")
    
    # Check PostgreSQL
    if not check_service_health("PostgreSQL", "localhost", 5432):
        pytest.skip("PostgreSQL is not running on localhost:5432")
    
    # Check Redis
    if not check_service_health("Redis", "localhost", 6379):
        pytest.skip("Redis is not running on localhost:6379")
    
    # Check RabbitMQ
    if not check_service_health("RabbitMQ", "localhost", 5672):
        pytest.skip("RabbitMQ is not running on localhost:5672")
    
    # Check RabbitMQ Management (optional but nice to have)
    check_rabbitmq_management("localhost", 15672, timeout=10)
    
    # Check agent containers
    if not check_agent_containers(['max', 'neo']):
        pytest.skip("Agent containers (Max/Neo) are not running. Run 'docker-compose up -d max neo' to start them.")
    
    print("✅ All required services are healthy!")
    yield

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def ensure_agents_running_fixture():
    """Ensure agent containers are running and healthy before integration tests"""
    print("🤖 Ensuring agent containers are running...")
    
    success = await ensure_agents_running(['max', 'neo'])
    if not success:
        pytest.skip("Failed to ensure agent containers are running. Check Docker and agent configuration.")
    
    yield
    
    # Optionally stop agents after tests (commented out to keep them running)
    # print("🛑 Stopping agent containers after tests...")
    # manager = AgentManager()
    # await manager.stop_agents(['max', 'neo'])

@pytest.fixture
def agent_manager():
    """Provide AgentManager instance for tests"""
    return AgentManager()

@pytest.fixture(scope="session")
def postgres_container():
    """PostgreSQL container for integration tests"""
    # Use external PostgreSQL if available, otherwise use testcontainer
    if check_service_health("PostgreSQL", "localhost", 5432, timeout=5):
        print("📦 Using external PostgreSQL service")
        class ExternalPostgres:
            def get_connection_url(self):
                return "postgresql://squadops:squadops123@localhost:5432/squadops"
        yield ExternalPostgres()
    else:
        print("📦 Starting PostgreSQL testcontainer")
        with PostgresContainer("postgres:15") as postgres:
            # Set up database schema
            postgres.exec([
                "psql", "-U", postgres.username, "-d", postgres.dbname, "-c",
                """
                CREATE TABLE IF NOT EXISTS execution_cycles (
                    ecid VARCHAR(50) PRIMARY KEY,
                    pid VARCHAR(50),
                    run_type VARCHAR(50),
                    initiated_by VARCHAR(100),
                    prd_path TEXT,
                    status VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS task_status (
                    task_id VARCHAR(100) PRIMARY KEY,
                    agent_name VARCHAR(100),
                    status VARCHAR(50),
                    progress FLOAT DEFAULT 0.0,
                    eta VARCHAR(50),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS agent_task_logs (
                    id SERIAL PRIMARY KEY,
                    task_id VARCHAR(100),
                    agent_name VARCHAR(100),
                    task_name VARCHAR(200),
                    task_status VARCHAR(50),
                    start_time TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS agent_heartbeats (
                    id SERIAL PRIMARY KEY,
                    agent_name VARCHAR(100),
                    status VARCHAR(50),
                    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB
                );
                """
            ])
            yield postgres

@pytest.fixture(scope="session")
def rabbitmq_container():
    """RabbitMQ container for integration tests"""
    # TODO: Fix testcontainers RabbitMQ import
    # with RabbitMQContainer() as rabbitmq:
    #     yield rabbitmq
    # Use external RabbitMQ with configuration from file
    config = load_test_config()
    
    class MockRabbitMQ:
        def get_connection_url(self):
            return f"amqp://{config['RABBITMQ_USER']}:{config['RABBITMQ_PASSWORD']}@{config['RABBITMQ_HOST']}:{config['RABBITMQ_PORT']}"
    yield MockRabbitMQ()

@pytest.fixture(scope="session")
def redis_container():
    """Redis container for integration tests"""
    # Use external Redis if available, otherwise use testcontainer
    if check_service_health("Redis", "localhost", 6379, timeout=5):
        print("📦 Using external Redis service")
        class ExternalRedis:
            def get_exposed_port(self, port):
                return port
            def get_connection_url(self):
                return "redis://localhost:6379"
        yield ExternalRedis()
    else:
        print("📦 Starting Redis testcontainer")
        with RedisContainer() as redis:
            yield redis

@pytest.fixture
def integration_config(postgres_container, rabbitmq_container, redis_container) -> Dict[str, str]:
    """Configuration for integration tests using real containers"""
    config = load_test_config()
    
    # Convert postgresql+psycopg2 URL to postgresql for asyncpg compatibility
    postgres_url = postgres_container.get_connection_url()
    if postgres_url.startswith('postgresql+psycopg2://'):
        postgres_url = postgres_url.replace('postgresql+psycopg2://', 'postgresql://')
    
    return {
        'database_url': postgres_url,
        'redis_url': f"redis://localhost:{redis_container.get_exposed_port(6379)}",
        'rabbitmq_url': rabbitmq_container.get_connection_url(),
        'ollama_url': config['OLLAMA_URL'],
        'task_api_url': config['TASK_API_URL'],
        'log_level': config['LOG_LEVEL'],
        'use_local_llm': config['USE_LOCAL_LLM']
    }

@pytest.fixture
async def clean_database(postgres_container):
    """Clean database state before each test"""
    # Clear all tables
    postgres_container.exec([
        "psql", "-U", postgres_container.username, "-d", postgres_container.dbname, "-c",
        """
        TRUNCATE TABLE execution_cycles, task_status, agent_task_logs, agent_heartbeats RESTART IDENTITY CASCADE;
        """
    ])
    yield
    # Clean up after test
    postgres_container.exec([
        "psql", "-U", postgres_container.username, "-d", postgres_container.dbname, "-c",
        """
        TRUNCATE TABLE execution_cycles, task_status, agent_task_logs, agent_heartbeats RESTART IDENTITY CASCADE;
        """
    ])

@pytest.fixture
async def clean_redis(redis_container):
    """Clean Redis state before each test"""
    import redis
    redis_client = redis.Redis.from_url(redis_container.get_connection_url())
    redis_client.flushall()
    yield
    redis_client.flushall()

@pytest.fixture
async def clean_rabbitmq(rabbitmq_container):
    """Clean RabbitMQ queues before each test"""
    # TODO: Re-enable when testcontainers RabbitMQ is fixed
    # For now, just yield without doing anything
    yield
    # import pika
    # connection = pika.BlockingConnection(
    #     pika.URLParameters(rabbitmq_container.get_connection_url())
    # )
    # channel = connection.channel()
    # 
    # # Purge all queues
    # try:
    #     channel.queue_purge('max')
    #     channel.queue_purge('neo')
    #     channel.queue_purge('eve')
    #     channel.queue_purge('nat')
    #     channel.queue_purge('data')
    #     channel.queue_purge('quark')
    #     channel.queue_purge('joi')
    #     channel.queue_purge('og')
    #     channel.queue_purge('hal')
    # except:
    #     pass  # Queues may not exist yet
    # 
    # connection.close()
    # yield
    # 
    # # Clean up after test
    # connection = pika.BlockingConnection(
    #     pika.URLParameters(rabbitmq_container.get_connection_url())
    # )
    # channel = connection.channel()
    # try:
    #     channel.queue_purge('max')
    #     channel.queue_purge('neo')
    #     channel.queue_purge('eve')
    #     channel.queue_purge('nat')
    #     channel.queue_purge('data')
    #     channel.queue_purge('quark')
    #     channel.queue_purge('joi')
    #     channel.queue_purge('og')
    #     channel.queue_purge('hal')
    # except:
    #     pass
    # connection.close()

# Integration test markers
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow
pytest.mark.database = pytest.mark.database
pytest.mark.rabbitmq = pytest.mark.rabbitmq
pytest.mark.redis = pytest.mark.redis


