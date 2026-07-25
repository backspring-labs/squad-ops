"""pf-31 Fix D — syntax gate for repair-path Python emissions.

Guards against the pf-31 repair-03 class: a truncated test-file emission
(SyntaxError mid-function) superseding the last good version and re-importing
the pytest collection-crash the repair was dispatched to fix.
"""

from __future__ import annotations

import pytest

from squadops.cycles.emission_integrity import (
    emission_integrity_instruction,
    syntax_gate_python_artifacts,
)

pytestmark = [pytest.mark.domain_capabilities]

_TRUNCATED = "def test_join_run(client):\n    resp = client.post(\n"
_VALID = "def test_join_run(client):\n    assert client is not None\n"


def test_truncated_python_artifact_rejected_with_line_info():
    kept, rejected = syntax_gate_python_artifacts(
        [{"name": "backend/tests/test_runs.py", "content": _TRUNCATED}]
    )
    assert kept == []
    ((art, error),) = rejected
    assert art["name"] == "backend/tests/test_runs.py"
    assert "SyntaxError at line" in error


def test_valid_python_and_non_python_pass_through():
    artifacts = [
        {"name": "backend/tests/test_runs.py", "content": _VALID},
        {"name": "frontend/src/App.jsx", "content": "const x = {"},  # not python — not parsed
        {"name": "notes.md", "content": "# hi"},
        "not-a-dict-entry",
    ]
    kept, rejected = syntax_gate_python_artifacts(artifacts)
    assert kept == artifacts
    assert rejected == []


def test_mixed_emission_drops_only_the_broken_file():
    """The pf-31 shape: one broken test file riding with a good source file —
    only the broken one is dropped, the good one lands."""
    good = {"name": "backend/routes.py", "content": "ROUTES = []\n"}
    bad = {"name": "backend/tests/test_runs.py", "content": _TRUNCATED}
    kept, rejected = syntax_gate_python_artifacts([good, bad])
    assert kept == [good]
    assert rejected[0][0] is bad


def test_py_artifact_without_content_passes_through():
    art = {"name": "x.py"}
    kept, rejected = syntax_gate_python_artifacts([art])
    assert kept == [art] and rejected == []


def test_path_key_shape_also_gated():
    kept, rejected = syntax_gate_python_artifacts([{"path": "a.py", "content": _TRUNCATED}])
    assert kept == [] and len(rejected) == 1


def test_instruction_names_file_error_and_completeness_demand():
    line = emission_integrity_instruction("backend/tests/test_runs.py", "SyntaxError at line 2: x")
    assert "backend/tests/test_runs.py" in line
    assert "DISCARDED" in line
    assert "COMPLETE" in line


def test_no_fenced_blocks_marker_shape():
    from squadops.cycles.emission_integrity import (
        EMISSION_FAILURE_NO_FENCED_BLOCKS,
        no_fenced_blocks_failure,
    )

    marker = no_fenced_blocks_failure(6203, ["backend/tests/test_runs.py"])
    assert marker == {
        "reason": EMISSION_FAILURE_NO_FENCED_BLOCKS,
        "response_chars": 6203,
        "expected_artifacts": ["backend/tests/test_runs.py"],
    }
    assert no_fenced_blocks_failure(0, None)["expected_artifacts"] == []


def test_emission_retry_reason_line_known_and_unknown():
    from squadops.cycles.emission_integrity import (
        emission_retry_reason_line,
        no_fenced_blocks_failure,
    )

    line = emission_retry_reason_line(no_fenced_blocks_failure(6203, ["x.py"]))
    assert "6203-character" in line
    assert "no fenced code block" in line
    # Unknown reason still yields a usable factual line, never a KeyError.
    assert "other_reason" in emission_retry_reason_line({"reason": "other_reason"})
