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


async def _run(recorder, vault_dir: Path, out: Path, *extra: str) -> int:
    """``main`` runs its own event loop, as it does from a shell; a thread keeps it off the test's."""
    import asyncio

    argv = [
        "--vault", str(vault_dir), "--project", "shelf", "--cycle", "cyc_1", "--run", "run_1",
        "--name", "shelf-dev", "--description", "a dev retry and its repair",
        "--replay-latency", "--out", str(out), *extra,
    ]  # fmt: skip
    return await asyncio.to_thread(recorder.main, argv)
