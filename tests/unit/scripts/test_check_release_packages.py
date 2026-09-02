"""The step-7 guard (#1151): a tag without its package, and a package that captured nothing.

What bug would these catch? The two recorded failures of the release-cut checklist — a tag
pushed and the package never captured (#789's class), and a capture that wrote
``captured: true`` over a roll-up of nulls because the API's 404 was valid JSON (#1076) —
neither of which anything checked after the fact.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "check_release_packages", REPO_ROOT / "scripts" / "dev" / "check_release_packages.py"
)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

REAL = REPO_ROOT / "site" / "content" / "releases"


def _write_package(releases: Path, tag: str, cycles: list[dict] | None) -> None:
    target = releases / tag
    target.mkdir(parents=True)
    (target / "index.md").write_text(f"# {tag}\n", encoding="utf-8")
    package = {"version": tag[1:], "tag": tag, "cycles": cycles}
    (target / "package.yaml").write_text(yaml.safe_dump(package), encoding="utf-8")


# --- the real tree --------------------------------------------------------------------


@pytest.mark.parametrize("tag", ["v1.7.0", "v1.6.6", "v1.6.2"])
def test_the_committed_packages_with_cycle_evidence_pass(tag):
    assert guard.package_problems(tag, REAL) == []


def test_a_backfilled_package_before_the_evidence_floor_passes_with_no_cycles():
    """v1.0.0 was captured from git alone (#789) — the cycle rule does not reach it."""
    package = yaml.safe_load((REAL / "v1.0.0" / "package.yaml").read_text(encoding="utf-8"))
    assert package.get("cycles") in (None, [])
    assert guard.package_problems("v1.0.0", REAL) == []


# --- the failures the guard exists for ------------------------------------------------


def test_a_tag_with_no_package_names_the_capture_command(tmp_path):
    (problem,) = guard.package_problems("v1.7.1", tmp_path)
    assert "no release package at site/content/releases/v1.7.1/" in problem
    assert "build_release_package.py 1.7.1 --cycle" in problem


def test_the_hollow_capture_of_1076_fails_by_name(tmp_path):
    """captured: true with every field null — what the 1.6.2 cut wrote before #1076."""
    _write_package(
        tmp_path,
        "v1.6.2",
        [
            {
                "cycle_id": "cyc_79eebcb82205",
                "captured": True,
                "status": None,
                "verdict": None,
                "verified": [],
                "failed": [],
                "required_unmet": [],
                "unverified": [],
                "run_count": None,
            }
        ],
    )
    (problem,) = guard.package_problems("v1.6.2", tmp_path)
    assert "cyc_79eebcb82205" in problem
    assert "hollow capture" in problem
    assert "verdict is null" in problem
    assert "run_count is None" in problem


@pytest.mark.parametrize("cycles", [[], None])
def test_an_empty_cycle_list_fails_from_the_evidence_floor(tmp_path, cycles):
    _write_package(tmp_path, "v1.9.0", cycles)
    (problem,) = guard.package_problems("v1.9.0", tmp_path)
    assert "carries no cycle evidence" in problem


def test_an_empty_cycle_list_passes_before_the_evidence_floor(tmp_path):
    _write_package(tmp_path, "v1.5.0", [])
    assert guard.package_problems("v1.5.0", tmp_path) == []


def test_rows_recorded_absent_are_disclosure_not_evidence(tmp_path):
    _write_package(
        tmp_path,
        "v1.8.0",
        [{"cycle_id": "cyc_aaaaaaaaaaaa", "captured": False, "reason": "API did not answer"}],
    )
    (problem,) = guard.package_problems("v1.8.0", tmp_path)
    assert "every cycle row" in problem
    assert "API did not answer" in problem


def test_an_absent_row_beside_a_captured_one_is_allowed(tmp_path):
    _write_package(
        tmp_path,
        "v1.8.0",
        [
            {"cycle_id": "cyc_aaaaaaaaaaaa", "captured": False, "reason": "moved"},
            {
                "cycle_id": "cyc_bbbbbbbbbbbb",
                "captured": True,
                "verdict": "accepted",
                "verified": ["tests_pass"],
                "run_count": 2,
            },
        ],
    )
    assert guard.package_problems("v1.8.0", tmp_path) == []


def test_a_package_naming_another_tag_fails(tmp_path):
    _write_package(tmp_path, "v1.8.0", [])
    text = (tmp_path / "v1.8.0" / "package.yaml").read_text(encoding="utf-8")
    (tmp_path / "v1.8.0" / "package.yaml").write_text(
        text.replace("tag: v1.8.0", "tag: v1.7.9"), encoding="utf-8"
    )
    problems = guard.package_problems("v1.8.0", tmp_path)
    assert any("names tag 'v1.7.9', not v1.8.0" in p for p in problems)


def test_only_semver_tags_are_releases():
    """The warmboot-era tags predate the packaging convention; a 2-digit minor sorts numerically."""
    tags = ["v0.1-warmboot-001", "v1.10.0", "v1.7.0", "v0.4-warmboot-restructure", "v1.9.2"]
    assert guard.semver_tags(tags) == ["v1.7.0", "v1.9.2", "v1.10.0"]


def test_main_exit_codes_and_messages(tmp_path, capsys):
    _write_package(
        tmp_path,
        "v1.7.0",
        [
            {
                "cycle_id": "c",
                "captured": True,
                "verdict": "accepted",
                "verified": [],
                "run_count": 1,
            }
        ],
    )
    assert guard.main(["--tag", "v1.7.0", "--releases-dir", str(tmp_path)]) == 0
    assert "1 tag(s) have a captured package" in capsys.readouterr().out

    assert guard.main(["--tag", "v1.7.0", "--tag", "v1.7.1", "--releases-dir", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "release-packages: FAIL" in err
    assert "v1.7.1: no release package" in err
    assert "step 7" in err


def test_a_tag_before_the_site_existed_is_not_asked_for_a_package(tmp_path):
    """The v0.1.x tags predate `site/` and the capture script; the guard's first run on the
    real tag list failed on all four of them, which would have kept main red forever."""
    assert guard.package_problems("v0.1.4", releases=tmp_path) == []
    assert guard.package_problems("v1.0.0", releases=tmp_path) != []
