"""The LLM factory selects by name and nothing else (#1157, SIP-0106 §3.1).

The bug this file exists for: two adapters in the tree and no caller able to reach the
second, because the factory defaulted ``provider="ollama"`` and every composition root
omitted it. A missing selector must fail the way an unknown one does.
"""

from __future__ import annotations

import pytest

from adapters.llm.atlas import AtlasAdapter
from adapters.llm.factory import create_llm_provider
from adapters.llm.ollama import OllamaAdapter
from adapters.llm.vllm import VLLMAdapter

pytestmark = [pytest.mark.domain_orchestration]


def test_a_missing_provider_is_an_error_not_ollama():
    with pytest.raises(TypeError, match="provider"):
        create_llm_provider(base_url="http://x:1", default_model="m")  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("name", "cls"),
    [("ollama", OllamaAdapter), ("vllm", VLLMAdapter), ("atlas", AtlasAdapter)],
)
def test_each_registered_name_resolves_its_own_adapter(name, cls):
    adapter = create_llm_provider(provider=name, base_url="http://x:1", default_model="m")
    assert type(adapter) is cls


@pytest.mark.parametrize("name", ["vllm", "atlas"])
def test_bearer_providers_receive_their_api_key(name):
    """The one provider-specific kwarg the factory forwards; dropped, a bearer-gated
    server (Atlas is one) answers 401 to every call."""
    adapter = create_llm_provider(
        provider=name, base_url="http://x:1", default_model="m", api_key="tok"
    )
    assert adapter._api_key == "tok"


def test_an_unknown_name_raises_and_never_falls_back():
    with pytest.raises(ValueError, match="Unknown LLM provider: olama"):
        create_llm_provider(provider="olama", base_url="http://x:1", default_model="m")
