"""Unit tests for executor-side patch verification (#389).

Each test names the bug it catches: the correction loop re-dispatching a
generative task after a good repair (re-roll clobbers the patch), or the
verifier accepting a patch without positive executed evidence.
"""

from pathlib import Path

from squadops.cycles.implementation_plan import TypedCheck
from squadops.cycles.patch_verification import (
    PATCH_FAILED,
    PATCH_PASSED,
    PATCH_UNVERIFIABLE,
    EvidenceSupersession,
    overlay_artifacts,
    supersede_evidence_artifacts,
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


class TestSupersedeEvidenceArtifacts:
    """#1111: an accepted patch re-stores the failed result's artifacts overlaid with the
    repair — so the failed run's own evidence (report, typed-check evaluation) landed under
    the task id AFTER the passing retest stored its report under its own id."""

    _PATCHED = [
        {"name": "backend/routes.py", "content": "fixed", "type": "source"},
        {"name": "backend/tests/test_runs.py", "content": "tests", "type": "test"},
        {"name": "test_report.md", "content": "3 validation errors for Run", "type": "test_report"},
        {
            "name": "typed_check_evaluation_task_4.json",
            "content": "{}",
            "type": "typed_check_evaluation",
        },
    ]

    def test_retest_report_replaces_the_failed_one_and_stale_evaluation_is_dropped(self):
        retest = [
            {"name": "backend/tests/test_runs.py", "content": "tests", "type": "test"},
            {"name": "test_report.md", "content": "11 passed in 0.05s", "type": "test_report"},
        ]
        out = supersede_evidence_artifacts(self._PATCHED, retest)
        assert [(a["name"], a["content"]) for a in out.artifacts] == [
            ("backend/routes.py", "fixed"),
            ("backend/tests/test_runs.py", "tests"),
            ("test_report.md", "11 passed in 0.05s"),
        ]
        assert out.replaced == ("test_report.md",)
        assert out.dropped == ("typed_check_evaluation_task_4.json",)

    def test_retest_without_evidence_drops_the_failed_evidence(self):
        out = supersede_evidence_artifacts(self._PATCHED, [])
        assert [a["name"] for a in out.artifacts] == [
            "backend/routes.py",
            "backend/tests/test_runs.py",
        ]
        assert out.replaced == ()
        assert out.dropped == ("test_report.md", "typed_check_evaluation_task_4.json")

    def test_retest_work_product_is_never_added_and_non_evidence_is_never_touched(self):
        """The retest's own suite files live under the retest id; a retest artifact
        that only shares a NAME with work product must not overwrite it here."""
        retest = [
            {"name": "backend/routes.py", "content": "retest copy", "type": "source"},
            {"name": "frontend/extra.test.jsx", "content": "new", "type": "test"},
        ]
        out = supersede_evidence_artifacts(self._PATCHED, retest)
        by_name = {a["name"]: a["content"] for a in out.artifacts}
        assert by_name["backend/routes.py"] == "fixed"
        assert "frontend/extra.test.jsx" not in by_name
        assert out.dropped == ("test_report.md", "typed_check_evaluation_task_4.json")

    def test_empty_inputs(self):
        out = supersede_evidence_artifacts(None, None)
        assert out == EvidenceSupersession([], (), ())


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


# --- #1229: the verdict comes from wherever the check actually ran ----------------------

_REPLAYS = __import__("pathlib").Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"


def _nextjs_tree_with_the_1221_patch():
    """The Next.js skeleton the failed task was evaluated against, and the first repair
    ``cyc_05abfc7c1f00`` produced for ``app/api/runs/route.ts`` — stored bytes."""
    from squadops.capabilities.scaffold import expand
    from tests.unit.capabilities._stack_fixtures import manifest_for_stack

    tree = {f["name"]: f["content"] for f in expand(manifest_for_stack("nextjs_ts"))}
    patch = [
        {
            "name": "app/api/runs/route.ts",
            "content": (_REPLAYS / "1-7-0-1221-repair-00-app-api-runs-route.ts").read_text(),
        }
    ]
    return tree, patch


_ROUTE_PARAMS = {"file": "app/api/runs/route.ts", "project_dir": "."}


def _compiles_criterion() -> list[TypedCheck]:
    return [
        TypedCheck(
            check="frontend_compiles",
            params=dict(_ROUTE_PARAMS),
            severity="error",
            description="the route compiles (vc-compiles-app-api-runs-route)",
        )
    ]


def _agent_rows(status: str, params: dict | None = None) -> dict:
    return {
        "environment": "agent:dev",
        "checks": [
            {
                "check": "acceptance:frontend_compiles",
                "severity": "error",
                "params": dict(params or _ROUTE_PARAMS),
                "status": status,
                "reason": "ok" if status == "passed" else "frontend_build_failed",
                "actual": None,
            }
        ],
    }


class TestTheVerdictComesFromWhereTheCheckRan:
    """``cyc_05abfc7c1f00``: three rounds on ``app/api/runs/route.ts``, two identical
    ``unverifiable`` verdicts, a run at 1/14. The criterion owning a ``.ts`` file needs
    node, runtime-api has none, so nothing blocking ever executed here. The repair now
    evaluates the same criteria where the toolchain lives and sends the rows along; this
    environment keeps cross-checking what it can."""

    @staticmethod
    def _no_npm_here(monkeypatch):
        from squadops.cycles import acceptance_checks

        monkeypatch.setattr(acceptance_checks.shutil, "which", lambda name: None)

    async def test_without_the_repairs_rows_the_1221_shape_is_still_unverifiable(self, monkeypatch):
        """The control: nothing executed in either environment is still not a verdict, and
        the #1221 backstop still names it a deadlock."""
        from adapters.cycles.dispatched_flow_executor import correction_is_deadlocked

        self._no_npm_here(monkeypatch)
        tree, patch = _nextjs_tree_with_the_1221_patch()
        result = await verify_patched_artifacts(
            _compiles_criterion(), patch, workspace_files=tree, stack="nextjs_ts"
        )
        assert result.status == PATCH_UNVERIFIABLE
        assert result.reason == "no_executed_blocking_checks"
        assert result.decided_by_agent == 0
        assert correction_is_deadlocked(result.status, result.reason, retest_decides=False)

    async def test_the_repairs_own_execution_decides_what_this_environment_cannot_run(
        self, monkeypatch
    ):
        self._no_npm_here(monkeypatch)
        tree, patch = _nextjs_tree_with_the_1221_patch()
        result = await verify_patched_artifacts(
            _compiles_criterion(),
            patch,
            workspace_files=tree,
            stack="nextjs_ts",
            agent_checks=_agent_rows("passed"),
        )
        assert result.status == PATCH_PASSED
        assert result.decided_by_agent == 1
        by_env = {
            (r.executed_in, r.status) for r in result.checks if r.check == "frontend_compiles"
        }
        assert ("runtime-api", "skipped") in by_env
        assert ("agent:dev", "passed") in by_env

    async def test_an_executed_failure_in_the_repairs_container_rejects(self, monkeypatch):
        self._no_npm_here(monkeypatch)
        tree, patch = _nextjs_tree_with_the_1221_patch()
        result = await verify_patched_artifacts(
            _compiles_criterion(),
            patch,
            workspace_files=tree,
            stack="nextjs_ts",
            agent_checks=_agent_rows("failed"),
        )
        assert result.status == PATCH_FAILED

    async def test_rows_for_another_file_say_nothing_about_this_criterion(self, monkeypatch):
        """Bug caught: matching on the check name alone — a green row for a sibling route
        would vouch for a file the repair never compiled."""
        self._no_npm_here(monkeypatch)
        tree, patch = _nextjs_tree_with_the_1221_patch()
        result = await verify_patched_artifacts(
            _compiles_criterion(),
            patch,
            workspace_files=tree,
            stack="nextjs_ts",
            agent_checks=_agent_rows(
                "passed", {"file": "app/api/runs/[run_id]/route.ts", "project_dir": "."}
            ),
        )
        assert result.status == PATCH_UNVERIFIABLE
        assert result.reason == "no_executed_blocking_checks"

    async def test_an_agent_pass_never_overrides_a_failure_that_executed_here(self):
        """Bug caught: the agent's rows treated as the verdict rather than as evidence —
        a failure this environment executed must stand whatever the repair reported."""
        rows = {
            "environment": "agent:dev",
            "checks": [
                {
                    "check": "acceptance:regex_match",
                    "severity": "error",
                    "params": {"file": "qa_handoff.md", "pattern": f"## {section}"},
                    "status": "passed",
                    "reason": "ok",
                }
                for section in ("How to Run", "How to Test", "Implemented Scope")
            ],
        }
        result = await verify_patched_artifacts(
            _heading_criteria(),
            [{"name": "qa_handoff.md", "content": BROKEN_DOC}],
            agent_checks=rows,
        )
        assert result.status == PATCH_FAILED
        assert result.decided_by_agent == 0

    async def test_a_local_evaluator_error_the_repair_executed_does_not_abort(self, monkeypatch):
        """An evaluator that breaks HERE on a criterion the repair executed cleanly is this
        environment's problem, not the patch's; without the repair's row it still aborts,
        exactly as before."""
        from squadops.cycles import patch_verification
        from squadops.cycles.acceptance_checks import CheckOutcome

        async def broken(criterion, workspace_root, **kwargs):
            return CheckOutcome.error(reason="boom")

        monkeypatch.setattr(patch_verification, "evaluate_criterion", broken)
        tree, patch = _nextjs_tree_with_the_1221_patch()
        with_rows = await verify_patched_artifacts(
            _compiles_criterion(),
            patch,
            workspace_files=tree,
            stack="nextjs_ts",
            agent_checks=_agent_rows("passed"),
        )
        assert with_rows.status == PATCH_PASSED
        without = await verify_patched_artifacts(
            _compiles_criterion(), patch, workspace_files=tree, stack="nextjs_ts"
        )
        assert without.status == PATCH_UNVERIFIABLE
        assert without.reason == "evaluator_error:frontend_compiles"


class TestAgentRowsFromEveryRepairStep:
    """#1256: the executor hands the verifier the protocol result's rows — one handler
    output per repair step, each in its own environment. Bug caught: a round whose dev
    step and qa step both evaluated rows and only one environment's records reaching
    the verdict, or a single handler output no longer being read."""

    def _step(self, environment: str, check: str, status: str) -> dict:
        return {
            "environment": environment,
            "checks": [
                {
                    "check": f"acceptance:{check}",
                    "status": status,
                    "severity": "error",
                    "params": {"file": "frontend/src/views/RunListView.jsx"},
                }
            ],
        }

    def test_a_sequence_of_step_outputs_yields_every_environments_records(self):
        from squadops.cycles.patch_verification import agent_check_records

        records = agent_check_records(
            (
                self._step("agent:dev", "frontend_compiles", "failed"),
                self._step("agent:qa", "dom_anchor_queries", "passed"),
            )
        )
        assert [(r.check, r.status, r.executed_in) for r in records] == [
            ("frontend_compiles", "failed", "agent:dev"),
            ("dom_anchor_queries", "passed", "agent:qa"),
        ]

    def test_a_single_handler_output_and_an_empty_sequence_still_read(self):
        from squadops.cycles.patch_verification import agent_check_records

        single = agent_check_records(self._step("agent:dev", "undefined_names", "passed"))
        assert [(r.check, r.executed_in) for r in single] == [("undefined_names", "agent:dev")]
        assert agent_check_records(()) == []
        assert agent_check_records([{"environment": "agent:dev", "checks": []}]) == []

    async def test_a_dev_steps_executed_failure_rejects_the_patch_runtime_api_could_not_judge(
        self,
    ):
        """The shakeout's round 1: neo reported ``frontend_compiles: failed`` on the patch
        and runtime-api — no node — skipped the same row and logged ``agent_rows=0``."""
        from squadops.cycles.patch_verification import PATCH_FAILED, verify_patched_artifacts

        criterion = TypedCheck(
            check="frontend_compiles",
            params={"file": "frontend/src/views/RunListView.jsx"},
            id="c1",
        )
        verdict = await verify_patched_artifacts(
            [criterion],
            [{"name": "frontend/src/views/RunListView.jsx", "content": "export default 1\n"}],
            agent_checks=(self._step("agent:dev", "frontend_compiles", "failed"),),
        )
        assert verdict.status == PATCH_FAILED
        assert [
            (r.check, r.status, r.executed_in)
            for r in verdict.checks
            if r.executed_in != "runtime-api"
        ] == [("frontend_compiles", "failed", "agent:dev")]


class TestAbsentFilesAreNotEvidenceAboutThePatch:
    """#1259: the Next.js shakeout on dfe466ab (cyc_9c379355b5e8, round 0) refused a correct
    route fix because the qa task's suite-bound checks — evaluated in the dev container and
    here — returned ``failed(file_not_found)`` for a suite the patch never carries. Bug
    caught: a dev repair of a qa failure rejected for a reason that says nothing about it;
    and the opposite regression — a repair that names a file and does not produce it
    sailing through."""

    _REPLAYS = Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"
    _SUITE = "__tests__/runs_api.test.ts"

    def _criteria(self):
        return [
            TypedCheck(
                check="assertion_kinds_match",
                params={"file": self._SUITE, "field_kinds": {"capacity": "number"}},
                id="kinds",
            ),
            TypedCheck(
                check="dom_anchor_queries",
                params={"file": self._SUITE, "anchors": {"RunListView": ["run-list"]}},
                id="anchors",
            ),
        ]

    def _route(self) -> dict:
        return {
            "name": "app/api/runs/route.ts",
            "content": (
                self._REPLAYS / "1-7-1-nextjs-shakeout-3-repair-00-app-api-runs-route.ts"
            ).read_text(encoding="utf-8"),
        }

    def _agent_rows(self, file: str) -> dict:
        return {
            "environment": "agent:dev",
            "checks": [
                {
                    "check": f"acceptance:{c.check}",
                    "status": "failed",
                    "severity": "error",
                    "reason": "file_not_found",
                    "params": {**c.params, "file": file},
                }
                for c in self._criteria()
            ],
        }

    async def test_the_round_0_patch_is_no_longer_refused_on_the_suite_it_never_carried(self):
        from squadops.cycles.patch_verification import (
            PATCH_UNVERIFIABLE,
            REASON_FILE_NOT_IN_PATCH,
            REASON_NO_EXECUTED_BLOCKING_CHECKS,
            verify_patched_artifacts,
        )

        verdict = await verify_patched_artifacts(
            self._criteria(),
            [self._route()],
            workspace_files={"lib/store.ts": "export const TABLES = {}"},
            agent_checks=self._agent_rows(self._SUITE),
        )
        # Nothing executed against the patch — the retest decides, as before #1240/#1246.
        assert (verdict.status, verdict.reason) == (
            PATCH_UNVERIFIABLE,
            REASON_NO_EXECUTED_BLOCKING_CHECKS,
        )
        assert {(r.status, r.reason) for r in verdict.checks} == {
            ("skipped", REASON_FILE_NOT_IN_PATCH)
        }
        assert {r.executed_in for r in verdict.checks} == {"runtime-api", "agent:dev"}

    async def test_with_the_suite_in_the_tree_the_same_patch_passes(self):
        from squadops.cycles.patch_verification import PATCH_PASSED, verify_patched_artifacts

        suite = (self._REPLAYS / "1-7-1-nextjs-shakeout-3-qa-round-0-runs_api.test.ts").read_text(
            encoding="utf-8"
        )
        verdict = await verify_patched_artifacts(
            self._criteria(),
            [self._route(), {"name": self._SUITE, "content": suite}],
            workspace_files={"lib/store.ts": "export const TABLES = {}"},
        )
        assert verdict.status == PATCH_PASSED
        assert [(r.check, r.status) for r in verdict.checks] == [
            ("assertion_kinds_match", "passed"),
            ("dom_anchor_queries", "passed"),
        ]

    async def test_an_agent_row_missing_a_file_the_patch_carries_still_rejects(self):
        """The control: the agent says a file the patch names is not there — that is about
        the patch (its tree lacked what the repair claimed), and it keeps its rejection power."""
        from squadops.cycles.patch_verification import PATCH_FAILED, verify_patched_artifacts

        criteria = [
            TypedCheck(
                check="assertion_kinds_match",
                params={"file": "app/api/runs/route.ts", "field_kinds": {"capacity": "number"}},
                id="kinds",
            )
        ]
        rows = {
            "environment": "agent:dev",
            "checks": [
                {
                    "check": "acceptance:assertion_kinds_match",
                    "status": "failed",
                    "severity": "error",
                    "reason": "file_not_found",
                    "params": criteria[0].params,
                }
            ],
        }
        verdict = await verify_patched_artifacts(criteria, [self._route()], agent_checks=rows)
        assert verdict.status == PATCH_FAILED
        assert [
            (r.executed_in, r.status, r.reason)
            for r in verdict.checks
            if r.executed_in != "runtime-api"
        ] == [("agent:dev", "failed", "file_not_found")]
