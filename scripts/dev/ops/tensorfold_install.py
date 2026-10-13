#!/usr/bin/env python3
"""Install what a frozen TensorFold recipe needs on this box (SIP-0111 §5.7, G4 readiness, #2229).

    tensorfold_install.py infra/tensorfold/recipes/qwen27b-nvfp4.yaml [--dry-run]

Idempotent: each part already present is checked and left alone.
1. **The caches** under ``~/tensorfold`` (``TF_HOME``): the Hugging Face store, TensorFold's home, and
   the compiled-kernel caches the switch mounts (the first start compiles; later ones reuse them).
2. **The image** the recipe names, built from ``infra/tensorfold/Dockerfile`` at the recipe's
   ``tensorfold_commit``. Its revision label must be that commit. A fresh build gets a new image id:
   what runs is pinned by the base image's digest and the TensorFold commit, and the recipe's
   ``image_id`` stays the record of the image the gates measured.
3. **The checkpoint and the drafter** at the recipe's revisions, fetched by the image itself
   (``huggingface_hub``), so the host needs nothing but Docker. ``HF_TOKEN`` is passed through
   when set, for a gated repository.

It never starts TensorFold: ``engine_switch.py to-tensorfold`` does, with the box held.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_switch import MAIN, TF_HOME, load_recipe  # noqa: E402

DOCKERFILE_DIR = MAIN / "infra" / "tensorfold"
#: Inside the container the switch runs, TF_HOME is mounted here (``serve_command``).
CACHE = "/cache"
CACHE_DIRS = ("hf", "home", "torch_extensions", "triton")


class InstallFailed(RuntimeError):
    """A part could not be installed or verified."""


def docker(
    *args: str, timeout: float = 7200, env: dict | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=timeout, env=env
    )


def host_path(container_path: str) -> Path:
    """Where a recipe's ``/cache/...`` path is on the host."""
    if not container_path.startswith(f"{CACHE}/"):
        raise InstallFailed(f"{container_path} is not under the recipe's cache {CACHE}")
    return TF_HOME / container_path[len(CACHE) + 1 :]


def ensure_caches(dry_run: bool) -> list[str]:
    missing = [d for d in CACHE_DIRS if not (TF_HOME / d).is_dir()]
    if not dry_run:
        for d in missing:
            (TF_HOME / d).mkdir(parents=True, exist_ok=True)
    return missing


def image_revision(image: str) -> str | None:
    """The TensorFold commit an image was built from, or None when there is no such image."""
    done = docker(
        "image",
        "inspect",
        "-f",
        '{{index .Config.Labels "org.opencontainers.image.revision"}}',
        image,
        timeout=60,
    )
    return done.stdout.strip() if done.returncode == 0 else None


def ensure_image(recipe: dict[str, Any], dry_run: bool) -> str:
    image, commit = recipe["image"], recipe["tensorfold_commit"]
    found = image_revision(image)
    if found == commit:
        return "present"
    if found is not None:
        raise InstallFailed(f"{image} exists but was built from {found}, not the recipe's {commit}")
    if dry_run:
        return "would build"
    built = docker(
        "build", "-t", image, "--build-arg", f"TENSORFOLD_COMMIT={commit}", str(DOCKERFILE_DIR)
    )
    if built.returncode != 0:
        raise InstallFailed(f"docker build {image}: {built.stderr.strip()[-400:]}")
    if image_revision(image) != commit:
        raise InstallFailed(f"{image} was built, but its revision label is not {commit}")
    return "built"


def ensure_snapshot(recipe: dict[str, Any], part: str, dry_run: bool) -> str:
    spec = recipe[part]
    target = host_path(spec["container_path"])
    if target.is_dir() and any(target.iterdir()):
        return "present"
    if dry_run:
        return "would download"
    env = {**os.environ}
    pull = [
        "run",
        "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-e",
        f"HF_HOME={CACHE}/hf",
        *(["-e", "HF_TOKEN"] if env.get("HF_TOKEN") else []),
        "-v",
        f"{TF_HOME}:{CACHE}",
        "--entrypoint",
        "python",
        recipe["image"],
        "-c",
        "import sys; from huggingface_hub import snapshot_download; "
        "print(snapshot_download(sys.argv[1], revision=sys.argv[2]))",
        spec["repo"],
        spec["revision"],
    ]
    done = docker(*pull, env=env)
    if done.returncode != 0:
        raise InstallFailed(
            f"download {spec['repo']}@{spec['revision']}: {done.stderr.strip()[-400:]}"
        )
    if not (target.is_dir() and any(target.iterdir())):
        raise InstallFailed(f"{spec['repo']} downloaded, but {target} is not the recipe's snapshot")
    return "downloaded"


def install(recipe_path: Path, dry_run: bool = False) -> dict[str, Any]:
    recipe = load_recipe(recipe_path)
    if "tensorfold_commit" not in recipe:
        raise InstallFailed(f"recipe {recipe_path.name} lacks tensorfold_commit")
    done = {
        "recipe": recipe["name"],
        "caches_created": ensure_caches(dry_run),
        "image": ensure_image(recipe, dry_run),
        "checkpoint": ensure_snapshot(recipe, "checkpoint", dry_run),
    }
    # A recipe without speculative decoding names no drafter.
    if "drafter" in recipe:
        done["drafter"] = ensure_snapshot(recipe, "drafter", dry_run)
    return done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("recipe", type=Path)
    parser.add_argument(
        "--dry-run", action="store_true", help="report what is missing; change nothing"
    )
    args = parser.parse_args(argv)
    try:
        print(json.dumps(install(args.recipe, args.dry_run)))
        return 0
    except InstallFailed as exc:
        print(json.dumps({"failed": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
