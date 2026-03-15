"""A2A client adapter — raw httpx streaming behind adapter boundary (SIP-0085).

v1 uses raw httpx SSE streaming for the proxy use case. The adapter
boundary means we can swap to SDK client later without changing callers.
"""

from __future__ import annotations

import itertools
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

_request_id_counter = itertools.count(1)

logger = logging.getLogger(__name__)


class A2AClientAdapter:
    """Stateless A2A client for proxying chat requests to agent servers.

    Per P1-RC4, v1 uses raw httpx streaming rather than the A2A SDK client.
    Each request is independent — session state lives in Redis/Postgres.
    """

    def __init__(self, timeout_seconds: float = 180.0) -> None:
        self._timeout = timeout_seconds
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def get_agent_card(self, base_url: str) -> dict[str, Any]:
        """Fetch the agent card from the well-known endpoint.

        Args:
            base_url: Agent's A2A server base URL (e.g. http://localhost:5000).

        Returns:
            Parsed agent card as a dict.

        Raises:
            httpx.HTTPStatusError: Non-2xx response.
            httpx.ConnectError: Connection failure.
        """
        client = await self._get_client()
        url = f"{base_url.rstrip('/')}/.well-known/agent.json"
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()
        return response.json()

    async def send_message(
        self,
        base_url: str,
        message: str,
        *,
        context_id: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """Send a message and return the full JSON response (non-streaming).

        Args:
            base_url: Agent's A2A server base URL.
            message: User message text.
            context_id: Optional conversation context ID.
            task_id: Optional task ID for continuation.

        Returns:
            Parsed JSON response.
        """
        client = await self._get_client()
        payload = self._build_payload(message, context_id=context_id, task_id=task_id)
        response = await client.post(
            f"{base_url.rstrip('/')}/",
            json=payload,
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()

    async def send_message_stream(
        self,
        base_url: str,
        message: str,
        *,
        context_id: str | None = None,
        task_id: str | None = None,
    ) -> AsyncIterator[str]:
        """Send a message and stream text chunks via SSE.

        Args:
            base_url: Agent's A2A server base URL.
            message: User message text.
            context_id: Optional conversation context ID.
            task_id: Optional task ID for continuation.

        Yields:
            Text content chunks from the agent's streaming response.
        """
        client = await self._get_client()
        payload = self._build_payload(
            message, method="message/stream", context_id=context_id, task_id=task_id,
        )

        async with client.stream(
            "POST",
            f"{base_url.rstrip('/')}/",
            json=payload,
            headers={"Accept": "text/event-stream"},
            timeout=self._timeout,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[len("data:") :].strip()
                if not data_str:
                    continue
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    logger.debug("Skipping malformed SSE data: %s", data_str[:200])
                    continue
                # Extract text from A2A message parts
                text = self._extract_text(data)
                if text:
                    yield text

    @staticmethod
    def _build_payload(
        message: str,
        *,
        method: str = "message/send",
        context_id: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """Build the JSON-RPC payload for sending a message."""
        params: dict[str, Any] = {
            "message": {
                "kind": "message",
                "role": "user",
                "parts": [{"kind": "text", "text": message}],
                "messageId": "",  # Server assigns if empty
            },
        }
        if context_id:
            params["message"]["contextId"] = context_id
        if task_id:
            params["message"]["taskId"] = task_id

        return {
            "jsonrpc": "2.0",
            "id": str(next(_request_id_counter)),
            "method": method,
            "params": params,
        }

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        """Extract text content from an A2A SSE event payload."""
        # A2A streaming events may nest content differently
        # Handle common patterns: direct result parts, artifact parts
        result = data.get("result", data)

        # Status update with message parts
        status = result.get("status", {})
        if isinstance(status, dict):
            message = status.get("message", {})
            if isinstance(message, dict):
                parts = message.get("parts", [])
                texts = []
                for part in parts:
                    if isinstance(part, dict) and part.get("kind") == "text":
                        texts.append(part.get("text", ""))
                if texts:
                    return "".join(texts)

        # Artifact update with parts
        artifact = result.get("artifact", {})
        if isinstance(artifact, dict):
            parts = artifact.get("parts", [])
            texts = []
            for part in parts:
                if isinstance(part, dict) and part.get("kind") == "text":
                    texts.append(part.get("text", ""))
            if texts:
                return "".join(texts)

        return ""

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
