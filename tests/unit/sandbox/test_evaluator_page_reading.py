"""The evaluator's finer quality reading (``infra/evaluator/page_reading.mjs``; SIP-0113 §10y,
#2637), run by node's own test runner against invented axe and Lighthouse results:
``infra/evaluator/page_reading.test.mjs``.

What bugs would it catch? A node counted under its violation's impact, not its own; an audit
weighted 0 listed as failing; the environment's plain-HTTP audits listed under best practices or
left in ``best_practices_app``; an errored audit read as resolved, or its category's list read as
empty; ``best_practices_app`` reading 0 where no weight remains; and a recomputation that isn't
Lighthouse's own score recorded as a reading. CI's regression job provisions node 20, so it never
skips there.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


def test_the_finer_reading_holds_against_invented_results():
    node = shutil.which("node")
    if node is None:
        if os.environ.get("CI"):
            pytest.fail("CI provisions node 20 for this job, and it's missing")
        pytest.skip("node isn't installed here; CI's regression job runs it")
    done = subprocess.run(
        [node, "--test", "infra/evaluator/page_reading.test.mjs"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]
