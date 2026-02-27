"""Tests for OllamaAdapter pull/delete/list_pulled methods (SIP-0075 §2.2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from squadops.llm.exceptions import LLMConnectionError, LLMModelNotFoundError, LLMTimeoutError

pytestmark = [pytest.mark.domain_orchestration]


@pytest.fixture()
def adapter():
    from adapters.llm.ollama import OllamaAdapter

    return OllamaAdapter(base_url="http://localhost:11434", default_model="qwen2.5:7b")


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


class TestPullModel:
    async def test_success(self, adapter):
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(200, {"status": "success"})
        adapter._client = mock_client

        result = await adapter.pull_model("qwen2.5:7b")
        assert result == {"status": "success"}
        mock_client.post.assert_awaited_once_with(
            "/api/pull",
            json={"name": "qwen2.5:7b", "stream": False},
            timeout=600.0,
        )

    async def test_timeout_raises(self, adapter):
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        adapter._client = mock_client

        with pytest.raises(LLMTimeoutError, match="timed out"):
            await adapter.pull_model("big-model:latest")

    async def test_connect_error_raises(self, adapter):
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("refused")
        adapter._client = mock_client

        with pytest.raises(LLMConnectionError, match="Failed to connect"):
            await adapter.pull_model("qwen2.5:7b")

    async def test_404_raises_model_not_found(self, adapter):
        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_response(404)
        adapter._client = mock_client

        with pytest.raises(LLMModelNotFoundError, match="not found in registry"):
            await adapter.pull_model("nonexistent:latest")


class TestDeleteModel:
    async def test_success(self, adapter):
        mock_client = AsyncMock()
        mock_client.request.return_value = _mock_response(200)
        adapter._client = mock_client

        result = await adapter.delete_model("qwen2.5:7b")
        assert result == {}
        mock_client.request.assert_awaited_once_with(
            "DELETE",
            "/api/delete",
            json={"name": "qwen2.5:7b"},
        )

    async def test_404_raises_model_not_found(self, adapter):
        mock_client = AsyncMock()
        mock_client.request.return_value = _mock_response(404)
        adapter._client = mock_client

        with pytest.raises(LLMModelNotFoundError, match="not found locally"):
            await adapter.delete_model("nonexistent:latest")

    async def test_connect_error_raises(self, adapter):
        mock_client = AsyncMock()
        mock_client.request.side_effect = httpx.ConnectError("refused")
        adapter._client = mock_client

        with pytest.raises(LLMConnectionError, match="Failed to connect"):
            await adapter.delete_model("qwen2.5:7b")


class TestListPulledModels:
    async def test_returns_models(self, adapter):
        mock_client = AsyncMock()
        models_data = [
            {"name": "qwen2.5:7b", "size": 4_000_000_000, "modified_at": "2026-01-01T00:00:00Z"},
        ]
        mock_client.get.return_value = _mock_response(200, {"models": models_data})
        adapter._client = mock_client

        result = await adapter.list_pulled_models()
        assert len(result) == 1
        assert result[0]["name"] == "qwen2.5:7b"
        assert result[0]["size"] == 4_000_000_000

    async def test_empty_list(self, adapter):
        mock_client = AsyncMock()
        mock_client.get.return_value = _mock_response(200, {"models": []})
        adapter._client = mock_client

        result = await adapter.list_pulled_models()
        assert result == []

    async def test_connect_error_raises(self, adapter):
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("refused")
        adapter._client = mock_client

        with pytest.raises(LLMConnectionError, match="Failed to connect"):
            await adapter.list_pulled_models()
