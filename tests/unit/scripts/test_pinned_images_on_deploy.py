"""A deploy that runs the sandbox builds the sandbox's pinned images when they aren't on the box.

The two images are SIP-0113's evaluator (#2580) and SIP-0102's sandbox environment, which cycle-create
preflight requires (#2582). Both are built through ``build_pinned_image.sh``, by the constant that pins
each tag.

What bugs would these catch?
- an image left to a manual script, so a deploy runs the sandbox without it: the evaluator measures
  nothing, or preflight refuses every cycle (the MacBook lane's deploy, 2026-10-20);
- a rebuild under the tag already on the box, FORCE_REBUILD included: a tag is the image's version,
  and a quality reading records only the tag (#2581's second read);
- a failed build that holds the sandbox's restart, or doesn't fail the deploy;
- a tag read by importing the package, which an older system python3 can't (Apple's 3.9);
- an image built after the deploy record, which reads the running services.

The scripts run against a stand-in ``docker`` that records its arguments, so no image is built and the
box's Docker is never reached. The deploy script is read, not run, as its order tests are.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DEV = ROOT / "scripts" / "dev"
DEPLOY = DEV / "ops" / "rebuild_and_deploy.sh"

#: (wrapper, the constant pinning its tag, its Dockerfile, its context)
IMAGES = [
    (
        "build_evaluator_image.sh",
        "EVALUATOR_IMAGE",
        "infra/evaluator/Dockerfile",
        "infra/evaluator",
    ),
    (
        "build_sandbox_env_image.sh",
        "SANDBOX_ENV_IMAGE",
        "infra/sandbox/sandbox-env.Dockerfile",
        "infra/sandbox",
    ),
]

#: Answers ``image inspect`` as present only for the one tag a test puts on the box, so an inspect
#: of any other name (the constant, an empty tag) reads as absent, as it would on a real box.
_FAKE_DOCKER = """#!/usr/bin/env bash
echo "$*" >> "$DOCKER_LOG"
if [ "$1 $2" = "image inspect" ]; then [ -n "$PRESENT_TAG" ] && [ "$3" = "$PRESENT_TAG" ]; exit $?; fi
exit 0
"""


def _run(
    tmp_path: Path,
    script: str,
    *args: str,
    on_box: str | None,
    python: str = sys.executable,
) -> tuple[subprocess.CompletedProcess, list]:
    """``on_box``: the tag the stand-in ``docker`` holds, or ``None`` for an empty box."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    docker = bin_dir / "docker"
    docker.write_text(_FAKE_DOCKER)
    docker.chmod(0o755)
    log = tmp_path / "docker.log"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "DOCKER_LOG": str(log),
        "PRESENT_TAG": on_box or "",
        "PYTHON": python,
    }
    done = subprocess.run(
        ["bash", str(DEV / script), *args], env=env, capture_output=True, text=True, timeout=60
    )
    calls = log.read_text().splitlines() if log.exists() else []
    return done, calls


def _tag(constant: str) -> str:
    from squadops.sandbox import environment

    return getattr(environment, constant)


@pytest.mark.parametrize(("script", "constant", "dockerfile", "context"), IMAGES)
@pytest.mark.parametrize(
    ("args", "on_box", "built_with"),
    [
        (("--if-absent",), True, None),
        (("--if-absent",), False, ""),
        (("--no-cache",), True, "--no-cache "),
        ((), True, ""),
    ],
    ids=["present-skipped", "absent-built", "no-cache-by-hand", "by-hand-always-built"],
)
def test_an_image_is_built_when_absent_and_rebuilt_only_by_hand(
    tmp_path, script, constant, dockerfile, context, args, on_box, built_with
):
    done, calls = _run(tmp_path, script, *args, on_box=_tag(constant) if on_box else None)

    assert done.returncode == 0, done.stderr
    builds = [c for c in calls if c.startswith("build ")]
    if built_with is None:
        assert builds == []
        assert f"{_tag(constant)} is on the box" in done.stdout
        assert f"image inspect {_tag(constant)}" in calls
    else:
        assert builds == [f"build {built_with}-t {_tag(constant)} -f {dockerfile} {context}"]


def test_a_constant_the_environment_doesnt_pin_is_refused_before_any_build(tmp_path):
    """Bug caught: a misspelt constant building an image tagged with nothing, or with the shell's
    error text as its tag."""
    done, calls = _run(
        tmp_path, "build_pinned_image.sh", "NO_SUCH_IMAGE", "Dockerfile", ".", on_box=None
    )

    assert done.returncode != 0
    assert "NO_SUCH_IMAGE is not a string literal" in done.stderr
    assert calls == []


@pytest.mark.parametrize(("script", "constant", "dockerfile", "context"), IMAGES)
def test_the_tag_is_read_by_a_python_that_cant_import_the_package(
    tmp_path, script, constant, dockerfile, context
):
    """Apple's python3 is 3.9, which can't import ``squadops.sandbox`` (it needs 3.10). Stood in by
    an interpreter run isolated from site-packages and the source path, which can't import it
    either, so the tag must be parsed from the source, never imported."""
    isolated = tmp_path / "python-without-squadops"
    isolated.write_text(f'#!/bin/sh\nexec "{sys.executable}" -I -S "$@"\n')
    isolated.chmod(0o755)
    probe = subprocess.run(
        [str(isolated), "-c", "import squadops.sandbox.environment"], capture_output=True
    )
    assert probe.returncode != 0, "the stand-in can import the package, so it proves nothing"

    done, calls = _run(tmp_path, script, "--if-absent", on_box=None, python=str(isolated))

    assert done.returncode == 0, done.stderr
    assert calls[-1] == f"build -t {_tag(constant)} -f {dockerfile} {context}"


def test_the_deploy_builds_each_image_only_if_absent_after_the_sandbox_and_before_the_record():
    text = DEPLOY.read_text()
    sandbox_build = text.index("docker compose --profile sandbox build sandbox-service")
    started = text.index("docker compose --profile sandbox up -d --wait sandbox-service")
    record = text.index('"$REPO_ROOT/scripts/dev/ops/record_deploy.sh"')

    for script, flag in (
        ("build_evaluator_image.sh", "EVALUATOR_FAILED"),
        ("build_sandbox_env_image.sh", "SANDBOX_ENV_FAILED"),
    ):
        call = text.index(f'"$REPO_ROOT/scripts/dev/{script}" --if-absent || {flag}=1')
        assert sandbox_build < started < call < record, script
        # Never rebuilt under its tag: the deploy calls the script one way only.
        assert text.count(f'{script}" ') == 1, script
        # A failed build fails the deploy, apart from the sandbox, which it doesn't hold.
        assert f'[ "${{{flag}:-0}}" = "1" ] && DEPLOY_FAILED=1' in text, script
        assert flag not in text[sandbox_build:started], script
        # The failure names its fix, in its own banner.
        banner = text.index(f'if [ "${{{flag}:-0}}" = "1" ]; then', record)
        assert f"./scripts/dev/{script}" in text[banner : text.index("\nfi\n", banner)], script


def test_no_tag_is_copied_outside_its_one_pinned_reference():
    """Bug caught: a second copy of a pinned tag, which drifts the moment the tag moves
    (``capture_delivered_app.py`` carried the environment image's from #1500 until #2582). Tests
    carry their own made-up tags and are out of scope."""
    pinned = ROOT / "src" / "squadops" / "sandbox" / "environment.py"
    copies = [
        str(path.relative_to(ROOT))
        for base in ("src", "scripts", "adapters")
        for path in sorted((ROOT / base).rglob("*"))
        if path.suffix in {".py", ".sh"}
        and path != pinned
        and any(t in path.read_text(encoding="utf-8") for t in (_tag(c) for _, c, _, _ in IMAGES))
    ]
    assert copies == []
