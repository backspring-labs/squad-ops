"""SIP-0111 §4 (#2199): the replay sends both engines the same call, and reads both streams the same way."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "engine_replay", ROOT / "scripts/dev/engine_replay.py"
)
er = importlib.util.module_from_spec(_spec)
sys.modules["engine_replay"] = er
_spec.loader.exec_module(er)


def envelope(reasoning: str | None, max_tokens: int | None = 12288) -> dict:
    kwargs = {
        "model": "qwen3.8:27b",
        **({"reasoning": reasoning} if reasoning else {}),
        **({"max_tokens": max_tokens} if max_tokens else {}),
    }
    return {
        "messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
        "chat_kwargs": kwargs,
    }


@pytest.mark.parametrize("level", ["low", "medium", "high"])
def test_a_thinking_call_carries_the_recipes_parity_effort_not_the_envelopes_level(level):
    """The overnight run's first launch sent the envelope's level, and the checkpoint's template turned
    `high` into an xhigh instruction Ollama's prompt never carried (#2199). Ollama hears only thinking on."""
    _, body = er.tensorfold_request(envelope(level), 1001, "served", parity_effort="medium")
    assert body["chat_template_kwargs"] == {"enable_thinking": True}
    assert body["reasoning_effort"] == "medium"
    _, ollama = er.ollama_request(envelope(level), 1001)
    assert ollama["think"] is True


@pytest.mark.parametrize("reasoning", [None, "none"])
def test_a_thinking_off_call_sends_no_effort(reasoning):
    _, body = er.tensorfold_request(envelope(reasoning), 1001, "served", parity_effort="medium")
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert "reasoning_effort" not in body
    _, ollama = er.ollama_request(envelope(reasoning), 1001)
    assert ollama["think"] is False


@pytest.mark.parametrize("cap, sent", [(12288, 12288), (None, 8192)])
def test_both_engines_get_the_same_messages_cap_and_seed(cap, sent):
    """A pair is only a pair if the two calls differ in engine alone. A capture without a cap gets the
    registry's default on both."""
    env = envelope("medium", cap)
    _, ollama = er.ollama_request(env, 1002)
    _, tf = er.tensorfold_request(env, 1002, "served", parity_effort="medium")
    assert tf["messages"] == ollama["messages"] == env["messages"]
    assert (
        (tf["max_tokens"], tf["seed"])
        == (ollama["options"]["num_predict"], ollama["options"]["seed"])
        == (sent, 1002)
    )


@pytest.mark.parametrize(
    "engine, line, expected",
    [
        (
            "ollama",
            json.dumps({"message": {"content": "a", "thinking": ""}, "done": False}),
            {"piece": "a", "think": ""},
        ),
        (
            "ollama",
            json.dumps(
                {"message": {"content": ""}, "done": True, "done_reason": "length", "eval_count": 9}
            ),
            {
                "piece": "",
                "think": "",
                "finish": "length",
                "final": {
                    "message": {"content": ""},
                    "done": True,
                    "done_reason": "length",
                    "eval_count": 9,
                },
            },
        ),
        (
            "tensorfold",
            "data: "
            + json.dumps(
                {"choices": [{"delta": {"reasoning_content": "t"}, "finish_reason": None}]}
            ),
            {"piece": "", "think": "t", "finish": None, "usage": None},
        ),
        (
            "tensorfold",
            "data: "
            + json.dumps(
                {
                    "choices": [{"delta": {}, "finish_reason": "length"}],
                    "usage": {"completion_tokens": 12288},
                }
            ),
            {"piece": "", "think": "", "finish": "length", "usage": {"completion_tokens": 12288}},
        ),
        (
            "tensorfold",
            "data: " + json.dumps({"choices": [], "usage": {"completion_tokens": 7}}),
            {"piece": "", "think": "", "finish": None, "usage": {"completion_tokens": 7}},
        ),
        ("tensorfold", "data: [DONE]", {"end": True}),
        ("tensorfold", ": keep-alive", None),
        (
            "tensorfold",
            "data: " + json.dumps({"error": {"message": "out of memory"}}),
            {"error": "{'message': 'out of memory'}"},
        ),
    ],
)
def test_each_stream_line_is_read_for_its_text_finish_and_counts(engine, line, expected):
    """A hit cap is read from the finish reason, and the token counts from the closing event or the usage
    block, which TensorFold sends in a chunk with no choices."""
    assert er.read_event(engine, line) == expected


def test_the_engine_counts_come_from_each_engines_own_record():
    ollama = er.engine_counts(
        "ollama",
        {
            "prompt_eval_count": 100,
            "eval_count": 50,
            "eval_duration": 2e9,
            "prompt_eval_duration": 1e9,
            "load_duration": 0,
        },
        {},
    )
    assert (ollama["prompt_tokens"], ollama["completion_tokens"], ollama["engine_decode_tps"]) == (
        100,
        50,
        25.0,
    )
    tf = er.engine_counts(
        "tensorfold",
        {},
        {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "prompt_tokens_details": {"cached_tokens": 64},
            "accepted": 30,
        },
    )
    assert (tf["prompt_tokens"], tf["completion_tokens"], tf["cached_tokens"]) == (100, 50, 64)
    assert tf["usage_extra"] == {"accepted": 30}
    # A stream that ended with no closing event has no counts, rather than a made-up rate.
    assert er.engine_counts("ollama", {}, {})["engine_decode_tps"] is None


def _recorded(tmp_path, engine: str, lines: list[str]):
    path = tmp_path / f"{engine}.jsonl"
    rows = [json.dumps({"request": {}})] + [json.dumps({"t": "0", "line": line}) for line in lines]
    path.write_text("\n".join(rows))
    return er.recorded_answer(path, engine)


def test_a_recorded_answer_keeps_the_counts_the_cap_check_reads(tmp_path):
    """The handler drops a cut final block only when ``completion_tokens`` reaches the cap (#2149). An
    answer rebuilt without TensorFold's usage-only chunk, or Ollama's closing event, has no count, so a
    cut-off answer would be scored as a pass."""
    tf = _recorded(
        tmp_path,
        "tensorfold",
        [
            ": keep-alive",
            "data: " + json.dumps({"choices": [{"delta": {"reasoning_content": "plan "}}]}),
            "data: " + json.dumps({"choices": [{"delta": {"content": "```py:a.py\nx = "}}]}),
            "data: " + json.dumps({"choices": [{"delta": {}, "finish_reason": "length"}]}),
            "data: "
            + json.dumps(
                {"choices": [], "usage": {"prompt_tokens": 9, "completion_tokens": 12288}}
            ),
            "data: [DONE]",
        ],
    )
    assert tf == {
        "content": "```py:a.py\nx = ",
        "reasoning_text": "plan ",
        "finish": "length",
        "prompt_tokens": 9,
        "completion_tokens": 12288,
    }
    ollama = _recorded(
        tmp_path,
        "ollama",
        [
            json.dumps({"message": {"content": "", "thinking": "t"}, "done": False}),
            json.dumps({"message": {"content": "ok"}, "done": False}),
            json.dumps(
                {
                    "message": {"content": ""},
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 7,
                    "eval_count": 30,
                }
            ),
        ],
    )
    assert (ollama["content"], ollama["reasoning_text"], ollama["completion_tokens"]) == (
        "ok",
        "t",
        30,
    )


def test_an_answer_with_no_thinking_hands_the_handler_none(tmp_path):
    answer = _recorded(
        tmp_path,
        "tensorfold",
        [
            "data: "
            + json.dumps({"choices": [{"delta": {"content": "x"}, "finish_reason": "stop"}]})
        ],
    )
    assert (answer["reasoning_text"], answer["completion_tokens"]) == (None, None)
