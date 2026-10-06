"""The reporting-only lint reading of a delivered app (#1937).

What bugs would these catch?
- Findings not counted by rule and by file, or a generated tree (``node_modules``, ``.next``)
  counted as the app's.
- A tool that is missing, fails or hangs read as a clean app: the reading must name what it did
  not cover, never report a silent zero.
- ESLint's report miscounted (a parse error dropped, a file's findings merged with another's).
- An unbounded reading: a large app naming every file.
"""

from __future__ import annotations

import json
import shutil

import pytest

from squadops.capabilities import delivered_lint
from squadops.capabilities.delivered_lint import MAX_FILES_NAMED, lint_delivered, reading
from squadops.core.bounded_run import BoundedRun

_RUFF = shutil.which("ruff")


@pytest.mark.skipif(_RUFF is None, reason="ruff is a dev and agent-image dependency")
def test_python_findings_are_counted_by_rule_and_file_and_generated_trees_are_skipped():
    tree = {
        "backend/main.py": "import os\n\n\ndef f(x):\n    return x\n",
        "node_modules/pkg/setup.py": "import os\n",
        ".next/cache/x.py": "import sys\n",
    }

    found = lint_delivered(tree)

    assert found["files_linted"] == {"python": 1, "js": 0}
    assert found["by_rule"]["ruff:F401"] == 1
    assert found["by_file"] == {"backend/main.py": found["total"]}
    assert found["unavailable"] == {}
    assert found["tools"]["ruff"].startswith("ruff ")


@pytest.mark.parametrize(
    ("which", "run", "why"),
    [
        (None, None, "ruff is not installed"),
        ("/usr/bin/ruff", BoundedRun(None, b"", b""), "ruff ran past 120s"),
        ("/usr/bin/ruff", BoundedRun(2, b"", b"error: bad"), "ruff exited 2: error: bad"),
    ],
    ids=["missing", "past-its-limit", "failed"],
)
def test_a_tool_that_cannot_run_is_named_never_read_as_a_clean_app(monkeypatch, which, run, why):
    monkeypatch.setattr(delivered_lint.shutil, "which", lambda name: which)
    monkeypatch.setattr(
        delivered_lint, "run_bounded_sync", lambda argv, **kw: run or BoundedRun(0, b"", b"")
    )

    found = lint_delivered({"app/main.py": "x = 1\n"})

    assert found["unavailable"] == {"ruff": why}
    assert (found["total"], found["tools"]) == (0, {})


def test_eslints_report_is_counted_per_file_with_parse_errors_kept(monkeypatch):
    """The runner's output as it printed it on 2.1 rebuild 2's Next.js app, cut to two files."""
    report = {
        "version": "10.12.0",
        "results": [
            {
                "file": "app/runs/[run_id]/page.tsx",
                "rules": [
                    "@typescript-eslint/no-explicit-any",
                    "@typescript-eslint/no-unused-vars",
                ],
            },
            {"file": "lib/store.ts", "rules": ["parse-error"]},
            {"file": "app/page.tsx", "rules": []},
        ],
    }
    monkeypatch.setattr(delivered_lint.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        delivered_lint,
        "run_bounded_sync",
        lambda argv, **kw: BoundedRun(0, json.dumps(report).encode(), b""),
    )

    found = lint_delivered(
        {"app/page.tsx": "x", "app/runs/[run_id]/page.tsx": "x", "lib/store.ts": "x"}
    )

    assert found["tools"] == {"eslint": "10.12.0"}
    assert found["by_file"] == {"app/runs/[run_id]/page.tsx": 2, "lib/store.ts": 1}
    assert found["by_rule"]["eslint:parse-error"] == 1
    assert found["total"] == 3


def test_a_large_app_names_its_most_found_files_and_counts_the_rest():
    findings = [("ruff:E501", f"f{n}.py") for n in range(MAX_FILES_NAMED + 5)]
    findings += [("ruff:E501", "f0.py")] * 3

    found = reading(findings, tools={"ruff": "ruff 0.16.6"}, linted={"python": 55}, unavailable={})

    assert len(found["by_file"]) == MAX_FILES_NAMED
    assert found["files_not_named"] == 5
    assert found["by_file"]["f0.py"] == 4
    assert found["total"] == len(findings)
