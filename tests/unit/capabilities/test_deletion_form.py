"""The deletion form, read and judged (#2612, SIP-0112 H.23).

A step's response removes a file with a ``delete:<path>`` fence. Each handler that parses emissions
either takes it, judged against the task's view and grant, or refuses it by name. Entered at the
parser, at ``read_deletions``, and at each handler's ``handle`` through a model answering the form.

Bugs caught:
- a deletion fence read as a file, so the product's file is emptied rather than removed;
- a removal of a path the view doesn't hold, or that a test step's grant excludes, taken silently;
- a removal dropped with nothing saying so, on a step that takes none;
- a task that names the file it removes failing its own expected-artifacts check;
- a repair whose one act is a removal read as an empty emission.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler
from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.capabilities.handlers.emitted_deletions import (
    REFUSED_ALREADY_REMOVED,
    REFUSED_HELD_BACK,
    REFUSED_NO_PRODUCT,
    REFUSED_NOT_GRANTED,
    REFUSED_NOT_IN_VIEW,
    REFUSED_OUTSIDE_GRANT,
    REFUSED_WRITTEN_TOO,
    read_deletions,
    without_removed,
)
from squadops.capabilities.handlers.fenced_parser import (
    MALFORMED_DELETION_UNSAFE_PATH,
    MALFORMED_DELETION_WITH_CONTENT,
    extract_fenced_deletions,
    extract_fenced_files,
)
from squadops.capabilities.handlers.impl.repair_handlers import (
    BuilderAssembleRepairHandler,
    DevelopmentCorrectionRepairHandler,
    QATestRepairHandler,
)
from squadops.capabilities.handlers.source_repository import source_repository_section
from squadops.cycles.deletions import DELETIONS_KEY, DELETIONS_REFUSED_KEY
from squadops.cycles.emission_integrity import emission_retry_reason_line
from squadops.llm.models import ChatMessage
from squadops.prompts.renderer import RequestTemplateRenderer
from squadops.tasks.task_types import DeletionGrant, TaskType, deletion_grant

_PROMPTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"
_REMOVE = "```delete:tally/old_report.py\n```\n"
_KEEP = "```python:tally/report.py\nprint('kept')\n```\n"
_VIEW = {
    "commit": "9a1c2f3e4b5d6a7f",
    "map": "- `tally/report.py` (10 bytes)",
    "paths": [
        "assets/mark.png",
        "checks/check_report.py",
        "tally/old_report.py",
        "tally/report.py",
    ],
    "held_back": ["assets/mark.png"],
    "deleted": [],
    "checks": [],
    "runners": [
        {
            "runner": "unittest",
            "checks": ["report"],
            "roots": ["checks"],
            "file_pattern": "check_*.py",
            "covers": ["tally/**"],
        }
    ],
    "instructions": {},
    "existing_files": {},
}


def _inputs(view=_VIEW, **extra):
    return {"prd": "fold the report", "source_repository": view, **extra}


# --- the parser ------------------------------------------------------------------------------


def test_a_deletion_fence_is_never_a_file():
    """Bug caught: ``delete`` read as a language slot, which wrote an empty file at the path."""
    assert [f["filename"] for f in extract_fenced_files(_KEEP + _REMOVE)] == ["tally/report.py"]


def test_a_deletion_fence_takes_no_fallback_of_a_lone_unlabeled_fence():
    """#566's fallback maps a lone filename-less fence only when nothing is labeled. A deletion
    fence is a label, so a model's prose fence beside it is never written over the expected
    file."""
    response = "```\nsome notes\n```\n" + _REMOVE
    assert extract_fenced_files(response, expected_artifacts=["tally/report.py"]) == []


@pytest.mark.parametrize(
    ("response", "paths", "malformed"),
    [
        (_REMOVE, ("tally/old_report.py",), ()),
        # blank lines inside are no content
        ("```delete:a.py\n\n\n```\n", ("a.py",), ()),
        # the fence closes at the end of the response
        ("```delete:a.py\n```", ("a.py",), ()),
        # one removal, however many times it is named
        (_REMOVE + _REMOVE, ("tally/old_report.py",), ()),
        # a label wedged into the header heals as a file's does (#431)
        ("```delete:path:a.py\n```\n", ("a.py",), ()),
        ("```python:a.py\nx\n```\n", (), ()),
        ("", (), ()),
    ],
    ids=["one", "blank-body", "eof", "twice", "label", "a-file", "empty"],
)
def test_the_form_is_read(response, paths, malformed):
    read = extract_fenced_deletions(response)
    assert (read.paths, read.malformed) == (paths, malformed)


@pytest.mark.parametrize(
    ("response", "path", "reason"),
    [
        ("```delete:/etc/passwd\n```\n", "/etc/passwd", MALFORMED_DELETION_UNSAFE_PATH),
        ("```delete:../secrets.env\n```\n", "../secrets.env", MALFORMED_DELETION_UNSAFE_PATH),
        ("```delete:a.py\nprint('x')\n```\n", "a.py", MALFORMED_DELETION_WITH_CONTENT),
    ],
    ids=["absolute", "traversal", "a-body"],
)
def test_a_malformed_fence_is_named_and_is_no_removal(response, path, reason):
    """Bug caught: a body under the fence read as a removal (it may be a file meant to be
    written) or an escaping path taken."""
    read = extract_fenced_deletions(response)
    assert read.paths == ()
    assert [(m[0], m[1]) for m in read.malformed] == [(path, reason)]


def test_a_step_that_takes_no_deletions_has_each_one_logged_as_refused(caplog):
    """The doc authors' and the builder's reading: the form is neither applied nor silent."""
    with caplog.at_level(logging.WARNING):
        assert extract_fenced_files(_REMOVE) == []
    assert "deletion form refused" in caplog.text and "tally/old_report.py" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        extract_fenced_files(_REMOVE, deletions_taken=True)
    assert "deletion form refused" not in caplog.text


# --- the grant -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("task_type", "grant"),
    [
        (TaskType.DEVELOPMENT_DEVELOP, DeletionGrant.PRODUCT),
        ("development.correction_repair", DeletionGrant.PRODUCT),
        (TaskType.QA_TEST, DeletionGrant.TESTS),
        ("qa.test_repair", DeletionGrant.TESTS),
        (TaskType.BUILDER_ASSEMBLE, None),
        (TaskType.DEVELOPMENT_DESIGN_PLAN, None),
        ("no.such_step", None),
    ],
)
def test_a_step_is_granted_what_it_authors(task_type, grant):
    """Bug caught: a planning or builder step able to remove a product file, or a repair
    unable to while its plan's author can."""
    assert deletion_grant(task_type) == grant


@pytest.mark.parametrize(
    ("response", "task_type", "view", "written", "refused"),
    [
        ("```delete:tally/ghost.py\n```\n", "development.develop", _VIEW, (), REFUSED_NOT_IN_VIEW),
        ("```delete:assets/mark.png\n```\n", "development.develop", _VIEW, (), REFUSED_HELD_BACK),
        (_REMOVE, "development.develop", _VIEW, ("tally/old_report.py",), REFUSED_WRITTEN_TOO),
        (
            _REMOVE,
            "development.develop",
            {**_VIEW, "deleted": ["tally/old_report.py"]},
            (),
            REFUSED_ALREADY_REMOVED,
        ),
        (_REMOVE, "qa.test", _VIEW, (), REFUSED_OUTSIDE_GRANT),
        (_REMOVE, "qa.test_repair", _VIEW, (), REFUSED_OUTSIDE_GRANT),
        # a product with no runner holds no test a qa step could remove
        (
            "```delete:checks/check_report.py\n```\n",
            "qa.test",
            {**_VIEW, "runners": []},
            (),
            REFUSED_OUTSIDE_GRANT,
        ),
        (_REMOVE, "builder.assemble", _VIEW, (), REFUSED_NOT_GRANTED),
    ],
    ids=[
        "no-such-file",
        "binary",
        "written-and-removed",
        "already-removed",
        "qa-outside-its-grant",
        "qa-repair-outside-its-grant",
        "qa-no-runner",
        "builder",
    ],
)
def test_a_removal_is_refused_by_name(response, task_type, view, written, refused):
    reading = read_deletions(response, _inputs(view), task_type, written)

    assert reading.accepted == ()
    assert [r.reason for r in reading.refused] == [refused]
    outputs = reading.outputs()
    assert outputs[DELETIONS_REFUSED_KEY][0]["reason"] == refused
    assert DELETIONS_KEY not in outputs
    # the retry is told which and why, not the generic extraction line
    line = emission_retry_reason_line(outputs["emission_failure"])
    assert reading.refused[0].path in line and refused in line


def test_a_run_with_no_product_removes_nothing():
    reading = read_deletions(_REMOVE, {"prd": "x"}, "development.develop", ())
    assert [r.reason for r in reading.refused] == [REFUSED_NO_PRODUCT]


def test_a_test_step_removes_a_test_a_runner_holds():
    """The grant's inside. Bug caught: the runner's rule read as a substring of the path, or
    every removal by a qa step refused."""
    reading = read_deletions(
        "```delete:checks/check_report.py\n```\n", _inputs(), "qa.test", ("checks/check_new.py",)
    )
    assert reading.accepted == ("checks/check_report.py",) and reading.refused == ()


def test_one_refused_removal_refuses_them_all():
    """All or nothing, as an anchored edit's transaction is: half an intended change is not the
    change."""
    reading = read_deletions(
        _REMOVE + "```delete:tally/ghost.py\n```\n", _inputs(), "development.develop", ()
    )
    assert reading.accepted == ()
    assert [r.path for r in reading.refused] == ["tally/ghost.py"]


def test_each_removal_is_judged_against_everything_the_emission_writes():
    """``written`` arrives as a generator from the handlers. Bug caught: the first path's check
    consuming it, so the second is taken though the same emission writes it."""
    reading = read_deletions(
        _REMOVE + "```delete:tally/report.py\n```\n",
        _inputs(),
        "development.develop",
        (name for name in ["tally/report.py"]),
    )

    assert reading.accepted == ()
    assert [(r.path, r.reason) for r in reading.refused] == [
        ("tally/report.py", REFUSED_WRITTEN_TOO)
    ]


def test_the_expected_list_gives_up_what_the_emission_removes():
    inputs = _inputs(expected_artifacts=["tally/old_report.py", "tally/report.py"])
    assert without_removed(inputs, ("tally/old_report.py",))["expected_artifacts"] == [
        "tally/report.py"
    ]
    # nothing removed: the same mapping, so an unchanged task reads as it did
    assert without_removed(inputs, ()) is inputs


# --- each handler that parses emissions -------------------------------------------------------


def _context(reply: str, *, role: str = "dev") -> MagicMock:
    ctx = MagicMock()
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(
        return_value=ChatMessage(role="assistant", content=reply, completion_tokens=40)
    )
    ctx.ports.llm.default_model = "test-model"
    ctx.ports.prompt_service.get_system_prompt.return_value = MagicMock(
        content="system", assembly_hash="h"
    )
    ctx.ports.llm_observability = None
    ctx.ports.request_renderer = RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(_PROMPTS / "fragments", _PROMPTS / "request_templates")
    )
    ctx.correlation_context = None
    ctx.disputed_checks = []
    ctx.task_id = "task-1"
    ctx.role_id = role
    return ctx


def _develop_inputs(**extra):
    return _inputs(subtask_focus="fold the report", **extra)


async def test_the_developer_hands_on_a_removal_beside_its_files():
    result = await DevelopmentDevelopHandler().handle(
        _context(_KEEP + _REMOVE), _develop_inputs(expected_artifacts=["tally/report.py"])
    )

    assert result.success is True
    assert result.outputs[DELETIONS_KEY] == ["tally/old_report.py"]
    # never an artifact: every reader of a task's artifacts reads files
    assert [a["name"] for a in result.outputs["artifacts"]] == ["tally/report.py"]


async def test_a_task_that_names_the_file_it_removes_meets_its_expected_artifacts():
    """A task names a file to be shown it, so a plan that removes one names it. Bug caught: FC1
    reading the removed file as one the task failed to produce."""
    result = await DevelopmentDevelopHandler().handle(
        _context(_REMOVE),
        _develop_inputs(
            expected_artifacts=["tally/old_report.py"],
            resolved_config={"output_validation": True},
        ),
    )

    assert result.outputs[DELETIONS_KEY] == ["tally/old_report.py"]
    [row] = [
        c
        for c in result.outputs["validation_result"]["checks"]
        if c["check"] == "expected_artifacts"
    ]
    assert row["passed"] is True and row["missing"] == []


async def test_the_developers_refused_removal_fails_the_emission_by_name():
    result = await DevelopmentDevelopHandler().handle(
        _context(_KEEP + "```delete:tally/ghost.py\n```\n"), _develop_inputs()
    )

    assert result.success is False
    assert "tally/ghost.py" in result.error and REFUSED_NOT_IN_VIEW in result.error
    assert result.outputs["emission_failure"]["reason"] == "deletion_refused"
    assert result.outputs.get("artifacts", []) == []


async def test_a_response_that_removes_nothing_is_read_as_it_was():
    result = await DevelopmentDevelopHandler().handle(_context(_KEEP), _develop_inputs())
    assert DELETIONS_KEY not in result.outputs and DELETIONS_REFUSED_KEY not in result.outputs


_SUITE = "```python:checks/check_new.py\nimport unittest\n```\n"
_QA_INPUTS = {
    "artifact_contents": {"tally/report.py": "print('x')\n"},
    "subtask_focus": "the report suite",
    "expected_artifacts": ["checks/check_new.py"],
}


async def test_a_test_step_removes_the_test_it_replaces():
    result = await QATestHandler().handle(
        _context(_SUITE + "```delete:checks/check_report.py\n```\n", role="qa"),
        _inputs(**_QA_INPUTS),
    )

    assert result.outputs[DELETIONS_KEY] == ["checks/check_report.py"]
    assert "checks/check_report.py" not in [a["name"] for a in result.outputs["artifacts"]]


async def test_a_test_step_cant_remove_the_source_under_test():
    """The qa grant, entered at ``handle``: QA can't rewrite the source to agree with its test
    (SIP-0100 3.1), and it can't remove it either."""
    result = await QATestHandler().handle(
        _context(_SUITE + _REMOVE, role="qa"), _inputs(**_QA_INPUTS)
    )

    assert result.success is False
    assert result.outputs[DELETIONS_REFUSED_KEY][0]["reason"] == REFUSED_OUTSIDE_GRANT
    assert "`check_*.py` under `checks`" in result.error


_REPAIR_INPUTS = {
    "failed_task_type": "development.develop",
    "failure_evidence": {},
    "correction_decision": {},
}


async def test_a_repair_whose_one_act_is_a_removal_is_not_contentless():
    """Bug caught: the extraction fallback, or #1372's marker, reading a removal as a response
    with no file, so the round is refunded as empty or stores the response as a document."""
    result = await DevelopmentCorrectionRepairHandler().handle(
        _context(_REMOVE), _inputs(**_REPAIR_INPUTS)
    )

    assert result.outputs[DELETIONS_KEY] == ["tally/old_report.py"]
    assert result.outputs["artifacts"] == []
    assert "emission_failure" not in result.outputs


@pytest.mark.parametrize(
    ("handler", "reason"),
    [
        (DevelopmentCorrectionRepairHandler, REFUSED_NOT_IN_VIEW),
        (QATestRepairHandler, REFUSED_NOT_IN_VIEW),
        (BuilderAssembleRepairHandler, REFUSED_NOT_GRANTED),
    ],
)
async def test_a_repairs_refused_removal_refuses_the_repair_by_name(handler, reason):
    result = await handler().handle(
        _context(_KEEP + "```delete:tally/ghost.py\n```\n"),
        _inputs(**{**_REPAIR_INPUTS, "resolved_config": {}}),
    )

    assert result.outputs["artifacts"] == []
    assert result.outputs[DELETIONS_REFUSED_KEY][0]["reason"] == reason
    assert result.outputs["emission_failure"]["reason"] == "deletion_refused"


async def test_a_self_evaluation_pass_has_its_removal_refused_in_the_evidence():
    """Bug caught: a removal a pass makes dropped with nothing on the task's record. A pass
    revises what it was shown; the first emission is where a removal is judged."""
    first = "```python:tally/report.py\ndef f():\n    pass\n```\n"
    ctx = _context(first)
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(
        side_effect=[
            ChatMessage(role="assistant", content=first, completion_tokens=40),
            ChatMessage(role="assistant", content=_KEEP + _REMOVE, completion_tokens=40),
            ChatMessage(role="assistant", content=_KEEP, completion_tokens=40),
        ]
    )
    result = await DevelopmentDevelopHandler().handle(
        ctx,
        _develop_inputs(
            expected_artifacts=["tally/report.py", "tally/other.py"],
            resolved_config={"output_validation": True, "max_self_eval_passes": 1},
        ),
    )

    named = result.evidence.metadata[DELETIONS_REFUSED_KEY]
    assert [(r["path"], r["reason"]) for r in named] == [("tally/old_report.py", "self_eval_pass")]
    assert DELETIONS_KEY not in result.outputs


# --- what each step is shown ------------------------------------------------------------------


def _prompt(ctx) -> str:
    return "\n".join(
        str(m.content) for m in ctx.ports.llm.chat_stream_with_usage.await_args_list[0].args[0]
    )


async def test_the_developer_is_shown_the_form_through_the_real_template():
    """Wiring at ``handle`` through the real renderer and assets (#448; the standard's rule 8)."""
    ctx = _context(_KEEP)
    await DevelopmentDevelopHandler().handle(ctx, _develop_inputs())

    prompt = _prompt(ctx)
    assert "````\n```delete:docs/old-setup-notes.md\n```\n````" in prompt
    assert "{{deletion}}" not in prompt


async def test_a_test_step_is_shown_the_form_in_its_runners_terms():
    """Bug caught: a test step taught to remove a source file, or a Python-shaped example shown
    on a product its runner reads another way (#2876)."""
    ctx = _context(_SUITE, role="qa")
    await QATestHandler().handle(ctx, _inputs(**_QA_INPUTS))

    prompt = _prompt(ctx)
    assert "```delete:checks/check_replaced.py\n```" in prompt
    assert "docs/old-setup-notes.md" not in prompt


async def test_a_test_step_of_a_product_with_no_runner_is_shown_no_form():
    ctx = _context(_SUITE, role="qa")
    await QATestHandler().handle(ctx, _inputs({**_VIEW, "runners": []}, **_QA_INPUTS))

    assert "```delete:" not in _prompt(ctx)


@pytest.mark.parametrize("task_type", [None, "strategy.analyze_prd", "builder.assemble"])
async def test_a_step_that_removes_nothing_is_shown_no_form(task_type):
    """Bug caught: a framing or plan author taught a form its step refuses."""
    ctx = _context("x")
    section = await source_repository_section(
        ctx.ports.request_renderer, _inputs(), task_type=task_type
    )

    assert "## THE PRODUCT YOU ARE CHANGING" in section and "```delete:" not in section
