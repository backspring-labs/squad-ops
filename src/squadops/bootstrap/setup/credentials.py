"""Each deploy's own credentials, decided (#2006).

The registry (``infra/deploy_credentials.json``) names every credential a deploy holds, and
``.env`` is each one's single home. This module decides, without touching anything: what
``ensure`` writes (``plan``) and what the doctor refuses (``problems``). The script that acts on
the decision (``scripts/dev/ops/deploy_credentials.py``) loads this file by path, because
bootstrap runs it before the venv exists. **Stdlib only** for that reason.
"""

from __future__ import annotations

import json
import re
import secrets
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
REGISTRY = REPO / "infra" / "deploy_credentials.json"


def load_registry(path: Path = REGISTRY) -> list[dict]:
    return json.loads(path.read_text())["credentials"]


def read_env(path: Path) -> dict[str, str]:
    """``KEY=value`` lines, the last one winning; comments and blank lines skipped."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


def generate() -> str:
    """48 hex characters: nothing a DSN, a URL or a shell would need escaped."""
    return secrets.token_hex(24)


def secret_file_content(credential: Mapping, value: str) -> str:
    return str(credential.get("secret_format") or "{value}").format(value=value)


def value_from_secret_file(credential: Mapping, content: str) -> str | None:
    """The value a secret file holds, read back through its format."""
    fmt = str(credential.get("secret_format") or "{value}")
    head, _, tail = fmt.partition("{value}")
    match = re.fullmatch(re.escape(head) + "(.+)" + re.escape(tail), content.strip())
    return match.group(1) if match else None


@dataclass(frozen=True)
class Plan:
    #: Variables ``.env`` gets, each with how it was decided (``generated`` or ``adopted``).
    env_updates: dict[str, tuple[str, str]]
    #: Secret files to (re)write, path → content.
    secret_writes: dict[str, str]


def plan(
    registry: Sequence[Mapping],
    env: Mapping[str, str],
    secret_files: Mapping[str, str],
    *,
    existing: bool,
    new_value: Callable[[], str] = generate,
) -> Plan:
    """What ``ensure`` writes.

    A variable ``.env`` holds is never changed. One it lacks, or holds empty, is generated on a
    new deploy. On a deploy that already exists (``existing``), the value it already runs with
    is adopted instead: the secret file it has, else the registry's ``legacy`` value, so it keeps
    working until it is rotated. ``secret_files`` maps each secret file the deploy has to its
    content; each is rewritten when it does not hold what ``.env`` says."""
    env_updates: dict[str, tuple[str, str]] = {}
    secret_writes: dict[str, str] = {}
    for credential in registry:
        name = credential["env"]
        value = env.get(name, "")
        if not value:
            adopted = None
            if existing:
                held = secret_files.get(credential.get("secret_file") or "")
                adopted = (
                    value_from_secret_file(credential, held) if held else None
                ) or credential.get("legacy")
            value = adopted or new_value()
            env_updates[name] = (value, "adopted" if adopted else "generated")
        target = credential.get("secret_file")
        if target:
            content = secret_file_content(credential, value)
            # A file bootstrap wrote through `cut` ends in a newline its readers strip.
            if (secret_files.get(target) or "").strip() != content:
                secret_writes[target] = content
    return Plan(env_updates, secret_writes)


def problems(registry: Sequence[Mapping], env: Mapping[str, str]) -> list[str]:
    """Each credential that is missing or holds a value the repository has committed."""
    found = []
    for credential in registry:
        value = env.get(credential["env"], "")
        if not value:
            found.append(f"{credential['env']} is not set ({credential['what']})")
        elif value in credential.get("committed", ()):
            found.append(
                f"{credential['env']} holds a value the repository commits ({credential['what']})"
            )
    return found


def rotation_targets(
    registry: Sequence[Mapping],
    env: Mapping[str, str],
    *,
    only: Sequence[str] = (),
    keep: Sequence[str] = (),
) -> list[str]:
    """The credentials a rotation replaces: ``only`` when named, else every one holding a value
    the repository commits; never one in ``keep``. A name the registry does not hold is refused,
    so a typo is not a credential silently left alone."""
    known = [c["env"] for c in registry]
    unknown = sorted((set(only) | set(keep)) - set(known))
    if unknown:
        raise ValueError(f"not credentials the registry names: {unknown}")
    if only:
        chosen = [name for name in known if name in only]
    else:
        committed = {c["env"]: set(c.get("committed", ())) for c in registry}
        chosen = [name for name in known if env.get(name, "") in committed[name]]
    return [name for name in chosen if name not in keep]
