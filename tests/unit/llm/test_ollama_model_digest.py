"""Ollama reports the digest of the weights behind each tag, and the port carries it (#1720).

Bug caught: the digest read past and dropped, as it was before #1720, so a model re-pulled under
the same tag between deploys leaves every deploy record claiming the same weights. A tag listed
without a digest must read as unknown, not as an empty string that compares equal to another.
"""

from __future__ import annotations

import httpx

from adapters.llm.ollama import OllamaAdapter
from tests.unit.llm.conformance import wire


def _tags(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/tags":
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "qwen3.8:27b", "digest": "22130167c4c2e9f0", "size": 17},
                    {"name": "local:dev", "digest": ""},
                    {"name": "qwen2.5:7b"},
                ]
            },
        )
    return httpx.Response(404)


async def test_each_listed_model_carries_its_digest_or_none():
    with wire(_tags):
        models = await OllamaAdapter(default_model="qwen2.5:7b").list_available_models()

    assert [(m.name, m.digest) for m in models] == [
        ("qwen3.8:27b", "22130167c4c2e9f0"),
        ("local:dev", None),
        ("qwen2.5:7b", None),
    ]
