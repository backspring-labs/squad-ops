"""Bootstrap leaves the deploy's engine where the switch put it (SIP-0111 §5.6, #2229).

What bug would this catch? A re-bootstrap after the cutover rewriting ``COMPOSE_FILE`` to the Ollama
overlay alone: the next ``docker compose`` recreates every model client on an Ollama that is stopped,
while TensorFold serves. Run, not read: the library's own function against a scratch ``.env``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[3] / "scripts" / "bootstrap" / "lib"
OLLAMA = "docker-compose.yml:docker-compose.ollama.yml"


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (
            f"COMPOSE_FILE={OLLAMA}:docker-compose.tensorfold.yml",
            f"{OLLAMA}:docker-compose.tensorfold.yml",
        ),
        (f"COMPOSE_FILE={OLLAMA}", OLLAMA),
        ("COMPOSE_FILE=docker-compose.yml", OLLAMA),
        ("", OLLAMA),
    ],
    ids=["on TensorFold", "on Ollama", "before the Ollama overlay", "no COMPOSE_FILE"],
)
def test_configuring_ollama_keeps_the_engine_the_deploy_runs(tmp_path, before, after):
    (tmp_path / ".env").write_text(f"SOMETHING=else\n{before}\n")
    script = (
        f"source {LIB}/common.sh; source {LIB}/docker_setup.sh; source {LIB}/ollama_setup.sh\n"
        "systemctl() { return 1; }\n"
        "configure_ollama_container\n"
    )
    done = subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )

    assert done.returncode == 0, done.stderr
    lines = (tmp_path / ".env").read_text().splitlines()
    assert [line for line in lines if line.startswith("COMPOSE_FILE=")] == [f"COMPOSE_FILE={after}"]
    assert "SOMETHING=else" in lines
