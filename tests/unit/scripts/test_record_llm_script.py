"""Recording a scripted squad's script from a run's stored emissions (#2495).

Entry point: the script's ``main``, over a real ``FilesystemArtifactVault`` holding a run's
artifacts as the executor stores them (``producing_task_type``, ``task_id``, ``attempt``, and a
repair's ``written_by_*``). The script is loaded by path, so an import break fails CI.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
from squadops.capabilities.handlers.fenced_parser import extract_fenced_files
from squadops.cycles.models import ArtifactRef
from squadops.llm.script import AnswerKey, ScriptLibrary

pytestmark = [pytest.mark.domain_orchestration]

REPO = Path(__file__).resolve().parents[3]
T0 = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def recorder():
    path = REPO / "scripts" / "dev" / "record_llm_script.py"
    spec = importlib.util.spec_from_file_location("record_llm_script", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["record_llm_script"] = module
    spec.loader.exec_module(module)
    return module


async def _store(vault, n, filename, content, seconds, artifact_type="source", **metadata):
    await vault.store(
        ArtifactRef(
            artifact_id=f"art_{n:012d}",
            project_id="shelf",
            artifact_type=artifact_type,
            filename=filename,
            content_hash="",
            size_bytes=0,
            media_type="text/plain",
            created_at=T0 + timedelta(seconds=seconds),
            cycle_id="cyc_1",
            run_id="run_1",
            metadata=metadata,
        ),
        content.encode(),
    )


@pytest.fixture
async def vault_dir(tmp_path) -> Path:
    vault = FilesystemArtifactVault(tmp_path / "vault")
    analyze = {"producing_task_type": "strategy.analyze_prd", "task_id": "t-an"}
    develop = {"producing_task_type": "development.develop", "task_id": "t-dev"}
    await _store(vault, 1, "analysis.md", "# Analysis\n", 0, "document", **analyze)
    # The dev task's failed first attempt banked two files, stamped with their attempt (#1436);
    # its accepted second attempt is stored unstamped, as the executor stores accepted outputs.
    failed = {"attempt": 1, "emission_status": "failed", **develop}
    await _store(vault, 2, "app.py", "raise SystemExit(1)\n", 10, **failed)
    await _store(vault, 3, "util.py", "X = 1", 11, **failed)
    await _store(vault, 4, "app.py", "print('ok')\n", 20, **develop)
    # A repair's bytes, stored under the task it repaired, its writer named beside them.
    await _store(
        vault,
        5,
        "app.py",
        "print('repaired')\n",
        30,
        **develop,
        written_by_task_id="t-rep",
        written_by_task_type="development.correction_repair",
    )
    await _store(
        vault,
        6,
        "api.py",
        "ROUTES = []\n",
        45,
        producing_task_type="development.develop",
        task_id="t-dev2",
    )
    # Files no model call wrote: a seeded scaffold file and an ingested PRD.
    await _store(vault, 7, "main.py", "", 1, scaffold_seeded=True, **develop)
    await _store(vault, 8, "prd.md", "the PRD", 0, "document")
    return tmp_path / "vault"


async def test_a_run_is_recorded_as_one_answer_per_attempt_keyed_as_the_provider_counts(
    recorder, vault_dir, tmp_path, capsys
):
    """Bugs caught: a repair recorded under the task it repaired (its answer then lands at the
    develop key and the repair finds none), a retry folded into its first attempt, a seeded file
    read as an answer, and the occurrence counted per file instead of per task."""
    out = tmp_path / "scripts"
    code = await _run(recorder, vault_dir, out)

    assert code == 0
    script = ScriptLibrary(out).get("shelf-dev")
    assert sorted(script.answers) == [
        AnswerKey("development.correction_repair", 1, 1),
        AnswerKey("development.develop", 1, 1),
        AnswerKey("development.develop", 1, 2),
        AnswerKey("development.develop", 2, 1),
        AnswerKey("strategy.analyze_prd", 1, 1),
    ]
    assert script.answers[AnswerKey("strategy.analyze_prd", 1, 1)].content == "# Analysis\n"
    assert dict(script.recorded_from) == {
        "project_id": "shelf",
        "cycle_id": "cyc_1",
        "run_id": "run_1",
        "failed_in_recording": ["development.develop occurrence 1 call 1"],
        "latency": {"scale": 1.0, "cap_seconds": None, "capped": 0, "total_seconds": 44.0},
    }
    # The latency is the gap from the previous attempt's last file: 10-0, 20-11, 30-20, 45-30.
    assert [
        script.answers[k].latency_seconds
        for k in [
            AnswerKey("strategy.analyze_prd", 1, 1),
            AnswerKey("development.develop", 1, 1),
            AnswerKey("development.develop", 1, 2),
            AnswerKey("development.correction_repair", 1, 1),
            AnswerKey("development.develop", 2, 1),
        ]
    ] == [None, 10.0, 9.0, 10.0, 15.0]
    assert f"--set llm_script=shelf-dev@{script.version}" in capsys.readouterr().out


async def test_a_scaled_replay_is_held_under_its_cap_and_says_so_in_the_script(
    recorder, vault_dir, tmp_path
):
    """#2892: a recorded gap spans whatever happened between two stored files, a gate's wait
    included, and a soak replays it scaled to last its nine hours. Bugs caught: one answer's
    replayed wait running past the deploy's task timeout, which fails a task the recording
    passed; or the scale left out of the script, so a scripted run's elapsed time reads as the
    recording's own."""
    out = tmp_path / "scripts"
    code = await _run(recorder, vault_dir, out, "--latency-scale", "2", "--latency-cap", "25")

    assert code == 0
    script = ScriptLibrary(out).get("shelf-dev")
    # 10, 9, 10 and 15 s gaps, doubled; the repair's 30 s held at 25.
    assert sorted(a.latency_seconds or 0 for a in script.answers.values()) == [
        0, 18.0, 20.0, 20.0, 25.0,
    ]  # fmt: skip
    assert script.recorded_from["latency"] == {
        "scale": 2.0,
        "cap_seconds": 25.0,
        "capped": 1,
        "total_seconds": 83.0,
    }


async def test_a_latency_shape_without_a_replayed_latency_is_refused(
    recorder, vault_dir, tmp_path, capsys
):
    """The edge: a scale asked of a script that replays no latency. Bug caught: the flag silently
    ignored, so a soak's scripts run in minutes when their recording said they were stretched."""
    import asyncio

    argv = [
        "--vault", str(vault_dir), "--project", "shelf", "--cycle", "cyc_1", "--name", "shelf-dev",
        "--description", "d", "--latency-scale", "2", "--out", str(tmp_path / "scripts"),
    ]  # fmt: skip

    assert await asyncio.to_thread(recorder.main, argv) == 2
    assert "add --replay-latency" in capsys.readouterr().err
    assert not (tmp_path / "scripts" / "shelf-dev.yaml").exists()


async def test_a_recorded_files_answer_parses_back_to_the_files_it_was_rebuilt_from(
    recorder, vault_dir, tmp_path
):
    """Bug caught: a fence the handlers' parser does not read (a missing newline before the
    close, a language token it refuses), so the recorded answer yields no file and the machinery
    cycle fails on the recording rather than on the path under test."""
    out = tmp_path / "scripts"
    await _run(recorder, vault_dir, out)
    answer = ScriptLibrary(out).get("shelf-dev").answers[AnswerKey("development.develop", 1, 1)]

    files = {f["filename"]: f["content"] for f in extract_fenced_files(answer.content)}

    assert files == {"app.py": "raise SystemExit(1)\n", "util.py": "X = 1\n"}


async def test_an_existing_script_is_never_overwritten(recorder, vault_dir, tmp_path, capsys):
    """Bug caught: a re-record replacing a script a cycle had pinned, so the pin named bytes that
    no longer exist and the next cycle on it was refused with no record of what changed."""
    out = tmp_path / "scripts"
    out.mkdir()
    (out / "shelf-dev.yaml").write_text("kept")

    assert await _run(recorder, vault_dir, out) == 2
    assert (out / "shelf-dev.yaml").read_text() == "kept"
    assert "a script is never overwritten" in capsys.readouterr().err


async def test_a_run_with_no_model_written_file_is_refused(recorder, tmp_path, capsys):
    vault = FilesystemArtifactVault(tmp_path / "vault")
    await _store(vault, 1, "prd.md", "the PRD", 0, "document")

    assert await _run(recorder, tmp_path / "vault", tmp_path / "scripts") == 2
    assert "no artifact here was written by a task's model call" in capsys.readouterr().err


QA = {"producing_task_type": "qa.test", "task_id": "task-run_1-m001-qa.test"}
REPAIR = {"producing_task_type": "qa.test_repair", "task_id": "repair-run_1-00-s00-qa.test_repair"}
FAILING = "def test_a():\n    x = 1\n    assert x == 2\n\n\ndef test_b():\n    assert True\n"
REPAIRED = "def test_a():\n    x = 1\n    assert x == 1\n\n\ndef test_b():\n    assert True\n"


@pytest.fixture
async def correction_vault(tmp_path) -> Path:
    """A qa task's suite failing, repaired by edit, and retested, as the 2.7 soak's recording
    stored one (cyc_1e784bf38f3c): the handler's own records beside each answer, the retest's
    re-emitted suite, and the repair's bytes stored again under the task it repaired."""
    vault = FilesystemArtifactVault(tmp_path / "vault")
    failed = {"attempt": 1, "emission_status": "failed", **QA}
    await _store(vault, 1, "tests/test_c1.py", FAILING, 0, "test", **failed)
    await _store(vault, 2, "test_report.md", "1 failed", 0, "test_report", **failed)
    await _store(
        vault, 3, "typed_check_evaluation_task_1.json", "{}", 0, "typed_check_evaluation", **failed
    )  # noqa: E501
    await _store(vault, 4, "tests/test_c1.py", REPAIRED, 30, "source", **REPAIR)
    retest = {"producing_task_type": "qa.test", "task_id": "retest-run_1-00-s00-qa.test"}
    await _store(vault, 5, "tests/test_c1.py", REPAIRED, 34, "test", **retest)
    await _store(vault, 6, "test_report.md", "1 passed", 34, "test_report", **retest)
    await _store(
        vault, 7, "tests/test_c1.py", REPAIRED, 40, "source", **QA,
        written_by_task_id=REPAIR["task_id"], written_by_task_type="qa.test_repair",
    )  # fmt: skip
    second = {"producing_task_type": "qa.test", "task_id": "task-run_1-m002-qa.test"}
    await _store(vault, 8, "tests/test_c2.py", "def test_c():\n    pass\n", 60, "test", **second)
    await _store(vault, 9, "test_report.md", "1 passed", 60, "test_report", **second)
    return tmp_path / "vault"


async def test_a_retest_takes_no_occurrence_and_a_handler_record_is_no_part_of_an_answer(
    recorder, correction_vault, tmp_path
):
    """#2892, from the soak's recording. Bugs caught: a retest's re-emitted suite (no model call)
    counted as a qa.test occurrence, so the next qa task is answered with the retest's files and
    its own criterion is never written; and a handler's test report or typed-check record fenced
    into the answer as though the model had written it."""
    out = tmp_path / "scripts"
    assert await _run(recorder, correction_vault, out) == 0
    script = ScriptLibrary(out).get("shelf-dev")

    assert sorted(script.answers) == [
        AnswerKey("qa.test", 1, 1),
        AnswerKey("qa.test", 2, 1),
        AnswerKey("qa.test_repair", 1, 1),
    ]
    files = {
        key.occurrence: {f["filename"]: f["content"] for f in extract_fenced_files(a.content)}
        for key, a in script.answers.items()
        if key.task_type == "qa.test"
    }
    assert files == {
        1: {"tests/test_c1.py": FAILING},
        2: {"tests/test_c2.py": "def test_c():\n    pass\n"},
    }


async def test_a_repair_is_answered_with_the_edit_its_handler_applies_to_the_revised_file(
    recorder, correction_vault, tmp_path
):
    """SIP-0107 §9.4: a repair that re-emits an existing file whole is refused, and the vault
    keeps only the revised file. Bugs caught: the revision recorded whole, so every replayed
    repair is refused and the correction path diverges from the recording's at its first
    repair; an edit whose anchor the handler cannot place once; and the repair's bytes, stored
    again under the task it repaired, recorded as a second edit of the same file."""
    from squadops.capabilities.anchored_edits import (
        apply_anchored_edits,
        parse_anchored_edits,
        whole_file_refusals,
    )

    out = tmp_path / "scripts"
    await _run(recorder, correction_vault, out)
    answer = ScriptLibrary(out).get("shelf-dev").answers[AnswerKey("qa.test_repair", 1, 1)]

    parse = parse_anchored_edits(answer.content)
    applied = apply_anchored_edits(
        parse, {"tests/test_c1.py": FAILING}, writable=["tests/test_c1.py"], producer="qa.test_repair",
        task_id=REPAIR["task_id"],
    )  # fmt: skip

    assert [e.path for e in parse.edits] == ["tests/test_c1.py"]
    assert applied.accepted
    assert applied.outcome.candidate_files["tests/test_c1.py"] == REPAIRED
    assert whole_file_refusals(extract_fenced_files(answer.content), ["tests/test_c1.py"]) == []


async def test_a_revision_no_edit_can_state_is_kept_whole_and_named_for_a_hand_fill(
    recorder, tmp_path, capsys
):
    """The edge: a revised line that reads as an edit marker, which no anchored edit can carry.
    Bug caught: the edit written anyway, so the handler reads a malformed fence and refuses it,
    or the answer silently dropped and the replay fails on a missing key with no note of why."""
    vault = FilesystemArtifactVault(tmp_path / "vault")
    await _store(vault, 1, "notes.txt", "a\n", 0, **QA)
    await _store(vault, 2, "notes.txt", "a\n=======\n", 10, **REPAIR)
    out = tmp_path / "scripts"

    assert await _run(recorder, tmp_path / "vault", out) == 0
    answer = ScriptLibrary(out).get("shelf-dev").answers[AnswerKey("qa.test_repair", 1, 1)]

    assert {f["filename"]: f["content"] for f in extract_fenced_files(answer.content)} == {
        "notes.txt": "a\n=======\n"
    }
    assert "no edit rebuilds notes.txt" in capsys.readouterr().out


def test_the_edit_answered_steps_are_the_repair_handlers_that_refuse_a_whole_file(recorder):
    """Bug caught: a new repair handler on the anchored-edit path the recorder does not know, so
    its recorded answers are written whole and refused at replay."""
    from squadops.capabilities.handlers.impl import repair_handlers

    refusing = {
        cls._task_type
        for cls in vars(repair_handlers).values()
        if isinstance(cls, type)
        and issubclass(cls, repair_handlers._RepairPromptMixin)
        and cls is not repair_handlers._RepairPromptMixin
    }

    assert refusing == recorder._ANCHORED_EDIT_STEPS


def _stored_change_request() -> str:
    """A proposal's ``change_request.yaml`` as the proposal handler stores it on a campaign
    branch: the authored fields, the derived ones, and the placed criterion file appended to the
    footprint."""
    import dataclasses

    from squadops.campaigns.change_request import (
        IncrementBasis,
        PlacedCriterionFile,
        content_hash,
        parse_change_request,
        stored_change_request,
    )

    request = parse_change_request(
        yaml.safe_load(AUTHORED_CHANGE),
        proposal_id="prop_1",
        version=1,
        baseline_tree="tree_1",
        basis=IncrementBasis.CAMPAIGN_BRANCH,
    )
    request = dataclasses.replace(
        request,
        footprint=(*request.footprint, "tests/test_criterion_T1.py"),
        criterion_files=(PlacedCriterionFile("T1", "tests/test_criterion_T1.py", ""),),
        goals_revision=3,
    )
    return stored_change_request(dataclasses.replace(request, content_hash=content_hash(request)))


AUTHORED_CHANGE = """kind: feature
criteria:
- id: T1
  statement: GET /books/count gives the shelf's size
  surface_kind: endpoint
  surface: GET /books/count
  observable: a shelf of 3 books answers 3
  paths:
  - backend/routes.py
must_not_break: []
footprint:
- backend/routes.py
backlog_item: SN-1
"""


async def test_a_proposal_is_answered_with_what_it_authored_not_what_the_framework_derived(
    recorder, tmp_path
):
    """#2892, the soak's first dry run: the stored change request carries the fields the
    framework derives, and the proposal handler refuses a document that authors them
    (``authored_derived_field``), so every replayed proposal was refused three times and the
    Campaign stopped at its first launch. Bugs caught: a derived field left in the answer; the
    framework's placed criterion file left in the authored footprint; and the derived fields not
    recorded, so the replayed answer can't be shown to be the one that was ruled on."""
    from squadops.campaigns.change_request import load_stored_change_request

    stored = _stored_change_request()
    vault = FilesystemArtifactVault(tmp_path / "vault")
    proposal = {"producing_task_type": "strategy.propose_increment", "task_id": "t-prop"}
    await _store(vault, 1, "change_request.yaml", stored, 0, "change_request", **proposal)
    out = tmp_path / "scripts"

    assert await _run(recorder, tmp_path / "vault", out) == 0
    script = ScriptLibrary(out).get("shelf-dev")
    key = AnswerKey("strategy.propose_increment", 1, 1)
    files = {f["filename"]: f["content"] for f in extract_fenced_files(script.answers[key].content)}
    derived = script.recorded_from["change_requests"][str(key)]

    assert yaml.safe_load(files["change_request.yaml"]) == {
        **yaml.safe_load(AUTHORED_CHANGE),
        "prd_delta": [],
        "manifest_delta": [],
        "retires": [],
        "replaces_verifiers": [],
    }
    authored = yaml.safe_load(files["change_request.yaml"])
    rebuilt = load_stored_change_request(yaml.safe_dump({**authored, **derived}))
    assert rebuilt.content_hash == yaml.safe_load(stored)["content_hash"]


async def _run(recorder, vault_dir: Path, out: Path, *extra: str) -> int:
    """``main`` runs its own event loop, as it does from a shell; a thread keeps it off the test's."""
    import asyncio

    argv = [
        "--vault", str(vault_dir), "--project", "shelf", "--cycle", "cyc_1", "--run", "run_1",
        "--name", "shelf-dev", "--description", "a dev retry and its repair",
        "--replay-latency", "--out", str(out), *extra,
    ]  # fmt: skip
    return await asyncio.to_thread(recorder.main, argv)
