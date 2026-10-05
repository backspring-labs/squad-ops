"""#1796: the boot audit renders each declared route, by the increment evaluation's own render.

What bugs would these catch? The audit passing an app whose declared page renders no view (#1794's
two rejected React rolls and one accepted cycle all passed it with a detail page no browser could
reach); a page the audit never read reported as a pass; and the driver drifting from the
evaluation's render it calls (a renamed function or argument would turn every route unread).
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[3]


def _load():
    sys.path.insert(0, str(_ROOT / "scripts" / "dev"))
    spec = importlib.util.spec_from_file_location(
        "audit_delivered_app", _ROOT / "scripts" / "dev" / "audit_delivered_app.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = _load()

DECLARED = {"/": ("runs-view", "run-list"), "/runs/{run_id}": ("run-detail-view",)}


@pytest.mark.parametrize(
    ("rendered", "expected"),
    [
        ({"/": frozenset({"runs-view"}), "/runs/{run_id}": frozenset({"run-detail-view"})}, []),
        (
            {"/": frozenset({"runs-view"}), "/runs/{run_id}": frozenset({"not-found-state"})},
            ["/runs/{run_id}: rendered without its view's root ('run-detail-view',)"],
        ),
        (
            {"/": frozenset({"runs-view"}), "/runs/{run_id}": None},
            ["/runs/{run_id}: not read (blocked_unverified), so not seen to render"],
        ),
    ],
    ids=["every-view-rendered", "detail-page-without-its-view", "detail-page-never-read"],
)
def test_each_declared_route_is_judged_by_the_evaluations_judge(rendered, expected):
    """A list's rows are state (an empty list shows none), so only each view's root anchor is
    judged, as §24p judges it. A page never read fails: the audit did not see it render."""
    assert audit.route_failures(DECLARED, rendered) == expected


def test_the_routes_are_read_in_the_render_container_with_the_runs_own_seeds():
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, json.loads(kwargs["input"])))
        return SimpleNamespace(
            returncode=0,
            stdout='INFO noise\n{"/": ["runs-view"], "/runs/{run_id}": null}\n',
            stderr="",
        )

    seeds = {"/runs/{run_id}": {"method": "POST", "path": "/api/runs", "param": "run_id"}}

    read = audit.render_declared_routes(
        {"a.ts": "x"}, "nextjs_ts", DECLARED, seeds, container="qa-box", run=run
    )

    [(argv, payload)] = calls
    assert argv[:6] == ["docker", "exec", "-i", "qa-box", "python3", "-c"]
    assert payload == {
        "stack": "nextjs_ts",
        "files": {"a.ts": "x"},
        "declared": {"/": ["runs-view", "run-list"], "/runs/{run_id}": ["run-detail-view"]},
        "seeds": seeds,
    }
    assert read == {"/": frozenset({"runs-view"}), "/runs/{run_id}": None}


@pytest.mark.parametrize(
    "outcome",
    [
        SimpleNamespace(returncode=1, stdout="", stderr="ModuleNotFoundError: squadops"),
        subprocess.TimeoutExpired(cmd="docker", timeout=1),
    ],
    ids=["driver-failed", "timed-out"],
)
def test_a_render_that_could_not_run_reads_every_route_unread(outcome):
    def run(argv, **kwargs):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    read = audit.render_declared_routes({}, "nextjs_ts", DECLARED, {}, run=run)

    assert read == {route: None for route in DECLARED}


def test_the_driver_calls_the_evaluations_render_as_it_is(monkeypatch):
    """Entered at the driver itself, against the real ``evaluate_increment`` module with only
    its render replaced. Bug caught: the driver and the evaluation drifting apart, so every
    audit reads every page unread."""
    from squadops.capabilities.handlers.cycle import evaluate_increment

    received = {}

    async def rendered(stack, files, declared, inputs):
        received.update(stack=stack, files=files, declared=declared, inputs=inputs)
        return {"/": frozenset({"runs-view"}), "/runs/{run_id}": None}

    monkeypatch.setattr(evaluate_increment, "_rendered", rendered)
    payload = {
        "stack": "fullstack_fastapi_react",
        "files": {"backend/main.py": "x"},
        "declared": {"/": ["runs-view"], "/runs/{run_id}": ["run-detail-view"]},
        "seeds": {"/runs/{run_id}": {"path": "/runs"}},
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    out = io.StringIO()

    with redirect_stdout(out):
        exec(compile(audit._RENDER_DRIVER, "<driver>", "exec"), {})  # noqa: S102

    assert json.loads(out.getvalue()) == {"/": ["runs-view"], "/runs/{run_id}": None}
    assert received["declared"] == {"/": ("runs-view",), "/runs/{run_id}": ("run-detail-view",)}
    assert received["inputs"] == {"increment_route_seeds": payload["seeds"]}
