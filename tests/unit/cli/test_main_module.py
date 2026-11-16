"""``python -m squadops.cli.main`` is the ``squadops`` command (#3122).

bootstrap.sh ends by running doctor this way. Without a ``__main__`` entry the module imported
its app and exited 0 having printed nothing, so every bootstrap's closing doctor ran no check.
"""

from __future__ import annotations

import subprocess
import sys


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "squadops.cli.main", *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_the_module_runs_the_command():
    """Bug caught: the module run that prints nothing and exits 0, read as a passing doctor."""
    result = _run("doctor", "--help")

    assert result.returncode == 0
    assert "Validate that the current machine satisfies a bootstrap profile" in result.stdout


def test_a_failure_through_the_module_exits_nonzero():
    """Bug caught: a doctor that can't run (an unknown profile) exiting 0 through the module."""
    result = _run("doctor", "no-such-profile")

    assert result.returncode == 1
    assert "no-such-profile" in (result.stdout + result.stderr)
