"""
Integration test configuration for SquadOps
Uses testcontainers to provide real services for integration testing
"""

import pytest
import asyncio
import os
import sys
from typing import AsyncGenerator, Dict, Any
from testcontainers.postgres import PostgresContainer
# from testcontainers.rabbitmq import RabbitMQContainer  # TODO: Fix testcontainers version
from testcontainers.redis import RedisContainer

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, '/app')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'agents'))

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def postgres_container():
    """PostgreSQL container for integration tests"""
    with PostgresContainer("postgres:15") as postgres:
        # Set up database schema
        postgres.exec_in_container([
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
    # Mock RabbitMQ URL for now
    class MockRabbitMQ:
        def get_connection_url(self):
            return "amqp://guest:guest@localhost:5672"
    yield MockRabbitMQ()

@pytest.fixture(scope="session")
def redis_container():
    """Redis container for integration tests"""
    with RedisContainer() as redis:
        yield redis

@pytest.fixture
async def integration_config(postgres_container, rabbitmq_container, redis_container) -> Dict[str, str]:
    """Configuration for integration tests using real containers"""
    return {
        'database_url': postgres_container.get_connection_url(),
        'redis_url': redis_container.get_connection_url(),
        'rabbitmq_url': rabbitmq_container.get_connection_url(),
        'ollama_url': 'http://localhost:11434',  # Mock LLM for integration tests
        'log_level': 'INFO'
    }

@pytest.fixture
async def clean_database(postgres_container):
    """Clean database state before each test"""
    # Clear all tables
    postgres_container.exec_in_container([
        "psql", "-U", postgres_container.username, "-d", postgres_container.dbname, "-c",
        """
        TRUNCATE TABLE execution_cycles, task_status, agent_task_logs, agent_heartbeats RESTART IDENTITY CASCADE;
        """
    ])
    yield
    # Clean up after test
    postgres_container.exec_in_container([
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


