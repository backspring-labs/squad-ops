"""Bootstrap installs and selects the engine its profile declares (SIP-0111, G4; #2229).

What bug would this catch? A profile that declares TensorFold bootstrapping a box on Ollama alone
(nothing installed, no switch), or one on Ollama installing TensorFold it never runs. Run, not
read: the library's functions, with its two commands answered by a stub that records them.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

LIB = Path(__file__).resolve().parents[3] / "scripts" / "bootstrap" / "lib"
RECIPE = "infra/tensorfold/recipes/qwen27b-nvfp4.yaml"


@pytest.mark.parametrize(
    ("block", "ran"),
    [
        (None, []),
        ({"engine": "ollama"}, []),
        (
            {"engine": "tensorfold", "recipe": RECIPE},
            [
                f"scripts/dev/ops/tensorfold_install.py {RECIPE}",
                f"scripts/dev/ops/engine_switch.py to-tensorfold {RECIPE}",
            ],
        ),
    ],
    ids=["no engine declared", "ollama", "tensorfold"],
)
def test_bootstrap_installs_and_switches_to_the_declared_engine(tmp_path, block, ran):
    venv = tmp_path / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").symlink_to(sys.executable)
    profile = {"name": "p"} | ({"inference_engine": block} if block else {})
    (tmp_path / "profile.yaml").write_text(yaml.safe_dump(profile))
    script = (
        f"source {LIB}/tensorfold_setup.sh\n"
        "info() { :; }\n"
        'run_or_dry() { shift; echo "RAN $*"; }\n'
        "install_inference_engine profile.yaml\n"
        "select_inference_engine profile.yaml\n"
    )

    done = subprocess.run(["bash", "-c", script], cwd=tmp_path, capture_output=True, text=True)

    assert done.returncode == 0, done.stderr
    assert [line[4:] for line in done.stdout.splitlines() if line.startswith("RAN ")] == ran
