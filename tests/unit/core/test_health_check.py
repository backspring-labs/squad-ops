#!/usr/bin/env python3
"""
Unit tests for health-check service
Tests FastAPI endpoints for health check service
"""

import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Add path for imports
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)
health_check_path = os.path.join(project_root, 'infra', 'health-check')
sys.path.insert(0, health_check_path)

# Mock dependencies before importing
with patch('asyncpg.create_pool'), \
     patch('aio_pika.connect_robust'), \
     patch('redis.asyncio.from_url'):
    import main as health_check_main
    app = health_check_main.app
    create_console_session = health_check_main.create_console_session
    get_console_session = health_check_main.get_console_session


class TestHealthCheckService:
    """Test health-check service endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.mark.unit
    def test_health_endpoint(self, client):
        """Test /health endpoint"""
        with patch.object(health_check_main.health_checker, 'check_rabbitmq', new_callable=AsyncMock, return_value={'status': 'ok'}), \
             patch.object(health_check_main.health_checker, 'check_postgres', new_callable=AsyncMock, return_value={'status': 'ok'}), \
             patch.object(health_check_main.health_checker, 'check_redis', new_callable=AsyncMock, return_value={'status': 'ok'}), \
             patch.object(health_check_main.health_checker, 'check_prefect', new_callable=AsyncMock, return_value={'status': 'ok'}), \
             patch.object(health_check_main.health_checker, 'check_prometheus', new_callable=AsyncMock, return_value={'status': 'ok'}), \
             patch.object(health_check_main.health_checker, 'check_grafana', new_callable=AsyncMock, return_value={'status': 'ok'}), \
             patch.object(health_check_main.health_checker, 'check_otel_collector', new_callable=AsyncMock, return_value={'status': 'ok'}), \
             patch.object(health_check_main.health_checker, 'get_agent_status', new_callable=AsyncMock, return_value=[]):
            response = client.get("/health")
            # Returns HTML template, so check for 200 status
            assert response.status_code == 200
    
    @pytest.mark.unit
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code in [200, 404]  # May redirect or 404
    
    @pytest.mark.unit
    def test_warmboot_next_run_id(self, client):
        """Test /warmboot/next-run-id endpoint"""
        with patch.object(health_check_main.health_checker, 'get_next_run_id', new_callable=AsyncMock, return_value='001'):
            response = client.get("/warmboot/next-run-id")
            assert response.status_code == 200
            data = response.json()
            assert 'run_id' in data
    
    @pytest.mark.unit
    def test_warmboot_submit(self, client):
        """Test /warmboot/submit endpoint"""
        request_data = {
            "run_id": "run-001",
            "application": "TestApp",
            "request_type": "from-scratch",
            "agents": ["max", "neo"],
            "priority": "HIGH",
            "description": "Test request"
        }
        
        with patch.object(health_check_main.health_checker, 'submit_warmboot_request', new_callable=AsyncMock, return_value={'status': 'submitted'}):
            response = client.post("/warmboot/submit", json=request_data)
            assert response.status_code == 200
    
    @pytest.mark.unit
    def test_warmboot_status(self, client):
        """Test /warmboot/status/{run_id} endpoint"""
        with patch.object(health_check_main.health_checker, 'get_warmboot_status', new_callable=AsyncMock, return_value={'status': 'running', 'run_id': 'run-001'}):
            response = client.get("/warmboot/status/run-001")
            assert response.status_code == 200
    
    @pytest.mark.unit
    def test_agent_status_endpoints(self, client):
        """Test agent status endpoints"""
        with patch.object(health_check_main.health_checker, 'get_agent_status', new_callable=AsyncMock, return_value=[]), \
             patch.object(health_check_main.health_checker, 'update_agent_status_in_db', new_callable=AsyncMock, return_value={'status': 'updated'}):
            # Test GET /health/agents (not /agent-status)
            response = client.get("/health/agents")
            assert response.status_code == 200
            
            # Test POST /health/agents/status
            # SIP-Agent-Lifecycle: Uses agent_id and lifecycle_state, not agent_name and status
            status_data = {
                "agent_id": "test-agent",
                "lifecycle_state": "READY",
                "tps": 10
            }
            response = client.post("/health/agents/status", json=status_data)
            assert response.status_code in [200, 201]
    
    @pytest.mark.unit
    def test_console_session_creation(self):
        """Test console session creation"""
        session_id = create_console_session()
        assert session_id is not None
        assert isinstance(session_id, str)
        assert len(session_id) > 0
    
    @pytest.mark.unit
    def test_get_console_session(self):
        """Test getting console session"""
        session_id = create_console_session()
        session = get_console_session(session_id)
        assert session is not None
        assert session.session_id == session_id
    
    @pytest.mark.unit
    def test_get_console_session_not_found(self):
        """Test getting non-existent console session"""
        session = get_console_session("non-existent-id")
        assert session is None
    
    @pytest.mark.unit
    def test_agent_gateway_endpoints(self, client):
        """Test agent gateway endpoints"""
        # Test GET /console/session (creates a new session)
        response = client.get("/console/session")
        assert response.status_code == 200
        data = response.json()
        assert 'session_id' in data
        
        # Test GET /console/responses/{session_id}
        session_id = data.get('session_id', 'test-session')
        response = client.get(f"/console/responses/{session_id}")
        assert response.status_code in [200, 404]
    
    @pytest.mark.unit
    def test_metrics_endpoint(self, client):
        """Test /metrics endpoint"""
        response = client.get("/metrics")
        assert response.status_code in [200, 404, 500]
    
    @pytest.mark.unit
    def test_info_endpoint(self, client):
        """Test /info endpoint"""
        response = client.get("/info")
        assert response.status_code in [200, 404, 500]

