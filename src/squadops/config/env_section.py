"""One config section read straight from its environment variables.

For a process that loads only its own section, never the whole platform config: the sandbox
service and the remote-execution worker. The layered loader resolves every ``secret://``
reference in the platform config, so a process that used it would need secrets it must never
hold. Same variable convention (``SQUADOPS__<SECTION>__<FIELD>``), one section.
"""

from __future__ import annotations

import os
from collections.abc import Iterable


def section_from_env(prefix: str, fields: Iterable[str]) -> dict[str, str]:
    """The section's variables, keyed by field. A variable under ``prefix`` that names no
    field raises: a typo would otherwise deploy as an unconfigured default."""
    values = {
        key[len(prefix) :].lower(): value
        for key, value in os.environ.items()
        if key.startswith(prefix)
    }
    unknown = set(values) - set(fields)
    if unknown:
        raise ValueError(
            f"unknown {prefix} settings: {sorted(unknown)} "
            "(a typo here would otherwise be silently ignored)"
        )
    return values
