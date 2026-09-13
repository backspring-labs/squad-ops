"""Where the framework version comes from (#1089).

``pyproject.toml`` is the single source. Installed metadata is a **copy made at
install time** — correct for a real install, because the copy is made from the file,
and stale from the moment the file changes in an editable one, because nothing
regenerates it.

That drift is not hypothetical. On a tree at 1.6.3 the call documented as
authoritative returned ``1.4.0``; ``squadops --version`` printed it, and
``version_cli.py`` — whose entire job is version correctness — announced
"Version bumped: 1.4.0 -> 1.6.3" while correctly editing 1.6.2.

Its own module rather than a function in ``__init__``: a definition between the
imports there pushes every later import past ruff's E402, and "where does the version
come from" is a concern of its own regardless.
"""

from __future__ import annotations

import os
import re
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path

_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


def resolve_version() -> str:
    """The version, preferring a source checkout over the install-time copy.

    A source tree wins because it is the thing being edited. Otherwise metadata,
    which is correct for an installed package and is all that exists there — the fix
    must not trade a stale dev version for a broken production one.
    """
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        text = ""
    # Only trust a pyproject that declares THIS package: a checkout nested inside an
    # unrelated project must not report the neighbour's version.
    if 'name = "squadops"' in text:
        match = _VERSION_RE.search(text)
        if match:
            return match.group(1)
    try:
        return _pkg_version("squadops")
    except PackageNotFoundError:
        return "unknown"


#: The image-level variable the runtime-api Dockerfile sets from its ``SOURCE_HASH`` build
#: argument (#80). An image variable like ``SQUADOPS_BASE_PATH``, not a ``SQUADOPS__*``
#: config setting: it is a fact about the build, and nothing configures it.
GIT_SHA_ENV = "SQUADOPS_GIT_SHA"


def resolve_git_sha() -> str | None:
    """The commit this process's image was built from, or ``None`` when that is unknown (#80).

    ``rebuild_and_deploy.sh`` derives it from ``git rev-parse --short HEAD`` and marks a build
    from uncommitted image paths with ``-dirty``, so a record never claims a commit its code
    does not match. ``unknown`` is the build argument's own default, meaning the image was
    built without the script; it reads as ``None`` rather than as a commit named "unknown".

    No source-checkout fallback, unlike ``resolve_version``: an image carries no ``.git``,
    and a process run from a checkout would report the checkout's HEAD whatever its working
    tree holds, which is the claim the dirty marker exists to refuse.
    """
    value = os.environ.get(GIT_SHA_ENV, "").strip()
    return value if value and value != "unknown" else None
