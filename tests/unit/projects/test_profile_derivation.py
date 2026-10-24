"""Deriving a repository-backed product's development profile (SIP-0112 H.4; contract 8, H.6).

The derivation reads the tree, the Development Configuration and the inherited baseline, and
nothing else. Tally's recorded profile is what it reads from the shared fixture. The two other
shapes are the 2.5 demonstrations' products, as their configurations on the Mac declare them:
continuum (pytest over a src layout, a lint with its reader, web packages with no tests) and
shelfnote (pytest at the root and vitest in its frontend, on a blueprint).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadops.projects.baseline import (
    FAIL,
    PASS,
    UNVERIFIED,
    CheckResult,
    InheritedBaseline,
    parse_baseline,
)
from squadops.projects.development_configuration import (
    Check,
    Commands,
    DevelopmentConfiguration,
    parse_configuration,
)
from squadops.projects.initialization import ProjectInitialization
from squadops.projects.profile_derivation import derive_profile
from tests.fixtures.shared_contract.repository import product_files, recorded

_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMMIT = "a" * 40
_NOT_FOUND = "its command was not found in the sandbox's image"

_CONTINUUM = {
    "pyproject.toml": b'[project]\nname = "continuum"\n[project.scripts]\ncontinuum = "continuum.cli:main"\n',
    "src/continuum/__init__.py": b"",
    "src/continuum/cli.py": b"",
    "tests/conftest.py": b"",
    "tests/test_cli.py": b"",
    "tests/visual/test_pages.py": b"",
    "web/package.json": b'{"name": "continuum-web", "private": true, "scripts": {"check": "svelte-check"}}',
    "web/src/App.svelte": b"",
    "plugins/chat/ui/package.json": b'{"name": "chat-ui", "private": true, "scripts": {"build": "vite build"}}',
}
_CONTINUUM_CHECKS = (
    Check("tests", (".venv/bin/python", "-m", "pytest", "tests", "-q", "--ignore=tests/visual",
                    "-p", "no:cacheprovider")),
    Check("lint", (".venv/bin/ruff", "check", "src", "tests"), findings="ruff"),
)  # fmt: skip
_SHELFNOTE = {
    "backend/__init__.py": b"",
    "backend/main.py": b"",
    "backend/requirements.txt": b"fastapi\n",
    "conftest.py": b"",
    "tests/test_books_api.py": b"",
    "frontend/package.json": b'{"name": "shelfnote-frontend", "private": true, "scripts": {"test": "vitest run"}}',
    "frontend/package-lock.json": b"{}",
    "frontend/src/App.jsx": b"",
    "frontend/src/App.test.jsx": b"",
    "frontend/src/setupTests.js": b"",
}
_SHELFNOTE_CHECKS = (
    Check("boots", (".venv/bin/python", "-c", "from backend.main import app")),
    Check("backend_tests", (".venv/bin/python", "-m", "pytest", "-q", "-p", "no:cacheprovider")),
    Check("frontend_tests", ("npm", "--prefix", "frontend", "test", "--silent")),
)


def _configuration(checks, *, stack=None) -> DevelopmentConfiguration:
    return DevelopmentConfiguration(
        project_id="prj-x",
        revision=3,
        validated_at_commit=_COMMIT,
        project_type="service",
        target="python",
        stack=stack,
        commands=Commands(working_directory=".", checks=tuple(checks), start=None),
        instruction_sources=(),
    )


def _baseline(checks, **results) -> InheritedBaseline:
    """Every check PASS unless ``results`` names it: a result, or (UNVERIFIED, its reason)."""
    rows = []
    for check in checks:
        result = results.get(check.id, PASS)
        verdict, reason = result if isinstance(result, tuple) else (result, None)
        rows.append(CheckResult(check.id, verdict, reason=reason))
    return InheritedBaseline("prj-x", _COMMIT, 3, {"image": "py3.12-node20"}, tuple(rows))


def _gaps(profile) -> list[tuple[str, str, str | None, tuple[str, ...]]]:
    return [(g.id, g.kind, g.subject, g.paths) for g in profile.gaps]


def test_the_shared_fixtures_recorded_profile_is_what_the_derivation_reads_from_tally():
    """The contract's recording and the derivation agree. Bugs caught: a recorded field the
    derivation never fills, a gap it names differently, or a rule that drifts from H.6's text."""
    profile = derive_profile(
        product_files(),
        parse_configuration(recorded("development_configuration", "valid")),
        parse_baseline(recorded("inherited_baseline", "valid")),
    )

    assert profile.to_document() == recorded("derived_profile", "valid")


def test_continuum_tests_with_pytest_over_its_src_layout_and_its_web_packages_have_no_tests():
    profile = derive_profile(
        _CONTINUUM, _configuration(_CONTINUUM_CHECKS), _baseline(_CONTINUUM_CHECKS, tests=FAIL)
    )

    (runner,) = profile.runners
    assert (runner.runner, runner.roots, runner.file_pattern, runner.covers) == (
        "pytest", ("tests",), "test_*.py", ("src/continuum/**",)
    )  # fmt: skip
    # The positional root is dropped from the one-file command, and -p's value kept.
    assert runner.single_file_argv == (
        ".venv/bin/python", "-m", "pytest", "-q", "--ignore=tests/visual", "-p", "no:cacheprovider",
        "{path}",
    )  # fmt: skip
    assert (runner.test_ids, runner.support_files) == ("pytest", ("tests/conftest.py",))
    # tests/visual is ignored by the command but still pytest's: it's a test, not the product's.
    assert profile.runner_for("tests/visual/test_pages.py") is runner
    assert profile.test_files == ("tests/test_*.py", "tests/**/test_*.py")
    assert [(x.check, x.tool, x.findings) for x in profile.lint] == [("lint", "ruff", "ruff")]
    assert [s.to_document() for s in profile.public_surfaces] == [
        {"kind": "command", "argv": ["continuum"]},
        {"kind": "package", "name": "continuum"},
    ]
    assert _gaps(profile) == [
        ("no_start_declaration", "disclosed", None, ("**",)),
        ("no_test_runner", "disclosed", None, ("plugins/chat/ui/**",)),
        ("no_test_runner", "disclosed", None, ("web/**",)),
    ]


def test_shelfnote_runs_pytest_at_its_root_and_vitest_through_its_frontends_npm_script():
    manifest = (_REPO_ROOT / "examples/03_group_run/interface_manifest.yaml").read_text()
    initialization = ProjectInitialization(
        "prj-x", _COMMIT, "main", "fullstack_fastapi_react", "sha256:x", manifest, (), "owner",
        datetime(2026, 10, 20, tzinfo=UTC),
    )  # fmt: skip
    configuration = _configuration(_SHELFNOTE_CHECKS, stack="fullstack_fastapi_react")

    profile = derive_profile(
        _SHELFNOTE, configuration, _baseline(_SHELFNOTE_CHECKS), initialization=initialization
    )

    pytest_runner, vitest = profile.runners
    assert [(r.runner, r.checks, r.roots, r.file_pattern, r.covers) for r in profile.runners] == [
        ("pytest", ("backend_tests",), (".",), "test_*.py", ("backend/**",)),
        ("vitest", ("frontend_tests",), ("frontend",), "*.test.*", ("frontend/**",)),
    ]
    assert vitest.single_file_argv == (
        "npm", "--prefix", "frontend", "test", "--silent", "--", "{path}"
    )  # fmt: skip
    assert profile.runner_for("frontend/src/App.test.jsx") is vitest
    assert profile.runner_for("tests/test_books_api.py") is pytest_runner
    assert profile.test_files == ("**/test_*.py", "frontend/**/*.test.*")
    assert profile.test_support_files == ("conftest.py", "frontend/src/setupTests.js")
    assert [(x.name, x.package_manager) for x in profile.languages] == [
        ("python", "pip"),
        ("javascript", "npm"),
    ]
    assert (profile.blueprint_stack, profile.client_routes) == (
        "fullstack_fastapi_react",
        ("/", "/create", "/runs/:id"),
    )
    assert _gaps(profile) == [
        ("no_start_declaration", "disclosed", None, ("**",)),
        ("no_test_id_reader", "disclosed", "vitest", ("**",)),
    ]


@pytest.mark.parametrize(
    ("files", "checks", "results", "expected"),
    [
        (
            _SHELFNOTE, _SHELFNOTE_CHECKS,
            {c.id: (UNVERIFIED, "timed out") for c in _SHELFNOTE_CHECKS},
            ("no_check_ran", "blocking", None, ("**",)),
        ),
        (
            _SHELFNOTE, _SHELFNOTE_CHECKS, {"frontend_tests": (UNVERIFIED, _NOT_FOUND)},
            ("missing_toolchain", "blocking", "npm", ("frontend/**",)),
        ),
        (
            _CONTINUUM, _CONTINUUM_CHECKS, {"lint": (UNVERIFIED, _NOT_FOUND)},
            ("missing_toolchain", "disclosed", "ruff", ("**",)),
        ),
        (
            {**_SHELFNOTE, "frontend/e2e/home.spec.ts": b""}, _SHELFNOTE_CHECKS[:2], {},
            ("test_files_unclassed", "blocking", None, ("frontend/e2e/**", "frontend/src/**")),
        ),
        (
            {**product_files(), "checks/more/check_parse.py": b""},
            parse_configuration(recorded("development_configuration", "valid")).commands.checks,
            {},
            ("runner_not_scopable", "disclosed", "unittest", ("**",)),
        ),
        (
            _CONTINUUM, (_CONTINUUM_CHECKS[0], Check("lint", ("ruff", "check", "src"))), {},
            ("lint_without_reader", "disclosed", "lint", ("**",)),
        ),
    ],
    ids=[
        "every check unverified",
        "the only runner over frontend/ lacks its toolchain",
        "a lint tool missing, with no runner needing it",
        "test files no runner owns",
        "a one-file command by name over two files of one name",
        "a lint with no findings reader",
    ],
)  # fmt: skip
def test_each_gap_is_named_with_its_kind_and_the_paths_it_applies_to(
    files, checks, results, expected
):
    profile = derive_profile(files, _configuration(checks), _baseline(checks, **results))

    assert expected in _gaps(profile)
