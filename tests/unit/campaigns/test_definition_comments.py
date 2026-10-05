"""A campaign definition's comment says what the file is, never which deploy it will run on (#1958).

The 2.0 set's pinned files say they carry the exit run "on the registered deploy (rebuild 19,
b0c25360)"; the set registered on rebuild 22. A comment cannot be corrected once its bytes are pinned,
so the deploy and the round belong to the pre-registration, recorded when they are read.

A file whose bytes ``provenance.yaml`` records is pinned and stays as written (editing it would break
its reconciliation, #1941). Every other definition follows the rule.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[3]
_DIRS = sorted(p.parent for p in _ROOT.glob("examples/*/campaigns/README.md"))

#: Facts about where or when a definition runs: a rebuild or round number, a deploy id, a commit.
_DEPLOY_FACT = re.compile(
    r"\brebuild\s+\d+\b|\bround\s+\d+\b|\bdep_[0-9a-f]{12}\b|\b(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b"
)


def deploy_facts(text: str) -> list[str]:
    """The deploy facts in ``text``'s comment lines, in order."""
    return [
        m.group(0)
        for line in text.splitlines()
        if line.lstrip().startswith("#")
        for m in _DEPLOY_FACT.finditer(line)
    ]


def _pinned(directory: Path) -> set[str]:
    provenance = directory / "provenance.yaml"
    if not provenance.exists():
        return set()
    data = yaml.safe_load(provenance.read_text(encoding="utf-8")) or {}
    return {d["sha256"] for c in data.get("campaigns", ()) for d in c.get("definitions", ())}


def offenders(directory: Path) -> dict[str, list[str]]:
    """Each definition in ``directory`` that provenance has not pinned, with the deploy facts its
    comments name; a definition naming none is left out."""
    pinned = _pinned(directory)
    found = {}
    for path in sorted(directory.glob("*.yaml")):
        if path.name == "provenance.yaml":
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() in pinned:
            continue
        if facts := deploy_facts(path.read_text(encoding="utf-8")):
            found[path.name] = facts
    return found


def test_no_unpinned_definition_names_a_deploy():
    """Bug caught: a new definition whose comment names the deploy it will run on, which the pin
    then freezes stale the moment a later round moves the deploy."""
    assert _DIRS, "the guard reads the tree it is meant to"
    assert {str(d.relative_to(_ROOT)): offenders(d) for d in _DIRS if offenders(d)} == {}


def test_a_pinned_file_is_left_as_written_and_an_edited_one_is_not(tmp_path):
    """The exemption is the pin, not the name. Bug caught: a pinned file edited later (its bytes,
    and so its claim, no longer what provenance recorded) passing because its name was once
    pinned."""
    pinned = b"# shakeout 7, on rebuild 19\nproject_id: group_run\n"
    (tmp_path / "pinned.yaml").write_bytes(pinned)
    (tmp_path / "edited.yaml").write_bytes(pinned + b"# and now rebuild 22\n")
    (tmp_path / "provenance.yaml").write_text(
        yaml.safe_dump(
            {
                "campaigns": [
                    {
                        "definitions": [
                            {"path": "pinned.yaml", "sha256": hashlib.sha256(pinned).hexdigest()}
                        ]
                    }
                ]
            }
        )
    )

    assert offenders(tmp_path) == {"edited.yaml": ["rebuild 19", "rebuild 22"]}


@pytest.mark.parametrize(
    ("comment", "facts"),
    [
        (
            "# the exit run on the registered deploy (rebuild 19, b0c25360)",
            ["rebuild 19", "b0c25360"],
        ),
        ("# shakeout 11, on dep_fd4de43a1f39 (3299ff78)", ["dep_fd4de43a1f39", "3299ff78"]),
        ("# the set's round 4", ["round 4"]),
        ("# shakeout 11: what the proposer is told about frozen criteria (#1938)", []),
        ("objective: accepted increments, not a comment: rebuild 3", []),
    ],
    ids=[
        "the 2.0 set's stale claim",
        "a deploy id and commit",
        "a round",
        "a clean comment",
        "not a comment",
    ],
)
def test_the_rule_reads_deploy_facts_in_comments_only(comment, facts):
    assert deploy_facts(comment) == facts
