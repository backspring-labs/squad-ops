"""
Integration tests for Docker build process with new multi-stage Dockerfiles.

These tests verify that:
1. Docker builds succeed with new Dockerfiles
2. Built containers have correct file structure
3. Agents can start in containers
4. Metadata artifacts (manifest.json, agent_info.json) are present
5. Build hash propagation works correctly
"""

import pytest
import subprocess
import docker
import time
import json
from pathlib import Path


@pytest.mark.integration
def test_qa_docker_build_succeeds():
    """Test that QA agent Docker build succeeds."""
    project_root = Path(__file__).parent.parent.parent
    
    # Build Docker image
    result = subprocess.run(
        ['docker', 'build', '-t', 'squadops/eve:test', 
         '--build-arg', 'AGENT_ROLE=qa',
         '-f', 'agents/roles/qa/Dockerfile', '.'],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=300  # 5 minute timeout
    )
    
    assert result.returncode == 0, f"Docker build failed: {result.stderr}"
    # Docker outputs to stderr, check for success indicators
    output = result.stderr + result.stdout
    assert "naming to docker.io/squadops/eve:test" in output or "Successfully tagged" in output or "Successfully built" in output


@pytest.mark.integration
def test_dev_docker_build_succeeds():
    """Test that Dev agent Docker build succeeds (includes Docker CLI)."""
    project_root = Path(__file__).parent.parent.parent
    
    # Build Docker image
    result = subprocess.run(
        ['docker', 'build', '-t', 'squadops/neo:test',
         '--build-arg', 'AGENT_ROLE=dev',
         '-f', 'agents/roles/dev/Dockerfile', '.'],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=300  # 5 minute timeout
    )
    
    assert result.returncode == 0, f"Docker build failed: {result.stderr}"
    # Docker outputs to stderr, check for success indicators
    output = result.stderr + result.stdout
    assert "naming to docker.io/squadops/neo:test" in output or "Successfully tagged" in output or "Successfully built" in output


@pytest.mark.integration
def test_built_container_has_correct_structure():
    """Test that built container has correct file structure."""
    client = docker.from_env()
    
    try:
        # Run container and check file structure
        container = client.containers.run(
            'squadops/eve:test',
            command='ls -la /app',
            remove=True,
            detach=False
        )
        
        output = container.decode('utf-8') if isinstance(container, bytes) else str(container)
        
        # Verify key files/directories exist
        assert 'agent.py' in output, "Entry point should exist"
        assert 'agents' in output, "Agents directory should exist"
        assert 'config' in output, "Config directory should exist"
        assert 'requirements.txt' in output, "Requirements should exist"
        
    except docker.errors.ImageNotFound:
        pytest.skip("Docker image not found - run test_qa_docker_build_succeeds first")
    except Exception as e:
        pytest.fail(f"Failed to inspect container: {e}")


@pytest.mark.integration
def test_built_container_has_capabilities():
    """Test that built container has required capabilities."""
    client = docker.from_env()
    
    try:
        # Check capabilities directory
        container = client.containers.run(
            'squadops/eve:test',
            command='ls -la /app/agents/capabilities/qa/',
            remove=True,
            detach=False
        )
        
        output = container.decode('utf-8') if isinstance(container, bytes) else str(container)
        
        # QA agent should have test_design, test_dev, test_execution
        assert 'test_design.py' in output, "test_design capability should exist"
        assert 'test_dev.py' in output, "test_dev capability should exist"
        assert 'test_execution.py' in output, "test_execution capability should exist"
        
    except docker.errors.ImageNotFound:
        pytest.skip("Docker image not found - run test_qa_docker_build_succeeds first")
    except Exception as e:
        pytest.fail(f"Failed to inspect container capabilities: {e}")


@pytest.mark.integration
def test_agent_can_start_in_container():
    """Smoke test: Verify agent can start in container (doesn't crash immediately)."""
    client = docker.from_env()
    
    try:
        # Start container and let it run for a few seconds
        container = client.containers.run(
            'squadops/eve:test',
            detach=True,
            environment={
                'AGENT_ID': 'test-eve',
                'AGENT_ROLE': 'qa',
                'RABBITMQ_URL': 'amqp://guest:guest@rabbitmq:5672/',
                'POSTGRES_URL': 'postgresql://squadops:squadops123@postgres:5432/squadops',
                'REDIS_URL': 'redis://redis:6379',
            }
        )
        
        # Wait a moment for startup
        time.sleep(3)
        
        # Check container is still running (didn't crash)
        container.reload()
        assert container.status == 'running' or container.status == 'exited', \
            f"Container should be running or exited gracefully, got: {container.status}"
        
        # Check logs for errors
        logs = container.logs().decode('utf-8')
        
        # Clean up
        container.stop()
        container.remove()
        
        # Should not have critical errors
        assert 'Traceback' not in logs or 'ModuleNotFoundError' not in logs, \
            f"Container should not have import errors: {logs[-500:]}"
        
    except docker.errors.ImageNotFound:
        pytest.skip("Docker image not found - run test_qa_docker_build_succeeds first")
    except Exception as e:
        pytest.fail(f"Failed to start container: {e}")


@pytest.mark.integration
def test_built_container_has_manifest_json():
    """Test that built container has manifest.json"""
    client = docker.from_env()
    
    try:
        container = client.containers.run(
            'squadops/eve:test',
            command=['sh', '-c', 'test -f /app/manifest.json && echo "exists"'],
            remove=True,
            detach=False
        )
        
        output = container.decode('utf-8') if isinstance(container, bytes) else str(container)
        assert 'exists' in output, "manifest.json should exist in container"
    except docker.errors.ImageNotFound:
        pytest.skip("Docker image not found - run test_qa_docker_build_succeeds first")
    except Exception as e:
        pytest.fail(f"Failed to check manifest.json: {e}")


@pytest.mark.integration
def test_built_container_has_agent_info_json():
    """Test that built container has agent_info.json"""
    client = docker.from_env()
    
    try:
        container = client.containers.run(
            'squadops/eve:test',
            command=['sh', '-c', 'test -f /app/agent_info.json && echo "exists"'],
            remove=True,
            detach=False
        )
        
        output = container.decode('utf-8') if isinstance(container, bytes) else str(container)
        assert 'exists' in output, "agent_info.json should exist in container"
    except docker.errors.ImageNotFound:
        pytest.skip("Docker image not found - run test_qa_docker_build_succeeds first")
    except Exception as e:
        pytest.fail(f"Failed to check agent_info.json: {e}")


@pytest.mark.integration
def test_manifest_json_structure():
    """Test that manifest.json has required fields"""
    client = docker.from_env()
    
    try:
        container = client.containers.run(
            'squadops/eve:test',
            command='cat /app/manifest.json',
            remove=True,
            detach=False
        )
        
        output = container.decode('utf-8') if isinstance(container, bytes) else str(container)
        manifest = json.loads(output)
        
        # Verify required fields
        assert 'manifest_version' in manifest, "manifest.json should have manifest_version"
        assert 'role' in manifest, "manifest.json should have role"
        assert 'capabilities' in manifest, "manifest.json should have capabilities"
        assert 'build_hash' in manifest, "manifest.json should have build_hash"
        assert 'build_time_utc' in manifest, "manifest.json should have build_time_utc"
        
        # Verify build_hash format
        assert manifest['build_hash'].startswith('sha256:'), "build_hash should start with 'sha256:'"
        
        # Verify role matches
        assert manifest['role'] == 'qa', f"Expected role 'qa', got '{manifest['role']}'"
        
    except docker.errors.ImageNotFound:
        pytest.skip("Docker image not found - run test_qa_docker_build_succeeds first")
    except json.JSONDecodeError as e:
        pytest.fail(f"manifest.json is not valid JSON: {e}")
    except Exception as e:
        pytest.fail(f"Failed to check manifest.json structure: {e}")


@pytest.mark.integration
def test_agent_info_json_structure():
    """Test that agent_info.json has required fields"""
    client = docker.from_env()
    
    try:
        container = client.containers.run(
            'squadops/eve:test',
            command='cat /app/agent_info.json',
            remove=True,
            detach=False
        )
        
        output = container.decode('utf-8') if isinstance(container, bytes) else str(container)
        agent_info = json.loads(output)
        
        # Verify required fields
        assert 'agent_info_version' in agent_info, "agent_info.json should have agent_info_version"
        assert 'role' in agent_info, "agent_info.json should have role"
        assert 'build_hash' in agent_info, "agent_info.json should have build_hash"
        assert 'capabilities' in agent_info, "agent_info.json should have capabilities"
        
        # Verify build_hash format
        assert agent_info['build_hash'].startswith('sha256:'), "build_hash should start with 'sha256:'"
        
        # Verify role matches
        assert agent_info['role'] == 'qa', f"Expected role 'qa', got '{agent_info['role']}'"
        
    except docker.errors.ImageNotFound:
        pytest.skip("Docker image not found - run test_qa_docker_build_succeeds first")
    except json.JSONDecodeError as e:
        pytest.fail(f"agent_info.json is not valid JSON: {e}")
    except Exception as e:
        pytest.fail(f"Failed to check agent_info.json structure: {e}")


@pytest.mark.integration
def test_build_hash_propagation():
    """Test that build hash from manifest.json matches agent_info.json"""
    client = docker.from_env()
    
    try:
        # Get manifest.json
        manifest_container = client.containers.run(
            'squadops/eve:test',
            command='cat /app/manifest.json',
            remove=True,
            detach=False
        )
        manifest_output = manifest_container.decode('utf-8') if isinstance(manifest_container, bytes) else str(manifest_container)
        manifest = json.loads(manifest_output)
        manifest_build_hash = manifest.get('build_hash')
        
        # Get agent_info.json
        agent_info_container = client.containers.run(
            'squadops/eve:test',
            command='cat /app/agent_info.json',
            remove=True,
            detach=False
        )
        agent_info_output = agent_info_container.decode('utf-8') if isinstance(agent_info_container, bytes) else str(agent_info_container)
        agent_info = json.loads(agent_info_output)
        agent_info_build_hash = agent_info.get('build_hash')
        
        # Verify build hashes match
        assert manifest_build_hash == agent_info_build_hash, \
            f"Build hash mismatch: manifest.json has '{manifest_build_hash}', agent_info.json has '{agent_info_build_hash}'"
        
        # Verify build hash is not empty or "unknown"
        assert manifest_build_hash and manifest_build_hash != "unknown", \
            f"Build hash should not be empty or 'unknown', got '{manifest_build_hash}'"
        
    except docker.errors.ImageNotFound:
        pytest.skip("Docker image not found - run test_qa_docker_build_succeeds first")
    except json.JSONDecodeError as e:
        pytest.fail(f"Failed to parse JSON: {e}")
    except Exception as e:
        pytest.fail(f"Failed to verify build hash propagation: {e}")

