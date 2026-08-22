"""#972: the regression script's tool preflight.

The defect class: a fail-stop gate whose failure is a bare "command not found"
mid-scroll, combined with a caller piping output (which masks the exit code),
reads as a green run in which no gate executed — observed at the v1.6.0 cut.
The preflight makes the failure one loud line, first, with the cause named.
"""

import subprocess
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "run_regression_tests.sh"


def test_missing_tool_fails_loudly_with_the_venv_hint():
    """Bug caught: no venv → bare 'ruff: command not found' buried in output.
    The preflight must exit 127 before ANY gate output, naming the fix."""
    result = subprocess.run(
        ["bash", str(_SCRIPT)],
        capture_output=True,
        text=True,
        env={"HOME": "/tmp", "PATH": "/usr/bin:/bin"},  # no venv on PATH
        timeout=30,
    )
    assert result.returncode == 127
    assert "activate the virtualenv" in result.stderr
    assert "source .venv/bin/activate" in result.stderr
    # Preflight fires BEFORE the gates — no gate banner may have printed.
    assert "Running ruff lint" not in result.stdout


def test_completion_line_is_declared_only_after_the_last_gate():
    """The positive-evidence line must be the script's final act — a completion
    line printed before pytest would defeat its purpose (scrollback would show
    it even when the suite never ran)."""
    text = _SCRIPT.read_text(encoding="utf-8")
    assert "ALL GATES PASSED" in text
    assert text.index("ALL GATES PASSED") > text.index("pytest -n auto")
