"""The console's settings as ``docker-compose.yml`` gives them to ``squadops-console`` (#2431).

The console reads each as required, so its tests import ``main`` under exactly these values,
with compose's ``${VAR:-default}`` interpolations resolved to their defaults.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

COMPOSE = Path(__file__).resolve().parents[3] / "docker-compose.yml"
_DEFAULTED = re.compile(r"\$\{([A-Z_]+):-([^}]*)\}")


def compose_settings() -> dict[str, str]:
    env = yaml.safe_load(COMPOSE.read_text())["services"]["squadops-console"]["environment"]
    return {name: _DEFAULTED.sub(lambda m: m.group(2), str(value)) for name, value in env.items()}
