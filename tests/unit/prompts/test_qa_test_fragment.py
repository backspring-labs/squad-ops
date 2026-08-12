"""Content pins for the qa.test task_type fragment (#877).

Roll 14 (cyc_25b4a9b0b637) died on a qa suite that fetched a live server, because
every guidance surface the author saw was stack-1-shaped: the fragment stated the
pytest discovery rule as universal and confined its no-live-server warning to jsdom
component tests. These tests pin the two properties the fix introduced — an
execution-environment rule that holds on every stack, and a discovery rule scoped
to the workspaces it is true of. A later edit that drops either re-opens the loss.
"""

from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_capabilities]

_FRAGMENT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "squadops"
    / "prompts"
    / "fragments"
    / "shared"
    / "task_type"
    / "task_type.qa.test.md"
).read_text(encoding="utf-8")


def test_the_execution_environment_rule_exists_and_covers_both_stacks():
    """The one sentence that would have prevented roll 14: no application server is
    running during test execution, on any stack — with the in-process alternative
    named for each stack, so the prohibition comes with a replacement strategy."""
    assert "## Execution Environment (hard rule)" in _FRAGMENT
    assert "No application server is\nrunning during test execution" in _FRAGMENT.replace("**", "")
    # stack #1's in-process client and stack #2's handler-import pattern
    assert "TestClient" in _FRAGMENT
    assert "from '@/app/api/runs/route'" in _FRAGMENT


def test_the_execution_rule_precedes_the_discovery_contract():
    """Strategy before naming: the author must learn how the suite executes before
    the file-naming rules — a suite named perfectly but fetching localhost still
    fails every test."""
    assert _FRAGMENT.index("## Execution Environment") < _FRAGMENT.index("## Discovery Contract")


def test_the_pytest_discovery_rule_is_scoped_to_python_workspaces():
    """The old fragment stated 'Backend tests MUST be Python pytest files' as a
    universal hard rule — nonsense on a single-tree TypeScript workspace, and
    contradicting the stack-2 supplement in the same prompt. The rule must be
    conditioned on the workspace shape, and the TypeScript branch must exist."""
    conditioned = _FRAGMENT.index("When the workspace declares Python dependency manifests")
    pytest_rule = _FRAGMENT.index("MUST be Python pytest files")
    assert conditioned < pytest_rule

    assert "single TypeScript application" in _FRAGMENT
