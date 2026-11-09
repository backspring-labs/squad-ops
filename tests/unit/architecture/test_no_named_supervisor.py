"""SquadOps names no external supervisor (the owner's ruling of 2026-11-07, SIP-0115 §10e).

What drives a Campaign from outside is an API client, and the product calls it the operator. It
carries no name of one, or of the tools it talks through. The names are held here as hashes, so this
file doesn't name them either.

What bug would this catch? A comment, a screen's text or a fixture naming the client again, as the
Campaigns plugin did before the ruling.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_contracts]

REPO = Path(__file__).resolve().parents[3]
ROOTS = ("src", "adapters", "console", "infra", "scripts", "tests", "docs/ops")
#: The repository check on that client's own pull requests. It goes with the owner's change to the
#: branch protection that requires it, never by this guard.
EXEMPT = frozenset({"1e7d37f0b79363a0"})
NAMES = frozenset(
    {
        "9cae07a2e9ceea5b",
        "a6af8190add5594f",
        "1fb565c514350bd3",
        "9fff3bcb10ca5e87",
    }
)
_WORD = re.compile(r"[a-z]+")


def _hash(word: str) -> str:
    return hashlib.sha256(word.encode()).hexdigest()[:16]


def _named(text: str) -> set[str]:
    return {word for word in _WORD.findall(text.lower()) if _hash(word) in NAMES}


def _files() -> list[str]:
    listed = subprocess.run(
        ["git", "ls-files", *ROOTS], cwd=REPO, capture_output=True, text=True, check=True
    )
    return [p for p in listed.stdout.split() if _hash(Path(p).name) not in EXEMPT]


def test_the_product_names_no_external_supervisor():
    found = {}
    for path in _files():
        try:
            text = (REPO / path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError):
            continue
        hits = _named(f"{path}\n{text}")
        if hits:
            found[path] = sorted(hits)
    assert found == {}


@pytest.mark.parametrize(
    ("text", "hits"),
    [("the operator rules the gate", 0), ("screwdriver", 0), (chr(66) + "UZZ ruled", 1)],
)
def test_a_name_is_found_whatever_its_case_and_a_longer_word_is_not(text, hits):
    assert len(_named(text)) == hits
