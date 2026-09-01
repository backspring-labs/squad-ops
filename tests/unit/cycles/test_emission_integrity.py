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
    unresolved_import_summary,
    unresolved_imports,
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
        # #998: the token facts and the signature ride the marker; a caller that
        # reports no tokens gets an honest None and the shape the chars alone support.
        "completion_tokens": None,
        "completion_cap": None,
        "signature": "unextractable",
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


# ---------------------------------------------------------------------------
# Intra-package import resolution (#591)
# ---------------------------------------------------------------------------


class TestUnresolvedImports:
    """The syntax gate proves each file parses ALONE. pf-37 proved that isn't
    enough: a repair emitted a coherent models.py/routes.py pair, SIP-0100
    restored the frozen models.py, and the surviving routes.py imported seven
    names the frozen module never defined. Every typed check passed — they read
    one file at a time — and the patch was accepted.
    """

    @staticmethod
    def _write(root, files: dict[str, str]) -> None:
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def test_a_submodule_is_not_an_unbound_name(self, tmp_path) -> None:
        """Bug caught: #1211, replayed from the shape that rejected a cut-gating
        shakeout. `from backend import store` resolves against the filesystem, not
        against what `__init__.py` binds — Python imports the submodule. Reporting it
        refused a valid repair in patch verification's pre-gate, before any criterion
        ran, and cost `cyc_052ca0358191` three correction rounds and its verdict.
        """
        self._write(
            tmp_path,
            {
                "backend/__init__.py": "",
                "backend/store.py": "def reset() -> None:\n    pass\n",
                "test_runs.py": "from backend import store as _store\n",
            },
        )

        assert unresolved_imports(tmp_path) == []

    def test_a_subpackage_is_not_an_unbound_name_either(self, tmp_path) -> None:
        """The directory form of the same thing — `pkg/name/__init__.py` rather than
        `pkg/name.py`. Fixing only the file form would leave the false positive alive
        for any package that groups its submodules."""
        self._write(
            tmp_path,
            {
                "backend/__init__.py": "",
                "backend/store/__init__.py": "def reset() -> None:\n    pass\n",
                "test_runs.py": "from backend import store\n",
            },
        )

        assert unresolved_imports(tmp_path) == []

    def test_a_genuinely_absent_name_is_still_reported(self, tmp_path) -> None:
        """The #591 finding must survive the #1211 fix. A name that is neither bound in
        `__init__.py` nor backed by a submodule file does not resolve, and silencing it
        would trade one false verdict for the opposite one."""
        self._write(
            tmp_path,
            {
                "backend/__init__.py": "",
                "backend/store.py": "def reset() -> None:\n    pass\n",
                "test_runs.py": "from backend import store, nonexistent\n",
            },
        )

        findings = unresolved_imports(tmp_path)

        assert len(findings) == 1
        source, module, missing = findings[0]
        assert source == "test_runs.py"
        assert module == "backend"
        assert missing == ("nonexistent",), "the submodule filter must not swallow real misses"

    def test_an_absent_name_inside_a_present_submodule_is_still_reported(self, tmp_path) -> None:
        """`from backend.store import gone` names a module that exists and a name it does
        not bind — the submodule filter must not reach this case at all, since the target
        resolves to store.py rather than to a package `__init__`."""
        self._write(
            tmp_path,
            {
                "backend/__init__.py": "",
                "backend/store.py": "def reset() -> None:\n    pass\n",
                "test_runs.py": "from backend.store import reset, gone\n",
            },
        )

        findings = unresolved_imports(tmp_path)

        assert len(findings) == 1
        assert findings[0][2] == ("gone",)

    def test_pf37_restored_frozen_model_leaves_routes_unimportable(self, tmp_path) -> None:
        """Bug caught: THE #591 defect, replayed from pf-37's real shape — the
        exact name set correction-00 imported against the frozen module."""
        self._write(
            tmp_path,
            {
                "backend/__init__.py": "",
                "backend/models.py": (
                    "from pydantic import BaseModel\n\n"
                    "class Participant(BaseModel):\n    id: str\n    name: str\n\n"
                    "class RunEvent(BaseModel):\n    id: str\n    title: str\n\n"
                    "class RunEventCreate(BaseModel):\n    title: str\n\n"
                    "class ParticipantName(BaseModel):\n    name: str\n"
                ),
                "backend/routes.py": (
                    "from .models import (\n"
                    "    RunCreate,\n"
                    "    RunResponse,\n"
                    "    RunListResponse,\n"
                    "    ParticipantJoin,\n"
                    ")\n"
                ),
            },
        )

        findings = unresolved_imports(tmp_path)

        assert len(findings) == 1
        source, module, missing = findings[0]
        assert source == "backend/routes.py"
        assert module == ".models"
        assert missing == ("ParticipantJoin", "RunCreate", "RunListResponse", "RunResponse")

        summary = unresolved_import_summary(findings)
        assert "backend/routes.py" in summary
        assert "RunCreate" in summary

    def test_resolvable_package_reports_nothing(self, tmp_path) -> None:
        """Bug caught: a check that flags healthy workspaces rejects every good
        patch — worse than the defect it fixes."""
        self._write(
            tmp_path,
            {
                "backend/__init__.py": "",
                "backend/models.py": "class RunEvent:\n    pass\n\nSTORE = {}\n",
                "backend/routes.py": "from .models import RunEvent, STORE\n",
            },
        )

        assert unresolved_imports(tmp_path) == []

    def test_third_party_and_stdlib_imports_are_ignored(self, tmp_path) -> None:
        """Bug caught: resolving imports that point outside the workspace turns
        every fastapi/pydantic import into a false rejection."""
        self._write(
            tmp_path,
            {
                "backend/__init__.py": "",
                "backend/routes.py": (
                    "import json\n"
                    "from pathlib import Path\n"
                    "from fastapi import APIRouter, status\n"
                    "from pydantic import BaseModel\n"
                ),
            },
        )

        assert unresolved_imports(tmp_path) == []

    def test_absolute_intra_workspace_import_is_resolved(self, tmp_path) -> None:
        """Bug caught: only handling relative imports misses `from backend.models
        import X`, which the scaffold's own test harness uses."""
        self._write(
            tmp_path,
            {
                "backend/__init__.py": "",
                "backend/models.py": "class RunEvent:\n    pass\n",
                "backend/tests/test_x.py": "from backend.models import RunEvent, Missing\n",
            },
        )

        findings = unresolved_imports(tmp_path)

        assert [(s, m, n) for s, m, n in findings] == [
            ("backend/tests/test_x.py", "backend.models", ("Missing",))
        ]

    def test_star_import_target_is_not_judged(self, tmp_path) -> None:
        """Bug caught: a module doing `from .base import *` binds names this walk
        can't see; judging it would reject valid code."""
        self._write(
            tmp_path,
            {
                "backend/__init__.py": "",
                "backend/base.py": "class Thing:\n    pass\n",
                "backend/models.py": "from .base import *\n",
                "backend/routes.py": "from .models import Thing, Anything\n",
            },
        )

        assert unresolved_imports(tmp_path) == []

    def test_conditional_definitions_are_not_judged(self, tmp_path) -> None:
        """Bug caught: TYPE_CHECKING blocks and optional-dependency fallbacks
        bind names conditionally — flagging them rejects idiomatic code."""
        self._write(
            tmp_path,
            {
                "backend/__init__.py": "",
                "backend/compat.py": (
                    "try:\n    from fast import Impl\nexcept ImportError:\n"
                    "    class Impl:\n        pass\n"
                ),
                "backend/routes.py": "from .compat import Impl\n",
            },
        )

        assert unresolved_imports(tmp_path) == []

    def test_unparseable_target_is_skipped(self, tmp_path) -> None:
        """Bug caught: double-reporting a truncated file the syntax gate already
        owns, instead of leaving that concern to it."""
        self._write(
            tmp_path,
            {
                "backend/__init__.py": "",
                "backend/models.py": "class RunEvent:\n    def broken(\n",
                "backend/routes.py": "from .models import RunEvent\n",
            },
        )

        assert unresolved_imports(tmp_path) == []

    def test_missing_target_module_is_not_reported(self, tmp_path) -> None:
        """Bug caught: treating an absent module as a name failure — it may be a
        third-party package that merely shares a directory name."""
        self._write(
            tmp_path,
            {
                "backend/__init__.py": "",
                "backend/routes.py": "from .nonexistent import Thing\n",
            },
        )

        assert unresolved_imports(tmp_path) == []


class TestEmissionStats:
    """#431 accounting: what the model produced vs what survived extraction."""

    def test_counts_content_chars_only(self):
        from squadops.cycles.emission_integrity import emission_stats

        arts = [
            {"name": "a.py", "content": "x" * 100, "type": "code"},
            {"name": "b.md", "content": "y" * 50, "type": "document"},
            {"name": "meta", "content": None},  # non-string content never counts
            "not-a-dict",
        ]
        stats = emission_stats(4000, arts)
        assert stats == {"response_chars": 4000, "extracted_chars": 150, "artifact_count": 3}

    def test_gap_rule_boundaries(self):
        from squadops.cycles.emission_integrity import extraction_loss_suspected

        # the production exhibit shape: ~3% retention on a large response
        assert extraction_loss_suspected({"response_chars": 28000, "extracted_chars": 800})
        # healthy prose-around-fences retention
        assert not extraction_loss_suspected({"response_chars": 28000, "extracted_chars": 21000})
        # floor: small responses legitimately extract small
        assert not extraction_loss_suspected({"response_chars": 1999, "extracted_chars": 0})
        # exactly at the ratio is NOT loss (strict less-than)
        assert not extraction_loss_suspected({"response_chars": 10000, "extracted_chars": 1500})
        # malformed stats never crash the evidence path
        assert not extraction_loss_suspected({"response_chars": "x"})
        assert not extraction_loss_suspected({})
