"""The shared fixture's product as a Git repository (SIP-0112 §8.2.3, #2407).

``product/`` holds the product as of its second commit, the Project's current development
baseline. ``first_commit/`` holds the files that differed at the first commit, and
``ABSENT_AT_FIRST_COMMIT`` names the files the second commit added. ``build_repository``
commits both, with fixed identities and dates and with every machine's Git configuration
kept out, so both commits hash the same on every machine. The recorded outputs under
``recorded/`` name those hashes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

FIXTURE = Path(__file__).resolve().parent
PRODUCT = FIXTURE / "product"
FIRST_COMMIT = FIXTURE / "first_commit"
RECORDED = FIXTURE / "recorded"

ABSENT_AT_FIRST_COMMIT = frozenset({"tally/report.py", "checks/check_report.py"})

# Each lane's recorded outputs (D12): the MacBook lane's, then the Spark lane's. The derived profile
# is contract 8, added for 2.5 (H.6).
OUTPUTS = (
    "project_source_context",
    "development_configuration",
    "workspace_commit_mapping",
    "inherited_baseline",
    "derived_profile",
    "outcome_evaluation_ref",
)
FORMS = ("valid", "missing_field", "unknown_major", "stale_commit")
#: Contract 5's reference has a fifth form: a calibration record's reading (SIP-0113 §10l, H.14).
OUTCOME_REF_FORMS = (*FORMS, "calibration_record")

_COMMITS = (
    {
        "message": "Tally: a ledger of named counters, served over HTTP",
        "name": "Tally Maintainer",
        "email": "maintainer@tally.example.invalid",
        "date": "2026-01-05T10:00:00+00:00",
    },
    {
        "message": "Add GET /report, a summary of the ledger",
        "name": "SquadOps",
        "email": "squadops@example.invalid",
        "date": "2026-02-09T10:00:00+00:00",
    },
)
# Files a checkout of this repository may hold that are never the product's.
_NOT_PRODUCT = frozenset({"__pycache__", "dist", ".DS_Store"})


@dataclass(frozen=True)
class FixtureRepository:
    path: Path
    first_commit: str
    second_commit: str


def build_repository(destination: Path) -> FixtureRepository:
    """Make the product into a Git repository at ``destination``, which must not exist."""
    destination.mkdir(parents=True)
    _git(destination, "init", "-q", "-b", "main")
    first = {p: c for p, c in product_files().items() if p not in ABSENT_AT_FIRST_COMMIT}
    first.update(_files_under(FIRST_COMMIT))
    commits = []
    for files, meta in ((first, _COMMITS[0]), (product_files(), _COMMITS[1])):
        _write_tree(destination, files)
        _git(destination, "add", "-A")
        _git(destination, "commit", "-q", "-m", meta["message"], env=_identity(meta))
        commits.append(_git(destination, "rev-parse", "HEAD").strip())
    return FixtureRepository(destination, commits[0], commits[1])


def tracked_files(repository: Path, commit: str) -> dict[str, bytes]:
    """Every file tracked at ``commit``, by repository-relative path, read as bytes."""
    listing = _git(repository, "ls-tree", "-r", "-z", "--name-only", commit)
    return {
        path: _git_bytes(repository, "cat-file", "blob", f"{commit}:{path}")
        for path in listing.split("\0")
        if path
    }


def product_files() -> dict[str, bytes]:
    return _files_under(PRODUCT)


def recorded(output: str, form: str) -> dict:
    with (RECORDED / output / f"{form}.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _files_under(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not _NOT_PRODUCT.intersection(path.relative_to(root).parts)
        and path.suffix != ".pyc"
    }


def _write_tree(destination: Path, files: dict[str, bytes]) -> None:
    for entry in destination.iterdir():
        if entry.name != ".git":
            shutil.rmtree(entry) if entry.is_dir() else entry.unlink()
    for relative, content in files.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        target.chmod(0o644)


def _identity(meta: dict[str, str]) -> dict[str, str]:
    return {
        "GIT_AUTHOR_NAME": meta["name"],
        "GIT_AUTHOR_EMAIL": meta["email"],
        "GIT_AUTHOR_DATE": meta["date"],
        "GIT_COMMITTER_NAME": meta["name"],
        "GIT_COMMITTER_EMAIL": meta["email"],
        "GIT_COMMITTER_DATE": meta["date"],
    }


def _git_bytes(repository: Path, *args: str, env: dict[str, str] | None = None) -> bytes:
    # Inherited GIT_* variables are dropped: under a hook, GIT_DIR and GIT_INDEX_FILE name
    # the caller's repository, and this one would be committed into it.
    clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    clean.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", **(env or {}))
    return subprocess.run(
        [
            "git",
            "-c", "commit.gpgsign=false",
            "-c", "core.autocrlf=false",
            "-c", "core.filemode=true",
            *args,
        ],
        cwd=repository,
        env=clean,
        check=True,
        capture_output=True,
    ).stdout  # fmt: skip


def _git(repository: Path, *args: str, env: dict[str, str] | None = None) -> str:
    return _git_bytes(repository, *args, env=env).decode("utf-8")
