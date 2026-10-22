"""``scripts/dev/audit_dependencies.sh``'s reading of the evaluator's npm audit (#1205, #2455, #2644).

Entered at the script, as CI runs it, with fake ``pip-audit`` and ``npm`` first on the PATH, so
nothing reaches a registry. What bugs would these catch?
- an audit whose endpoint didn't answer read as one that found nothing, so every accepted advisory
  looks fixed and the script advises deleting their reasons (main's run 39711921204, a 503);
- a report that wasn't read at all passing the job;
- a new advisory, or an accepted one, read the wrong way round.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "dev" / "audit_dependencies.sh"
ACCEPTED = sorted(
    line.split("#")[0].strip()
    for line in (REPO / "infra" / "evaluator" / "audit-ignore.txt").read_text().splitlines()
    if line.split("#")[0].strip()
)


def _report(*advisories: str) -> str:
    return json.dumps(
        {
            "vulnerabilities": {
                f"pkg{i}": {
                    "via": [
                        {
                            "url": f"https://github.com/advisories/{a}",
                            "name": f"pkg{i}",
                            "severity": "moderate",
                            "title": "an invented advisory",
                        }
                    ]
                }
                for i, a in enumerate(advisories)
            }
        }
    )


def _run(tmp_path: Path, npm_output: str, npm_exit: int) -> subprocess.CompletedProcess:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (tmp_path / "npm-output.json").write_text(npm_output)
    fakes = {
        "pip-audit": "#!/bin/sh\necho 'No known vulnerabilities found'\n",
        "npm": f"#!/bin/sh\ncat '{tmp_path / 'npm-output.json'}'\nexit {npm_exit}\n",
    }
    for name, body in fakes.items():
        path = bin_dir / name
        path.write_text(body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    return subprocess.run(
        ["bash", str(SCRIPT)], cwd=REPO, env=env, capture_output=True, text=True, timeout=60
    )


@pytest.mark.parametrize(
    "npm_output",
    [
        json.dumps({"message": "503 Service Unavailable", "error": {"summary": "", "detail": ""}}),
        "npm error audit endpoint returned an error",
    ],
    ids=["the-endpoint-answered-an-error", "no-json-at-all"],
)
def test_an_audit_that_read_nothing_says_not_run_and_never_calls_an_accepted_id_stale(
    tmp_path, npm_output
):
    done = _run(tmp_path, npm_output, npm_exit=1)

    assert done.returncode == 1
    assert "NOT RUN" in done.stderr
    assert "delete from audit-ignore" not in done.stdout + done.stderr


@pytest.mark.parametrize(
    ("advisories", "returncode", "line"),
    [
        (ACCEPTED, 0, "ACCEPTED"),
        ((*ACCEPTED, "GHSA-aaaa-bbbb-cccc"), 1, "NEW      GHSA-aaaa-bbbb-cccc"),
        (ACCEPTED[1:], 1, "no longer reported"),
    ],
    ids=["only-accepted", "a-new-advisory", "an-accepted-one-gone"],
)
def test_a_report_that_was_read_is_judged_against_the_accepted_ids(
    tmp_path, advisories, returncode, line
):
    assert ACCEPTED, "the evaluator's ignore list is the fixture: it lists accepted advisories"
    done = _run(tmp_path, _report(*advisories), npm_exit=0 if advisories == ACCEPTED else 1)

    assert (done.returncode, line in done.stdout) == (returncode, True)
    assert "NOT RUN" not in done.stderr
