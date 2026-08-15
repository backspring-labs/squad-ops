"""Every worked example in an authoring asset must survive the gate it teaches against.

Prose stating a rule does not survive an example demonstrating its violation — the
examples are what get copied. That has now cost two window rolls:

* roll 16 (`cyc_99efd51aedc5`) — the sole-author builder example carried a Dockerfile-less
  ``expected_artifacts`` while the prose rule said otherwise, and the plan reproduced the
  example twice in a row (#890/#891, whose finding was recorded as *patterns beat prose*);
* roll 4 (`cyc_92c44f8704ab`) — the qa proposer example applied ``regex_match`` to
  ``backend/tests/test_users.py``, a source file, **four lines above** the prose saying
  document-only. The plan reproduced the shape against ``__tests__/runs.test.ts`` and was
  system-rejected at ``progress_plan_review`` after 67 minutes of framing (#916).

Correcting each instance leaves the class open. This closes it: an example that production
would reject is a defect decidable offline in milliseconds, so it is decided here instead
of in a cycle.

Deliberately runs the **real** validators rather than re-stating their rules — a test that
reimplemented "regex is document-only" would drift from the gate and start certifying
examples the gate rejects, which is precisely the failure being prevented.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from squadops.cycles.acceptance_check_spec import CHECK_SPECS
from squadops.cycles.implementation_plan import ImplementationPlan

pytestmark = [pytest.mark.domain_contracts]

_PROMPTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"
#: A `tasks:` mapping in a fenced or bare block — the shape a proposer copies.
_TASKS_BLOCK = re.compile(r"(?:^|\n)(tasks:\n(?:[ \t].*\n|\n)*)")


def _example_task_blocks() -> list[tuple[str, list[dict]]]:
    """Every authoring asset's worked example, as raw task dicts.

    Deliberately separate from plan construction. The first version of this file built
    the plan first and inspected its tasks, with ``except ValueError: continue`` for
    blocks that are not full plans — which silently swallowed an example naming a
    nonexistent check, because that is exactly what makes plan construction raise. Two
    mutations survived as a result. Raw extraction cannot be defeated that way.
    """
    found: list[tuple[str, list[dict]]] = []
    for asset in sorted(_PROMPTS.rglob("*.md")):
        text = asset.read_text(encoding="utf-8")
        if "acceptance_criteria" not in text:
            continue
        for block in _TASKS_BLOCK.findall(text):
            try:
                data = yaml.safe_load(block)
            except yaml.YAMLError:
                continue
            if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
                continue
            tasks = [
                t for t in data["tasks"] if isinstance(t, dict) and t.get("acceptance_criteria")
            ]
            if tasks:
                found.append((str(asset.relative_to(_PROMPTS)), tasks))
    return found


def _example_plans() -> list[tuple[str, ImplementationPlan, list[dict]]]:
    """Every authoring asset's worked example, parsed as a plan the gate can judge."""
    found: list[tuple[str, ImplementationPlan, list[dict]]] = []
    for asset in sorted(_PROMPTS.rglob("*.md")):
        text = asset.read_text(encoding="utf-8")
        if "acceptance_criteria" not in text:
            continue
        for block in _TASKS_BLOCK.findall(text):
            try:
                data = yaml.safe_load(block)
            except yaml.YAMLError:
                continue
            if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
                continue
            tasks = [
                t for t in data["tasks"] if isinstance(t, dict) and t.get("acceptance_criteria")
            ]
            if not tasks:
                continue
            for index, task in enumerate(tasks):
                task.setdefault("task_index", index)
                task.setdefault("agent", "a")
                task.setdefault("title", task.get("focus", "example"))
                task.setdefault("task_type", "qa.test")
                task.setdefault("role", "qa")
            doc = {
                "version": 1,
                "project_id": "p",
                "cycle_id": "c",
                "run_id": "r",
                "prd_hash": "h",
                "summary": {"objective": "o"},
                "tasks": tasks,
            }
            try:
                plan = ImplementationPlan.from_yaml(yaml.safe_dump(doc))
            except ValueError:  # not a full plan example — nothing to judge
                continue
            found.append((str(asset.relative_to(_PROMPTS)), plan, tasks))
    return found


def test_at_least_one_example_is_found():
    """A parser that silently matches nothing would make every assertion below vacuous —
    the exact way a sweep-style test rots into decoration."""
    assert _example_plans(), "no authoring example parsed as a plan; the extractor drifted"
    assert _example_task_blocks(), "no authoring example task block found; the regex drifted"


def test_no_shipped_example_would_be_rejected_by_the_criteria_scope_gate():
    """Bug caught: an asset teaches a criterion shape production refuses.

    Measured against roll 4's own rejection class. The gate's validator is called
    directly, so the two can never disagree about what is allowed.
    """
    offenders: list[str] = []
    for name, plan, _ in _example_plans():
        for error in plan.validate_criteria_scope():
            offenders.append(f"{name}: {error}")

    assert offenders == [], (
        "an authoring example would be rejected in production — examples are what get "
        "copied, so this ships a guaranteed framing rejection:\n  " + "\n  ".join(offenders)
    )


def test_every_example_criterion_uses_a_real_check_with_real_parameters():
    """Bug caught: an example names a check that does not exist, or passes it parameters
    it does not accept.

    Caught while fixing #916: the first replacement for the bad example used `name` and
    `count_min`, where `function_defined` declares `name_prefix` and `min_count`. A
    plausible-looking example with wrong parameter names teaches an unsatisfiable
    criterion just as effectively as a forbidden one.
    """
    problems: list[str] = []
    for name, tasks in _example_task_blocks():
        for task in tasks:
            for criterion in task["acceptance_criteria"]:
                if not isinstance(criterion, dict):
                    # Prose criteria are a legitimate shape (advisory, not typed) — the
                    # typed-parameter contract below simply does not apply to them.
                    continue
                check = criterion.get("check")
                spec = CHECK_SPECS.get(check)
                if spec is None:
                    problems.append(f"{name}: unknown check {check!r}")
                    continue
                supplied = set(criterion) - {"check", "severity"}
                missing = spec.required_params - supplied
                unknown = supplied - spec.required_params - spec.optional_params
                if missing:
                    problems.append(f"{name}: {check} missing {sorted(missing)}")
                if unknown:
                    problems.append(f"{name}: {check} given unknown {sorted(unknown)}")

    assert problems == [], "authoring examples teach invalid criteria:\n  " + "\n  ".join(problems)
