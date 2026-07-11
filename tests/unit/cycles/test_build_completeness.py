"""Deliverable-completeness gate for builder runs (#291).

``compute_missing_required_files`` is the run-level net the per-task validator
(#107) can't provide: it fires only for builder runs and only when the complete
emitted set is missing a file the build profile requires. Each test names the
specific bug it catches — the whole point of #291 is that a builder run must
not ship green without the ``Dockerfile`` its profile mandates (#276).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from squadops.cycles.build_completeness import compute_missing_required_files
from squadops.cycles.models import ArtifactRef
from squadops.tasks.models import TaskEnvelope

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


def _envelope(task_type: str) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=f"task_{task_type}",
        agent_id="a",
        cycle_id="cyc_1",
        pulse_id="p",
        project_id="test",
        task_type=task_type,
        correlation_id="c",
        causation_id="c",
        trace_id="t",
        span_id="s",
        inputs={},
    )


def _ref(filename: str) -> tuple[str, ArtifactRef]:
    art_id = f"art_{filename}"
    return art_id, ArtifactRef(
        artifact_id=art_id,
        project_id="test",
        artifact_type="document",
        filename=filename,
        content_hash="h",
        size_bytes=1,
        media_type="text/plain",
        created_at=NOW,
    )


# fullstack_fastapi_react.required_files == ("Dockerfile", "qa_handoff.md")
_BUILDER_PLAN = [
    _envelope("development.develop"),
    _envelope("builder.assemble"),
    _envelope("qa.test"),
]


def test_missing_required_file_is_reported():
    """The #276 bug: builder run emits qa_handoff.md but no Dockerfile, and ships
    green. The gate must return the profile and the missing Dockerfile so the run
    fails instead."""
    result = compute_missing_required_files(
        _BUILDER_PLAN,
        [_ref("qa_handoff.md")],
        {"build_profile": "fullstack_fastapi_react"},
    )
    assert result == ("fullstack_fastapi_react", ["Dockerfile"])


def test_all_required_files_present_returns_none():
    """A complete deliverable must not be failed — false positives here would
    fail every well-formed builder run."""
    result = compute_missing_required_files(
        _BUILDER_PLAN,
        [_ref("Dockerfile"), _ref("qa_handoff.md"), _ref("docker-compose.yaml")],
        {"build_profile": "fullstack_fastapi_react"},
    )
    assert result is None


def test_non_builder_run_is_never_checked():
    """A plain develop+test build run (no builder.* task) has no build profile;
    the gate must not fire even though 'Dockerfile' is absent — otherwise every
    non-builder cycle would start failing."""
    plan = [_envelope("development.develop"), _envelope("qa.test")]
    result = compute_missing_required_files(
        plan,
        [_ref("src/main.py")],
        {"build_profile": "fullstack_fastapi_react"},
    )
    assert result is None


def test_required_file_in_subdirectory_satisfies_by_basename():
    """A Dockerfile emitted under a subdirectory still satisfies the required
    'Dockerfile' — basename matching mirrors the builder handler and must not
    fail a complete deliverable on a path difference."""
    result = compute_missing_required_files(
        _BUILDER_PLAN,
        [_ref("backend/Dockerfile"), _ref("qa_handoff.md")],
        {"build_profile": "fullstack_fastapi_react"},
    )
    assert result is None


def test_default_profile_used_when_build_profile_absent():
    """When resolved_config omits build_profile, the gate must resolve the same
    default (python_cli_builder) the builder handler uses — otherwise the check
    and the handler would disagree on what's required. python_cli_builder needs
    Dockerfile/__main__.py/requirements.txt/qa_handoff.md; emit none → all
    reported missing."""
    result = compute_missing_required_files(
        _BUILDER_PLAN,
        [_ref("notes.txt")],
        {},  # no build_profile
    )
    assert result is not None
    profile_name, missing = result
    assert profile_name == "python_cli_builder"
    assert set(missing) == {"Dockerfile", "__main__.py", "requirements.txt", "qa_handoff.md"}


def test_unknown_profile_defers_instead_of_crashing():
    """An unknown profile is a config error already surfaced by the builder task;
    the completeness net must defer (None), not raise — a run at completion must
    not crash on a bad profile name here."""
    result = compute_missing_required_files(
        _BUILDER_PLAN,
        [_ref("qa_handoff.md")],
        {"build_profile": "does_not_exist"},
    )
    assert result is None


def test_only_missing_subset_reported_not_present_ones():
    """python_cli_builder needs four files; emit three → only the one truly
    absent is reported, so the failure message names the real gap."""
    result = compute_missing_required_files(
        _BUILDER_PLAN,
        [_ref("Dockerfile"), _ref("__main__.py"), _ref("qa_handoff.md")],
        {"build_profile": "python_cli_builder"},
    )
    assert result == ("python_cli_builder", ["requirements.txt"])
