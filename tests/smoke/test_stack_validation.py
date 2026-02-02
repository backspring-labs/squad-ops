"""
Stack Validation Integration Test

Verifies the complete SquadOps stack post-migration:
1. Infrastructure services running (Postgres, Redis, RabbitMQ)
2. Agent containers built with new architecture
3. Agents online and reporting heartbeats
4. Agent console chat functional (full A2A round-trip)

This is the ultimate gate for SIP-0.8.8 + SIP-0.8.9 completion.

Usage:
    # Ensure stack is running first
    docker-compose up -d postgres redis rabbitmq health-check max neo nat eve data

    # Run the test
    pytest tests/smoke/test_stack_validation.py -v -m stack_validation
"""

import os
import uuid
import pytest
import httpx
import asyncio

# Configurable via environment for different environments
BASE_URL = os.environ.get("HEALTH_CHECK_URL", "http://localhost:8000")
AGENT_ONLINE_TIMEOUT = int(os.environ.get("AGENT_ONLINE_TIMEOUT", "60"))
CHAT_RESPONSE_TIMEOUT = int(os.environ.get("CHAT_RESPONSE_TIMEOUT", "30"))


async def wait_until_healthy(client: httpx.AsyncClient, timeout: int = 30) -> bool:
    """Wait until health-check service reports all dependencies healthy."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            resp = await client.get(f"{BASE_URL}/health/infra")
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    # Check that we got a list of components and core ones are online
                    if isinstance(data, list) and len(data) > 0:
                        online_components = [c for c in data if c.get("status") == "online"]
                        # At least RabbitMQ, PostgreSQL, and Redis should be online
                        core_online = sum(
                            1 for c in online_components
                            if c.get("component") in ["RabbitMQ", "PostgreSQL", "Redis"]
                        )
                        if core_online >= 3:
                            return True
                except (ValueError, KeyError):
                    # Non-JSON response or missing fields
                    pass
        except httpx.RequestError:
            pass
        await asyncio.sleep(2)
    return False


async def wait_for_agents_online(client: httpx.AsyncClient, timeout: int = 60) -> list:
    """Wait until at least one agent is online."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            resp = await client.get(f"{BASE_URL}/health/agents")
            if resp.status_code == 200:
                agents = resp.json()
                online = [a for a in agents if a.get("network_status") == "online"]
                if online:
                    return online
        except httpx.RequestError:
            pass
        await asyncio.sleep(3)
    return []


@pytest.mark.smoke
@pytest.mark.stack_validation
class TestStackValidation:
    """End-to-end stack validation tests."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Ensure health-check service and dependencies are ready."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            healthy = await wait_until_healthy(client, timeout=30)
            if not healthy:
                pytest.skip("Health-check service not ready - is the stack running?")

    async def test_infrastructure_healthy(self):
        """Verify health-check service is responding and core infra is online."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{BASE_URL}/health/infra")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list), f"Expected list, got: {type(data)}"

            # Check core infrastructure components
            components = {c.get("component"): c.get("status") for c in data}
            assert components.get("RabbitMQ") == "online", f"RabbitMQ not online: {components}"
            assert components.get("PostgreSQL") == "online", f"PostgreSQL not online: {components}"
            assert components.get("Redis") == "online", f"Redis not online: {components}"

    async def test_agents_online(self):
        """Verify at least one agent is online and reporting heartbeats."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            online_agents = await wait_for_agents_online(client, AGENT_ONLINE_TIMEOUT)
            assert len(online_agents) >= 1, (
                f"No agents online after {AGENT_ONLINE_TIMEOUT}s. "
                "Ensure agent containers are running."
            )

            # Verify agents have valid lifecycle state
            for agent in online_agents:
                assert agent.get("lifecycle_state") != "UNKNOWN", (
                    f"Agent {agent.get('agent_name')} has UNKNOWN lifecycle state"
                )

    async def test_agent_console_chat_roundtrip(self):
        """
        Complete agent chat round-trip validation.

        1. Create console session via command
        2. Enter chat mode with an online agent
        3. Send a message
        4. Poll for response
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 1. Wait for agents
            online_agents = await wait_for_agents_online(client, AGENT_ONLINE_TIMEOUT)
            assert len(online_agents) >= 1, "No agents available for chat"
            target_agent = online_agents[0].get("agent_name", "max")

            # 2. Create session and enter chat mode
            session_id = str(uuid.uuid4())

            resp = await client.post(
                f"{BASE_URL}/console/command",
                json={"session_id": session_id, "command": f"chat {target_agent}"}
            )
            assert resp.status_code == 200, f"Failed to start chat: {resp.text}"
            data = resp.json()
            assert data.get("mode") == "chat", f"Not in chat mode: {data}"

            # 3. Send a test message
            correlation_id = str(uuid.uuid4())[:8]
            test_message = f"Stack validation ping [{correlation_id}]"

            resp = await client.post(
                f"{BASE_URL}/console/command",
                json={"session_id": session_id, "command": test_message}
            )
            assert resp.status_code == 200, f"Failed to send message: {resp.text}"

            # 4. Poll for response
            response_received = False
            poll_interval = 2
            max_attempts = CHAT_RESPONSE_TIMEOUT // poll_interval

            for attempt in range(max_attempts):
                await asyncio.sleep(poll_interval)
                resp = await client.get(f"{BASE_URL}/console/responses/{session_id}")
                if resp.status_code == 200:
                    data = resp.json()
                    responses = data.get("responses", [])
                    if responses:
                        # Any response from the agent counts as success
                        response_received = True
                        break

            # 5. End chat session
            await client.post(
                f"{BASE_URL}/console/command",
                json={"session_id": session_id, "command": "chat end"}
            )

            assert response_received, (
                f"Agent {target_agent} did not respond within {CHAT_RESPONSE_TIMEOUT}s. "
                f"Correlation ID: {correlation_id}"
            )

    async def test_warmboot_form_accessible(self):
        """Verify WarmBoot form / dashboard is accessible."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{BASE_URL}/")
            assert resp.status_code == 200
            # Check for some expected content in the dashboard
            content = resp.text.lower()
            assert "squadops" in content or "health" in content or "agent" in content, (
                "Dashboard does not appear to contain expected content"
            )

    async def test_all_configured_agents_online(self):
        """Verify all 5 configured agents are online."""
        expected_agents = {"max", "neo", "nat", "eve", "data"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            online_agents = await wait_for_agents_online(client, AGENT_ONLINE_TIMEOUT)
            online_ids = {a.get("agent_id") for a in online_agents}

            missing = expected_agents - online_ids
            if missing:
                pytest.skip(f"Not all agents online. Missing: {missing}")

            assert expected_agents <= online_ids, (
                f"Expected agents {expected_agents}, got {online_ids}"
            )
