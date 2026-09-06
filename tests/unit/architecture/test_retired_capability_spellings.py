"""#922: "capability" means bindable agent competence — the two host-internal meanings are
retired from the code and the live config.

Three things were called capability: the task type (``CapabilityContract.capability_id``,
``HandlerRegistry.get(capability_id)`` — the task-type registry that looked like the
competence-binding seam the packs SIP wants), the stack-settings bundle (``dev_capability``,
selected per cycle by id — this repo's "profile"), and the SIP's bindable competence, which
is the word in the distribution format and keeps it. A pack published against the old
``capability_id`` would have frozen the collision in a distribution format for good.

This guard fails the retired spellings wherever they could come back: source, adapters,
scripts, tests, the contract manifests and the live request profiles. History — plans,
records, set configs of finished lines, the site, SIPs — keeps its words.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]

#: Where the words could come back. Not ``docs/``, ``site/``, ``sips/`` (history and the
#: SIPs that record the rename as an amendment), and not this file (the subject).
_LIVE_ROOTS = ("src", "adapters", "scripts", "tests", "examples", "config", "agents")
_LIVE_SUFFIXES = {".py", ".yaml", ".yml", ".toml", ".sh"}

#: The retired spellings and what each became. Word-bounded, so ``capability_set``
#: (the embodiment column, SIP-0090's competence sense) and ``LLMCapability`` (a provider
#: feature flag) are untouched — they were never one of the three.
RETIRED: dict[str, str] = {
    r"\bcapability_id\b": "task_type",
    r"\b_capability_id\b": "_task_type",
    r"\bCapabilityContract\b": "TaskContract",
    r"\bREASONING_BY_CAPABILITY\b": "REASONING_BY_TASK_TYPE",
    r"\bAUTHOR_MANIFEST_CAPABILITY\b": "AUTHOR_MANIFEST_TASK_TYPE",
    r"\bdev_capabilit(y|ies)\b": "development_profile(s)",
    r"\bDEV_CAPABILITIES\b": "DEVELOPMENT_PROFILES",
    r"\bDevelopmentCapability\b": "DevelopmentProfile",
    r"\bDEFAULT_DEV_CAPABILITY\b": "DEFAULT_DEVELOPMENT_PROFILE",
    r"\beffective_capability_name\b": "effective_development_profile",
    r"\bresolve_dev_capability\b": "resolve_development_profile",
    r"\bget_capability\b": "get_development_profile",
}

_SELF = Path(__file__).resolve()


def _live_files():
    for root in _LIVE_ROOTS:
        base = _REPO / root
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if (
                path.is_file()
                and path.suffix in _LIVE_SUFFIXES
                and path.resolve() != _SELF
                and "__pycache__" not in path.parts
                and ".venv" not in path.parts
            ):
                yield path


@pytest.mark.parametrize("pattern", sorted(RETIRED), ids=lambda p: p.strip("\\b"))
def test_no_retired_spelling_survives_in_live_code_or_config(pattern):
    """Bug caught: the fourth meaning. A handler, a test fixture, a profile YAML or a
    ``--set`` example that brings ``capability_id`` or ``dev_capability`` back, after
    which the packs SIP publishes against a word that means three things again."""
    rx = re.compile(pattern)
    hits = []
    for path in _live_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append(f"{path.relative_to(_REPO)}:{n}: {line.strip()[:100]}")
    assert not hits, (
        f"retired spelling {pattern} (now {RETIRED[pattern]}) is back in "
        f"{len(hits)} place(s):\n  " + "\n  ".join(hits[:20])
    )


def test_the_task_type_registry_is_keyed_on_task_type_not_capability():
    """The seam the packs SIP must not be wired into by mistake: the handler registry
    is the task-type registry, and says so in its own vocabulary."""
    from squadops.orchestration.handler_registry import HandlerRegistry

    assert "task_type" in HandlerRegistry.get.__code__.co_varnames
    assert "capability_id" not in HandlerRegistry.get.__code__.co_varnames


def test_a_contract_manifest_declares_its_task_type():
    """The on-disk contract key follows the model: ``task_type:``, not ``capability_id:``."""
    manifests = list((_REPO / "src" / "squadops" / "capabilities" / "manifests").rglob("*.yaml"))
    assert manifests
    keyed = [m for m in manifests if re.search(r"^task_type:", m.read_text(), re.M)]
    assert keyed, "no contract manifest declares task_type:"
    stale = [m for m in manifests if re.search(r"^\s*capability_id:", m.read_text(), re.M)]
    assert stale == []
