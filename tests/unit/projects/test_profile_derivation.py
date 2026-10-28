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
    "frontend/package.json": (
        b'{"name": "shelfnote-frontend", "private": true, "scripts": {"test": "vitest run"},'
        b' "devDependencies": {"vitest": "^2.1.9"}}'
    ),
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
        "npm", "--prefix", "frontend", "test", "--silent", "--", "{name}"
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
    # #2757 (SIP-0109 §24ci (a)): vitest's tests are named one by one, as pytest's are.
    assert (pytest_runner.test_ids, vitest.test_ids) == ("pytest", "vitest")
    assert _gaps(profile) == [("no_start_declaration", "disclosed", None, ("**",))]


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
            {**_SHELFNOTE, "frontend/src/a.test.jsx": b"", "frontend/src/data.test.jsx": b""},
            _SHELFNOTE_CHECKS, {},
            ("runner_not_scopable", "disclosed", "vitest", ("**",)),
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
        "a name filter that selects another file too",
        "a lint with no findings reader",
    ],
)  # fmt: skip
def test_each_gap_is_named_with_its_kind_and_the_paths_it_applies_to(
    files, checks, results, expected
):
    profile = derive_profile(files, _configuration(checks), _baseline(checks, **results))

    assert expected in _gaps(profile)


_PKG = b'{"name": "%s", "private": true, "scripts": {"test": "%s"}%s}'
_V2 = b', "devDependencies": {"vitest": "^2.1.9"}'
_NPM = ("npm", "--prefix", "frontend", "test", "--silent")
_TAIL = (
    ", so a criterion's discrimination is unread and it isn't accepted as discriminating "
    "(SIP-0109 §24ci (a))"
)


def _vitest_profile(script, deps, argv=_NPM, extra=None):
    files = {
        **_SHELFNOTE,
        "frontend/package.json": _PKG % (b"shelfnote-frontend", script.encode(), deps),
        **(extra or {}),
    }
    checks = (*_SHELFNOTE_CHECKS[:2], Check("frontend_tests", argv))
    configuration = _configuration(checks, stack="fullstack_fastapi_react")
    return derive_profile(files, configuration, _baseline(checks))


@pytest.mark.parametrize(
    ("script", "deps", "argv", "extra", "why"),
    [
        # Specs that allow vitest 2 alone keep the reader.
        ("vitest run", _V2, _NPM, None, None),
        ("vitest run", b', "dependencies": {"vitest": "~2.0.5"}', _NPM, None, None),
        ("vitest run", b', "devDependencies": {"vitest": "2.1.9"}', _NPM, None, None),
        ("vitest run", b', "devDependencies": {"vitest": "2.x"}', _NPM, None, None),
        # Another major, or a spec that admits one, is refused.
        ("vitest run", b', "devDependencies": {"vitest": "1.6.0"}', _NPM, None,
         "its package's vitest '1.6.0' allows more than vitest 2, the major the reader is validated on"),
        ("vitest run", b', "devDependencies": {"vitest": ">=2.0.0"}', _NPM, None,
         "its package's vitest '>=2.0.0' allows more than vitest 2, the major the reader is validated on"),
        ("vitest run", b', "devDependencies": {"vitest": "2.1.9 || ^3.0.0"}', _NPM, None,
         "its package's vitest '2.1.9 || ^3.0.0' allows more than vitest 2, the major the reader is validated on"),
        ("vitest run", b', "devDependencies": {"vitest": ">=2 <4"}', _NPM, None,
         "its package's vitest '>=2 <4' allows more than vitest 2, the major the reader is validated on"),
        ("vitest run", b', "devDependencies": {"vitest": "npm:vitest@2.1.9"}', _NPM, None,
         "its package's vitest 'npm:vitest@2.1.9' allows more than vitest 2, the major the reader is validated on"),
        ("vitest run", b"", _NPM, None,
         "no package.json at its root or the repository's declares a vitest version"),
        # The command as run, the script and what the configured argv forwards to it.
        ("vitest run --reporter=dot", _V2, _NPM, None, "its test command names a reporter"),
        ("vitest run", _V2, ("npm", "--prefix", "frontend", "test", "--", "--reporter=dot"), None,
         "its test command names a reporter"),
        ("vitest run", _V2, ("yarn", "--cwd", "frontend", "test", "--reporter=dot"), None,
         "its test command names a reporter"),
        ("vitest run 2>&1", _V2, _NPM, None, "its test command merges stderr into stdout"),
        # Configs: the conventional ones, the one --config names, and a workspace.
        ("vitest run", _V2, _NPM,
         {"frontend/vitest.config.ts": b"export default { test: { reporters: ['junit'] } }"},
         "frontend/vitest.config.ts configures reporters"),
        ("vitest run --config testing/custom.ts", _V2, _NPM,
         {"frontend/testing/custom.ts": b"export default { test: { reporters: ['dot'] } }"},
         "frontend/testing/custom.ts configures reporters"),
        ("vitest run --config=testing/missing.ts", _V2, _NPM, None,
         "its --config testing/missing.ts isn't in the tree, so its reporters can't be read"),
        ("vitest run", _V2, _NPM, {"frontend/vitest.workspace.ts": b"export default []"},
         "frontend/vitest.workspace.ts sets its projects, whose reporters aren't read"),
    ],
    ids=["^2", "~2 in dependencies", "exact 2", "2.x", "another major", "open-ended",
         "an alternative major", "a range across majors", "an alias", "no version",
         "a reporter in the script", "a reporter forwarded by npm", "a reporter forwarded by yarn",
         "stderr merged", "a reporters config", "a --config naming reporters",
         "a --config not in the tree", "a workspace"],
)  # fmt: skip
def test_vitest_is_given_its_reader_only_where_the_products_output_is_what_it_reads(
    script, deps, argv, extra, why
):
    """SIP-0112 H.10's blind spot (the MacBook lane's G4 on #2764; the second review of #2769).
    Bug caught: the reader given by the runner's kind or by the script's text alone, so a product
    on a spec admitting another vitest major, a forwarded or configured reporter, or stderr merged
    into stdout shows nothing at capture and every criterion reads blocked_unverified at its first
    increment, instead of the gap naming why here."""
    profile = _vitest_profile(script, deps, argv, extra)

    vitest = next(r for r in profile.runners if r.runner == "vitest")
    gaps = [g for g in profile.gaps if g.id == "no_test_id_reader" and g.subject == "vitest"]
    if why is None:
        assert (vitest.test_ids, gaps) == ("vitest", [])
    else:
        assert vitest.test_ids is None
        assert [(g.paths, g.reason, g.closes_by) for g in gaps] == [
            (
                ("frontend/**",),
                f"vitest's reader can't read this product's output under frontend: {why}" + _TAIL,
                "vitest 2 run with its default reporter, its stderr apart",
            )
        ]


def test_each_vitest_runner_is_read_on_its_own_output_and_its_gap_is_confined_to_it():
    """The second review's P2. Bug caught: the refusal keyed by the runner's kind, so with two vitest
    packages one's reason overwrites the other's, a compatible one loses its reader, or the gap reads
    unconfined instead of naming the package it is about."""
    files = {
        **_SHELFNOTE,
        "frontend/package.json": _PKG % (b"shelfnote-frontend", b"vitest run", _V2),
        "admin/package.json": _PKG
        % (b"shelfnote-admin", b"vitest run", b', "devDependencies": {"vitest": "1.6.0"}'),
        "admin/src/Admin.jsx": b"",
        "admin/src/Admin.test.jsx": b"",
    }
    checks = (
        *_SHELFNOTE_CHECKS,
        Check("admin_tests", ("npm", "--prefix", "admin", "test", "--silent")),
    )
    configuration = _configuration(checks, stack="fullstack_fastapi_react")

    profile = derive_profile(files, configuration, _baseline(checks))

    readers = {r.roots: r.test_ids for r in profile.runners if r.runner == "vitest"}
    assert readers == {("frontend",): "vitest", ("admin",): None}
    assert [(g.paths, g.reason) for g in profile.gaps if g.id == "no_test_id_reader"] == [
        (
            ("admin/**",),
            "vitest's reader can't read this product's output under admin: its package's vitest "
            "'1.6.0' allows more than vitest 2, the major the reader is validated on" + _TAIL,
        )
    ]
