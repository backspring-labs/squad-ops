"""SIP-0111 §4 (#2199): the replay sends both engines the same call, and reads both streams the same way."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import httpx
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
        "termination": "length",
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
    # Ollama's adapter reports no termination, so the handler reads the cap from the count, as live.
    assert (
        ollama["content"],
        ollama["reasoning_text"],
        ollama["completion_tokens"],
        ollama["termination"],
    ) == ("ok", "t", 30, None)


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


def _split(tmp_path, cells: dict[tuple[str, str, str], int]) -> Path:
    """A split whose held-out envelopes are named by their cell, and the store rows ``plan`` reads."""
    strata, rows = {}, []
    for (task_type, seam, stack), n in cells.items():
        ids = [f"{task_type}-{stack}-{i}" for i in range(n)]
        strata[f"{task_type}|{stack}"] = {"tuning": [], "held_out": ids}
        rows += [f"{eid}|{task_type}|{seam}|{stack}" for eid in ids]
    path = tmp_path / "split.json"
    path.write_text(json.dumps({"sha256": "s", "strata": strata}))
    return path, "\n".join(rows)


def test_the_held_out_plan_runs_every_generation_once_with_no_envelope_twice_in_a_row(
    tmp_path, monkeypatch
):
    """A generation run twice or not at all changes the denominator; an envelope after itself gets a
    prefix-cache hit its pair didn't. The panel is drawn from the held-out set, two per seam and stack."""
    split, rows = _split(
        tmp_path,
        {
            ("development.develop", "build_authoring", "react"): 5,
            ("qa.test_repair", "repair", "nextjs"): 1,
            ("development.design_plan", "plan_writing", "react"): 3,
        },
    )
    monkeypatch.setattr(er, "psql", lambda sql: rows)
    out = tmp_path / "plan.json"
    er.plan(split, out, seed=7)
    doc = json.loads(out.read_text())

    ids = [m["envelope_id"] for m in doc["held_out"]]
    assert sorted(map(tuple, doc["order"])) == sorted(
        (eid, g) for eid in ids for g in er.GENERATIONS
    )
    assert all(a[0] != b[0] for a, b in zip(doc["order"], doc["order"][1:], strict=False))
    cells = [
        next(m for m in doc["held_out"] if m["envelope_id"] == e)["seam"] for e in doc["panel"]
    ]
    assert sorted(cells) == ["build_authoring"] * 2 + ["plan_writing"] * 2 + ["repair"]
    er.plan(split, tmp_path / "again.json", seed=7)
    assert json.loads((tmp_path / "again.json").read_text())["sha256"] == doc["sha256"]


def test_a_plan_whose_envelopes_the_store_lacks_is_refused(tmp_path, monkeypatch):
    split, rows = _split(tmp_path, {("qa.test", "build_authoring", "react"): 2})
    monkeypatch.setattr(er, "psql", lambda sql: rows.splitlines()[0])
    with pytest.raises(SystemExit, match="does not hold"):
        er.plan(split, tmp_path / "plan.json", seed=7)


def test_both_generations_of_an_envelope_run_and_a_restart_skips_only_what_is_done(
    tmp_path, monkeypatch
):
    """Entered at ``run``, as the overnight driver calls it. Keyed by envelope alone, a restart would skip
    generation 2 once generation 1 was written, and both would write one raw file."""
    doc = {
        "held_out": [
            {"envelope_id": e, "task_type": "qa.test", "seam": "build_authoring", "stack": "react"}
            for e in ("a", "b")
        ],
        "order": [["a", 1], ["b", 1], ["a", 2], ["b", 2]],
        "panel": ["a"],
        "panel_seed": 1001,
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(doc))
    sent: list[tuple[str, int, str]] = []

    def fake_call(url, body, headers, raw_path, engine):
        sent.append((body["messages"][0]["content"], body["options"]["seed"], raw_path.name))
        return {"wall_s": 1.0, "finish": "stop"}

    monkeypatch.setattr(
        er,
        "envelope",
        lambda eid: envelope("medium") | {"messages": [{"role": "user", "content": eid}]},
    )
    monkeypatch.setattr(er, "stream_call", fake_call)
    done = tmp_path / "ollama" / "held-out"
    done.mkdir(parents=True)
    (done / "summary.jsonl").write_text(json.dumps({"envelope_id": "a", "seed": 1001}) + "\n")

    assert er.run(plan_path, "held-out", None, "ollama", None, tmp_path, None, None, None) == 0

    assert sent == [("b", 1001, "b-g1.jsonl"), ("a", 1002, "a-g2.jsonl"), ("b", 1002, "b-g2.jsonl")]
    rows = [json.loads(r) for r in (done / "summary.jsonl").read_text().splitlines()][1:]
    assert [(r["envelope_id"], r["generation"], r["raw"]) for r in rows] == [
        ("b", 1, "b-g1.jsonl"),
        ("a", 2, "a-g2.jsonl"),
        ("b", 2, "b-g2.jsonl"),
    ]


#: An invented header value standing for a key, never a real one: the shape a multi-line key file sent as one header has.
_SENT = "aaaa-bbbb-cccc-dddd"


@pytest.mark.parametrize(
    "exc, recorded",
    [
        # h11 quotes a refused header whole, the bearer key among it (#2744, seen 2026-10-27).
        (
            httpx.LocalProtocolError(f"Illegal header value b'Bearer {_SENT}\\nmother {_SENT}'"),
            "LocalProtocolError",
        ),
        (
            ConnectionRefusedError(111, f"refused, sent {_SENT}"),
            "ConnectionRefusedError (errno 111)",
        ),
        (ValueError(f"bad body: {_SENT}"), "ValueError"),
    ],
)
def test_a_call_that_fails_before_any_answer_records_its_type_never_its_text(
    exc, recorded, tmp_path, monkeypatch, capsys
):
    """Entered at ``run``, as the overnight driver calls it. A transport error's text can carry the
    request's headers, and the row is a ``var/`` record the line's Release carries (#2744): the key
    reached a replay row and stdout before this. The arm still counts the failure."""

    def failing_call(url, body, headers, raw_path, engine):
        raise exc

    monkeypatch.setattr(er, "envelope", lambda eid: envelope("medium"))
    monkeypatch.setattr(er, "stream_call", failing_call)

    assert (
        er.run(
            _two_envelope_plan(tmp_path),
            "held-out",
            None,
            "ollama",
            None,
            tmp_path,
            None,
            None,
            None,
        )
        == 0
    )

    summary = (tmp_path / "ollama" / "held-out" / "summary.jsonl").read_text()
    assert [json.loads(r)["error"] for r in summary.splitlines()] == [recorded, recorded]
    assert _SENT not in summary
    assert _SENT not in capsys.readouterr().out


@pytest.mark.parametrize(
    "engine, read",
    [
        ("ollama", lambda b: (b["options"]["temperature"], b["options"]["num_predict"])),
        ("tensorfold", lambda b: (b["temperature"], b["max_tokens"])),
    ],
)
def test_the_draft_checks_overrides_land_on_each_engines_own_fields(engine, read, monkeypatch):
    """The check compares a drafted reply with a plain one, so a sampler left on, or a cap written to a
    field the engine ignores, makes it compare two different calls."""
    monkeypatch.setattr(er, "api_key", lambda: "k")
    _, body, _ = er._request(
        envelope("medium"), engine, 1001, ("served", "medium"), True, True, 512
    )
    assert read(body) == (0.0, 512)
    _, plain, _ = er._request(
        envelope("medium"), engine, 1001, ("served", "medium"), None, False, None
    )
    # Without them, the call is production's: the envelope's own cap, and no sampler override.
    options = plain["options"] if engine == "ollama" else plain
    assert options.get("num_predict", options.get("max_tokens")) == 12288
    assert options.get("temperature") in (None, 1.0)


# --- #2253: the budget measurement's overrides ------------------------------------------------------


@pytest.mark.parametrize(
    "engine, cap",
    [("ollama", lambda b: b["options"]["num_predict"]), ("tensorfold", lambda b: b["max_tokens"])],
)
def test_max_tokens_sends_the_call_above_the_envelopes_cap(engine, cap, monkeypatch):
    """The raised-cap arm sends 16,384 on envelopes captured at 12,288. The draft check's
    ``--max-tokens-cap`` only lowers a cap, so an arm run with it would have sent 12,288 and measured
    nothing; a cap written to a field the engine ignores would send the envelope's own."""
    monkeypatch.setattr(er, "api_key", lambda: "k")
    env = envelope("medium", 12288)
    _, raised, _ = er._request(env, engine, 1001, ("served", "medium"), None, False, None, 16384)
    _, capped, _ = er._request(env, engine, 1001, ("served", "medium"), None, False, 16384)
    assert (cap(raised), cap(capped)) == (16384, 12288)


_ASSET = (
    "---\ntemplate_id: request.retry\nrequired_variables:\n  - completion_tokens\n---\n"
    "### Your previous response was cut off\n\nIt used {{completion_tokens}} tokens. Write the answer "
    "again, and keep any reasoning short so that the output fits.\n"
)
_QUOTE = "keep any reasoning short so that the output fits."


def test_the_note_is_the_assets_own_words_sent_after_the_envelopes_messages(tmp_path, monkeypatch):
    """A note paraphrased from the re-ask's asset measures some other instruction, and one merged into
    the envelope's messages changes the captured prompt for every later call. It goes last, as the
    re-ask sends its fact (#2149), on both engines."""
    asset = tmp_path / "retry.md"
    asset.write_text(_ASSET)
    note = er.first_call_note(asset, _QUOTE)
    assert (note["text"], note["asset_sha256"]) == (
        _QUOTE,
        hashlib.sha256(_ASSET.encode()).hexdigest(),
    )
    monkeypatch.setattr(er, "api_key", lambda: "k")
    env = envelope("medium")
    for engine in ("ollama", "tensorfold"):
        _, body, _ = er._request(
            env, engine, 1001, ("served", "medium"), None, False, None, None, note["text"]
        )
        assert body["messages"] == [*env["messages"], {"role": "user", "content": _QUOTE}]
    assert env["messages"] == envelope("medium")["messages"]


@pytest.mark.parametrize(
    "asset_text, quote, refusal",
    [
        (_ASSET, "keep your reasoning short.", "word for word"),  # a paraphrase
        (
            _ASSET,
            "template_id: request.retry",
            "word for word",
        ),  # the front matter is not the asset
        (_ASSET, None, "template variable"),  # the whole asset, its variable unrendered
        ("---\ntemplate_id: x\nno closing line\n", None, "front matter"),
    ],
)
def test_a_note_the_asset_does_not_hold_word_for_word_is_refused(
    tmp_path, asset_text, quote, refusal
):
    asset = tmp_path / "retry.md"
    asset.write_text(asset_text)
    with pytest.raises(SystemExit, match=refusal):
        er.first_call_note(asset, quote)


def _two_envelope_plan(tmp_path) -> Path:
    doc = {
        "held_out": [
            {
                "envelope_id": e,
                "task_type": "qa.test",
                "seam": "build_authoring",
                "stack": "nextjs_ts",
            }
            for e in ("a", "b")
        ],
        "order": [["a", 1], ["b", 1]],
        "panel": [],
        "panel_seed": 1001,
    }
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(doc))
    return path


def test_an_arm_records_its_overrides_and_a_restart_with_other_settings_is_refused(
    tmp_path, monkeypatch
):
    """Entered at ``run``, as the measurement calls it. Without the manifest, a restart with other
    settings appends to the first arm's summary and skips every call that arm made: one folder, two
    arms, and nothing to say which row is which."""
    plan = _two_envelope_plan(tmp_path)
    sent: list[tuple[int, str]] = []

    def fake_call(url, body, headers, raw_path, engine):
        sent.append((body["options"]["num_predict"], body["messages"][-1]["content"]))
        return {"wall_s": 1.0, "finish": "stop"}

    monkeypatch.setattr(
        er,
        "envelope",
        lambda eid: (
            envelope("medium", 12288)
            | {"messages": [{"role": "user", "content": eid}], "messages_sha256": eid}
        ),
    )
    monkeypatch.setattr(er, "stream_call", fake_call)
    note = {"asset": "a.md", "asset_sha256": "s", "quote": None, "text": "be brief"}
    note["text_sha256"] = hashlib.sha256(b"be brief").hexdigest()
    arm = tmp_path / f"ollama-max16384-note-{note['text_sha256'][:8]}" / "held-out"

    def go(greedy: bool = False) -> int:
        return er.run(
            plan, "held-out", None, "ollama", None, tmp_path, None, None, None, greedy, 16384, note
        )

    assert go() == 0
    settings = json.loads((arm / "manifest.json").read_text())["settings"]
    assert (settings["max_tokens"], settings["first_call_note"]["text"]) == (16384, "be brief")
    rows = [json.loads(r) for r in (arm / "summary.jsonl").read_text().splitlines()]
    assert [(r["envelope_id"], r["max_tokens"], r["captured_max_tokens"]) for r in rows] == [
        ("a", 16384, 12288),
        ("b", 16384, 12288),
    ]
    assert {(r["messages_sent"], r["first_call_note_sha256"]) for r in rows} == {
        (2, note["text_sha256"])
    }
    assert sent == [(16384, "be brief")] * 2

    assert go() == 0  # the same settings resume, and nothing is left to call
    assert len(sent) == 2
    with pytest.raises(SystemExit, match="greedy"):
        go(greedy=True)
    assert len(sent) == 2


def test_two_arms_under_one_name_are_refused_before_any_is_scored(tmp_path, monkeypatch):
    """Arms recorded under one name in two folders share every key, and the scorer's table would hand
    one arm's answers to both."""
    arms = []
    for out in ("first", "second"):
        part = tmp_path / out / "tensorfold-qwen27b-nvfp4" / "held-out"
        part.mkdir(parents=True)
        row = {"envelope_id": "e", "seed": 1001, "task_type": "qa.test", "seam": "build_authoring"}
        row |= {"stack": "nextjs_ts", "engine": "tensorfold-qwen27b-nvfp4", "raw": "e-g1.jsonl"}
        (part / "summary.jsonl").write_text(json.dumps(row) + "\n")
        (part / "e-g1.jsonl").write_text(
            json.dumps({"request": {}}) + "\n" + json.dumps({"t": 0, "line": "data: [DONE]"})
        )
        arms.append(part.parent)
    monkeypatch.syspath_prepend(str(ROOT / "scripts" / "dev"))
    monkeypatch.setattr(er, "envelope", lambda eid: {"role": "qa"})

    def no_container(*args, **kwargs):  # the refusal comes first: no agent container is reached
        raise AssertionError(f"reached a container: {args[0]}")

    monkeypatch.setattr(er.subprocess, "run", no_container)
    with pytest.raises(SystemExit, match="share a key"):
        er.score(arms, tmp_path / "scores.jsonl")
