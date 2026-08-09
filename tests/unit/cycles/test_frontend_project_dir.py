"""Which directory holds the buildable project is a stack fact (#822).

`FrontendCompilesCheck` resolved `workspace_root / "frontend"` unconditionally. That is a
property of `fullstack_fastapi_react`, not of frontends: a Next.js app builds at the project
root. For a second stack, every view's bundler check would have reported `no_frontend_tree`.

SIP-0096 declines to credit a skip, so this is visible rather than a false green — but the
consequence is still severe, because `frontend_compiles` is the *only* bundler-level coverage a
view has, and stack #2 has no AST tier at all (the nine `ast.parse` checks are Python-only). The
whole static surface of stack #2's views would have been empty, reported as not-executed.

Bug classes guarded:

- **a second stack's views skipping the only check that can see their defects** — fay-4 and
  fay-8 each shipped a view with a rollup bind-time error invisible to every static check and to
  `node --check`, which is why #648 built this;
- the fix moving the reference contract. Stack #1's criteria pack emits no `project_dir`, so its
  contract must be byte-identical — this is the release's banked evidence;
- a project directory escaping the workspace, which a bare `workspace_root / value` join would
  have permitted the moment the value stopped being a literal;
- the parameter being added speculatively. S5's admission rule wants a field demonstrated on two
  stacks; `frontend/` vs `.` is the demonstration, and the build *command* is deliberately not
  parameterized because both stacks run `npm run build`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from squadops.cycles.acceptance_check_spec import CHECK_SPECS
from squadops.cycles.acceptance_checks import _CHECK_IMPLS

pytestmark = [pytest.mark.domain_contracts]


def _tree(root: Path, project_dir: str, view: str) -> Path:
    """A workspace whose buildable project sits at ``project_dir``."""
    proj = root / project_dir if project_dir != "." else root
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "package.json").write_text(json.dumps({"name": "app"}), encoding="utf-8")
    view_path = root / view
    view_path.parent.mkdir(parents=True, exist_ok=True)
    view_path.write_text("export default function V() { return null }\n", encoding="utf-8")
    return root


async def _evaluate(root: Path, params: dict) -> object:
    check = _CHECK_IMPLS["frontend_compiles"]()
    return await check.evaluate(params, root)


async def test_a_root_built_project_is_found_when_declared(tmp_path: Path, monkeypatch):
    """The Next.js shape. Without `project_dir` this reported `no_frontend_tree` and the view
    went unchecked; `npm` is stubbed absent so the assertion is about *discovery*, not about
    standing a real bundler up in a unit test."""
    import shutil

    monkeypatch.setattr(shutil, "which", lambda _: None)
    _tree(tmp_path, ".", "app/runs/page.tsx")

    outcome = await _evaluate(tmp_path, {"file": "app/runs/page.tsx", "project_dir": "."})

    assert outcome.status == "skipped"
    assert outcome.reason == "missing_tooling", (
        "the project was found; the only thing missing is npm"
    )


async def test_the_default_is_still_the_first_stacks_layout(tmp_path: Path, monkeypatch):
    """Stack #1 emits no `project_dir`. If the default moved, every existing cycle's view
    checks would start reporting `no_frontend_tree`."""
    import shutil

    monkeypatch.setattr(shutil, "which", lambda _: None)
    _tree(tmp_path, "frontend", "frontend/src/views/RunsListView.jsx")

    outcome = await _evaluate(tmp_path, {"file": "frontend/src/views/RunsListView.jsx"})

    assert outcome.reason == "missing_tooling"


async def test_a_root_built_project_without_the_param_is_not_found(tmp_path: Path):
    """The defect, reproduced. This is what stack #2 would have gotten for every view."""
    _tree(tmp_path, ".", "app/runs/page.tsx")

    outcome = await _evaluate(tmp_path, {"file": "app/runs/page.tsx"})

    assert outcome.status == "skipped"
    assert outcome.reason == "no_frontend_tree"


@pytest.mark.parametrize("escape", ["../outside", "/etc", "frontend/../../.."])
async def test_a_project_dir_cannot_escape_the_workspace(tmp_path: Path, escape: str):
    """`project_dir` is now attacker-adjacent in a way a literal never was: it arrives from a
    contract. A bare join would resolve outside the workspace and run `npm install` there."""
    _tree(tmp_path, "frontend", "frontend/src/views/V.jsx")

    outcome = await _evaluate(tmp_path, {"file": "frontend/src/views/V.jsx", "project_dir": escape})

    assert outcome.status == "error"


def test_the_parameter_is_declared_so_authoring_time_validation_covers_it():
    """`path_params` drives the pre-eval traversal rejection in `implementation_plan`, and
    `param_types` drives type checking. An undeclared param would be accepted by the parser and
    then be unvalidated at both layers."""
    spec = CHECK_SPECS["frontend_compiles"]

    assert "project_dir" in spec.optional_params
    assert "project_dir" in spec.path_params
    assert spec.param_types["project_dir"] is str
    assert "project_dir" not in spec.required_params, (
        "requiring it would move stack #1's contract, which the release's evidence is bound to"
    )


def test_the_build_command_is_deliberately_not_parameterized():
    """S5's admission rule: a field must be demonstrated on two stacks. `frontend/` vs `.` is
    demonstrated; both stacks run `npm run build`, so a `build_argv` parameter would be a
    one-stack guess wearing a general name — the exact decay the rule exists to prevent."""
    spec = CHECK_SPECS["frontend_compiles"]

    assert not {"build_argv", "install_argv", "package_manager"} & (
        spec.optional_params | spec.required_params
    )
