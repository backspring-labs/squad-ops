"""
Integration tests for Docker build process.

These tests verify that:
1. Docker builds succeed with the unified agent Dockerfile
2. Built containers have correct file structure
3. Agents can start in containers
4. Build args are propagated correctly
"""

import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture(scope="module")
def build_qa_image(project_root):
    """Build QA agent Docker image for tests."""
    result = subprocess.run(
        [
            "docker",
            "build",
            "-t",
            "squadops/eve:test",
            "--build-arg",
            "AGENT_ROLE=qa",
            "-f",
            "agents/Dockerfile",
            ".",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        pytest.skip(f"Docker build failed: {result.stderr[:200]}")
    return "squadops/eve:test"


@pytest.fixture(scope="module")
def build_dev_image(project_root):
    """Build Dev agent Docker image for tests."""
    result = subprocess.run(
        [
            "docker",
            "build",
            "-t",
            "squadops/neo:test",
            "--build-arg",
            "AGENT_ROLE=dev",
            "-f",
            "agents/Dockerfile",
            ".",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        pytest.skip(f"Docker build failed: {result.stderr[:200]}")
    return "squadops/neo:test"


@pytest.mark.integration
def test_qa_docker_build_succeeds(project_root):
    """Test that QA agent Docker build succeeds."""
    result = subprocess.run(
        [
            "docker",
            "build",
            "-t",
            "squadops/eve:test",
            "--build-arg",
            "AGENT_ROLE=qa",
            "-f",
            "agents/Dockerfile",
            ".",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert result.returncode == 0, f"Docker build failed: {result.stderr[:500]}"


@pytest.mark.integration
def test_dev_docker_build_succeeds(project_root):
    """Test that Dev agent Docker build succeeds."""
    result = subprocess.run(
        [
            "docker",
            "build",
            "-t",
            "squadops/neo:test",
            "--build-arg",
            "AGENT_ROLE=dev",
            "-f",
            "agents/Dockerfile",
            ".",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert result.returncode == 0, f"Docker build failed: {result.stderr[:500]}"


@pytest.mark.integration
def test_built_container_has_correct_structure(build_qa_image):
    """Test that built container has correct file structure."""
    result = subprocess.run(
        ["docker", "run", "--rm", build_qa_image, "ls", "-la", "/app"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, f"Container check failed: {result.stderr}"
    output = result.stdout

    # Check for expected directories
    assert "src" in output, "Expected src/ directory in container"
    assert "adapters" in output, "Expected adapters/ directory in container"


@pytest.mark.integration
def test_built_container_has_squadops_package(build_qa_image):
    """Test that squadops package is installed in container."""
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            build_qa_image,
            "python",
            "-c",
            "import squadops; print(squadops.__version__)",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, f"Package import failed: {result.stderr}"
    assert "0.8" in result.stdout or "0.9" in result.stdout, f"Unexpected version: {result.stdout}"


@pytest.mark.integration
def test_built_container_has_instances_yaml(build_qa_image):
    """Test that instances.yaml is present in container."""
    result = subprocess.run(
        ["docker", "run", "--rm", build_qa_image, "cat", "/app/agents/instances/instances.yaml"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, f"instances.yaml not found: {result.stderr}"
    assert "instances:" in result.stdout, "Invalid instances.yaml content"


@pytest.mark.integration
def test_agent_can_start_in_container(build_qa_image):
    """Test that agent entry point can be loaded (doesn't require full startup)."""
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-e",
            "SQUADOPS__AGENT__ID=eve",
            build_qa_image,
            "python",
            "-c",
            "from squadops.agents.entrypoint import AgentRunner; print('Entry point loadable')",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, f"Agent entry point failed to load: {result.stderr}"
    assert "Entry point loadable" in result.stdout


@pytest.mark.integration
def test_build_hash_propagation(project_root):
    """Test that build hash is propagated to container labels."""
    test_hash = "test-hash-12345"

    result = subprocess.run(
        [
            "docker",
            "build",
            "-t",
            "squadops/hash-test:latest",
            "--build-arg",
            "AGENT_ROLE=qa",
            "--build-arg",
            f"BUILD_HASH={test_hash}",
            "-f",
            "agents/Dockerfile",
            ".",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert result.returncode == 0, f"Docker build failed: {result.stderr[:500]}"

    # Check label was applied
    inspect_result = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            '{{index .Config.Labels "squadops.build_hash"}}',
            "squadops/hash-test:latest",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert test_hash in inspect_result.stdout, f"Build hash not in labels: {inspect_result.stdout}"

    # Cleanup
    subprocess.run(["docker", "rmi", "squadops/hash-test:latest"], capture_output=True, timeout=30)
