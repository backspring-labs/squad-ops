"""A fresh box gets exactly what the frozen recipe pins (SIP-0111 §5.7, G4 readiness, #2229).

What bug would these catch? An image rebuilt from another TensorFold commit, or a checkpoint at
another revision, serving under the recipe's name, so production runs what no gate measured; a
present image or checkpoint rebuilt or fetched again; and a download that "succeeded" into a path
the switch never mounts.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "dev" / "ops"))
_spec = importlib.util.spec_from_file_location(
    "tensorfold_install", ROOT / "scripts/dev/ops/tensorfold_install.py"
)
ti = importlib.util.module_from_spec(_spec)
sys.modules["tensorfold_install"] = ti
_spec.loader.exec_module(ti)

RECIPE = ROOT / "infra" / "tensorfold" / "recipes" / "qwen27b-nvfp4.yaml"
COMMIT = "cb2ebf0540f42604e2759b2ddef497861e928248"


class _Docker:
    """``docker`` as the box answers: the image's revision label (None: no image), and which
    snapshots a download writes. Every call is kept."""

    def __init__(self, tf_home: Path, revision: str | None, writes: bool = True):
        self.tf_home, self.revision, self.writes = tf_home, revision, writes
        self.calls: list[list[str]] = []

    def __call__(self, *args, timeout=7200, env=None):
        self.calls.append(list(args))
        if args[:2] == ("image", "inspect"):
            ok = self.revision is not None
            return subprocess.CompletedProcess(
                args, 0 if ok else 1, f"{self.revision}\n" if ok else "", ""
            )
        if args[0] == "build":
            self.revision = args[args.index("--build-arg") + 1].split("=", 1)[1]
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[0] == "run":
            repo, revision = args[-2], args[-1]
            if self.writes:
                org, name = repo.split("/")
                snap = self.tf_home / f"hf/hub/models--{org}--{name}/snapshots/{revision}"
                snap.mkdir(parents=True)
                (snap / "config.json").write_text("{}")
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError(args)


@pytest.fixture
def box(tmp_path, monkeypatch):
    monkeypatch.setattr(ti, "TF_HOME", tmp_path)
    monkeypatch.delenv("HF_TOKEN", raising=False)

    def at(revision, writes=True):
        d = _Docker(tmp_path, revision, writes)
        monkeypatch.setattr(ti, "docker", d)
        return d

    return at


def test_a_fresh_box_gets_the_recipes_image_checkpoint_and_drafter(box, tmp_path):
    docker = box(None)

    done = ti.install(RECIPE)

    assert done == {
        "recipe": "qwen27b-nvfp4",
        "caches_created": ["hf", "home", "torch_extensions", "triton"],
        "image": "built",
        "checkpoint": "downloaded",
        "drafter": "downloaded",
    }
    build = next(c for c in docker.calls if c[0] == "build")
    assert f"TENSORFOLD_COMMIT={COMMIT}" in build
    pulls = [c[-2:] for c in docker.calls if c[0] == "run"]
    assert pulls == [
        ["nvidia/Qwen3.8-27B-NVFP4", "482ca0f3832238542f8f5295dde86b5f22711d80"],
        ["z-lab/Qwen3.8-27B-DFlash2", "50307d4c4cde6860d4eee73e2547cd786fe8e8a4"],
    ]


def test_a_box_that_has_everything_is_left_alone(box, tmp_path):
    for repo, rev in (
        ("nvidia--Qwen3.8-27B-NVFP4", "482ca0f3832238542f8f5295dde86b5f22711d80"),
        ("z-lab--Qwen3.8-27B-DFlash2", "50307d4c4cde6860d4eee73e2547cd786fe8e8a4"),
    ):
        snap = tmp_path / f"hf/hub/models--{repo}/snapshots/{rev}"
        snap.mkdir(parents=True)
        (snap / "config.json").write_text("{}")
    docker = box(COMMIT)

    done = ti.install(RECIPE)

    assert (done["image"], done["checkpoint"], done["drafter"]) == ("present",) * 3
    assert [c[0] for c in docker.calls] == ["image"]


@pytest.mark.parametrize(
    ("revision", "writes", "said"),
    [
        ("0" * 40, True, "was built from 0000"),
        (None, False, "is not the recipe's snapshot"),
    ],
    ids=["an image from another commit", "a download that lands elsewhere"],
)
def test_what_the_recipe_does_not_pin_is_refused(box, revision, writes, said):
    box(revision, writes)
    with pytest.raises(ti.InstallFailed, match=said):
        ti.install(RECIPE)
