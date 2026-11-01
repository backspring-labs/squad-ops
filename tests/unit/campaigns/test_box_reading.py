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


def _tensorfold(running: int | None) -> object:
    """TensorFold as the quiet-box check reads it: its authenticated ``/v1/models`` and
    ``/metrics`` (SIP-0111 §5.5). ``None``: the metrics refuse the key."""
    from adapters.llm.tensorfold import TensorFoldAdapter

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "qwen3.8-27b-tf-nvfp4"}, {"id": "q"}]})
        if running is None:
            return httpx.Response(401, json={"error": {"message": "A valid API key is required"}})
        return httpx.Response(
            200,
            text=f"tensorfold:requests_running {running}\ntensorfold:requests_waiting 0\n",
        )

    adapter = TensorFoldAdapter(
        base_url="http://tensorfold:8080", default_model="qwen3.8-27b-tf-nvfp4", api_key="k"
    )
    adapter._client = httpx.AsyncClient(
        base_url="http://tensorfold:8080", transport=httpx.MockTransport(handler)
    )
    return adapter


@pytest.mark.parametrize(
    ("running", "quiet", "said"),
    [
        (0, True, None),
        (2, True, None),
        (None, False, "could not be read"),
    ],
    ids=["idle", "serving the crew", "refused the key"],
)
async def test_tensorfold_is_quiet_while_it_serves_its_declared_model(running, quiet, said):
    """SIP-0109 §24cu, entered at the TensorFold adapter. Bugs caught: a campaign launch, or a
    run start, refused because the crew is mid-call on the shared engine, which serves the
    squad beside it (the 2026-11-01 launch Mother's own model call blocked); an alias read as a
    second model; and a refused key read as an idle engine (SIP-0111 §5.5, kept)."""
    readings = await read_engines({"tensorfold": _tensorfold(running)})
    declared = declared_models(_record(ModelWeights("qwen3.8-27b-tf-nvfp4", None)))

    quietness = box_quietness(declared, readings)

    assert quietness.quiet is quiet
    if said:
        assert any(said in reason for reason in quietness.reasons), quietness.reasons
    else:
        assert quietness.reasons == ()
