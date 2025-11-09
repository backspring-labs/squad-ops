"""
Unit tests for SIP-046 spec definitions (AgentRequest/AgentResponse).
"""

import pytest
from datetime import datetime
from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse, Error, Timing

def test_agent_request_creation():
    """Test AgentRequest creation and validation"""
    request = AgentRequest(
        action="build.artifact",
        payload={"task_id": "test-001", "project": "test-project"},
        metadata={"pid": "PID-001", "ecid": "ECID-001"}
    )
    
    assert request.action == "build.artifact"
    assert request.payload["task_id"] == "test-001"
    assert request.metadata["pid"] == "PID-001"
    assert request.metadata["ecid"] == "ECID-001"

def test_agent_request_validation():
    """Test AgentRequest validation requires pid and ecid"""
    with pytest.raises(ValueError, match="metadata.pid is required"):
        AgentRequest(
            action="build.artifact",
            payload={},
            metadata={"ecid": "ECID-001"}  # Missing pid
        )
    
    with pytest.raises(ValueError, match="metadata.ecid is required"):
        AgentRequest(
            action="build.artifact",
            payload={},
            metadata={"pid": "PID-001"}  # Missing ecid
        )

def test_agent_request_idempotency_key():
    """Test AgentRequest idempotency key generation"""
    request = AgentRequest(
        action="build.artifact",
        payload={"task_id": "test-001"},
        metadata={"pid": "PID-001", "ecid": "ECID-001"}
    )
    
    key1 = request.generate_idempotency_key("agent-001")
    key2 = request.generate_idempotency_key("agent-001")
    
    # Same request should generate same key
    assert key1 == key2
    
    # Different agent should generate different key
    key3 = request.generate_idempotency_key("agent-002")
    assert key1 != key3

def test_agent_request_to_dict():
    """Test AgentRequest serialization"""
    request = AgentRequest(
        action="build.artifact",
        payload={"task_id": "test-001"},
        metadata={"pid": "PID-001", "ecid": "ECID-001", "tags": ["test"]}
    )
    
    data = request.to_dict()
    assert data["action"] == "build.artifact"
    assert data["payload"]["task_id"] == "test-001"
    assert data["metadata"]["pid"] == "PID-001"
    assert data["metadata"]["ecid"] == "ECID-001"
    assert data["metadata"]["tags"] == ["test"]

def test_agent_request_from_dict():
    """Test AgentRequest deserialization"""
    data = {
        "action": "build.artifact",
        "payload": {"task_id": "test-001"},
        "metadata": {"pid": "PID-001", "ecid": "ECID-001"}
    }
    
    request = AgentRequest.from_dict(data)
    assert request.action == "build.artifact"
    assert request.payload["task_id"] == "test-001"
    assert request.metadata["pid"] == "PID-001"

def test_agent_request_action_format_validation():
    """Test AgentRequest action format validation"""
    request = AgentRequest(
        action="build.artifact",
        payload={},
        metadata={"pid": "PID-001", "ecid": "ECID-001"}
    )
    
    assert request.validate_action_format() is True
    
    request.action = "invalid"
    assert request.validate_action_format() is False

def test_timing_creation():
    """Test Timing creation"""
    started = datetime.utcnow()
    ended = datetime.utcnow()
    
    timing = Timing.create(started, ended)
    assert timing.started_at == started.isoformat()
    assert timing.ended_at == ended.isoformat()
    
    # Test with None (uses current time)
    timing2 = Timing.create()
    assert timing2.started_at is not None
    assert timing2.ended_at is not None

def test_error_creation():
    """Test Error creation"""
    error = Error(
        code="VALIDATION_ERROR",
        message="Test error",
        retryable=False
    )
    
    assert error.code == "VALIDATION_ERROR"
    assert error.message == "Test error"
    assert error.retryable is False

def test_agent_response_success():
    """Test AgentResponse success creation"""
    timing = Timing.create()
    response = AgentResponse.success(
        result={"status": "ok", "data": "test"},
        idempotency_key="key-001",
        timing=timing
    )
    
    assert response.status == "ok"
    assert response.result["status"] == "ok"
    assert response.idempotency_key == "key-001"
    assert response.timing == timing
    assert response.error is None

def test_agent_response_failure():
    """Test AgentResponse failure creation"""
    timing = Timing.create()
    response = AgentResponse.failure(
        error_code="VALIDATION_ERROR",
        error_message="Test error",
        retryable=False,
        idempotency_key="key-001",
        timing=timing
    )
    
    assert response.status == "error"
    assert response.error.code == "VALIDATION_ERROR"
    assert response.error.message == "Test error"
    assert response.error.retryable is False
    assert response.idempotency_key == "key-001"

def test_agent_response_validation():
    """Test AgentResponse validation"""
    # Valid success response
    response = AgentResponse.success(
        result={},
        idempotency_key="key-001"
    )
    assert response.status == "ok"
    
    # Valid error response
    response = AgentResponse.failure(
        error_code="ERROR",
        error_message="Test",
        idempotency_key="key-001"
    )
    assert response.status == "error"
    
    # Invalid status
    with pytest.raises(ValueError, match="status must be 'ok' or 'error'"):
        AgentResponse(
            status="invalid",
            result={},
            idempotency_key="key-001"
        )
    
    # Error status without error object
    with pytest.raises(ValueError, match="error is required when status is 'error'"):
        AgentResponse(
            status="error",
            result={},
            error=None,
            idempotency_key="key-001"
        )

def test_agent_response_to_dict():
    """Test AgentResponse serialization"""
    timing = Timing.create()
    response = AgentResponse.success(
        result={"data": "test"},
        idempotency_key="key-001",
        timing=timing
    )
    
    data = response.to_dict()
    assert data["status"] == "ok"
    assert data["result"]["data"] == "test"
    assert data["idempotency_key"] == "key-001"
    assert data["timing"]["started_at"] == timing.started_at
    assert data["timing"]["ended_at"] == timing.ended_at
    
    # Test error response
    error_response = AgentResponse.failure(
        error_code="ERROR",
        error_message="Test error",
        retryable=True,
        idempotency_key="key-002"
    )
    
    error_data = error_response.to_dict()
    assert error_data["status"] == "error"
    assert error_data["error"]["code"] == "ERROR"
    assert error_data["error"]["message"] == "Test error"
    assert error_data["error"]["retryable"] is True

def test_agent_response_from_dict():
    """Test AgentResponse deserialization"""
    data = {
        "status": "ok",
        "result": {"data": "test"},
        "idempotency_key": "key-001",
        "timing": {
            "started_at": "2025-01-01T00:00:00",
            "ended_at": "2025-01-01T00:01:00"
        }
    }
    
    response = AgentResponse.from_dict(data)
    assert response.status == "ok"
    assert response.result["data"] == "test"
    assert response.idempotency_key == "key-001"
    assert response.timing is not None
    
    # Test error response
    error_data = {
        "status": "error",
        "result": {},
        "error": {
            "code": "ERROR",
            "message": "Test error",
            "retryable": False
        },
        "idempotency_key": "key-002",
        "timing": {
            "started_at": "2025-01-01T00:00:00",
            "ended_at": "2025-01-01T00:01:00"
        }
    }
    
    error_response = AgentResponse.from_dict(error_data)
    assert error_response.status == "error"
    assert error_response.error.code == "ERROR"
    assert error_response.error.message == "Test error"
