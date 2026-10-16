"""``record_deploy.sh`` reads the deploy that runs, from whichever checkout it is run in (#2354).

What bug would this catch? #2354: run from a worktree, the script's bare ``docker compose`` took the
project from the worktree's directory name. ``verify_loaded.py``'s record check then built a stray
runtime image, network and database volume for a project nobody deployed, and failed with a build
log line as its reason. The script is run here against a fake ``docker`` on ``PATH`` that records
every call, so nothing is built and the compose calls themselves are what is asserted.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "ops" / "record_deploy.sh"

_FAKE_DOCKER = """#!{python}
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_DOCKER_LOG"], "a") as log:
    log.write(json.dumps({{
        "args": args,
        "cwd": os.getcwd(),
        "project": os.environ.get("COMPOSE_PROJECT_NAME"),
        "files": os.environ.get("COMPOSE_FILE"),
    }}) + "\\n")
if args[:2] == ["inspect", "squadops-runtime-api"]:
    if os.environ.get("FAKE_NO_RUNTIME"):
        sys.exit(1)
    print(os.environ["FAKE_LABELS"])
elif args[:2] == ["compose", "ps"]:
    print(json.dumps({{"Service": "runtime-api", "ID": "c1", "State": "running"}}))
elif args[:1] == ["ps"]:
    pass
elif args[:1] == ["inspect"]:
    print("sha256:img")
elif args[:2] == ["image", "inspect"]:
    print("{{}}")
elif args[:2] == ["compose", "run"]:
    sys.stdin.read()
    print("dep_fake describes what runs: 1 services")
"""


def _run(tmp_path: Path, *, no_runtime: bool = False) -> tuple[subprocess.CompletedProcess, list]:
    bin_dir, deploy_dir, elsewhere = tmp_path / "bin", tmp_path / "deploy", tmp_path / "worktree"
    for d in (bin_dir, deploy_dir, elsewhere):
        d.mkdir()
    fake = bin_dir / "docker"
    fake.write_text(_FAKE_DOCKER.format(python=sys.executable))
    fake.chmod(0o755)
    log = tmp_path / "docker.log"
    log.touch()
    files = f"{deploy_dir}/docker-compose.yml,{deploy_dir}/docker-compose.tensorfold.yml"
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "FAKE_DOCKER_LOG": str(log),
        "FAKE_LABELS": f"squad-ops|{deploy_dir}|{files}",
    }
    if no_runtime:
        env["FAKE_NO_RUNTIME"] = "1"
    result = subprocess.run(
        [str(SCRIPT), "--check"], cwd=elsewhere, env=env, capture_output=True, text=True
    )
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    return result, calls


def test_every_compose_call_is_made_in_the_running_deploys_project(tmp_path):
    result, calls = _run(tmp_path)

    assert result.returncode == 0, result.stderr
    compose = [c for c in calls if c["args"][:1] == ["compose"]]
    assert [c["args"][:2] for c in compose] == [["compose", "ps"], ["compose", "run"]]
    deploy_dir = str(tmp_path / "deploy")
    for call in compose:
        assert call["cwd"] == deploy_dir
        assert call["project"] == "squad-ops"
        assert call["files"] == (
            f"{deploy_dir}/docker-compose.yml:{deploy_dir}/docker-compose.tensorfold.yml"
        )


def test_with_no_runtime_running_it_refuses_and_composes_nothing(tmp_path):
    """Bug caught: a missing runtime falling through to a bare ``docker compose run``, which is
    what builds a stray project."""
    result, calls = _run(tmp_path, no_runtime=True)

    assert result.returncode == 1
    assert "no deploy to read" in result.stderr
    assert not [c for c in calls if c["args"][:1] == ["compose"]]
