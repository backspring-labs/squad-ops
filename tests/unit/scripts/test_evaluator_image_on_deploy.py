"""A deploy that runs the sandbox builds SIP-0113's evaluator image when it isn't on the box (#2580).

What bugs would these catch?
- the evaluator image left to a manual script, so a deploy runs the sandbox with no evaluator and
  loaded check ``2416`` is red on a fresh box (the MacBook lane's deploy, 2026-10-20);
- a rebuild under the tag already on the box, FORCE_REBUILD included: its base and Chromium aren't
  pinned, so the same tag would name a different evaluator, and every quality reading records only
  the tag (#2581's second read);
- a failed evaluator build that holds the sandbox's restart, though the sandbox runs without it, or
  that doesn't fail the deploy;
- the tag read by importing the package, which an older system python3 can't (Apple's 3.9);
- the evaluator built after the deploy record, which reads the running services.

The build script runs against a stand-in ``docker`` that records its arguments, so no image is
built and the box's Docker is never reached. The deploy script is read, not run, as its order tests
are.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BUILD = ROOT / "scripts" / "dev" / "build_evaluator_image.sh"
DEPLOY = ROOT / "scripts" / "dev" / "ops" / "rebuild_and_deploy.sh"

_FAKE_DOCKER = """#!/usr/bin/env bash
echo "$*" >> "$DOCKER_LOG"
if [ "$1 $2" = "image inspect" ]; then exit "${INSPECT_RC:-1}"; fi
exit 0
"""


def _build(
    tmp_path: Path, *args: str, on_box: bool, python: str = sys.executable
) -> tuple[subprocess.CompletedProcess, list]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(_FAKE_DOCKER)
    docker.chmod(0o755)
    log = tmp_path / "docker.log"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "DOCKER_LOG": str(log),
        "INSPECT_RC": "0" if on_box else "1",
        "PYTHON": python,
    }
    done = subprocess.run(
        ["bash", str(BUILD), *args], env=env, capture_output=True, text=True, timeout=60
    )
    calls = log.read_text().splitlines() if log.exists() else []
    return done, calls


def _tag() -> str:
    from squadops.sandbox.environment import EVALUATOR_IMAGE

    return EVALUATOR_IMAGE


@pytest.mark.parametrize(
    ("args", "on_box", "built_with"),
    [
        (("--if-absent",), True, None),
        (("--if-absent",), False, ""),
        (("--no-cache",), True, "--no-cache "),
        ((), True, ""),
    ],
    ids=["present-skipped", "absent-built", "no-cache-rebuilt", "by-hand-always-built"],
)
def test_the_image_is_built_when_absent_and_rebuilt_only_when_asked(
    tmp_path, args, on_box, built_with
):
    done, calls = _build(tmp_path, *args, on_box=on_box)

    assert done.returncode == 0, done.stderr
    builds = [c for c in calls if c.startswith("build ")]
    if built_with is None:
        assert builds == []
        assert f"{_tag()} is on the box" in done.stdout
    else:
        assert builds == [f"build {built_with}-t {_tag()} infra/evaluator"]


def test_the_deploy_builds_the_evaluator_only_if_absent_after_the_sandbox_and_before_the_record():
    text = DEPLOY.read_text()
    sandbox_build = text.index("docker compose --profile sandbox build sandbox-service")
    started = text.index("docker compose --profile sandbox up -d --wait sandbox-service")
    evaluator = text.index(
        '"$REPO_ROOT/scripts/dev/build_evaluator_image.sh" --if-absent || EVALUATOR_FAILED=1'
    )
    record = text.index('"$REPO_ROOT/scripts/dev/ops/record_deploy.sh"')

    assert sandbox_build < started < evaluator < record
    # Never rebuilt under the tag on the box: the deploy calls the script one way only.
    assert text.count('build_evaluator_image.sh" ') == 1
    # A failed build fails the deploy, apart from the sandbox, which it doesn't hold.
    assert '[ "${EVALUATOR_FAILED:-0}" = "1" ] && DEPLOY_FAILED=1' in text
    assert "EVALUATOR_FAILED" not in text[sandbox_build:started]


def test_the_tag_is_read_by_a_python_that_cant_import_the_package(tmp_path):
    """Apple's python3 is 3.9, which can't import ``squadops.sandbox`` (it needs 3.10). Stood in by
    an interpreter run isolated from site-packages and the source path, which can't import it
    either, so the script must parse the tag from the source, never import it."""
    isolated = tmp_path / "python-without-squadops"
    isolated.write_text(f'#!/bin/sh\nexec "{sys.executable}" -I -S "$@"\n')
    isolated.chmod(0o755)
    probe = subprocess.run(
        [str(isolated), "-c", "import squadops.sandbox.environment"], capture_output=True
    )
    assert probe.returncode != 0, "the stand-in can import the package, so it proves nothing"

    done, calls = _build(tmp_path, "--if-absent", on_box=False, python=str(isolated))

    assert done.returncode == 0, done.stderr
    assert calls[-1] == f"build -t {_tag()} infra/evaluator"
