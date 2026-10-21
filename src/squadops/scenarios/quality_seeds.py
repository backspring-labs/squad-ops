"""Each sample application's quality seed, declared (SIP-0113 §10j, §10n ruling 6; #2562).

``config/quality_seeds.yaml`` maps a Project to its seed file, Outcome Evaluation's own: never
derived from a Project's layout, and never a field of the Project registry, which is Project
Lifecycle Management's. A Project with no entry has no seed, and its seeded reading is *not
measured*, ``no_seed``.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from squadops.campaigns import seed_plan
from squadops.config.path_resolver import PathResolver

#: Where the declarations are, under the repository root.
DECLARATIONS = Path("config") / "quality_seeds.yaml"


def _root() -> Path:
    return PathResolver.get_base_path()


def quality_seed(
    project_id: str, root: Path | None = None
) -> tuple[Mapping[str, Any], bytes] | None:
    """The Project's seed and its bytes, or ``None`` when it declares none. A declaration that
    names a file that isn't there, or isn't a quality seed, raises ``SeedRefused``: a seed that
    was declared and can't be read is refused, never read as no seed."""
    base = root if root is not None else _root()
    declarations = base / DECLARATIONS
    if not declarations.is_file():
        return None
    entries = yaml.safe_load(declarations.read_text(encoding="utf-8")) or {}
    path = entries.get(project_id)
    if not path:
        return None
    file = base / str(path)
    if not file.is_file():
        raise seed_plan.SeedRefused(f"{project_id}'s quality seed {path} is declared and missing")
    raw = file.read_bytes()
    return seed_plan.load(raw), raw
