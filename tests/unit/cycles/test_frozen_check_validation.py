"""Frozen-file check validation (pf-42).

pf-42's plan asserted ``field_present`` for a ``RunEvent`` field called
``meeting_location`` on ``backend/models.py``, and ``import_present`` for the module
``backend.routes`` on ``backend/main.py``. Both files are frozen — the manifest declares
the field as ``location``, and the frozen main.py imports ``from .routes``. Both checks
were error-severity, and neither could ever pass: a repair rewriting a frozen file has
its emission restored before the check re-runs, so the correction loop burns its whole
budget failing identically.

The checks below use the real group_run manifest and the two real failing specs, so a
regression here means the actual pf-42 plan would be admitted again.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadops.capabilities.scaffold import InterfaceManifest
from squadops.capabilities.scaffold_contract import emit_contract_dict
from squadops.cycles.frozen_check_validation import frozen_check_violations
from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.verification_contract import VerificationContract

pytestmark = [pytest.mark.domain_cycles]

_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)


def _manifest_content() -> str:
    return _MANIFEST_PATH.read_text(encoding="utf-8")


def _contract() -> VerificationContract:
    manifest = InterfaceManifest.from_yaml(_manifest_content())
    return VerificationContract.from_dict(emit_contract_dict(manifest))


def _plan(criteria_yaml: str, *, artifact: str = "backend/models.py") -> ImplementationPlan:
    return ImplementationPlan.from_yaml(
        f"""\
version: 1
project_id: group_run
cycle_id: cyc_test
prd_hash: abc123

tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: "Backend models"
    description: "Create data models"
    expected_artifacts:
      - "{artifact}"
    acceptance_criteria:
{criteria_yaml}
    depends_on: []

summary:
  total_tasks: 1
  total_dev_tasks: 1
  total_qa_tasks: 0
  estimated_layers: []
"""
    )


# --- the two real pf-42 defects ------------------------------------------------ #


async def test_pf42_invented_field_name_on_frozen_models_is_rejected():
    """The exact check that would have cost pf-42 its roll."""
    plan = _plan(
        """\
      - check: field_present
        file: backend/models.py
        class_name: RunEvent
        fields: [id, title, datetime, meeting_location, participants]
"""
    )
    errors = await frozen_check_violations(plan, _contract(), _manifest_content())

    assert len(errors) == 1
    msg = errors[0]
    assert "field_present" in msg
    assert "backend/models.py" in msg
    # the operator needs the real name, not just "it failed"
    assert "meeting_location" in msg
    assert "location" in msg
    assert "frozen" in msg


async def test_pf42_absolute_import_against_relative_frozen_import_is_rejected():
    """Frozen main.py imports ``from .routes``; the plan asserted ``backend.routes``."""
    plan = _plan(
        """\
      - check: import_present
        file: backend/main.py
        module: backend.routes
""",
        artifact="backend/main.py",
    )
    errors = await frozen_check_violations(plan, _contract(), _manifest_content())

    assert len(errors) == 1
    assert "import_present" in errors[0]
    assert "backend/main.py" in errors[0]


# --- the checks that must still be admitted ------------------------------------ #


async def test_check_the_frozen_file_actually_satisfies_is_admitted():
    """Same check, real field name — the scaffold satisfies it, so the plan stands."""
    plan = _plan(
        """\
      - check: field_present
        file: backend/models.py
        class_name: RunEvent
        fields: [id, title, datetime, location, participants]
"""
    )
    assert await frozen_check_violations(plan, _contract(), _manifest_content()) == []


async def test_checks_on_fill_slots_are_not_pre_validated():
    """A fill slot is empty at authoring time — judging it now would reject every plan."""
    plan = _plan(
        """\
      - check: endpoint_defined
        file: backend/routes.py
        methods_paths: ["POST /runs"]
""",
        artifact="backend/routes.py",
    )
    assert await frozen_check_violations(plan, _contract(), _manifest_content()) == []


async def test_warning_severity_failure_does_not_reject():
    """A warning cannot block a build (RC-9), so a failing one must not block a plan."""
    plan = _plan(
        """\
      - check: field_present
        severity: warning
        file: backend/models.py
        class_name: RunEvent
        fields: [meeting_location]
"""
    )
    assert await frozen_check_violations(plan, _contract(), _manifest_content()) == []


async def test_prose_criteria_are_ignored():
    plan = _plan(
        """\
      - "RunEvent carries every field the PRD lists"
"""
    )
    assert await frozen_check_violations(plan, _contract(), _manifest_content()) == []


# --- failing open where proving nothing ---------------------------------------- #


async def test_unparseable_manifest_does_not_reject_the_plan():
    """The manifest has its own upstream net; a parse failure is not a plan defect."""
    plan = _plan(
        """\
      - check: field_present
        file: backend/models.py
        class_name: RunEvent
        fields: [meeting_location]
"""
    )
    assert await frozen_check_violations(plan, _contract(), ":\n  not: [valid") == []


async def test_multiple_violations_are_all_reported():
    """One rejection per defect — an operator fixing a plan should see every problem."""
    plan = ImplementationPlan.from_yaml(
        """\
version: 1
project_id: group_run
cycle_id: cyc_test
prd_hash: abc123

tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: "Backend models"
    description: "models"
    expected_artifacts: ["backend/models.py"]
    acceptance_criteria:
      - check: field_present
        file: backend/models.py
        class_name: RunEvent
        fields: [meeting_location]
    depends_on: []
  - task_index: 1
    task_type: development.develop
    role: dev
    focus: "Backend app"
    description: "app"
    expected_artifacts: ["backend/main.py"]
    acceptance_criteria:
      - check: import_present
        file: backend/main.py
        module: backend.routes
    depends_on: [0]

summary:
  total_tasks: 1
  total_dev_tasks: 1
  total_qa_tasks: 0
  estimated_layers: []
"""
    )
    errors = await frozen_check_violations(plan, _contract(), _manifest_content())

    assert len(errors) == 2
    assert "Task 0" in errors[0]
    assert "Task 1" in errors[1]
