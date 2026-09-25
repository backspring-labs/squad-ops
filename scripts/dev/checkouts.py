"""Which checkout is the main one: a single home for the lookup (1.8.2 plan §3.2 item 8).

The deploy's state lives in the main checkout whichever checkout a script runs from: its
``data/`` volume, the verification-set records under ``var/``, the ``secrets/`` the deploy
reads, its ``.env``. A worktree is a second view of the same repository and holds none of
it. Three scripts resolved this, and the driver's copy of the lookup was what wrote the 1.7.4
and 1.7.5 records into two worktrees that looked disposable.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def main_checkout(path: Path) -> Path:
    """The main checkout of the repository ``path`` is in: itself, or the one a worktree
    hangs off. Refuses outside a checkout rather than falling back to ``path``, which is the
    fallback that stranded the records."""
    proc = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True,
        text=True,
    )
    common = Path(proc.stdout.strip()) if proc.returncode == 0 else None
    if common is None or common.name != ".git":
        raise SystemExit(
            f"{path}: cannot find the main checkout "
            f"(git rev-parse --git-common-dir: {(proc.stderr or proc.stdout).strip()})"
        )
    return common.parent
