"""
Integration test configuration for SquadOps
Uses testcontainers to provide real services for integration testing
"""

import asyncio
import os
import sys
import time
from pathlib import Path

import pytest
import pytest_asyncio
import requests
from testcontainers.postgres import PostgresContainer

# from testcontainers.rabbitmq import RabbitMQContainer  # TODO: Fix testcontainers version
from testcontainers.redis import RedisContainer

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, '/app')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'agents'))

# Import agent manager for container management
import os
import sys

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
            'RUNTIME_API_URL': os.getenv('RUNTIME_API_URL', 'http://localhost:8001'),
            'LOG_LEVEL': os.getenv('LOG_LEVEL', 'INFO'),
            'USE_LOCAL_LLM': os.getenv('USE_LOCAL_LLM', 'true')
        }
    
    return config

def check_service_health(service_name: str, host: str, port: int, timeout: int = 30, retries: int = 3) -> bool:
    """
    Check if a service is healthy and accepting connections with retry logic.
    
    Args:
        service_name: Name of the service
        host: Host address
        port: Port number
        timeout: Timeout per retry attempt in seconds
        retries: Number of retry attempts
        
    Returns:
        True if service is healthy, False otherwise
    """
    for attempt in range(1, retries + 1):
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                sock.close()
                if result == 0:
                    if attempt > 1:
                        print(f"✅ {service_name} is healthy on {host}:{port} (succeeded on attempt {attempt})")
                    else:
                        print(f"✅ {service_name} is healthy on {host}:{port}")
                    return True
            except Exception:
                pass
            time.sleep(1)
        
        if attempt < retries:
            print(f"⚠️  {service_name} health check attempt {attempt}/{retries} failed on {host}:{port}, retrying...")
            time.sleep(2)  # Brief pause between retries
    
    print(f"❌ {service_name} failed health check on {host}:{port} after {retries} attempts ({timeout}s each)")
    print(f"   Troubleshooting: Check if {service_name} is running with 'docker ps' or 'systemctl status {service_name.lower()}'")
    return False

def check_rabbitmq_management(host: str, port: int, timeout: int = 30, retries: int = 3) -> bool:
    """
    Check RabbitMQ management interface with retry logic.
    
    Args:
        host: Host address
        port: Port number
        timeout: Timeout per retry attempt in seconds
        retries: Number of retry attempts
        
    Returns:
        True if RabbitMQ management is healthy, False otherwise
    """
    for attempt in range(1, retries + 1):
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"http://{host}:{port}/api/overview", timeout=5)
                if response.status_code == 200:
                    if attempt > 1:
                        print(f"✅ RabbitMQ management is healthy on {host}:{port} (succeeded on attempt {attempt})")
                    else:
                        print(f"✅ RabbitMQ management is healthy on {host}:{port}")
                    return True
            except Exception:
                pass
            time.sleep(1)
        
        if attempt < retries:
            print(f"⚠️  RabbitMQ management health check attempt {attempt}/{retries} failed on {host}:{port}, retrying...")
            time.sleep(2)  # Brief pause between retries
    
    print(f"❌ RabbitMQ management failed health check on {host}:{port} after {retries} attempts ({timeout}s each)")
    print(f"   Troubleshooting: RabbitMQ management is optional but recommended. Check with 'docker ps' or visit http://{host}:{port}")
    return False

def check_agent_containers(agents: list = ['max', 'neo'], retries: int = 3) -> bool:
    """
    Check that agent containers are running and healthy with retry logic.
    
    Args:
        agents: List of agent names to check
        retries: Number of retry attempts
    
    Returns:
        True if all agent containers are healthy, False otherwise
    """
    print(f"🤖 Checking agent containers: {agents}")
    
    for attempt in range(1, retries + 1):
        try:
            manager = AgentManager()
            
            # Get container info
            container_info = manager.get_agent_container_info()
            
            all_healthy = True
            failed_agents = []
            
            for agent in agents:
                if agent not in container_info:
                    print(f"❌ Agent {agent} not found in configuration")
                    all_healthy = False
                    failed_agents.append(agent)
                    continue
                    
                info = container_info[agent]
                if not info['running']:
                    print(f"❌ Agent {agent} ({info['container_name']}) is not running: {info['status']}")
                    all_healthy = False
                    failed_agents.append(agent)
                else:
                    if attempt > 1:
                        print(f"✅ Agent {agent} ({info['container_name']}) is running: {info['status']} (succeeded on attempt {attempt})")
                    else:
                        print(f"✅ Agent {agent} ({info['container_name']}) is running: {info['status']}")
            
            if all_healthy:
                return True
            
            if attempt < retries:
                print(f"⚠️  Agent container check attempt {attempt}/{retries} failed for: {failed_agents}, retrying...")
                time.sleep(2)  # Brief pause between retries
            else:
                print(f"❌ Agent containers failed health check after {retries} attempts")
                print("   Troubleshooting: Start agents with 'docker-compose up -d max neo' or check logs with 'docker logs squadops-max'")
                return False
                
        except Exception as e:
            if attempt < retries:
                print(f"⚠️  Agent container check attempt {attempt}/{retries} failed with error: {e}, retrying...")
                time.sleep(2)
            else:
                print(f"❌ Agent container check failed after {retries} attempts: {e}")
                print("   Troubleshooting: Check Docker is running and agent containers exist")
                return False
    
    return False

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
    """
    Check that all required services are running before integration tests.
    Provides detailed error messages and troubleshooting hints.
    """
    print("🔍 Checking required services for integration tests...")
    print("="*70)
    
    service_status = {}
    all_services_healthy = True
    
    # Check PostgreSQL
    print("\n📊 Checking PostgreSQL...")
    postgres_healthy = check_service_health("PostgreSQL", "localhost", 5432, timeout=30, retries=3)
    service_status['postgres'] = postgres_healthy
    if not postgres_healthy:
        all_services_healthy = False
        print("   💡 To start PostgreSQL: docker-compose up -d postgres")
        pytest.skip("PostgreSQL is not running on localhost:5432. Start with 'docker-compose up -d postgres'")
    
    # Check Redis
    print("\n📊 Checking Redis...")
    redis_healthy = check_service_health("Redis", "localhost", 6379, timeout=30, retries=3)
    service_status['redis'] = redis_healthy
    if not redis_healthy:
        all_services_healthy = False
        print("   💡 To start Redis: docker-compose up -d redis")
        pytest.skip("Redis is not running on localhost:6379. Start with 'docker-compose up -d redis'")
    
    # Check RabbitMQ
    print("\n📊 Checking RabbitMQ...")
    rabbitmq_healthy = check_service_health("RabbitMQ", "localhost", 5672, timeout=30, retries=3)
    service_status['rabbitmq'] = rabbitmq_healthy
    if not rabbitmq_healthy:
        all_services_healthy = False
        print("   💡 To start RabbitMQ: docker-compose up -d rabbitmq")
        pytest.skip("RabbitMQ is not running on localhost:5672. Start with 'docker-compose up -d rabbitmq'")
    
    # Check RabbitMQ Management (optional but nice to have)
    print("\n📊 Checking RabbitMQ Management (optional)...")
    rabbitmq_mgmt_healthy = check_rabbitmq_management("localhost", 15672, timeout=10, retries=2)
    service_status['rabbitmq_management'] = rabbitmq_mgmt_healthy
    if not rabbitmq_mgmt_healthy:
        print("   ⚠️  RabbitMQ Management is optional but recommended for debugging")
    
    # Check agent containers
    print("\n📊 Checking agent containers...")
    agents_healthy = check_agent_containers(['max', 'neo'], retries=3)
    service_status['agent_containers'] = agents_healthy
    if not agents_healthy:
        all_services_healthy = False
        print("   💡 To start agents: docker-compose up -d max neo")
        pytest.skip("Agent containers (Max/Neo) are not running. Start with 'docker-compose up -d max neo'")
    
    # Print summary
    print("\n" + "="*70)
    print("Service Health Summary:")
    print("="*70)
    for service, healthy in service_status.items():
        status = "✅" if healthy else "❌"
        print(f"{status} {service.upper()}: {'Healthy' if healthy else 'Unavailable'}")
    
    if all_services_healthy:
        print("\n✅ All required services are healthy!")
    else:
        print("\n❌ Some required services are unavailable")
        print("\nTroubleshooting:")
        print("  1. Check service status: docker ps")
        print("  2. Start services: docker-compose up -d postgres redis rabbitmq max neo")
        print("  3. Check logs: docker logs squadops-max")
        print("  4. Run service check: python tests/integration/check_services.py")
    
    print("="*70 + "\n")
    yield

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session")
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
                    cycle_id VARCHAR(50) PRIMARY KEY,
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
def integration_config(postgres_container, rabbitmq_container, redis_container) -> dict[str, str]:
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
        'runtime_api_url': config['RUNTIME_API_URL'],
        'log_level': config['LOG_LEVEL'],
        'use_local_llm': config['USE_LOCAL_LLM']
    }

@pytest_asyncio.fixture
async def clean_database(postgres_container):
    """
    Clean database state before and after each test.
    Ensures proper test isolation by resetting all tables used in integration tests.
    """
    import asyncpg
    
    # Get connection URL
    postgres_url = postgres_container.get_connection_url()
    if postgres_url.startswith('postgresql+psycopg2://'):
        postgres_url = postgres_url.replace('postgresql+psycopg2://', 'postgresql://')
    
    # Create connection pool for cleanup
    db_pool = await asyncpg.create_pool(postgres_url, min_size=1, max_size=3)
    
    try:
        async with db_pool.acquire() as conn:
            # Ensure all tables exist before truncating
            await conn.execute("""
                -- Create projects table (SIP-0047)
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT now(),
                    updated_at TIMESTAMP DEFAULT now()
                );
                
                -- Create tables if they don't exist (for test isolation)
                CREATE TABLE IF NOT EXISTS cycle (
                    cycle_id TEXT PRIMARY KEY,
                    pid TEXT NOT NULL,
                    project_id TEXT REFERENCES projects(project_id),
                    run_type TEXT,
                    title TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT now(),
                    initiated_by TEXT,
                    status TEXT DEFAULT 'active',
                    notes TEXT
                );
                
                CREATE TABLE IF NOT EXISTS agent_task_log (
                    task_id TEXT PRIMARY KEY,
                    pid TEXT,
                    cycle_id TEXT,
                    agent TEXT NOT NULL,
                    agent_id TEXT,
                    task_name TEXT,
                    task_type TEXT,
                    inputs JSONB DEFAULT '{}'::jsonb,
                    phase TEXT,
                    status TEXT NOT NULL,
                    priority TEXT,
                    description TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    duration INTERVAL,
                    artifacts JSONB,
                    dependencies TEXT[],
                    error_log TEXT,
                    delegated_by TEXT,
                    delegated_to TEXT,
                    project_id TEXT,
                    pulse_id TEXT,
                    correlation_id TEXT,
                    causation_id TEXT,
                    trace_id TEXT,
                    span_id TEXT,
                    metrics JSONB,
                    created_at TIMESTAMP DEFAULT now()
                );
                
                CREATE TABLE IF NOT EXISTS task_status (
                    task_id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress FLOAT DEFAULT 0.0,
                    eta TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS agent_status (
                    agent_name TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    current_task_id TEXT,
                    version TEXT,
                    tps INTEGER DEFAULT 0,
                    memory_count INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS squad_mem_pool (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent TEXT NOT NULL,
                    ns TEXT NOT NULL DEFAULT 'squad',
                    pid TEXT,
                    cycle_id TEXT,
                    tags TEXT[],
                    importance FLOAT DEFAULT 0.7,
                    status TEXT DEFAULT 'pending',
                    validator TEXT,
                    content JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
                
                CREATE TABLE IF NOT EXISTS memory_reuse_log (
                    id SERIAL PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    accessed_at TIMESTAMPTZ DEFAULT now(),
                    query_context TEXT
                );
                
                CREATE TABLE IF NOT EXISTS warmboot_runs (
                    run_id TEXT PRIMARY KEY,
                    run_name TEXT NOT NULL,
                    squad_config JSONB,
                    benchmark_target TEXT,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    status TEXT NOT NULL,
                    metrics JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Truncate all tables used in integration tests
            # Use CASCADE to handle foreign key constraints
            await conn.execute("""
                TRUNCATE TABLE 
                    execution_cycle,
                    agent_task_log,
                    task_status,
                    agent_status,
                    squad_mem_pool,
                    projects,
                    memory_reuse_log,
                    warmboot_runs
                RESTART IDENTITY CASCADE;
            """)
            
            # Reset sequences
            await conn.execute("""
                -- Reset any sequences if they exist
                DO $$
                DECLARE
                    seq_name TEXT;
                BEGIN
                    FOR seq_name IN 
                        SELECT sequence_name 
                        FROM information_schema.sequences 
                        WHERE sequence_schema = 'public'
                    LOOP
                        EXECUTE 'ALTER SEQUENCE ' || seq_name || ' RESTART WITH 1';
                    END LOOP;
                END $$;
            """)
            
            # Create permanent placeholder project for smoke tests
            # This satisfies FK constraints without requiring per-test project creation
            await conn.execute("""
                INSERT INTO projects (project_id, name, description)
                VALUES ('smoke-test-placeholder-project', 'Smoke Test Placeholder Project', 
                        'Permanent placeholder project for ACI smoke tests')
                ON CONFLICT (project_id) DO UPDATE
                SET name = EXCLUDED.name,
                    description = EXCLUDED.description;
            """)
        
        yield
        
        # Clean up after test
        async with db_pool.acquire() as conn:
            await conn.execute("""
                TRUNCATE TABLE 
                    execution_cycle,
                    agent_task_log,
                    task_status,
                    agent_status,
                    squad_mem_pool,
                    memory_reuse_log,
                    warmboot_runs
                RESTART IDENTITY CASCADE;
            """)
    finally:
        await db_pool.close()

@pytest_asyncio.fixture
async def clean_redis(redis_container):
    """Clean Redis state before each test"""
    import redis
    redis_client = redis.Redis.from_url(redis_container.get_connection_url())
    redis_client.flushall()
    yield
    redis_client.flushall()

@pytest_asyncio.fixture
async def clean_rabbitmq(rabbitmq_container):
    """
    Clean RabbitMQ queues and exchanges before and after each test.
    Ensures proper test isolation by purging all queues used in integration tests.
    """
    import aio_pika
    
    # Get RabbitMQ connection URL
    rabbitmq_url = rabbitmq_container.get_connection_url()
    
    # List of queues that may be used in integration tests
    # Based on agent names and common queue patterns
    agent_queues = [
        'max_tasks', 'max_comms',
        'neo_tasks', 'neo_comms',
        'eve_tasks', 'eve_comms',
        'nat_tasks', 'nat_comms',
        'data_tasks', 'data_comms',
        'quark_tasks', 'quark_comms',
        'joi_tasks', 'joi_comms',
        'og_tasks', 'og_comms',
        'hal_tasks', 'hal_comms',
        'squad_broadcast',
        'task.developer.assign',
        'task.developer.completed',
        'task.qa.assign',
        'task.qa.completed'
    ]
    
    async def purge_queues():
        """Purge all known queues"""
        try:
            connection = await aio_pika.connect_robust(rabbitmq_url)
            channel = await connection.channel()
            
            purged_count = 0
            for queue_name in agent_queues:
                try:
                    queue = await channel.declare_queue(queue_name, passive=True)
                    await queue.purge()
                    purged_count += 1
                except Exception:
                    # Queue doesn't exist yet, which is fine
                    pass
            
            # Also try to purge any dynamically created queues
            # List all queues using RabbitMQ Management API if available
            try:
                import requests
                config = load_test_config()
                mgmt_url = f"http://{config.get('RABBITMQ_HOST', 'localhost')}:15672"
                auth = (config.get('RABBITMQ_USER', 'squadops'), config.get('RABBITMQ_PASSWORD', 'squadops123'))
                
                response = requests.get(f"{mgmt_url}/api/queues", auth=auth, timeout=5)
                if response.status_code == 200:
                    queues = response.json()
                    for queue_info in queues:
                        queue_name = queue_info.get('name', '')
                        if queue_name and queue_name not in agent_queues:
                            try:
                                queue = await channel.declare_queue(queue_name, passive=True)
                                await queue.purge()
                                purged_count += 1
                            except Exception:
                                pass
            except Exception:
                # Management API not available or failed, continue without it
                pass
            
            await channel.close()
            await connection.close()
            
            if purged_count > 0:
                print(f"🧹 Purged {purged_count} RabbitMQ queues")
                
        except Exception as e:
            # If RabbitMQ cleanup fails, log but don't fail the test
            print(f"⚠️  Failed to clean RabbitMQ queues: {e}")
            print("   This is non-fatal - tests will continue but may have queue pollution")
    
    # Clean before test
    await purge_queues()
    
    yield
    
    # Clean after test
    await purge_queues()

# Retry decorator for flaky network-dependent tests
# Note: This decorator should be applied AFTER @pytest.mark.asyncio
# The retry logic is implemented within the test function itself
def retry_on_network_error(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator to retry tests that may fail due to transient network issues.
    
    This decorator wraps the test function and adds retry logic for network errors.
    It preserves the async function signature and pytest fixture parameters.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
    
    Usage:
        @pytest.mark.integration
        @pytest.mark.asyncio
        @retry_on_network_error(max_retries=3)
        async def test_network_dependent(integration_config, ...):
            # Test code here
    """
    def decorator(func):
        import asyncio
        import functools
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except (ConnectionError, TimeoutError, OSError) as e:
                    last_exception = e
                    error_msg = str(e).lower()
                    
                    # Only retry on network-related errors
                    network_errors = ['connection', 'timeout', 'network', 'unreachable', 'refused', 'name or service not known']
                    if not any(err in error_msg for err in network_errors):
                        # Not a network error, re-raise immediately
                        raise
                    
                    if attempt < max_retries:
                        wait_time = delay * (backoff ** (attempt - 1))
                        print(f"⚠️  Network error on attempt {attempt}/{max_retries}: {e}")
                        print(f"   Retrying in {wait_time:.1f}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"❌ Network error after {max_retries} attempts: {e}")
                        raise
                except Exception as e:
                    # For non-network errors, check error message
                    error_msg = str(e).lower()
                    network_errors = ['connection', 'timeout', 'network', 'unreachable', 'refused', 'name or service not known']
                    
                    if any(err in error_msg for err in network_errors):
                        last_exception = e
                        if attempt < max_retries:
                            wait_time = delay * (backoff ** (attempt - 1))
                            print(f"⚠️  Network error on attempt {attempt}/{max_retries}: {e}")
                            print(f"   Retrying in {wait_time:.1f}s...")
                            await asyncio.sleep(wait_time)
                        else:
                            print(f"❌ Network error after {max_retries} attempts: {e}")
                            raise
                    else:
                        # Not a network error, re-raise immediately
                        raise
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator

# Integration test markers
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow
pytest.mark.database = pytest.mark.database
pytest.mark.rabbitmq = pytest.mark.rabbitmq
pytest.mark.redis = pytest.mark.redis
pytest.mark.service_postgres = pytest.mark.service_postgres
pytest.mark.service_rabbitmq = pytest.mark.service_rabbitmq
pytest.mark.service_redis = pytest.mark.service_redis
pytest.mark.service_ollama = pytest.mark.service_ollama
pytest.mark.agent_containers = pytest.mark.agent_containers


