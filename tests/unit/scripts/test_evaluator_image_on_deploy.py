"""A deploy that runs the sandbox builds SIP-0113's evaluator image when it isn't on the box (#2580).

What bugs would these catch?
- the evaluator image left to a manual script, so a deploy runs the sandbox with no evaluator and
  loaded check ``2416`` is red on a fresh box (the MacBook lane's deploy, 2026-10-20);
- a rebuild on every deploy of an image that's already there, since it's a long Chromium build;
- the evaluator built after the sandbox starts or after the deploy record, or a failed build
  reported as a deployed sandbox.

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


def _build(tmp_path: Path, *args: str, on_box: bool) -> tuple[subprocess.CompletedProcess, list]:
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
        "PYTHON": sys.executable,
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


def test_the_deploys_sandbox_step_builds_the_evaluator_before_it_starts_or_records():
    text = DEPLOY.read_text()
    sandbox_build = text.index("docker compose --profile sandbox build sandbox-service")
    evaluator = text.index('"$REPO_ROOT/scripts/dev/build_evaluator_image.sh" --if-absent')
    started = text.index("docker compose --profile sandbox up -d --wait sandbox-service")
    record = text.index('"$REPO_ROOT/scripts/dev/ops/record_deploy.sh"')

    assert sandbox_build < evaluator < started < record
    # A failed evaluator build fails the sandbox step, as a failed sandbox build does.
    step = text[evaluator - 400 : started]
    assert step.count("|| BUILD_OK=false") == 2
    assert '"$REPO_ROOT/scripts/dev/build_evaluator_image.sh" --no-cache' in step
