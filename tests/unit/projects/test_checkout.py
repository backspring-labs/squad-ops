"""A source-backed run's bounded view of its product (SIP-0112 E.4.3)."""

import pytest

from squadops.projects.checkout import (
    FOCUS_BUDGET_BYTES,
    MAP_PATH_LIMIT,
    MAX_WORKSPACE_BYTES,
    CheckoutManifest,
    CheckoutTooLarge,
    focus_paths,
    manifest_of,
    repository_map,
    source_repository_input,
)

COMMIT = "c" * 40


def _classify(path: str) -> str:
    return "document" if path.endswith(".md") else "source"


def _manifest(files, executable=(), instructions=()):
    return manifest_of(COMMIT, files, executable, instructions, classify=_classify)


def test_the_manifest_names_binary_and_executable_files_and_only_real_instruction_paths():
    manifest = _manifest(
        {
            "run.sh": b"#!/bin/sh\n",
            "mark.png": b"\x89PNG\r\n",
            "CONTRIBUTING.md": b"x",
            "web/package-lock.json": b"{}",
        },
        {"run.sh"},
        ["CONTRIBUTING.md", "AGENTS.md"],
    )

    assert (manifest.binary, manifest.executable) == ({"mark.png"}, {"run.sh"})
    assert manifest.held_back == {"mark.png", "web/package-lock.json"}
    assert manifest.instruction_paths == ("CONTRIBUTING.md",)
    assert CheckoutManifest.from_json(manifest.to_json()) == manifest


def test_a_product_past_the_workspace_limit_is_refused_by_name_never_truncated():
    """Bug caught: a large product seeded whole, then cut at the 512 KB context cap, so a task
    works from a tree with files silently missing."""
    over = b"x" * (MAX_WORKSPACE_BYTES + 1)
    with pytest.raises(CheckoutTooLarge, match="KB of source and config"):
        _manifest({"big.py": over})
    # What no workspace carries doesn't count: binary bytes, a generated lockfile, a document
    _manifest({"big.bin": b"\xff" * len(over), "uv.lock": over, "NOTES.md": over})


def test_the_map_lists_every_path_or_past_its_limit_every_directory():
    small = _manifest({"a/b.py": b"xy", "c.png": b"\xff", "uv.lock": b"l"})
    assert repository_map(small) == (
        "- `a/b.py` (2 bytes)\n- `c.png` (1 bytes, binary)\n- `uv.lock` (1 bytes, generated)"
    )

    many = {f"pkg/m{i}.py": b"x" for i in range(MAP_PATH_LIMIT + 1)} | {"README.md": b"r"}
    assert repository_map(_manifest(many)) == (
        f"- `README.md`\n- `pkg/` ({MAP_PATH_LIMIT + 1} files)"
    )


def test_the_focus_is_the_named_text_files_in_order_within_the_budget():
    files = {
        "a.py": b"a" * 10,
        "big.py": b"b" * FOCUS_BUDGET_BYTES,
        "img.png": b"\xff",
        "c.py": b"c",
    }
    manifest = _manifest(files)

    assert focus_paths(manifest, ["missing.py", "img.png", "a.py", "a.py", "c.py"]) == [
        "a.py",
        "c.py",
    ]
    assert focus_paths(manifest, ["a.py", "big.py", "c.py"]) == ["a.py"]


def test_the_input_carries_the_map_the_instructions_and_the_named_files():
    manifest = _manifest({"a.py": b"old", "CONTRIBUTING.md": b"rules"}, (), ["CONTRIBUTING.md"])

    view = source_repository_input(manifest, {"a.py": "new", "CONTRIBUTING.md": "rules"}, ["a.py"])

    assert view["commit"] == COMMIT
    assert view["instructions"] == {"CONTRIBUTING.md": "rules"}
    assert view["existing_files"] == {"a.py": "new"}
    assert "`a.py`" in view["map"]
