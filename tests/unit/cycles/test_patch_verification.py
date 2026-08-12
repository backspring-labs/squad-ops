"""Unit tests for executor-side patch verification (#389).

Each test names the bug it catches: the correction loop re-dispatching a
generative task after a good repair (re-roll clobbers the patch), or the
verifier accepting a patch without positive executed evidence.
"""

from squadops.cycles.implementation_plan import TypedCheck
from squadops.cycles.patch_verification import (
    PATCH_FAILED,
    PATCH_PASSED,
    PATCH_UNVERIFIABLE,
    overlay_artifacts,
    verify_patched_artifacts,
)

# The field-evidence contract from cyc_6841d75f167c: qa_handoff.md must
# contain five headings; the broken generation misses two, the repair
# restores them.
BROKEN_DOC = "# QA Handoff\n## How to Run\n## Expected Behavior\n"
REPAIRED_DOC = (
    "# QA Handoff\n## How to Run\n## How to Test\n## Expected Behavior\n"
    "## Implemented Scope\n## Known Limitations\n"
)


def _heading_criteria() -> list[TypedCheck]:
    return [
        TypedCheck(
            check="regex_match",
            params={"file": "qa_handoff.md", "pattern": f"## {section}"},
            severity="error",
            description=f"Contains {section} section",
        )
        for section in ("How to Run", "How to Test", "Implemented Scope")
    ]


class TestVerifyPatchedArtifacts:
    async def test_passed_when_repair_satisfies_blocking_criteria(self):
        """Bug caught: a good repair re-dispatched into a re-roll (the #389
        oscillation) because no path existed to verify it behaviorally."""
        artifacts = overlay_artifacts(
            [{"name": "qa_handoff.md", "content": BROKEN_DOC}],
            [{"name": "qa_handoff.md", "content": REPAIRED_DOC}],
        )
        result = await verify_patched_artifacts(_heading_criteria(), artifacts)
        assert result.status == PATCH_PASSED
        assert all(r.status == "passed" for r in result.checks)

    async def test_failed_when_repair_still_misses_required_section(self):
        """Bug caught: false-accepting an incomplete repair (broken doc kept)."""
        result = await verify_patched_artifacts(
            _heading_criteria(),
            [{"name": "qa_handoff.md", "content": BROKEN_DOC}],
        )
        assert result.status == PATCH_FAILED
        failed = [r for r in result.checks if r.status == "failed"]
        assert {r.description for r in failed} == {
            "Contains How to Test section",
            "Contains Implemented Scope section",
        }

    async def test_overlay_patch_supersedes_base_artifact(self):
        """Bug caught: overlay precedence inverted — verification would run
        against the broken original and every good repair would read FAILED."""
        merged = overlay_artifacts(
            [{"name": "qa_handoff.md", "content": BROKEN_DOC}, {"name": "a.txt", "content": "x"}],
            [{"name": "qa_handoff.md", "content": REPAIRED_DOC}, {"name": "b.txt", "content": "y"}],
        )
        by_name = {a["name"]: a["content"] for a in merged}
        assert by_name["qa_handoff.md"] == REPAIRED_DOC
        assert set(by_name) == {"qa_handoff.md", "a.txt", "b.txt"}

    async def test_verdict_names_the_exact_workspace_it_evaluated(self):
        """#734 Slice A: the repair-acceptance verdict is content-addressed to
        the workspace mapping it materialized — computed from the parameter,
        never store state (the spike's risk note). Bug caught: hashing
        upstream state that differs from what the evaluator actually saw."""
        from squadops.sandbox.models import compute_revision_id

        workspace = {"backend/models.py": "x = 1\n"}
        result = await verify_patched_artifacts(
            _heading_criteria(),
            [{"name": "qa_handoff.md", "content": REPAIRED_DOC}],
            workspace_files=workspace,
        )
        assert result.status == PATCH_PASSED
        assert result.workspace_revision_id == compute_revision_id(workspace)
        # The empty context is a nameable state, distinct from None.
        bare = await verify_patched_artifacts(
            _heading_criteria(), [{"name": "qa_handoff.md", "content": REPAIRED_DOC}]
        )
        assert bare.workspace_revision_id == compute_revision_id({})

    async def test_early_returns_carry_no_workspace_identity(self):
        """Unparseable/typed-less criteria never materialize a workspace —
        stamping an id there would claim an evaluation that never ran."""
        result = await verify_patched_artifacts(
            ["prose only"], [{"name": "qa_handoff.md", "content": REPAIRED_DOC}]
        )
        assert result.status == PATCH_UNVERIFIABLE
        assert result.workspace_revision_id is None

    async def test_unverifiable_when_no_typed_criteria(self):
        """Bug caught: a prose-only contract silently 'passing' with zero
        behavioral evidence — patch acceptance requires executed checks."""
        result = await verify_patched_artifacts(
            ["backend responds correctly"],
            [{"name": "qa_handoff.md", "content": REPAIRED_DOC}],
        )
        assert result.status == PATCH_UNVERIFIABLE
        assert result.reason == "no_typed_criteria"

    async def test_unverifiable_when_all_blocking_checks_skipped(self):
        """Bug caught: typed acceptance disabled → every row skipped → the
        old logic would have accepted the patch with nothing executed."""
        result = await verify_patched_artifacts(
            _heading_criteria(),
            [{"name": "qa_handoff.md", "content": REPAIRED_DOC}],
            typed_acceptance_enabled=False,
        )
        assert result.status == PATCH_UNVERIFIABLE
        assert result.reason == "no_executed_blocking_checks"

    async def test_unverifiable_on_unparseable_dict_criterion(self):
        """Bug caught: verifying against only the intelligible subset of a
        contract — an unknown check name must force fallback, not be skipped."""
        result = await verify_patched_artifacts(
            [{"check": "not_a_real_check", "file": "qa_handoff.md"}],
            [{"name": "qa_handoff.md", "content": REPAIRED_DOC}],
        )
        assert result.status == PATCH_UNVERIFIABLE
        assert result.reason == "unparseable_criteria"

    async def test_dict_form_criteria_are_parsed_and_evaluated(self):
        """Bug caught: criteria arriving as dicts (deserialized envelope)
        being ignored — the fix would silently never engage."""
        result = await verify_patched_artifacts(
            [
                {
                    "check": "regex_match",
                    "file": "qa_handoff.md",
                    "pattern": "## Known Limitations",
                    "description": "Contains Known Limitations section",
                }
            ],
            [{"name": "qa_handoff.md", "content": REPAIRED_DOC}],
        )
        assert result.status == PATCH_PASSED

    async def test_warning_severity_failure_does_not_block(self):
        """Bug caught: RC-9 regression — a warning-severity miss blocking
        patch acceptance that error-severity evidence already justified."""
        criteria = [
            TypedCheck(
                check="regex_match",
                params={"file": "qa_handoff.md", "pattern": "## How to Test"},
                severity="error",
                description="required section",
            ),
            TypedCheck(
                check="regex_match",
                params={"file": "qa_handoff.md", "pattern": "## Nonexistent Nicety"},
                severity="warning",
                description="optional section",
            ),
        ]
        result = await verify_patched_artifacts(
            criteria, [{"name": "qa_handoff.md", "content": REPAIRED_DOC}]
        )
        assert result.status == PATCH_PASSED
        warning_row = next(r for r in result.checks if r.severity == "warning")
        assert warning_row.status == "failed"

    async def test_check_rows_render_for_ledger_normalization(self):
        """Bug caught: patch-verified evidence emitted in a shape
        normalize_task_checks can't read → the ledger would show the task
        as never re-verified (§6.1 keys on 'check' + 'status')."""
        result = await verify_patched_artifacts(
            _heading_criteria()[:1],
            [{"name": "qa_handoff.md", "content": REPAIRED_DOC}],
        )
        row = result.checks[0].to_check_row()
        assert row["check"] == "acceptance:regex_match"
        assert row["status"] == "passed"
        assert row["passed"] is True
        assert row["patch_verified"] is True


# --------------------------------------------------------------------------- #
# repair path rebase (#507) — bug caught: every roll-4 repair emitted
# app/routes.py while checks target backend/routes.py; the overlay appended it
# as net-new, typed verification ran on the un-patched original, and three
# QA-validated repairs were discarded by re-dispatch until the time budget.
# --------------------------------------------------------------------------- #

from squadops.cycles.patch_verification import rebase_artifact_paths  # noqa: E402


def test_wrong_directory_repair_is_rehomed_to_expected_path():
    arts = [{"name": "app/routes.py", "content": "fixed"}]
    out = rebase_artifact_paths(arts, ["backend/routes.py", "backend/models.py"])
    assert out == [{"name": "backend/routes.py", "content": "fixed"}]


def test_rehomed_repair_supersedes_in_overlay():
    base = [{"name": "backend/routes.py", "content": "broken"}]
    patches = rebase_artifact_paths(
        [{"name": "app/routes.py", "content": "fixed"}], ["backend/routes.py"]
    )
    merged = {a["name"]: a["content"] for a in overlay_artifacts(base, patches)}
    assert merged == {"backend/routes.py": "fixed"}


def test_exact_expected_path_passes_through():
    arts = [{"name": "backend/routes.py", "content": "x"}]
    assert rebase_artifact_paths(arts, ["backend/routes.py"]) == arts


def test_ambiguous_basename_is_never_rehomed():
    arts = [{"name": "app/routes.py", "content": "x"}]
    out = rebase_artifact_paths(arts, ["backend/routes.py", "frontend/routes.py"])
    assert out[0]["name"] == "app/routes.py"


def test_unmatched_and_net_new_files_pass_through():
    arts = [{"name": "README.md", "content": "x"}, {"name": "", "content": "y"}, {"other": 1}]
    assert rebase_artifact_paths(arts, ["backend/routes.py"]) == arts


# The pf-37 shape (#591): correction-00 emitted a coherent models.py/routes.py
# pair, SIP-0100 restored the frozen models.py, and the surviving routes.py
# imported names the frozen module never defines. Every typed check passed —
# routes.py compiles perfectly alone — and the patch was ACCEPTED, then the
# suite failed to collect.
FROZEN_MODELS = (
    "from pydantic import BaseModel\n\n"
    "class RunEvent(BaseModel):\n    id: str\n    title: str\n\n"
    "class RunEventCreate(BaseModel):\n    title: str\n"
)
REPAIR_ROUTES = (
    "from .models import RunCreate, RunResponse\n\ndef create_run(body):\n    return body\n"
)
GOOD_ROUTES = (
    "from .models import RunEvent, RunEventCreate\n\ndef create_run(body):\n    return body\n"
)


def _routes_criteria() -> list[TypedCheck]:
    """The checks pf-37 actually ran against routes.py — all file-local."""
    return [
        TypedCheck(
            check="function_defined",
            params={"file": "backend/routes.py", "name_prefix": "create_", "min_count": 1},
            severity="error",
            description="routes.py defines a create_ handler",
        ),
    ]


class TestUnresolvedImportsBlockAcceptance:
    async def test_patch_with_unresolvable_imports_is_rejected(self):
        """Bug caught: THE #591 defect — every file-local check passes, the patch
        is accepted, and the assembled app cannot import at all."""
        artifacts = [
            {"name": "backend/__init__.py", "content": ""},
            {"name": "backend/models.py", "content": FROZEN_MODELS},
            {"name": "backend/routes.py", "content": REPAIR_ROUTES},
        ]
        result = await verify_patched_artifacts(_routes_criteria(), artifacts, stack="python")

        assert result.status == PATCH_FAILED
        assert "unresolved_imports" in (result.reason or "")
        assert "RunCreate" in (result.reason or "")
        assert "backend/routes.py" in (result.reason or "")

    async def test_same_patch_would_pass_every_typed_check(self):
        """Pins WHY the defect was invisible: the file-local criterion passes on
        the very artifacts the check above rejects. Without this, a future
        refactor could weaken the criteria and call #591 'fixed'."""
        import tempfile
        from pathlib import Path

        from squadops.cycles.acceptance_evaluation import evaluate_criterion
        from squadops.cycles.patch_verification import materialize_artifacts

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            materialize_artifacts(
                [
                    {"name": "backend/models.py", "content": FROZEN_MODELS},
                    {"name": "backend/routes.py", "content": REPAIR_ROUTES},
                ],
                root,
            )
            outcome = await evaluate_criterion(
                _routes_criteria()[0],
                root,
                stack="python",
                typed_acceptance_enabled=True,
                command_acceptance_enabled=True,
            )

        assert outcome.status == "passed"

    async def test_resolvable_patch_still_accepted(self):
        """Bug caught: the new gate rejecting healthy patches — it must only bite
        on genuinely unimportable combinations."""
        artifacts = [
            {"name": "backend/__init__.py", "content": ""},
            {"name": "backend/models.py", "content": FROZEN_MODELS},
            {"name": "backend/routes.py", "content": GOOD_ROUTES},
        ]
        result = await verify_patched_artifacts(_routes_criteria(), artifacts, stack="python")

        assert result.status == PATCH_PASSED

    async def test_non_python_patches_are_unaffected(self):
        """Bug caught: the doc/markdown repair path (the original #389 case)
        regressing because an import walk runs over a workspace with no Python."""
        artifacts = overlay_artifacts(
            [{"name": "qa_handoff.md", "content": BROKEN_DOC}],
            [{"name": "qa_handoff.md", "content": REPAIRED_DOC}],
        )
        result = await verify_patched_artifacts(_heading_criteria(), artifacts)

        assert result.status == PATCH_PASSED


# ---------------------------------------------------------------------------
# #643: the workspace substrate — patched files verified inside the accepted tree
# ---------------------------------------------------------------------------


_ROUTES_IMPORTING_SIBLING = """\
from backend.errors import ApiError


def not_found() -> ApiError:
    return ApiError()
"""

_ERRORS_MODULE = "class ApiError(Exception):\n    pass\n"


def _module_imports_criterion() -> list[TypedCheck]:
    return [
        TypedCheck(
            check="module_imports",
            params={"file": "backend/routes.py"},
            severity="error",
            description="routes module imports",
        )
    ]


class TestWorkspaceFiles:
    """#643 (fay-1): patch verification materialized ONLY failed-outputs +
    repairs, so a repaired fill file importing its frozen scaffold siblings
    could never be accepted — both fay-1 candidates were rejected in a
    routes.py-only workspace despite importing clean in the real tree."""

    async def test_sibling_import_accepted_with_workspace_substrate(self):
        result = await verify_patched_artifacts(
            _module_imports_criterion(),
            [{"name": "backend/routes.py", "content": _ROUTES_IMPORTING_SIBLING}],
            workspace_files={
                "backend/__init__.py": "",
                "backend/errors.py": _ERRORS_MODULE,
            },
        )
        assert result.status == PATCH_PASSED

    async def test_sibling_import_rejected_without_workspace_substrate(self):
        # The fay-1 rejection, pinned: identical patch, no substrate.
        result = await verify_patched_artifacts(
            _module_imports_criterion(),
            [{"name": "backend/routes.py", "content": _ROUTES_IMPORTING_SIBLING}],
        )
        assert result.status == PATCH_FAILED

    async def test_patched_artifact_supersedes_its_workspace_slot(self):
        # The substrate's stale copy of the repaired file (the pre-repair
        # tree) must not shadow the patch under verification.
        result = await verify_patched_artifacts(
            _module_imports_criterion(),
            [{"name": "backend/routes.py", "content": _ROUTES_IMPORTING_SIBLING}],
            workspace_files={
                "backend/__init__.py": "",
                "backend/errors.py": _ERRORS_MODULE,
                "backend/routes.py": "raise RuntimeError('pre-repair tree was evaluated')\n",
            },
        )
        assert result.status == PATCH_PASSED


def _fill_slot_criterion(pattern: str = "def register") -> TypedCheck:
    return TypedCheck(
        check="regex_match",
        params={"file": "backend/routes.py", "pattern": pattern},
        severity="error",
        description="file-owned: routes defines its registration entrypoint",
        id="vc-routes-entrypoint",
    )


class TestFileOwnedGate:
    """#870: a repair is gated by the criteria that OWN the files it rewrote.

    Roll 12 (cyc_e4b2444fa300): a dev repair for a qa.test failure re-emitted four
    routes that no longer compiled. qa.test has no typed criteria, so patch
    verification was structurally silent and the broken tree sailed into the
    behavioral retest. The files' own contract criteria — which gated their
    original authoring — were never consulted.
    """

    async def test_gate_rejects_a_repair_that_fails_its_files_own_criteria(self):
        """Bug caught: the roll-12 shape — no task criteria at all, and a repair
        that violates the rewritten file's own contract reaches the retest."""
        result = await verify_patched_artifacts(
            ["prose only"],
            [{"name": "backend/routes.py", "content": "x = 1\n"}],
            file_owned_criteria=[_fill_slot_criterion()],
        )
        assert result.status == PATCH_FAILED
        assert result.reason == "file_owned_criteria"
        assert [r.status for r in result.checks] == ["failed"]

    async def test_gate_pass_still_leaves_the_retest_to_decide(self):
        """Bug caught: a compiling repair auto-accepted on gate evidence alone —
        compiling is necessary, never sufficient; with no task criteria the
        structurally-unevaluable verdict must survive so the retest decides."""
        result = await verify_patched_artifacts(
            ["prose only"],
            [{"name": "backend/routes.py", "content": "def register():\n    pass\n"}],
            file_owned_criteria=[_fill_slot_criterion()],
        )
        assert result.status == PATCH_UNVERIFIABLE
        assert result.reason == "no_typed_criteria"
        # The gate's executed evidence still rides on the verdict.
        assert [r.status for r in result.checks] == ["passed"]

    async def test_an_unevaluable_gate_row_changes_nothing(self):
        """Bug caught: a gate row this environment cannot execute (stack #2's
        compile checks — runtime-api has no node) flipping the verdict and
        severing the retest path. The gate is monotone: only executed failures
        reject."""
        skipped_gate = TypedCheck(
            check="command_exit_zero",
            params={"argv": ["true"]},
            severity="error",
            description="file-owned: needs a toolchain this environment may lack",
            id="vc-routes-compiles",
        )
        result = await verify_patched_artifacts(
            ["prose only"],
            [{"name": "backend/routes.py", "content": "x = 1\n"}],
            file_owned_criteria=[skipped_gate],
            command_acceptance_enabled=False,
        )
        assert result.status == PATCH_UNVERIFIABLE
        assert result.reason == "no_typed_criteria"

    async def test_gate_dedupes_criteria_the_task_already_carries(self):
        """Bug caught: a dev-task repair (whose task criteria ARE its file's
        criteria) evaluating and reporting every check twice."""
        shared = _fill_slot_criterion()
        result = await verify_patched_artifacts(
            [shared],
            [{"name": "backend/routes.py", "content": "def register():\n    pass\n"}],
            file_owned_criteria=[shared],
        )
        assert result.status == PATCH_PASSED
        assert len(result.checks) == 1

    async def test_gate_failure_is_named_beside_the_task_criteria(self):
        """Bug caught: a repair that satisfies the failed task's own criteria but
        breaks the rewritten file's contract being accepted — the roll-12 shape
        one level up, where task criteria exist and pass."""
        result = await verify_patched_artifacts(
            [
                TypedCheck(
                    check="regex_match",
                    params={"file": "qa_handoff.md", "pattern": "## How to Test"},
                    severity="error",
                    description="Contains How to Test section",
                )
            ],
            [
                {"name": "qa_handoff.md", "content": "# QA Handoff\n## How to Test\n"},
                {"name": "backend/routes.py", "content": "x = 1\n"},
            ],
            file_owned_criteria=[_fill_slot_criterion()],
        )
        assert result.status == PATCH_FAILED
        assert result.reason == "file_owned_criteria"
