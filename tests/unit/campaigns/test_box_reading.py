"""What the quiet-box check reads, through the real ports (SIP-0109 §9.3; #1802)."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from squadops.campaigns.box import box_quietness
from squadops.campaigns.box_reading import declared_models, read_engines
from squadops.cycles.deploy_record import DeployRecord, ModelWeights

#: The live Ollama ``/api/ps`` on the Spark, 2026-10-02, trimmed to what is read.
_PS = {
    "models": [
        {
            "name": "qwen3.8:27b",
            "size": 18882431548,
            "digest": "22130167c4c20e20c7b71454612966ca8e8171e9b3cc8ab6ce8aa6cbfec79643",
        }
    ]
}
_DIGEST = _PS["models"][0]["digest"]


def _record(*models: ModelWeights) -> DeployRecord:
    return DeployRecord(
        deploy_id="dep_x",
        recorded_at=datetime(2026, 10, 2, tzinfo=UTC),
        recorded_by="rebuild",
        source_revision="385c22b9",
        services=(),
        models=models,
    )


def _ollama(handler) -> object:
    from adapters.llm.ollama import OllamaAdapter

    adapter = OllamaAdapter(base_url="http://ollama:11434", default_model="qwen3.8:27b")
    adapter._client = httpx.AsyncClient(
        base_url="http://ollama:11434", transport=httpx.MockTransport(handler)
    )
    return adapter


def _ps(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/api/ps"
    return httpx.Response(200, json=_PS)


@pytest.mark.parametrize(
    ("declared", "quiet"),
    [
        (ModelWeights("qwen3.8:27b", _DIGEST), True),
        # The same tag re-pulled: another model under a declared name (#1720).
        (ModelWeights("qwen3.8:27b", "0" * 64), False),
        (ModelWeights("qwen2.5:7b", None), False),
    ],
    ids=["declared", "re-pulled-under-the-tag", "undeclared"],
)
async def test_the_resident_models_are_read_against_the_deploy_record(declared, quiet):
    """Entered at the Ollama adapter on the live ``/api/ps`` shape. Bugs caught: the servable
    list read in place of the resident one, or the digest dropped on the way to the check."""
    readings = await read_engines({"ollama": _ollama(_ps)})

    assert box_quietness(declared_models(_record(declared)), readings).quiet is quiet


async def test_an_engine_that_cannot_be_read_is_never_quiet():
    """Bug caught: a connection failure read as an empty engine — a quiet box — so a launch
    proceeds onto a box nobody could see."""

    def refused(request):
        raise httpx.ConnectError("refused")

    [reading] = await read_engines({"ollama": _ollama(refused)})

    assert reading.loaded is None
    assert "LLMConnectionError" in reading.error
    assert box_quietness((), (reading,)).quiet is False


def test_no_recorded_deploy_declares_nothing():
    assert declared_models(None) == ()
