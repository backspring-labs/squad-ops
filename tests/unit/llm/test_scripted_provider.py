"""The scripted provider and the port that serves it beside the engine (#2495).

The keying rule under test: an answer is keyed by ``(task_type, occurrence, call)``, where the
occurrence counts distinct task ids of that type in the cycle, in the order their first calls
arrive, and the call counts the task's own calls. Each test enters through the deploy's port,
``with_scripted_model``, which every composition root builds.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from adapters.llm.factory import create_llm_provider, with_scripted_model
from squadops.llm.call_scope import LLMCallScope, use_llm_call_scope
from squadops.llm.models import ChatMessage
from squadops.llm.script import (
    LLMScriptError,
    ScriptEntryMissingError,
    ScriptLibrary,
    ScriptVersionMismatchError,
    UnscopedScriptedCallError,
    script_version,
)
from squadops.ports.llm.provider import LLMCapability

pytestmark = [pytest.mark.domain_orchestration]

RAW = textwrap.dedent(
    """\
    script: dev-repair
    description: a failing patch, its repair, and the task's re-ask
    replay_latency: true
    answers:
      - task_type: development.develop
        occurrence: 1
        call: 1
        content: "```python:app.py\\nraise SystemExit(1)\\n```"
        latency_seconds: 4.5
        prompt_tokens: 1000
        completion_tokens: 90
        reasoning_tokens: 12
        reasoning_text: chose the short path
        termination: length
      - task_type: development.develop
        occurrence: 1
        call: 2
        content: "the re-ask's answer"
      - task_type: development.develop
        occurrence: 2
        call: 1
        content: "```python:app.py\\nprint('ok')\\n```"
      - task_type: qa.test
        occurrence: 1
        call: 1
        content: "qa's answer"
    """
)
VERSION = script_version(RAW.encode())
MSG = [ChatMessage(role="user", content="a prompt that differs on every run: run_7f3a")]


class _BoobyTrappedEngine:
    """Every call the engine is asked for fails the test: the proof no scripted call reaches it."""

    def __init__(self, engine):
        self.engine_adapter = engine
        self.asked: list[str | None] = []

        async def _refuse(*args, **kwargs):
            self.asked.append(kwargs.get("model"))
            raise AssertionError("a scripted call reached the engine")

        engine.chat_stream_with_usage = _refuse
        engine.chat = _refuse


@pytest.fixture
def library(tmp_path: Path) -> ScriptLibrary:
    (tmp_path / "dev-repair.yaml").write_text(RAW)
    return ScriptLibrary(tmp_path)


@pytest.fixture
def slept() -> list[float]:
    return []


@pytest.fixture
def port(library, slept, monkeypatch):
    """The deploy's port, over a real Ollama adapter whose every call fails the test."""
    engine = create_llm_provider(
        provider="ollama", base_url="http://unreachable.invalid:1", default_model="qwen2.5:7b"
    )
    trap = _BoobyTrappedEngine(engine)
    port = with_scripted_model(engine, library)

    async def _sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(port._scripted, "_sleep", _sleep)
    port.trap = trap
    return port


def _scope(task_id: str, task_type: str = "development.develop", script: str | None = None):
    return use_llm_call_scope(
        LLMCallScope(
            cycle_id="cyc_1",
            task_id=task_id,
            task_type=task_type,
            llm_script=script if script is not None else f"dev-repair@{VERSION}",
        )
    )


async def _ask(port, task_id: str, task_type: str = "development.develop") -> ChatMessage:
    with _scope(task_id, task_type):
        return await port.chat_stream_with_usage(MSG, model="scripted", max_tokens=8192)


async def test_a_task_s_calls_and_the_next_task_of_its_type_take_successive_keys(port):
    """The keying rule, including a repair: the same task type answered by a second task.
    Bugs caught: a second call of one task answered with its first answer (a re-ask loop that
    never ends), and a repair answered with the failing patch it was sent to fix."""
    first = await _ask(port, "task-a")
    reask = await _ask(port, "task-a")
    repair = await _ask(port, "task-b")
    first_again_by_its_own_count = await _ask(port, "task-q", task_type="qa.test")

    assert [first.content, reask.content, repair.content, first_again_by_its_own_count.content] == [
        "```python:app.py\nraise SystemExit(1)\n```",
        "the re-ask's answer",
        "```python:app.py\nprint('ok')\n```",
        "qa's answer",
    ]
    assert port.trap.asked == []


async def test_the_answer_carries_every_figure_a_real_response_does(port):
    """What the handlers read off a response: the ledger's token counts, the cap check's
    termination, the emission log's reasoning text. Bug caught: a figure dropped, so the usage
    ledger read a scripted call as unreported, or a recorded cap-hit never reached the cap path."""
    answer = await _ask(port, "task-a")

    assert answer == ChatMessage(
        role="assistant",
        content="```python:app.py\nraise SystemExit(1)\n```",
        prompt_tokens=1000,
        completion_tokens=90,
        total_tokens=1090,
        tokens_per_second=20.0,
        reasoning_tokens=12,
        reasoning_text="chose the short path",
        termination="length",
    )


async def test_a_missing_entry_fails_naming_it_and_never_reaches_the_engine(port):
    """No fallback. Bug caught: a call past the script's end answered by the deploy's model, so a
    machinery cycle silently became a model run (and its record still said scripted)."""
    await _ask(port, "task-a")
    await _ask(port, "task-a")

    with pytest.raises(ScriptEntryMissingError, match="development.develop occurrence 1 call 3"):
        await _ask(port, "task-a")
    assert port.trap.asked == []


async def test_only_a_script_that_replays_latency_waits_and_it_waits_the_recorded_time(
    port, slept, tmp_path
):
    """Bug caught: the soak's increments taking no time because the wait was skipped, or every
    machinery check slowed by latency its script did not ask for."""
    await _ask(port, "task-a")
    await _ask(port, "task-a")  # no latency recorded: no wait
    assert slept == [4.5]

    fast = RAW.replace("replay_latency: true", "replay_latency: false")
    (tmp_path / "dev-repair.yaml").write_text(fast)
    fast_scope = LLMCallScope(
        "cyc_2", "task-z", "development.develop", f"dev-repair@{script_version(fast.encode())}"
    )
    with use_llm_call_scope(fast_scope):
        await port.chat_stream_with_usage(MSG, model="scripted")
    assert slept == [4.5]


async def test_another_model_goes_to_the_engine_and_a_scripted_one_is_labelled_scripted(port):
    """One port, two engines. Bugs caught: a model profile's call sent to the script (every other
    profile broken on a deploy that serves scripts), and a scripted call charted as the engine's."""
    with pytest.raises(AssertionError, match="reached the engine"):
        with _scope("task-a"):
            await port.chat_stream_with_usage(MSG, model="qwen2.5:7b")

    assert port.trap.asked == ["qwen2.5:7b"]
    assert (port.engine, port.engine_for("qwen2.5:7b"), port.engine_for("scripted")) == (
        "ollama",
        "ollama",
        "scripted",
    )
    assert port.list_models()[-1] == "scripted"


@pytest.mark.parametrize(
    ("scope", "error", "message"),
    [
        (None, UnscopedScriptedCallError, "outside any task"),
        (
            LLMCallScope(cycle_id="cyc_9", task_id="t", task_type="development.develop"),
            LLMScriptError,
            "its cycle names no script: set llm_script=<name>@<version>",
        ),
        (
            LLMCallScope("cyc_9", "t", "development.develop", "dev-repair@0123456789ab"),
            ScriptVersionMismatchError,
            f"holds dev-repair@{VERSION}",
        ),
    ],
)
async def test_a_call_with_no_task_no_script_or_another_version_fails_before_any_answer(
    port, scope, error, message
):
    """Bugs caught: a scripted call outside a task keyed by nothing; a cycle with no script
    answered from some default; an agent image holding another version answering anyway."""
    if scope is None:
        with pytest.raises(error, match=message):
            await port.chat_stream_with_usage(MSG, model="scripted")
    else:
        with use_llm_call_scope(scope), pytest.raises(error, match=message):
            await port.chat_stream_with_usage(MSG, model="scripted")
    assert port.trap.asked == []


async def test_a_step_whose_envelope_carries_no_config_takes_its_cycle_s_script(port):
    """A pulse-check repair's envelope carries no resolved config. Bug caught: it failed as
    'names no script' though its cycle named one, or a cycle switched scripts mid-run."""
    await _ask(port, "task-a")
    with use_llm_call_scope(LLMCallScope("cyc_1", "task-b", "development.develop")):
        repair = await port.chat_stream_with_usage(MSG, model="scripted")
    assert repair.content == "```python:app.py\nprint('ok')\n```"

    with pytest.raises(LLMScriptError, match="named script dev-repair@.* and now other@"):
        with _scope("task-c", script="other@0123456789ab"):
            await port.chat_stream_with_usage(MSG, model="scripted")


async def test_a_seed_is_refused_rather_than_dropped(port):
    """SIP-0111 §5.1's rule: a control that would change a generation is refused where it can't
    reach a sampler, so a replay never claims draws it did not make."""
    with _scope("task-a"), pytest.raises(ValueError, match="does not support seed"):
        await port.chat_stream_with_usage(MSG, model="scripted", seed=7)


async def test_the_listing_names_scripted_with_the_library_s_version_and_no_weights(port, library):
    """What the create-time check and the deploy record read. Bugs caught: `scripted` missing
    from the listing (every machinery cycle refused as 'model not pulled'), and a pull of it
    reaching the engine."""

    async def _engine_listing():
        return []

    port._engine.list_available_models = _engine_listing
    listed = await port.list_available_models()

    assert [(m.name, m.digest) for m in listed] == [("scripted", library.digest())]
    assert port.supports(LLMCapability.MODEL_LISTING) is True
    with pytest.raises(ValueError, match="no weights to pull"):
        await port.pull_model("scripted")
