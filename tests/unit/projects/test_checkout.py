"""A source-backed run's bounded view of its product (SIP-0112 E.4.3)."""

import pytest

from squadops.projects.checkout import (
    FOCUS_BUDGET_BYTES,
    MAP_FOLDED_NOTE,
    MAP_PATH_LIMIT,
    MAX_WORKSPACE_BYTES,
    CheckoutManifest,
    CheckoutTooLarge,
    RunnerView,
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
    """Bug caught: a large product seeded whole, then cut at the context's limit, so a task
    works from a tree with files silently missing."""
    _manifest(
        {"src/game.luau": b"x" * (2_354_012)}
    )  # z_tower-ascension's source and config (#3118)
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
        f"{MAP_FOLDED_NOTE}\n- `README.md`\n- `pkg/` ({MAP_PATH_LIMIT + 1} files)"
    )


def _game(*, art: int, shots: int) -> dict[str, bytes]:
    """A game's shape: one source directory, and art and documents that outnumber it."""
    return (
        {"src/Client/UI/Screens/HUD.luau": b"hud", "src/Client/UI/Theme.luau": b"th"}
        | {"docs/GAME_CONTEXT.md": b"ctx", "README.md": b"r", "cover.png": b"\xff"}
        | {f"art/icons/i{n}.png": b"\xff" for n in range(art)}
        | {f"docs/shots/s{n}.png": b"\xff" for n in range(shots)}
        | {"docs/diagram.png": b"\xff", "src/Client/UI/Screens/hud_frame.png": b"\xff"}
    )


def test_a_tree_past_the_limit_folds_what_no_task_changes_and_lists_every_other_path():
    """#3178. Bug caught: a game of 619 files, 385 of them art, read ``src/ (137 files)``, so a
    proposal named ``src/Client/UI/HUD.luau`` for the HUD at ``src/Client/UI/Screens/HUD.luau``."""
    tree = _game(art=MAP_PATH_LIMIT, shots=30)
    assert len(tree) > MAP_PATH_LIMIT

    assert repository_map(_manifest(tree)).split("\n") == [
        "- `README.md` (1 bytes)",
        # a directory holding nothing a task changes is one line, at the shallowest such one
        f"- `art/` ({MAP_PATH_LIMIT} binary or generated files)",
        "- `cover.png` (1 bytes, binary)",
        # beside a listed file, the directory's own held-back files are counted apart
        "- `docs/` (1 binary or generated files, beside the files listed)",
        "- `docs/GAME_CONTEXT.md` (3 bytes)",
        "- `docs/shots/` (30 binary or generated files)",
        "- `src/Client/UI/Screens/` (1 binary or generated files, beside the files listed)",
        "- `src/Client/UI/Screens/HUD.luau` (3 bytes)",
        "- `src/Client/UI/Theme.luau` (2 bytes)",
    ]


def test_a_removed_file_is_named_in_a_folded_map_and_left_out_of_its_count():
    tree = _game(art=MAP_PATH_LIMIT, shots=2)
    removed = ["art/icons/i0.png", "src/Client/UI/Theme.luau"]

    lines = repository_map(_manifest(tree), removed).split("\n")

    assert "- `art/icons/i0.png` (removed by this run)" in lines
    assert "- `src/Client/UI/Theme.luau` (removed by this run)" in lines
    # the removed icon sits in its directory now, so the rest fold beside it
    assert (
        f"- `art/icons/` ({MAP_PATH_LIMIT - 1} binary or generated files, beside the files listed)"
        in lines
    )


def test_a_tree_of_text_past_the_limit_says_its_files_are_not_listed():
    """Folding what no task changes can't bring a tree of source under the limit. Bug caught:
    the directory counts read as "every file the product holds", which the prompts call the map."""
    tree = {f"src/m{i}.py": b"x" for i in range(MAP_PATH_LIMIT + 1)} | {"art/a.png": b"\xff"}

    assert repository_map(_manifest(tree)).split("\n") == [
        MAP_FOLDED_NOTE,
        "- `art/` (1 files)",
        f"- `src/` ({MAP_PATH_LIMIT + 1} files)",
    ]


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


_RUNNER = RunnerView("pytest", ("tests",), ("tests",), "test_*.py", ("src/**",))


def test_the_input_carries_the_map_the_checks_the_instructions_and_the_named_files():
    manifest = manifest_of(
        COMMIT,
        {"a.py": b"old", "CONTRIBUTING.md": b"rules"},
        (),
        ["CONTRIBUTING.md"],
        classify=_classify,
        checks=[("tests", ("python3", "-m", "pytest", "tests"))],
        runners=[_RUNNER],
    )
    assert CheckoutManifest.from_json(manifest.to_json()) == manifest

    view = source_repository_input(manifest, {"a.py": "new", "CONTRIBUTING.md": "rules"}, ["a.py"])

    assert view["commit"] == COMMIT
    assert view["checks"] == [{"id": "tests", "argv": ["python3", "-m", "pytest", "tests"]}]
    # SIP-0112 H.4 point 3: where a test goes so the product's checks run it
    assert view["runners"] == [
        {
            "runner": "pytest",
            "checks": ["tests"],
            "roots": ["tests"],
            "file_pattern": "test_*.py",
            "covers": ["src/**"],
        }
    ]
    assert view["instructions"] == {"CONTRIBUTING.md": "rules"}
    assert view["existing_files"] == {"a.py": "new"}
    assert "`a.py`" in view["map"]
    assert view["new_files"] == []


def test_the_input_names_the_files_a_task_names_that_neither_the_product_nor_the_run_holds():
    """#3178. Bug caught: a developer told to read ``src/Client/UI/HUD.luau`` in full, shown no
    content and no reason, since the product's HUD is under ``Screens/``."""
    manifest = _manifest({"src/Screens/HUD.luau": b"hud", "art/a.png": b"\xff"})
    current = {"src/Screens/HUD.luau": "hud", "src/Added.luau": "the run's own, written earlier"}

    view = source_repository_input(
        manifest,
        current,
        (p for p in ["src/HUD.luau", "src/Screens/HUD.luau", "src/Added.luau", "src/HUD.luau"]),
    )

    assert view["new_files"] == ["src/HUD.luau"]
    assert view["existing_files"] == {"src/Screens/HUD.luau": "hud"}


def test_a_manifest_stored_before_the_runners_reads_with_none():
    """Bug caught: a run seeded before 2.5 and resumed on a 2.5 deploy failing to read its own
    checkout manifest, which has no ``runners`` key."""
    stored = _manifest({"a.py": b"x"}).to_json().replace(b',\n "runners": []', b"")
    assert b"runners" not in stored

    manifest = CheckoutManifest.from_json(stored)

    assert manifest.runners == ()
    assert source_repository_input(manifest, {"a.py": "x"}, [])["runners"] == []


def test_a_checkout_the_cap_accepts_is_carried_whole_and_reaches_the_worker():
    """#3118 and #3049: three limits, one tree. Bugs caught: the checkout cap raised without the
    resolution's, so a run the checkout accepts is refused at its first acceptance workspace once
    the squad adds files; or the remote request's limit set below the resolution's, so a tree a
    run carries whole is refused at the worker's port."""
    from squadops.capabilities.context_assembly import ARTIFACT_CONTENTS_LIMIT_BYTES
    from squadops.remote_execution.models import REQUEST_TREE_LIMIT_BYTES

    assert ARTIFACT_CONTENTS_LIMIT_BYTES - MAX_WORKSPACE_BYTES >= 1024 * 1024  # the squad's room
    assert REQUEST_TREE_LIMIT_BYTES == ARTIFACT_CONTENTS_LIMIT_BYTES
