"""pf-31 Fix A — authoritative contract-expectation rendering + prose-conflict lint.

The bug these guard against: the resolved TypedChecks reached every pf-31 repair
as low-salience dict reprs below contradicting prose, so all 7 repairs emitted the
prose's ``{run_id}`` where the contract pins ``{id}`` and were rejected over that
one token (docs/plans/pf31-correction-convergence-fixes.md, Fix A).
"""

from __future__ import annotations

import pytest

from squadops.cycles.contract_expectations import (
    expectation_lines,
    is_typed_criterion,
    prose_criteria,
)
from squadops.cycles.implementation_plan import (
    ImplementationPlan,
    PlanSummary,
    PlanTask,
    TypedCheck,
)
from squadops.cycles.verification_contract import VerificationContract

pytestmark = [pytest.mark.domain_capabilities]


class TestExpectationLines:
    def test_endpoint_defined_renders_exact_paths_with_param_names(self):
        """The line must carry the literal path-parameter spelling — the exact
        token every pf-31 repair got wrong."""
        entry = TypedCheck(
            check="endpoint_defined",
            params={
                "file": "backend/routes.py",
                "methods_paths": ["POST /runs", "GET /runs/{id}", "POST /runs/{id}/join"],
            },
            id="vc-routes-endpoints",
        )
        (line,) = expectation_lines([entry])
        assert "`GET /runs/{id}`" in line
        assert "`POST /runs/{id}/join`" in line
        assert "path-parameter names" in line

    def test_endpoint_defined_accepts_pair_shape(self):
        entry = {
            "check": "endpoint_defined",
            "file": "b/m.py",
            "methods_paths": [["POST", "/users"]],
        }
        (line,) = expectation_lines([entry])
        assert "`POST /users`" in line

    def test_import_present_with_symbol_renders_direct_import_form(self):
        """pf-31 corr-00 class: `from . import errors` failed where the check
        demands the direct symbol import."""
        entry = {
            "check": "import_present",
            "params": {"file": "backend/routes.py", "module": ".errors", "symbol": "ApiError"},
            "id": "vc-routes-apierror",
        }
        (line,) = expectation_lines([entry])
        assert "`from .errors import ApiError`" in line

    def test_import_present_module_only(self):
        (line,) = expectation_lines(
            [{"check": "import_present", "file": "m.py", "module": "fastapi"}]
        )
        assert "import module `fastapi`" in line

    @pytest.mark.parametrize(
        "entry,fragment",
        [
            (
                {
                    "check": "field_present",
                    "file": "m.py",
                    "class_name": "RunEvent",
                    "fields": ["id", "title"],
                },
                "class `RunEvent`",
            ),
            (
                {
                    "check": "function_defined",
                    "file": "t.py",
                    "name_prefix": "test_",
                    "min_count": 8,
                },
                "at least 8 functions named `test_*`",
            ),
            (
                {"check": "command_exit_zero", "argv": ["python", "-m", "py_compile", "x.py"]},
                "`python -m py_compile x.py` must exit 0",
            ),
            (
                {
                    "check": "harness_boundary",
                    "file": "t.py",
                    "entry_modules": ["backend.main", "app.main"],
                    "client_ctor": "TestClient",
                },
                "must NOT import the app entry module (`backend.main`, `app.main`)",
            ),
        ],
    )
    def test_known_check_types_render(self, entry, fragment):
        (line,) = expectation_lines([entry])
        assert fragment in line

    def test_harness_boundary_states_prohibition_not_construction(self):
        """pf-33 corr-00 regression: the old wording ("must build its TestClient
        against one of: backend.main...") read as an instruction to import the
        entry module and construct the client — eve's repair obeyed it and was
        rejected by the very check the line rendered. The line must forbid the
        import/construction and point at the scaffold `client` fixture."""
        (line,) = expectation_lines(
            [
                {
                    "check": "harness_boundary",
                    "file": "backend/tests/test_runs.py",
                    "entry_modules": ["backend.main", "app.main"],
                    "client_ctor": "TestClient",
                }
            ]
        )
        assert "must NOT import" in line
        assert "must NOT construct `TestClient(...)`" in line
        assert "`client` fixture" in line
        assert "must build its" not in line  # the misleading phrasing stays dead

    def test_unknown_check_type_still_surfaces(self):
        """A new check vocabulary entry must not be silently dropped from the
        authoritative block — that would recreate the invisibility bug."""
        (line,) = expectation_lines([{"check": "future_check", "file": "x.py", "threshold": 3}])
        assert "future_check" in line and "threshold=3" in line

    def test_prose_and_typed_split(self):
        criteria = [
            "POST /runs validates required fields",
            {"check": "import_present", "file": "m.py", "module": "fastapi"},
        ]
        assert prose_criteria(criteria) == ["POST /runs validates required fields"]
        assert len(expectation_lines(criteria)) == 1
        assert not is_typed_criterion(criteria[0])
        assert is_typed_criterion(criteria[1])

    def test_empty_and_none_inputs(self):
        assert expectation_lines(None) == []
        assert expectation_lines([]) == []
        assert prose_criteria(None) == []


def _contract() -> VerificationContract:
    return VerificationContract.from_dict(
        {
            "contract_version": 1,
            "skeleton": {
                "expander": "fullstack_fastapi_react",
                "interface_manifest_hash": "a" * 64,
            },
            "capabilities": ["python"],
            "frozen": [{"path": "backend/errors.py", "sha256": "b" * 64}],
            "fill_files": {
                "backend/routes.py": {
                    "interface": [
                        {
                            "check": "endpoint_defined",
                            "id": "vc-routes-endpoints",
                            "methods_paths": [
                                "POST /runs",
                                "GET /runs/{id}",
                                "POST /runs/{id}/join",
                                "POST /runs/{id}/leave",
                            ],
                        },
                    ],
                    "implementation": [],
                },
            },
        }
    )


def _plan(description: str, prose: list[str]) -> ImplementationPlan:
    task = PlanTask(
        task_index=0,
        task_type="development.develop",
        role="dev",
        focus="backend API routes",
        description=description,
        expected_artifacts=["backend/routes.py"],
        acceptance_criteria=list(prose),
        criteria_refs=["vc-routes-endpoints"],
    )
    return ImplementationPlan(
        version=1,
        project_id="p",
        cycle_id="c",
        prd_hash="h",
        tasks=[task],
        summary=PlanSummary(total_dev_tasks=1, total_qa_tasks=0, total_tasks=1),
    )


class TestProseContractConflictLint:
    def test_pf31_param_name_conflict_warns(self):
        plan = _plan(
            "Implement GET /runs/{run_id} (detail) and POST /runs/{run_id}/join.",
            ["GET /runs/{run_id} returns run detail"],
        )
        warnings = plan.lint_prose_contract_conflicts(_contract())
        assert any("{run_id}" in w and "pf-31" in w for w in warnings)

    def test_pf30_method_conflict_warns(self):
        plan = _plan(
            "Implement DELETE /runs/{id}/leave to remove a participant.",
            [],
        )
        warnings = plan.lint_prose_contract_conflicts(_contract())
        assert any("DELETE" in w and "different method" in w for w in warnings)

    def test_consistent_prose_is_silent(self):
        plan = _plan(
            "Implement POST /runs, GET /runs/{id}, POST /runs/{id}/join, POST /runs/{id}/leave.",
            ["GET /runs/{id} returns run detail; POST /runs/{id}/join adds a participant"],
        )
        assert plan.lint_prose_contract_conflicts(_contract()) == []

    def test_no_refs_no_warnings(self):
        task = PlanTask(
            task_index=0,
            task_type="development.develop",
            role="dev",
            focus="x",
            description="GET /whatever/{weird_param}",
            expected_artifacts=["a.py"],
        )
        plan = ImplementationPlan(
            version=1,
            project_id="p",
            cycle_id="c",
            prd_hash="h",
            tasks=[task],
            summary=PlanSummary(total_dev_tasks=1, total_qa_tasks=0, total_tasks=1),
        )
        assert plan.lint_prose_contract_conflicts(_contract()) == []
