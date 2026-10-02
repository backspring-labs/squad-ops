"""The cycle-create model preflight asks the port, not the adapter class (#1157, SIP-0106 §3.2).

Bug: ``isinstance(port, OllamaAdapter)`` returned ``None`` — "unverifiable, warn and
allow" — for every other provider, so on vLLM or Atlas a profile naming an absent model
was never caught before dispatch.
"""

from __future__ import annotations

import pytest

from squadops.api.routes.cycles.cycles import _pulled_model_names
from squadops.llm.models import ModelInfo
from squadops.ports.llm.provider import LLMCapability

pytestmark = [pytest.mark.domain_api]


class _Port:
    def __init__(self, *, listing: bool, models=None, fail=False):
        self._listing, self._models, self._fail = listing, models or [], fail

    def supports(self, capability: str) -> bool:
        return capability == LLMCapability.MODEL_LISTING and self._listing

    async def list_available_models(self):
        if self._fail:
            raise ConnectionError("backend down")
        return self._models


async def test_any_provider_declaring_listing_is_verified():
    port = _Port(listing=True, models=[ModelInfo(name="qwen3.8:27b"), ModelInfo(name="")])
    assert await _pulled_model_names(port) == ["qwen3.8:27b"]


async def test_a_provider_without_listing_is_unverifiable_not_empty():
    """``None`` warns-and-allows; ``[]`` would read as *no models present* and block."""
    assert await _pulled_model_names(_Port(listing=False)) is None


async def test_an_unreachable_backend_is_unverifiable():
    assert await _pulled_model_names(_Port(listing=True, fail=True)) is None


async def test_no_llm_port_is_unverifiable():
    """The create route reads an unwired port as ``None``; a campaign's launch may too."""
    assert await _pulled_model_names(None) is None
