"""The acceptance-criteria check, characterized before #1994 moves its two decisions out.

#1994's second piece moves two parts of ``_CycleTaskHandler._evaluate_typed_acceptance``'s loop
beside the evaluator (``squadops.cycles.acceptance_evaluation``): the check row it builds, and
RC-9's blocking matrix, which decides what a failed or erroring criterion appends to ``missing``
and how its evaluator-error strikes are counted and escalated. That is a move: no field of a row,
no entry of ``missing`` or its order, no strike count and no log line may change.

These cases drive the real method through the real evaluator, on real criteria and a real
workspace, and compare everything it banks against a golden captured from the code BEFORE the
move. The evaluator is never patched, so the move can't need a test edit. Only the machine is
pinned: the checks that shell out to Node's tools skip as ``missing_tooling`` where a tool is
absent and run where it is present, so the tools are pinned absent and the golden describes the
handler, not the box.

Bug caught: a move that changes one cell of the matrix while the rest stay green. A warning that
starts to block; an authored skip for missing tooling that reads ``passed``; an injected check's
skip counted as an evidence gap; the evaluator-error wording turned into the app-incompleteness
wording; a third strike that still appends; a strike counted for a failure, or for a warning; a
row's identity fields (task, check index, criterion id) lost; or the lists rebound instead of
appended to.

Regenerate (only for a DELIBERATE behaviour change, in the PR that makes it):
    UPDATE_TYPED_ACCEPTANCE_GOLDENS=1 \
        pytest tests/unit/capabilities/handlers/test_typed_acceptance_characterization.py
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.cycles.implementation_plan import TypedCheck

pytestmark = [pytest.mark.domain_capabilities]

_GOLDEN_PATH = Path(__file__).parent / "goldens" / "typed_acceptance_characterization.json"
#: The tools a typed check shells out to, pinned absent (``test_qa_dev_handle_characterization``).
_TOOLS = frozenset({"tsc", "npm", "npx", "node", "ruff"})
#: The method's temporary workspace, named per run.
_TMPDIR = re.compile(r"squadops-typed-acc-[A-Za-z0-9_]+")

_FASTAPI = (
    "from fastapi import FastAPI\n"
    "app = FastAPI()\n\n"
    '@app.get("/users")\n'
    "def list_users():\n"
    "    return []\n"
)
_FASTAPI_NO_USERS = "from fastapi import FastAPI\napp = FastAPI()\n"
_JSX = "export default function App() {\n  return null\n}\n"


def _art(name: str, content: str) -> dict:
    return {"name": name, "content": content, "media_type": "text/plain", "type": "code"}


def _users(severity: str, *, method: str = "GET", description: str = "the users endpoint"):
    return TypedCheck(
        check="endpoint_defined",
        params={"file": "main.py", "methods_paths": [f"{method} /users"]},
        severity=severity,
        description=description,
    )


def _unsafe_command(severity: str) -> TypedCheck:
    # argv outside the safelist: the evaluator returns status=error.
    return TypedCheck(
        check="command_exit_zero",
        params={"argv": ["python", "-c", "print(1)"]},
        severity=severity,
        description="the command runs",
    )


_FASTAPI_STACK = {"stack": "fastapi"}

#: name -> (criteria, artifacts, resolved_config, extra inputs, prior strikes per criterion)
_CASES: dict[str, tuple[list, list[dict], dict, dict, int]] = {}
for _sev in ("error", "warning"):
    _CASES[f"{_sev}_passed"] = ([_users(_sev)], [_art("main.py", _FASTAPI)], _FASTAPI_STACK, {}, 0)
    _CASES[f"{_sev}_failed"] = (
        [_users(_sev, method="POST")],
        [_art("main.py", _FASTAPI)],
        _FASTAPI_STACK,
        {},
        0,
    )
    _CASES[f"{_sev}_error"] = ([_unsafe_command(_sev)], [_art("main.py", _FASTAPI)], {}, {}, 0)
    # endpoint_defined with no stack set: skipped, never an error (RC-12a).
    _CASES[f"{_sev}_skipped_unsupported"] = ([_users(_sev)], [_art("main.py", _FASTAPI)], {}, {}, 0)
_CASES.update(
    {
        "info_failed": (
            [_users("info", method="POST")],
            [_art("main.py", _FASTAPI)],
            _FASTAPI_STACK,
            {},
            0,
        ),
        # RC-9a's label falls back to the check's name.
        "error_failed_no_description": (
            [_users("error", method="POST", description="")],
            [_art("main.py", _FASTAPI)],
            _FASTAPI_STACK,
            {},
            0,
        ),
        # Config off: a skip the author's config chose, never an evidence gap.
        "typed_acceptance_off": (
            [_users("error"), _unsafe_command("error")],
            [_art("main.py", _FASTAPI)],
            {"stack": "fastapi", "typed_acceptance": False},
            {},
            0,
        ),
        "command_acceptance_off": (
            [_users("error", method="POST"), _unsafe_command("error")],
            [_art("main.py", _FASTAPI)],
            {"stack": "fastapi", "command_acceptance_checks": False},
            {},
            0,
        ),
        # An authored error check skipped for missing tooling is an evidence gap (#423); the
        # same check injected by the framework is not (#605).
        "authored_skip_missing_tooling": (
            [TypedCheck(check="undefined_names", params={"file": "src/App.jsx"}, severity="error")],
            [_art("src/App.jsx", _JSX)],
            {},
            {},
            0,
        ),
        "injected_skip_missing_tooling": ([], [_art("src/App.jsx", _JSX)], {}, {}, 0),
        "injected_failed": ([], [_art("main.py", "print(undefined_thing)\n")], {}, {}, 0),
        # An authored row for the injected check and file wins, at its own severity.
        "authored_overrides_injected": (
            [TypedCheck(check="undefined_names", params={"file": "main.py"}, severity="warning")],
            [_art("main.py", "print(undefined_thing)\n")],
            {},
            {},
            0,
        ),
        # RC-9b: the first two evaluator errors are fed back; the third is escalated.
        "error_second_strike": ([_unsafe_command("error")], [], {}, {}, 1),
        "error_third_strike": ([_unsafe_command("error")], [], {}, {}, 2),
        "prose_and_unparseable": (
            ["Users can be listed", {"check": "no_such_check", "params": {}}, 42],
            [],
            {},
            {},
            0,
        ),
        "nothing_to_evaluate": ([], [_art("notes.md", "# notes\n")], {}, {}, 0),
        # The accepted workspace is materialized first, and the task's own artifact supersedes
        # its slot: routes.py passes from the workspace, main.py fails on the candidate.
        "workspace_then_candidate": (
            [
                TypedCheck(
                    check="endpoint_defined",
                    params={"file": "routes.py", "methods_paths": ["GET /users"]},
                    severity="error",
                ),
                _users("error"),
            ],
            [_art("main.py", _FASTAPI_NO_USERS)],
            _FASTAPI_STACK,
            {"acceptance_workspace_files": {"routes.py": _FASTAPI, "main.py": _FASTAPI}},
            0,
        ),
        # The identity fields: the task's index and a bind-mode criterion's contract id.
        "identity_fields": (
            [
                TypedCheck(
                    check="endpoint_defined",
                    params={"file": "main.py", "methods_paths": ["GET /users"]},
                    severity="error",
                    id="vc-users-listed",
                )
            ],
            [_art("main.py", _FASTAPI)],
            _FASTAPI_STACK,
            {"subtask_index": 3},
            0,
        ),
    }
)


def _normalized(value: Any) -> Any:
    """JSON-shaped, with the per-run workspace name replaced, so the golden is stable."""
    text = json.dumps(value, sort_keys=True, default=str)
    return json.loads(_TMPDIR.sub("squadops-typed-acc-<tmp>", text))


async def _observe(case: str, monkeypatch, caplog) -> dict:
    criteria, artifacts, config, extra, prior = _CASES[case]
    real_which = shutil.which
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name, *a, **kw: None if name in _TOOLS else real_which(name, *a, **kw),
    )
    inputs = {"acceptance_criteria": list(criteria), "resolved_config": dict(config), **extra}
    # The method appends to the lists it's handed; a sentinel in each catches a rebinding.
    checks: list[dict] = [{"check": "earlier_row"}]
    missing: list[str] = ["earlier_entry"]
    counts: dict[str, int] = {
        c.fingerprint(): prior for c in criteria if isinstance(c, TypedCheck) and prior
    }
    with caplog.at_level(logging.DEBUG, logger="squadops"):
        await QATestHandler()._evaluate_typed_acceptance(inputs, artifacts, checks, missing, counts)
    log = [
        {
            "logger": r.name,
            "level": r.levelname,
            "message": r.getMessage(),
            **(
                {k: getattr(r, k) for k in ("check", "severity", "fingerprint", "reason", "actual")}
                if r.getMessage() == "typed_check_evaluator_error_escalated"
                else {}
            ),
        }
        for r in caplog.records
        if r.name.startswith("squadops")
    ]
    return _normalized(
        {"checks": checks, "missing": missing, "typed_error_counts": counts, "log": log}
    )


@pytest.mark.parametrize("case", sorted(_CASES))
async def test_the_acceptance_check_is_unchanged_on_every_case(case, monkeypatch, caplog):
    observed = await _observe(case, monkeypatch, caplog)

    golden = json.loads(_GOLDEN_PATH.read_text()) if _GOLDEN_PATH.exists() else {}
    if os.environ.get("UPDATE_TYPED_ACCEPTANCE_GOLDENS") == "1":
        golden[case] = observed
        _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        _GOLDEN_PATH.write_text(json.dumps(golden, indent=1, sort_keys=True) + "\n")

    assert case in golden, f"no golden for {case}; capture it from the code before the move"
    assert observed == golden[case], (
        f"{case}: the acceptance check banked something different. If the change is "
        "DELIBERATE, regenerate the golden in the same PR so it reads as a behaviour change."
    )


def _rows(case: str, golden: dict) -> list[dict]:
    return [r for r in golden[case]["checks"] if r["check"] != "earlier_row"]


def test_the_cases_exercise_every_cell_the_move_carries():
    """Guards the golden against going vacuous: a case that silently stopped reaching its cell
    (the evaluator answering differently, a criterion no longer parsed) would pass against a
    regenerated golden and prove nothing."""
    golden = json.loads(_GOLDEN_PATH.read_text())

    for sev in ("error", "warning"):
        statuses = {
            status: _rows(f"{sev}_{name}", golden)[0]["status"]
            for status, name in (
                ("passed", "passed"),
                ("failed", "failed"),
                ("error", "error"),
                ("skipped", "skipped_unsupported"),
            )
        }
        assert statuses == {s: s for s in statuses}, sev

    assert golden["error_failed"]["missing"] == ["earlier_entry", "acceptance:the users endpoint"]
    assert golden["warning_failed"]["missing"] == ["earlier_entry"]
    assert golden["warning_error"]["typed_error_counts"] == {}
    assert _rows("error_skipped_unsupported", golden)[0]["evidence_gap"] is True
    assert _rows("typed_acceptance_off", golden)[0]["evidence_gap"] is False
    authored = _rows("authored_skip_missing_tooling", golden)
    injected = _rows("injected_skip_missing_tooling", golden)
    assert [(r["reason"], r["evidence_gap"]) for r in authored if r["check"].endswith("names")] == [
        ("missing_tooling", True)
    ]
    assert [(r["reason"], r["evidence_gap"]) for r in injected if r["check"].endswith("names")] == [
        ("missing_tooling", False)
    ]
    third = golden["error_third_strike"]
    assert third["missing"] == ["earlier_entry"]
    assert list(third["typed_error_counts"].values()) == [3]
    assert any(e["message"] == "typed_check_evaluator_error_escalated" for e in third["log"])
    assert golden["nothing_to_evaluate"]["checks"] == [{"check": "earlier_row"}]
    identity = _rows("identity_fields", golden)[0]
    assert (identity["task_index"], identity["criterion_id"]) == (3, "vc-users-listed")
