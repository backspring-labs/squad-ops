"""What CI treats as a prose-only diff (scripts/dev/classify_ci_diff.sh).

A prose-only diff skips integration, the install and import lanes, the dependency audit and
the scaffold skeleton gate, and runs the prose lane instead of the whole unit suite. So a
path wrongly called prose ships untested.

Bug caught: the filter this replaced counted every `.md` file as documentation, so a change
to a prompt asset under src/squadops/prompts — what the model is told — a stored report
under tests/fixtures, or a PRD under examples/ rode a docs-only diff. The other direction
matters less but still costs: a plan or SIP edit classified as code runs every lane for
nothing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "classify_ci_diff.sh"


def _classify(*paths: str) -> str:
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input="\n".join(paths) + ("\n" if paths else ""),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.mark.parametrize(
    "paths",
    [
        ("docs/plans/1-8-0-plan.md", "docs/ROADMAP.md"),
        ("sips/accepted/SIP-0107-Scoped-Code-Revision.md", "sips/registry.yaml"),
        ("docs/plans/verification-sets/1-8-diagnostic-contentless-builder.yaml",),
        ("site/content/releases/v1.7.5/index.md",),
        ("CLAUDE.md", "README.md", "CHANGELOG.md", "CONTRIBUTING.md"),
        ("docs/Screenshot 2026-02-21 at 7.34.43 PM.png",),
    ],
)
def test_prose_only_diffs_skip_the_code_lanes(paths):
    assert _classify(*paths) == "code=false"


@pytest.mark.parametrize(
    "paths",
    [
        # The misclassifications the old `.*\.md$` rule made: runtime and test inputs.
        ("src/squadops/prompts/fragments/shared/task_type/qa.test.md",),
        ("src/squadops/prompts/request_templates/request.cycle_task_base.md",),
        ("tests/fixtures/roll_replays/1-6-5-react-roll-3-round-0-test_report.md",),
        ("examples/03_group_run/prd.md",),
        (".github/PULL_REQUEST_TEMPLATE.md",),
        # One code path among prose makes the whole diff code.
        ("docs/plans/1-8-0-plan.md", "src/squadops/capabilities/handlers/cycle/qa_test.py"),
        ("site/content/releases/v1.7.5/package.yaml",),
        (".github/workflows/ci.yml",),
    ],
)
def test_any_path_off_the_prose_list_runs_every_lane(paths):
    assert _classify(*paths) == "code=true"


def test_an_empty_diff_runs_every_lane():
    """Nothing proves the diff prose-only, so nothing is skipped."""
    assert _classify() == "code=true"
