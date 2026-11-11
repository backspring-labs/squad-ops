"""A scripted squad's task, end to end through the agent a live cycle dispatches to (#2495).

Wiring, entered at ``AgentRunner._handle_task_envelope``, the method the agent's comms consumer
hands each dispatched envelope to. Everything between it and the handler's model call is the
production code: the runner's real ``_create_ports`` (so the LLM port is the one the agent's
composition root builds, ``with_scripted_model`` over ``create_llm_provider``), the real system,
handler registry, prompt service and request renderer, and a real handler. Only the I/O-bound
bindings are replaced: RabbitMQ (the reply is captured), Redis, LangFuse. The engine under the
port is a real Ollama adapter whose every call fails the test.

What reaches the port is asserted by what comes back: the answer recorded for the task's key is
the artifact the handler emits, and the usage the reply carries is the recorded one.
"""

from __future__ import annotations

import json
import textwrap
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from adapters.llm.script_positions import InProcessScriptPositions
from squadops.llm.script import script_version
from squadops.tasks.models import TaskEnvelope

pytestmark = [pytest.mark.domain_agents]

SCRIPT = textwrap.dedent(
    """\
    script: analyze-reroll
    description: the first analysis is thrown away by a re-roll; the second stands
    answers:
      - task_type: strategy.analyze_prd
        occurrence: 1
        call: 1
        content: |
          # First analysis
          The one a re-roll replaces.
        prompt_tokens: 1500
        completion_tokens: 120
      - task_type: strategy.analyze_prd
        occurrence: 2
        call: 1
        content: |
          # Second analysis
          The one that stands.
        prompt_tokens: 1600
        completion_tokens: 140
    """
)
REFERENCE = f"analyze-reroll@{script_version(SCRIPT.encode())}"


def _config():
    """The fields ``_create_ports`` reads, as a deploy's config would carry them."""
    return SimpleNamespace(
        llm=SimpleNamespace(
            provider="ollama",
            url="http://unreachable.invalid:1",
            timeout=5,
            api_key=None,
            model=None,
        ),
        prompts=SimpleNamespace(asset_source_provider="filesystem"),
        telemetry=SimpleNamespace(backend="null", otlp_endpoint=None),
        langfuse=SimpleNamespace(enabled=False),
        tools=SimpleNamespace(filesystem=SimpleNamespace(provider="local")),
        remote_execution=SimpleNamespace(provider="none", wait_seconds=900, max_attempts=2),
        runtime_api_url="http://runtime-api:8001",
        auth=SimpleNamespace(agent_client=None, oidc=None),
        comms=SimpleNamespace(delivery=None),
    )


@pytest.fixture
async def runner(tmp_path, monkeypatch):
    from squadops.agents import entrypoint

    (tmp_path / "analyze-reroll.yaml").write_text(SCRIPT)
    monkeypatch.setattr("squadops.llm.script.PACKAGED_SCRIPTS_DIR", tmp_path)
    monkeypatch.setattr(
        entrypoint,
        "load_instance_config",
        lambda aid: {"id": aid, "role": "strat", "model": "qwen2.5:7b"},
    )
    queue = AsyncMock()
    monkeypatch.setattr("adapters.comms.factory.create_queue_adapter", lambda *a, **k: queue)
    monkeypatch.setattr("adapters.comms.factory.create_task_attempts", lambda *a, **k: None)
    # #3005: the positions a deploy keeps in Redis, held in the test.
    monkeypatch.setattr(
        "adapters.llm.factory.create_script_positions",
        lambda comms: InProcessScriptPositions(),
    )

    agent = entrypoint.AgentRunner(role="strat", agent_id="strat-agent")
    agent._config = _config()
    agent.system = await agent._create_system()

    engine = agent.system.ports.llm._engine
    engine.asked = []

    async def _refuse(*args, **kwargs):
        engine.asked.append(kwargs.get("model"))
        raise AssertionError("a scripted call reached the engine")

    engine.chat_stream_with_usage = _refuse
    engine.chat = _refuse
    agent.queue = queue
    agent.engine = engine
    return agent


def _envelope(task_id: str, script: str = REFERENCE) -> dict:
    envelope = TaskEnvelope(
        task_id=task_id,
        agent_id="strat-agent",
        cycle_id="cyc_machinery",
        pulse_id="pulse_1",
        project_id="proj_1",
        task_type="strategy.analyze_prd",
        correlation_id=f"corr_{task_id}",
        causation_id="cause_1",
        trace_id="trace_1",
        span_id="span_1",
        timeout=60.0,
        inputs={
            "prd": "A shelf of books, searchable by title.",
            "agent_model": "scripted",
            "resolved_config": {"llm_script": script},
        },
        metadata={"role": "strat"},
    )
    return {"payload": envelope.to_dict()}


async def _handle(runner, task_id: str) -> dict:
    runner.queue.publish.reset_mock()
    await runner._handle_task_envelope(_envelope(task_id), {"reply_queue": "replies"})
    (queue_name, body), _ = runner.queue.publish.call_args
    assert queue_name == "replies"
    return json.loads(body)["payload"]


async def test_a_re_rolled_task_is_answered_from_the_next_occurrence_through_the_real_handler(
    runner,
):
    """Bugs caught: the scope not reaching the port (every scripted call 'outside any task'), the
    profile's model not reaching it (the engine asked instead), and a re-roll of the same task
    type answered with the attempt it replaced."""
    first = await _handle(runner, "task-1")
    reroll = await _handle(runner, "task-2")

    assert (first["status"], reroll["status"]) == ("SUCCEEDED", "SUCCEEDED")
    assert [a["content"] for a in first["outputs"]["artifacts"]] == [
        "# First analysis\nThe one a re-roll replaces.\n"
    ]
    assert [a["content"] for a in reroll["outputs"]["artifacts"]] == [
        "# Second analysis\nThe one that stands.\n"
    ]
    # The usage ledger the run sums read the recorded figures, one call each.
    assert [
        (
            r["llm_usage"]["calls"],
            r["llm_usage"]["prompt_tokens"],
            r["llm_usage"]["completion_tokens"],
        )
        for r in (first, reroll)
    ] == [(1, 1500, 120), (1, 1600, 140)]
    assert runner.engine.asked == []


async def test_a_task_past_the_script_fails_visibly_naming_its_key_and_no_model_answers(runner):
    """No fallback, at the live entry point. Bug caught: a missing answer turned into a model call
    or a silent empty success, so the cycle went on as if the machinery had worked."""
    await _handle(runner, "task-1")
    await _handle(runner, "task-2")
    third = await _handle(runner, "task-3")

    assert third["status"] == "FAILED"
    assert "has no answer for strategy.analyze_prd occurrence 3 call 1" in third["error"]
    assert runner.engine.asked == []


async def test_a_task_on_a_real_model_still_reaches_the_engine_on_the_same_agent(runner):
    """The other profiles keep the engine. Bug caught: the router sending every call to the
    script once a deploy served one, so every model cycle failed on 'no script'."""
    envelope = _envelope("task-model")
    envelope["payload"]["inputs"]["agent_model"] = "qwen2.5:7b"
    envelope["payload"]["inputs"]["resolved_config"] = {}

    await runner._handle_task_envelope(envelope, {"reply_queue": "replies"})

    assert runner.engine.asked == ["qwen2.5:7b"]
