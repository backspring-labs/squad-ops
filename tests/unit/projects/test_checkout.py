"""A source-backed run's bounded view of its product (SIP-0112 E.4.3)."""

import pytest

from squadops.projects.checkout import (
    FOCUS_BUDGET_BYTES,
    MAP_PATH_LIMIT,
    MAX_TEXT_BYTES,
    CheckoutManifest,
    CheckoutTooLarge,
    focus_paths,
    manifest_of,
    repository_map,
    source_repository_input,
)

COMMIT = "c" * 40


def test_the_manifest_names_binary_and_executable_files_and_only_real_instruction_paths():
    manifest = manifest_of(
        COMMIT,
        {"run.sh": b"#!/bin/sh\n", "mark.png": b"\x89PNG\r\n", "CONTRIBUTING.md": b"x"},
        {"run.sh"},
        ["CONTRIBUTING.md", "AGENTS.md"],
    )

    assert (manifest.binary, manifest.executable) == ({"mark.png"}, {"run.sh"})
    assert manifest.instruction_paths == ("CONTRIBUTING.md",)
    assert CheckoutManifest.from_json(manifest.to_json()) == manifest


def test_a_product_past_the_text_limit_is_refused_by_name_never_truncated():
    """Bug caught: a large product seeded whole, then cut at the 512 KB context cap, so a task
    works from a tree with files silently missing."""
    with pytest.raises(CheckoutTooLarge, match="KB of text"):
        manifest_of(COMMIT, {"big.py": b"x" * (MAX_TEXT_BYTES + 1)}, (), ())
    # binary bytes don't count toward the text a prompt could carry
    manifest_of(COMMIT, {"big.bin": b"\xff" * (MAX_TEXT_BYTES + 1)}, (), ())


def test_the_map_lists_every_path_or_past_its_limit_every_directory():
    small = manifest_of(COMMIT, {"a/b.py": b"xy", "c.png": b"\xff"}, (), ())
    assert repository_map(small) == "- `a/b.py` (2 bytes)\n- `c.png` (1 bytes, binary)"

    many = {f"pkg/m{i}.py": b"x" for i in range(MAP_PATH_LIMIT + 1)} | {"README.md": b"r"}
    assert repository_map(manifest_of(COMMIT, many, (), ())) == (
        f"- `README.md`\n- `pkg/` ({MAP_PATH_LIMIT + 1} files)"
    )


def test_the_focus_is_the_named_text_files_in_order_within_the_budget():
    files = {
        "a.py": b"a" * 10,
        "big.py": b"b" * FOCUS_BUDGET_BYTES,
        "img.png": b"\xff",
        "c.py": b"c",
    }
    manifest = manifest_of(COMMIT, files, (), ())

    assert focus_paths(manifest, ["missing.py", "img.png", "a.py", "a.py", "c.py"]) == [
        "a.py",
        "c.py",
    ]
    assert focus_paths(manifest, ["a.py", "big.py", "c.py"]) == ["a.py"]


def test_the_input_carries_the_map_the_instructions_and_the_named_files():
    manifest = manifest_of(
        COMMIT, {"a.py": b"old", "CONTRIBUTING.md": b"rules"}, (), ["CONTRIBUTING.md"]
    )

    view = source_repository_input(manifest, {"a.py": "new", "CONTRIBUTING.md": "rules"}, ["a.py"])

    assert view["commit"] == COMMIT
    assert view["instructions"] == {"CONTRIBUTING.md": "rules"}
    assert view["existing_files"] == {"a.py": "new"}
    assert "`a.py`" in view["map"]
