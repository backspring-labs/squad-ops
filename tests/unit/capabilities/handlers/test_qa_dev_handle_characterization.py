"""qa and dev ``handle()``, characterized whole before #1444 extracts from them.

#1444 moves the self-evaluation loop and the shared generation tail out of
``QATestHandler.handle`` and ``DevelopmentDevelopHandler.handle`` onto the base handler,
and gathers the qa handler's fill-mode steps into one unit. That is an extraction: no
byte of what reaches the model, what the suite runs on, what the handler returns, what
it banks as evidence, or what it logs may change.

``test_llm_call_characterization.py`` already pins the self-eval transcripts. It does not
pin a fill-mode run end to end, and fill mode is where the steps interleave: the fill
parse, the scaffold merge, the shell-rewrite drop, the self-eval fill fold, the fill-merge
evidence artifact and the scaffold evidence all ride one function today. These cases
drive the real ``handle()`` through each shape and compare everything observable against
a golden captured from the code BEFORE the extraction.

Bug caught: an extraction that changes behaviour in one shape while the other stays
green — a follow-up fill folded after the file merge instead of before it, a shell
rewrite a self-eval pass is no longer stopped from making, the trigger log lost from the
qa path or gained on the dev path, the fill-mode prompt section rendered for an authoring
task, or the empty-emission failure losing its #1372 content.

Regenerate (only for a DELIBERATE behaviour change, in the PR that makes it):
    UPDATE_HANDLE_GOLDENS=1 pytest tests/unit/capabilities/handlers/test_qa_dev_handle_characterization.py
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler
from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.capabilities.handlers.test_runner import RunTestsResult
from squadops.capabilities.verification_scaffold_emission import emit_verification_scaffold
from squadops.llm.models import ChatMessage
from tests.unit.capabilities._stack_fixtures import manifest_for_stack

pytestmark = [pytest.mark.domain_capabilities]

_GOLDEN_PATH = Path(__file__).parent / "goldens" / "qa_dev_handle_characterization.json"
_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
_SHELL = "__tests__/scaffold/vc-probe-api-runs.scaffold.test.ts"
_LOGGERS = (
    "squadops.capabilities.handlers.cycle.qa_test",
    "squadops.capabilities.handlers.cycle.develop",
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


class _Renderer:
    """A request renderer whose output is a hash of exactly what it was asked to render,
    so a section rendered with different variables — or rendered at all where it was not
    before — changes the prompt and therefore the golden."""

    async def render(self, template_id: str, variables: dict[str, Any], environment: str = "x"):
        payload = json.dumps(variables, sort_keys=True, default=str)
        rendered = MagicMock()
        rendered.content = f"[{template_id} {_sha(payload)}]"
        rendered.template_id = template_id
        rendered.template_version = "1"
        rendered.render_hash = _sha(template_id + payload)
        return rendered


def _context(*responses: str) -> tuple[MagicMock, list]:
    calls: list[tuple[list[ChatMessage], dict]] = []
    queued = list(responses)

    ctx = MagicMock()
    assembled = MagicMock()
    assembled.content = "System prompt"
    assembled.assembly_hash = "sha256:test"
    ctx.ports.prompt_service.get_system_prompt.return_value = assembled
    ctx.ports.prompt_service.assemble.return_value = assembled
    ctx.ports.request_renderer = _Renderer()
    ctx.ports.llm.default_model = "test-model"

    async def _capture(messages, **kwargs):
        calls.append((list(messages), dict(kwargs)))
        if not queued:
            raise AssertionError(f"handler made {len(calls)} LLM calls; fewer were seeded")
        return ChatMessage(
            role="assistant", content=queued.pop(0), prompt_tokens=11, completion_tokens=7
        )

    ctx.ports.llm.chat_stream_with_usage = _capture
    ctx.correlation_context = None
    return ctx, calls


def _suite_result(failures: tuple[dict, ...] = ()) -> RunTestsResult:
    return RunTestsResult(
        executed=True,
        exit_code=1 if failures else 0,
        stdout="1 failed" if failures else "3 passed",
        runner="vitest",
        suite_broken=False,
        test_file_count=3,
        source_file_count=2,
        test_failures=failures,
    )


def _normalize(value: Any) -> Any:
    """Artifact contents become their hash and length, so the golden stays readable
    while still pinning every byte."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k == "content" and isinstance(v, str):
                out[k] = {"sha": _sha(v), "len": len(v)}
            else:
                out[k] = _normalize(v)
        return out
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


async def _run(handler, responses, inputs, monkeypatch, caplog, suite=None) -> dict:
    ran_on: list[list[dict]] = []

    async def _fake_build_validation(framework, sources, tests, timeout_seconds=None):
        ran_on.append([{"path": t["path"], "sha": _sha(t["content"])} for t in tests])
        return suite if suite is not None else _suite_result()

    monkeypatch.setattr(
        "squadops.capabilities.handlers.test_runner.run_build_validation", _fake_build_validation
    )
    ctx, calls = _context(*responses)
    with caplog.at_level(logging.INFO):
        result = await handler.handle(ctx, inputs)

    for artifact in result.outputs.get("artifacts", []):
        if artifact.get("type") == "typed_check_evaluation":
            # The one wall-clock field in the output; everything else in it is pinned.
            body = json.loads(artifact["content"])
            body.pop("evaluated_at", None)
            artifact["content"] = json.dumps(body, sort_keys=True)

    return _normalize(
        {
            "success": result.success,
            "error": result.error,
            "transcripts": [
                [[m.role, {"sha": _sha(m.content), "len": len(m.content)}] for m in msgs]
                for msgs, _ in calls
            ],
            "kwargs": [kw for _, kw in calls],
            "suite_ran_on": ran_on,
            "outputs": result.outputs,
            "outputs_keys": list(result.outputs),
            "evidence_metadata": result.evidence.metadata,
            "log": [r.getMessage() for r in caplog.records if r.name in _LOGGERS],
        }
    )


@pytest.fixture(scope="module")
def scaffold_input() -> dict:
    emission = emit_verification_scaffold(manifest_for_stack("nextjs_ts"))
    return {
        "manifest": emission.manifest.to_dict(),
        "files": [dict(f) for f in emission.files],
    }


def _fenced(path: str, body: str, lang: str = "python") -> str:
    return f"```{lang}:{path}\n{body}\n```\n"


def _stored(name: str) -> str:
    return (_FIXTURES / "roll_replays" / name).read_text(encoding="utf-8")


def _reference_routes() -> str:
    path = _FIXTURES / "reference_fills/fullstack_fastapi_react/group_run/backend/routes.py"
    return path.read_text(encoding="utf-8")


def _cases(scaffold: dict) -> dict[str, dict]:
    qa_suite = _stored("1-6-6-react-roll-1-backend-suite.py.txt")
    nextjs_suite = _stored("1-7-3-nextjs-checkpoint-runs.test.ts")
    fill_create = "```fill:slot-vc-probe-api-runs\n    expect(body.id).toBeTruthy()\n```\n"
    fill_join = (
        "```fill:slot-vc-probe-api-runs-join\n    expect(body.participants).toHaveLength(1)\n```\n"
    )
    return {
        # qa, whole-file authoring: the primary names the wrong file, validation fails on
        # the expected artifact, and one self-eval pass emits the stored roll-1 suite.
        "qa_authoring_self_eval": {
            "handler": QATestHandler,
            "responses": [
                _fenced("tests/test_wrong.py", "def test_a():\n    assert True"),
                _fenced("tests/test_routes.py", qa_suite),
            ],
            "inputs": {
                "prd": "group_run",
                "subtask_focus": "cover the routes",
                "expected_artifacts": ["tests/test_routes.py"],
                "acceptance_criteria": [],
                "artifact_contents": {"backend/routes.py": _reference_routes()},
                "resolved_config": {"output_validation": True, "max_self_eval_passes": 1},
            },
        },
        "qa_authoring_no_fenced_blocks": {
            "handler": QATestHandler,
            "responses": ["I will write the tests for the routes module next."],
            "inputs": {
                "prd": "group_run",
                "subtask_focus": "cover the routes",
                "expected_artifacts": ["tests/test_routes.py"],
                "artifact_contents": {"backend/routes.py": _reference_routes()},
                "resolved_config": {"output_validation": True},
            },
        },
        # qa, fill mode: fills only on the primary; the expected additive file is missing,
        # so a self-eval pass runs and emits a second fill, the additive suite from the
        # 1.7.3 checkpoint, and an attempted shell rewrite that must be dropped. The canned
        # runner reports a shell failure so the P5 scaffold evidence has a row to classify.
        "qa_fill_self_eval": {
            "handler": QATestHandler,
            "responses": [
                "Fills below.\n\n" + fill_create,
                fill_join
                + _fenced("__tests__/runs.test.ts", nextjs_suite, "typescript")
                + _fenced(_SHELL, "// REWRITTEN", "typescript"),
            ],
            "inputs": {
                "prd": "group_run",
                "subtask_focus": "fill the scaffold",
                "expected_artifacts": ["__tests__/runs.test.ts"],
                "acceptance_criteria": [],
                "artifact_contents": {},
                "resolved_config": {
                    "development_profile": "nextjs_ts",
                    "output_validation": True,
                    "max_self_eval_passes": 1,
                },
                "verification_scaffold": scaffold,
            },
            "suite": _suite_result(
                (
                    {
                        "file": _SHELL,
                        "title": "POST /api/runs -> 201 [vc-probe-api-runs]",
                        "messages": ["expected 500 to be 201 // Object.is equality"],
                        "line": 12,
                        "suite_level": False,
                    },
                )
            ),
        },
        "qa_fill_validation_off": {
            "handler": QATestHandler,
            "responses": [fill_create + fill_join],
            "inputs": {
                "prd": "group_run",
                "subtask_focus": "fill the scaffold",
                "expected_artifacts": [],
                "artifact_contents": {},
                "resolved_config": {"development_profile": "nextjs_ts"},
                "verification_scaffold": scaffold,
            },
        },
        "qa_fill_no_fills_no_files": {
            "handler": QATestHandler,
            "responses": ["The slots are straightforward; I will fill them."],
            "inputs": {
                "prd": "group_run",
                "subtask_focus": "fill the scaffold",
                "expected_artifacts": [],
                "artifact_contents": {},
                "resolved_config": {"development_profile": "nextjs_ts", "output_validation": True},
                "verification_scaffold": scaffold,
            },
        },
        # dev: the primary names the wrong file; one self-eval pass emits the reference
        # routes module. The dev loop has no trigger log and classifies by filename.
        "dev_self_eval": {
            "handler": DevelopmentDevelopHandler,
            "responses": [
                _fenced("backend/wrong.py", "x = 1"),
                _fenced("backend/routes.py", _reference_routes()),
            ],
            "inputs": {
                "prd": "group_run",
                "subtask_focus": "backend routes",
                "expected_artifacts": ["backend/routes.py"],
                "acceptance_criteria": [],
                "artifact_contents": {},
                "resolved_config": {"output_validation": True, "max_self_eval_passes": 1},
            },
        },
        "dev_no_fenced_blocks": {
            "handler": DevelopmentDevelopHandler,
            "responses": ["The routes module needs a join endpoint."],
            "inputs": {
                "prd": "group_run",
                "subtask_focus": "backend routes",
                "expected_artifacts": ["backend/routes.py"],
                "artifact_contents": {},
                "resolved_config": {"output_validation": True},
            },
        },
    }


_CASE_NAMES = [
    "qa_authoring_self_eval",
    "qa_authoring_no_fenced_blocks",
    "qa_fill_self_eval",
    "qa_fill_validation_off",
    "qa_fill_no_fills_no_files",
    "dev_self_eval",
    "dev_no_fenced_blocks",
]


@pytest.mark.parametrize("case", _CASE_NAMES)
async def test_handle_is_unchanged_on_every_shape(case, scaffold_input, monkeypatch, caplog):
    spec = _cases(scaffold_input)[case]
    observed = await _run(
        spec["handler"](),
        spec["responses"],
        spec["inputs"],
        monkeypatch,
        caplog,
        suite=spec.get("suite"),
    )

    golden = json.loads(_GOLDEN_PATH.read_text()) if _GOLDEN_PATH.exists() else {}
    if os.environ.get("UPDATE_HANDLE_GOLDENS") == "1":
        golden[case] = observed
        _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        _GOLDEN_PATH.write_text(json.dumps(golden, indent=1, sort_keys=True) + "\n")
        return

    assert case in golden, f"no golden for {case}; capture it from the pre-extraction code"
    assert observed == golden[case], (
        f"{case}: handle() changed what it sends, runs, returns, banks or logs. If the "
        "change is DELIBERATE, regenerate the golden in the same PR so it reads as a "
        "behaviour change, never as a refactor side effect."
    )


def test_the_cases_exercise_what_the_extraction_moves(scaffold_input):
    """Guards the golden against going vacuous: a case that silently stopped reaching
    the self-eval loop, the fill fold or the shell drop would still match its own
    regenerated golden and prove nothing."""
    golden = json.loads(_GOLDEN_PATH.read_text())

    fill = golden["qa_fill_self_eval"]
    assert len(fill["transcripts"]) == 2  # the self-eval pass ran
    meta = fill["evidence_metadata"]
    assert meta["self_eval_passes"] == 1
    assert meta["self_eval_fills"][0]["applied"] == ["slot-vc-probe-api-runs-join"]
    assert "scaffold_evidence" in fill["outputs"]
    assert any("self_eval trigger" in line for line in fill["log"])
    assert any("emission parse: fills=1" in line for line in fill["log"])
    # the self-eval pass's rewrite of a merged shell never reached the stored artifacts
    shell_rows = [a for a in fill["outputs"]["artifacts"] if a["name"] == _SHELL]
    assert len(shell_rows) == 1
    assert shell_rows[0]["content"]["sha"] != _sha("// REWRITTEN")
    assert shell_rows[0]["content"]["len"] > len("// REWRITTEN")

    assert len(golden["dev_self_eval"]["transcripts"]) == 2
    assert not any("self_eval trigger" in line for line in golden["dev_self_eval"]["log"])
    for failed in ("qa_authoring_no_fenced_blocks", "qa_fill_no_fills_no_files"):
        assert golden[failed]["success"] is False
        assert "emission_failure" in golden[failed]["outputs"]
