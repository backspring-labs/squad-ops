"""#1897 — a qa self-evaluation pass that edits its suite leaves the suite a suite.

Shakeout 4's increment 1 (``cyc_13ad0d592175``, task m004): the pass repaired
``backend/tests/criteria/test_T2.py`` with an anchored edit, the edited file came back typed
``source``, and the suite then ran on no test files. Entered at ``HandlerExecutor.execute`` on
the real qa handler and templates, the path the qa agent runs.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.agents.base import PortsBundle
from squadops.bootstrap.handlers import create_handler_registry
from squadops.capabilities.handlers.test_runner import RunTestsResult
from squadops.llm.models import ChatMessage
from squadops.orchestration.handler_executor import HandlerExecutor
from squadops.prompts.renderer import RequestTemplateRenderer
from squadops.tasks.models import TaskEnvelope

pytestmark = [pytest.mark.domain_capabilities]

_PROMPTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"
_PATH = "backend/tests/criteria/test_T2.py"
_SUITE = "def test_join_at_capacity_is_refused(client):\n    assert client is not None\n"
_FIRST = f"```python:{_PATH}\n{_SUITE}```\n"
_EDIT = (
    f"```edit:{_PATH}\n<<<<<<< SEARCH\ndef test_join_at_capacity_is_refused(client):\n=======\n"
    "import pytest\n\n\ndef test_join_at_capacity_is_refused(client):\n>>>>>>> REPLACE\n```\n"
)
_WHOLE = f"```python:{_PATH}\nimport pytest\n\n\n{_SUITE}```\n"


async def _qa(pass_answer: str, monkeypatch, caplog):
    runner = AsyncMock(return_value=RunTestsResult(executed=True, exit_code=0, stdout="1 passed"))
    monkeypatch.setattr("squadops.capabilities.handlers.test_runner.run_generated_tests", runner)
    answers = iter([_FIRST, pass_answer])

    async def _chat(messages, **kwargs):
        return ChatMessage(role="assistant", content=next(answers), completion_tokens=40)

    llm = MagicMock()
    llm.default_model = "qwen3.8:27b"
    llm.chat_stream_with_usage = _chat
    prompt_service = MagicMock()
    prompt_service.assemble.return_value = MagicMock(content="system", assembly_hash="h")
    ports = PortsBundle(
        llm=llm,
        memory=MagicMock(),
        prompt_service=prompt_service,
        queue=MagicMock(),
        metrics=MagicMock(),
        events=MagicMock(),
        filesystem=MagicMock(),
        request_renderer=RequestTemplateRenderer(
            FilesystemPromptAssetAdapter(_PROMPTS / "fragments", _PROMPTS / "request_templates")
        ),
    )
    envelope = TaskEnvelope(
        task_id="task-run_1-m004-qa.test",
        agent_id="eve",
        cycle_id="cyc",
        pulse_id="p",
        project_id="group_run",
        task_type="qa.test",
        correlation_id="c",
        causation_id="c",
        trace_id="t",
        span_id="s",
        inputs={
            "prd": "Runs API",
            "artifact_contents": {"backend/routes.py": "def join():\n    return {}\n"},
            "subtask_focus": "criterion T2's file",
            "expected_artifacts": [_PATH],
            "acceptance_criteria": [
                {
                    "check": "import_present",
                    "params": {"file": _PATH, "module": "pytest"},
                    "id": "vc-t2-imports-pytest",
                }
            ],
            "resolved_config": {"output_validation": True, "max_self_eval_passes": 1},
        },
    )
    executor = HandlerExecutor("eve", create_handler_registry(roles=["qa"]), ports, role="qa")
    with caplog.at_level(logging.INFO):
        result = await executor.execute(envelope)
    suites = [[f["path"] for f in call.args[1]] for call in runner.await_args_list]
    stored = {a["name"]: a for a in (result.outputs or {}).get("artifacts", [])}
    return result, suites, stored


@pytest.mark.parametrize("answer", [_EDIT, _WHOLE], ids=["edits-the-file", "re-emits-it-whole"])
async def test_the_file_a_pass_repairs_is_the_file_the_suite_runs(monkeypatch, caplog, answer):
    """Bug caught (#1897): the edited file typed by its path, ``source``, so the suite the
    pass had just repaired ran on no test files and the task failed ``tests_pass``. The
    whole-file pass, typed by the handler, is the control."""
    result, suites, stored = await _qa(answer, monkeypatch, caplog)

    assert result.status == "SUCCEEDED", result.error
    assert suites[-1] == [_PATH], "the suite ran on the repaired file"
    assert stored[_PATH]["type"] == "test"
    assert stored[_PATH]["content"].startswith("import pytest\n")
