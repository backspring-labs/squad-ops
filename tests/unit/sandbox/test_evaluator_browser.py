"""The evaluator's browser vocabulary (``infra/evaluator/browser.mjs``; SIP-0113 §10p rulings 1 to
5), run by node's own test runner against a fake page: ``infra/evaluator/browser.test.mjs``.

What bugs would it catch? A name matched by substring, so "Join" finds "Joined"; a fill typed into
the leave form's name box; a check read before its step, or after a failed one; a broken page or
a control not found read as anything else; what a check saw quoting the page, whose text is the
scenario's held-out values. CI's regression job provisions node 20, so it never skips there.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


def test_the_browser_vocabulary_holds_against_a_fake_page():
    node = shutil.which("node")
    if node is None:
        if os.environ.get("CI"):
            pytest.fail("CI provisions node 20 for this job, and it's missing")
        pytest.skip("node isn't installed here; CI's regression job runs it")
    done = subprocess.run(
        [node, "--test", "infra/evaluator/browser.test.mjs"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]
