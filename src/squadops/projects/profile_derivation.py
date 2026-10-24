"""Deriving a repository-backed product's development profile (SIP-0112 H.4; contract 8, H.6).

When the inherited baseline is captured, the profile is read from three things and nothing else:
- the tree at the configuration's validated commit;
- the Development Configuration revision, whose checks say which runners and lint tools the
  product uses and how each is run;
- the baseline, which says which checks ran, and which couldn't for want of a toolchain or an
  environment.

It reads what the product declares and never guesses past it:
- a check whose command names no runner or lint tool this recognises is left as a check: it's
  still run and read, and it simply isn't a runner;
- what the squad can't serve is named as a gap, with what it stops (H.6), never filled in.
"""

from __future__ import annotations

import configparser
import json
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from squadops.projects.baseline import UNVERIFIED, CheckResult, InheritedBaseline, toolchain_missing
from squadops.projects.derived_profile import (
    BLOCKING,
    DISCLOSED,
    DerivedProfile,
    Gap,
    Language,
    Lint,
    Runner,
    Surface,
    Toolchain,
)
from squadops.sandbox.findings import PYTEST
from squadops.stacks.scaffold import InterfaceManifest

if TYPE_CHECKING:
    from squadops.projects.development_configuration import Check, DevelopmentConfiguration
    from squadops.projects.initialization import ProjectInitialization

#: Directories a product's tree may hold that are never its own source.
_NOT_SOURCE = frozenset({"node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".git"})
_PYTHON_MANIFESTS = ("pyproject.toml", "setup.py", "setup.cfg", "Pipfile")
_PYTHON_LOCKS = {"uv.lock": "uv", "poetry.lock": "poetry", "Pipfile.lock": "pipenv"}
_NODE_LOCKS = {"pnpm-lock.yaml": "pnpm", "yarn.lock": "yarn", "package-lock.json": "npm"}
_OTHER_MANIFESTS = {"go.mod": ("go", "go"), "Cargo.toml": ("rust", "cargo")}
_NODE_TOOLS = ("npm", "pnpm", "yarn")
_LINT_TOOLS = ("ruff", "flake8", "pylint", "mypy", "eslint", "tsc", "svelte-check", "biome")
_PYTEST_FILES = ("test_*.py", "*_test.py")
_JS_FILES = ("*.test.*", "*.spec.*")
_JS_SETUP = ("setupTests.", "vitest.setup.", "jest.setup.", "test-setup.")
#: A file named like a test by any runner this recognises, so one no runner owns is unclassed.
_TEST_LOOKING = (*_PYTEST_FILES, *_JS_FILES)
#: pytest's options that take their value as the next argument, so it's never read as a path.
_PYTEST_VALUED = frozenset(
    {
        "-p", "-k", "-m", "-c", "-o", "-W", "-n", "-r", "--rootdir", "--deselect", "--ignore",
        "--ignore-glob", "--tb", "--maxfail", "--junitxml", "--basetemp", "--confcutdir",
        "--log-level", "--durations",
    }
)  # fmt: skip


def derive_profile(
    files: Mapping[str, bytes],
    configuration: DevelopmentConfiguration,
    baseline: InheritedBaseline,
    *,
    initialization: ProjectInitialization | None = None,
) -> DerivedProfile:
    """The profile of the tree ``files`` (repository-relative paths, at the configuration's
    validated commit), under ``configuration`` and the ``baseline`` captured there."""
    tree = _Tree(files)
    commands = configuration.commands
    wd = commands.working_directory
    results = {r.id: r for r in baseline.checks}

    found: list[tuple[Check, _Found]] = []
    lint: list[Lint] = []
    for check in commands.checks:
        runner = _runner_of(check, tree, wd)
        if runner is not None:
            found.append((check, runner))
            continue
        tool = _lint_tool(check, tree, wd)
        if tool is not None:
            lint.append(Lint(check.id, tool, check.findings))
    runners = _runners(found, tree)
    owner = _owners(tree, runners)
    toolchains = _toolchains(commands.checks, results)
    python = _python_interpreter(commands.checks)
    return DerivedProfile(
        project_id=configuration.project_id,
        commit=configuration.validated_at_commit,
        development_configuration_revision=configuration.revision,
        environment_image=str(baseline.environment.get("image", "unknown")),
        languages=_languages(tree),
        runners=runners,
        lint=tuple(lint),
        toolchains=toolchains,
        start_declared=commands.start is not None,
        public_surfaces=_surfaces(tree, configuration, python),
        blueprint_stack=configuration.stack,
        client_routes=_client_routes(configuration, initialization),
        test_files=_test_globs(runners, owner),
        test_support_files=tuple(dict.fromkeys(f for r in runners for f in r.support_files)),
        gaps=_gaps(tree, configuration, results, runners, owner, lint, toolchains),
    )


# --- the tree ---


class _Tree:
    """The product's own tracked files, and what they declare."""

    def __init__(self, files: Mapping[str, bytes]) -> None:
        self.files = {
            p: b for p, b in files.items() if not _NOT_SOURCE & set(PurePosixPath(p).parts[:-1])
        }
        self.paths = sorted(self.files)
        self.dirs = {str(d) for p in self.paths for d in PurePosixPath(p).parents if str(d) != "."}

    def named(self, *names: str) -> list[str]:
        return [p for p in self.paths if PurePosixPath(p).name in names]

    def under(self, root: str) -> list[str]:
        return [p for p in self.paths if _within(p, root)]

    def text(self, path: str) -> str | None:
        data = self.files.get(path)
        if data is None:
            return None
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return None

    def json(self, path: str) -> dict[str, Any]:
        text = self.text(path)
        try:
            value = json.loads(text) if text is not None else {}
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    def toml(self, path: str) -> dict[str, Any]:
        text = self.text(path)
        try:
            return tomllib.loads(text) if text is not None else {}
        except tomllib.TOMLDecodeError:
            return {}

    def ini(self, path: str, section: str) -> Mapping[str, str]:
        text = self.text(path)
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read_string(text or "")
        except configparser.Error:
            return {}
        return parser[section] if parser.has_section(section) else {}


def _relative(path: str, root: str) -> PurePosixPath:
    return PurePosixPath(path) if root == "." else PurePosixPath(path).relative_to(root)


def _within(path: str, root: str) -> bool:
    return root == "." or PurePosixPath(path).is_relative_to(root)


def _join(wd: str, path: str) -> str:
    joined = PurePosixPath(wd) / path.removeprefix("./")
    return str(joined) if str(joined) != "" else "."


def _parent(path: str) -> str:
    return str(PurePosixPath(path).parent)


# --- runners ---


@dataclass(frozen=True)
class _Found:
    """One check's runner, before checks are grouped into runners."""

    runner: str
    root: str
    patterns: tuple[str, ...]
    suite: tuple[str, ...]
    single: tuple[str, ...] | None
    #: Which argv element names the file pattern (unittest's ``-p`` value), to unify a group's.
    pattern_at: int | None = None


def _runner_of(check: Check, tree: _Tree, wd: str) -> _Found | None:
    argv = check.argv
    names = [PurePosixPath(a).name for a in argv]
    module = _module(argv)
    if module == "unittest":
        return _unittest(argv, wd)
    if module == "pytest" or "pytest" in names:
        return _pytest(argv, tree, wd)
    script = _package_script(argv, tree, wd)
    if script is not None:
        prefix, text = script
        for kind in ("vitest", "jest"):
            if kind in text.split():
                extra = ("{path}",) if "--" in argv else ("--", "{path}")
                return _Found(kind, prefix, _JS_FILES, argv, (*argv, *extra))
        return None
    for kind in ("vitest", "jest"):
        if kind in names:
            return _Found(kind, wd, _JS_FILES, argv, (*argv, "{path}"))
    return None


def _module(argv: Sequence[str]) -> str | None:
    for i, arg in enumerate(argv[:-1]):
        if arg == "-m":
            return argv[i + 1]
    return None


def _option(argv: Sequence[str], *names: str) -> tuple[int, str] | None:
    """The index and value of the first of ``names`` in ``argv``, as ``-x V`` or ``--x=V``."""
    for i, arg in enumerate(argv):
        if arg in names and i + 1 < len(argv):
            return i + 1, argv[i + 1]
        for name in names:
            if name.startswith("--") and arg.startswith(f"{name}="):
                return i, arg
    return None


def _unittest(argv: tuple[str, ...], wd: str) -> _Found:
    start = _option(argv, "-s", "--start-directory")
    pattern = _option(argv, "-p", "--pattern")
    root = _join(wd, start[1].split("=", 1)[-1] if start else ".")
    if pattern is None:
        return _Found("unittest", root, ("test*.py",), argv, (*argv, "-p", "{name}"))
    at, value = pattern
    single = (*argv[:at], "{name}", *argv[at + 1 :])
    return _Found("unittest", root, (value,), argv, single, pattern_at=at)


def _pytest(argv: tuple[str, ...], tree: _Tree, wd: str) -> _Found:
    start = next(
        (i + 1 for i, a in enumerate(argv) if PurePosixPath(a).name == "pytest"),
        len(argv),
    )
    positional: list[int] = []
    skip = False
    for i in range(start, len(argv)):
        arg = argv[i]
        if skip:
            skip = False
        elif arg in _PYTEST_VALUED:
            skip = True
        elif not arg.startswith("-"):
            positional.append(i)
    paths = [_join(wd, argv[i].split("::", 1)[0]) for i in positional]
    roots = [
        p if p in tree.dirs else _parent(p) for p in paths if p in tree.dirs or p in tree.files
    ]
    config = _pytest_config(tree, wd)
    if not roots:
        roots = [_join(wd, p) for p in config.get("testpaths", "").split()] or [wd]
    patterns = tuple(config.get("python_files", "").split()) or _PYTEST_FILES
    rest = tuple(a for i, a in enumerate(argv) if i not in positional)
    single = (*rest, "{path}") if wd == "." else None
    return _Found("pytest", roots[0], patterns, argv, single)


def _pytest_config(tree: _Tree, wd: str) -> Mapping[str, str]:
    """pytest's ``testpaths`` and ``python_files``, from the file it reads them from."""
    pyproject = tree.toml(_join(wd, "pyproject.toml"))
    options = pyproject.get("tool", {}).get("pytest", {}).get("ini_options", {})
    if options:
        return {k: " ".join(v) if isinstance(v, list) else str(v) for k, v in options.items()}
    for name, section in (
        ("pytest.ini", "pytest"),
        ("tox.ini", "pytest"),
        ("setup.cfg", "tool:pytest"),
    ):
        found = tree.ini(_join(wd, name), section)
        if found:
            return found
    return {}


def _package_script(argv: tuple[str, ...], tree: _Tree, wd: str) -> tuple[str, str] | None:
    """For ``npm``, ``pnpm`` or ``yarn`` running a package script: its directory and its text."""
    if not argv or PurePosixPath(argv[0]).name not in _NODE_TOOLS:
        return None
    prefix, name, i = wd, None, 1
    while i < len(argv):
        arg = argv[i]
        if arg in ("--prefix", "-C", "--dir", "--cwd") and i + 1 < len(argv):
            prefix, i = _join(wd, argv[i + 1]), i + 2
            continue
        if arg == "--":
            break
        if not arg.startswith("-") and name is None:
            if arg in ("run", "run-script"):
                name = next((a for a in argv[i + 1 :] if not a.startswith("-")), None)
                break
            name = "test" if arg in ("test", "t") else arg
        i += 1
    scripts = tree.json(_join(prefix, "package.json")).get("scripts") or {}
    text = scripts.get(name) if name else None
    return (prefix, text) if isinstance(text, str) else None


def _runners(found: list[tuple[Check, _Found]], tree: _Tree) -> tuple[Runner, ...]:
    """The checks grouped by runner and root, in the configuration's order: one runner for each
    file pattern its tests are named by."""
    groups: dict[tuple[str, str], list[tuple[Check, _Found]]] = {}
    for check, f in found:
        groups.setdefault((f.runner, f.root), []).append((check, f))
    runners: list[Runner] = []
    for (kind, root), members in groups.items():
        first = members[0][1]
        checks = tuple(c.id for c, _ in members)
        suite, single, patterns = first.suite, first.single, first.patterns
        if kind == "unittest" and len({f.patterns for _, f in members}) > 1:
            pattern = _unified([p for _, f in members for p in f.patterns])
            if first.pattern_at is not None:
                at = first.pattern_at
                suite = (*suite[:at], pattern, *suite[at + 1 :])
            patterns = (pattern,)
        under = tree.under(root)
        present = [p for p in patterns if any(fnmatch(PurePosixPath(f).name, p) for f in under)]
        for pattern in present or patterns[:1]:
            runners.append(
                Runner(
                    runner=kind,
                    checks=checks,
                    covers=_covers(kind, root, tree, patterns),
                    roots=(root,),
                    file_pattern=pattern,
                    suite_argv=suite,
                    single_file_argv=single,
                    test_ids=PYTEST if kind == "pytest" else None,
                    support_files=_support(kind, root, tree),
                )
            )
    return tuple(runners)


def _owners(tree: _Tree, runners: Sequence[Runner]) -> dict[str, Runner]:
    """Each test file's runner: the first that holds it (``DerivedProfile.runner_for``'s rule)."""
    owners = {}
    for path in tree.paths:
        runner = next((r for r in runners if r.holds(path)), None)
        if runner is not None:
            owners[path] = runner
    return owners


def _unified(names: Sequence[str]) -> str:
    """One glob for a group's file names: their common prefix and suffix around a ``*``."""
    prefix = _common(names)
    suffix = _common([n[len(prefix) :][::-1] for n in names])[::-1]
    return f"{prefix}*{suffix}"


def _common(names: Sequence[str]) -> str:
    shortest = min(names, key=len)
    for i, char in enumerate(shortest):
        if any(n[i] != char for n in names):
            return shortest[:i]
    return shortest


def _covers(kind: str, root: str, tree: _Tree, patterns: tuple[str, ...]) -> tuple[str, ...]:
    """The product paths a runner's tests exercise: a JavaScript runner's package, or the Python
    packages outside its test files."""
    if kind not in ("pytest", "unittest"):
        return ("**",) if root == "." else (f"{root}/**",)

    def tests_only(d: str) -> bool:
        python = [p for p in tree.under(d) if p.endswith(".py")]
        names = [PurePosixPath(p).name for p in python]
        return all(n == "conftest.py" or any(fnmatch(n, x) for x in patterns) for n in names)

    tops = sorted(
        {PurePosixPath(p).parts[0] for p in tree.paths if len(PurePosixPath(p).parts) > 1}
    )
    packages = [d for d in tops if f"{d}/__init__.py" in tree.files]
    packages += [
        f"src/{d}"
        for d in sorted({PurePosixPath(p).parts[1] for p in tree.under("src") if p.count("/") > 1})
        if f"src/{d}/__init__.py" in tree.files
    ]
    product = [d for d in packages if not tests_only(d)]
    if not product:
        product = [
            d for d in tops if any(p.endswith(".py") for p in tree.under(d)) and not tests_only(d)
        ]
    return tuple(f"{d}/**" for d in product) or ("**",)


def _support(kind: str, root: str, tree: _Tree) -> tuple[str, ...]:
    under = tree.under(root)
    if kind == "pytest":
        return tuple(p for p in tree.named("conftest.py") if p in under or "/" not in p)
    if kind in ("vitest", "jest"):
        return tuple(p for p in under if PurePosixPath(p).name.startswith(_JS_SETUP))
    return ()


def _test_globs(runners: Sequence[Runner], owner: Mapping[str, Runner]) -> tuple[str, ...]:
    """Where the tree's test files are, as globs on the whole path: each runner's root and pattern,
    and that pattern nested under its root where its tests are nested."""
    globs: list[str] = []
    for r in runners:
        (root,) = r.roots
        owned = [p for p, o in owner.items() if o is r]
        direct = f"{root}/{r.file_pattern}" if root != "." else r.file_pattern
        nested = f"{root}/**/{r.file_pattern}" if root != "." else f"**/{r.file_pattern}"
        depth = {len(_relative(p, root).parts) for p in owned}
        if not owned or 1 in depth:
            globs.append(direct)
        if any(d > 1 for d in depth):
            globs.append(nested)
    return tuple(dict.fromkeys(globs))


def _lint_tool(check: Check, tree: _Tree, wd: str) -> str | None:
    words = [PurePosixPath(a).name for a in check.argv]
    script = _package_script(check.argv, tree, wd)
    if script is not None:
        words += script[1].split()
    module = _module(check.argv)
    if module:
        words.append(module)
    return next((t for t in _LINT_TOOLS if t in words), None)


# --- toolchains, languages, surfaces ---


def _toolchains(
    checks: Sequence[Check], results: Mapping[str, CheckResult]
) -> tuple[Toolchain, ...]:
    """Each check's command, and whether the baseline's image had it: read from the baseline's
    own evidence, never from a stack's environment contract."""
    needed: dict[str, list[str]] = {}
    for check in checks:
        needed.setdefault(PurePosixPath(check.argv[0]).name, []).append(check.id)
    return tuple(
        Toolchain(
            name=name,
            required_by=tuple(ids),
            available=not any(c in results and toolchain_missing(results[c]) for c in ids),
        )
        for name, ids in needed.items()
    )


def _python_interpreter(checks: Sequence[Check]) -> str:
    for check in checks:
        if PurePosixPath(check.argv[0]).name.startswith("python"):
            return check.argv[0]
    return "python3"


def _languages(tree: _Tree) -> tuple[Language, ...]:
    languages: list[Language] = []
    python = [
        p
        for p in tree.paths
        if PurePosixPath(p).name in _PYTHON_MANIFESTS
        or fnmatch(PurePosixPath(p).name, "requirements*.txt")
    ]
    if python or any(p.endswith(".py") for p in tree.paths):
        locks = [m for lock, m in _PYTHON_LOCKS.items() if tree.named(lock)]
        manager = locks[0] if locks else ("pip" if python else None)
        languages.append(Language("python", manager, tuple(python)))
    node = tree.named("package.json")
    if node:
        typed = tree.named("tsconfig.json") or any(p.endswith((".ts", ".tsx")) for p in tree.paths)
        locks = [m for lock, m in _NODE_LOCKS.items() if tree.named(lock)]
        languages.append(
            Language(
                "typescript" if typed else "javascript", locks[0] if locks else "npm", tuple(node)
            )
        )
    for manifest, (language, manager) in _OTHER_MANIFESTS.items():
        if tree.named(manifest):
            languages.append(Language(language, manager, tuple(tree.named(manifest))))
    return tuple(languages)


def _surfaces(
    tree: _Tree, configuration: DevelopmentConfiguration, python: str
) -> tuple[Surface, ...]:
    """The public surfaces a criterion may assert on (§24bv point 5): the start declaration's
    base URLs, copied from contract 7; the product's command-line entry points; its packages."""
    surfaces: list[Surface] = []
    start = configuration.commands.start
    for entry in start.entry_points if start else ():
        if entry.kind in ("http_base", "ui_base"):
            surfaces.append(Surface(entry.kind, url=entry.url))
    pyproject = tree.toml("pyproject.toml")
    for name in pyproject.get("project", {}).get("scripts", {}) or {}:
        surfaces.append(Surface("command", argv=(name,)))
    packages = _python_packages(tree)
    for package in packages:
        if f"{package}/__main__.py" in tree.files:
            surfaces.append(Surface("command", argv=(python, "-m", PurePosixPath(package).name)))
    node = tree.json("package.json")
    bins = node.get("bin")
    for name in (
        bins if isinstance(bins, dict) else ([node["name"]] if bins and node.get("name") else [])
    ):
        surfaces.append(Surface("command", argv=(str(name),)))
    surfaces += [Surface("package", name=PurePosixPath(p).name) for p in packages]
    if node.get("name") and not node.get("private"):
        surfaces.append(Surface("package", name=str(node["name"])))
    return tuple(surfaces)


def _python_packages(tree: _Tree) -> list[str]:
    tops = sorted({PurePosixPath(p).parts[0] for p in tree.paths if "/" in p})
    found = [d for d in tops if f"{d}/__init__.py" in tree.files and d not in ("tests", "test")]
    src = sorted({PurePosixPath(p).parts[1] for p in tree.under("src") if p.count("/") > 1})
    return found + [f"src/{d}" for d in src if f"src/{d}/__init__.py" in tree.files]


def _client_routes(
    configuration: DevelopmentConfiguration, initialization: ProjectInitialization | None
) -> tuple[str, ...] | None:
    """A blueprint's client routes, from the manifest its Project was initialized from."""
    if configuration.stack is None:
        return None
    if initialization is None:
        return ()
    manifest = InterfaceManifest.from_yaml(initialization.manifest)
    return tuple(r.path for r in manifest.frontend.routes)


# --- gaps ---


def _gaps(
    tree: _Tree,
    configuration: DevelopmentConfiguration,
    results: Mapping[str, CheckResult],
    runners: Sequence[Runner],
    owner: Mapping[str, Runner],
    lint: Sequence[Lint],
    toolchains: Sequence[Toolchain],
) -> tuple[Gap, ...]:
    """Each gap, in H.6's table's order."""
    checks = configuration.commands.checks
    gaps: list[Gap] = []
    ran = [c.id for c in checks if c.id in results and results[c.id].result != UNVERIFIED]
    if not ran:
        why = "none is declared" if not checks else "every declared check is UNVERIFIED"
        gaps.append(
            Gap(
                "no_check_ran",
                BLOCKING,
                None,
                ("**",),
                f"no check ran at the baseline: {why}",
                "a check the sandbox can run, declared in the Development Configuration",
            )
        )
    for toolchain in toolchains:
        if not toolchain.available:
            gaps.append(_toolchain_gap(toolchain, runners, ran))
    unowned = [
        p
        for p in tree.paths
        if p not in owner and any(fnmatch(PurePosixPath(p).name, t) for t in _TEST_LOOKING)
    ]
    if unowned:
        dirs = tuple(dict.fromkeys(f"{_parent(p)}/**" if "/" in p else "**" for p in unowned))
        gaps.append(
            Gap(
                "test_files_unclassed",
                BLOCKING,
                None,
                dirs,
                f"{len(unowned)} files named as tests belong to no runner: {', '.join(unowned[:3])}"
                + ("…" if len(unowned) > 3 else ""),
                "a check that runs them, declared in the Development Configuration",
            )
        )
    for check in checks:
        result = results.get(check.id)
        reason = result.reason if result is not None else None
        if reason is not None and reason.startswith("environment gap:"):
            names = _names(
                reason.removeprefix("environment gap: ").removesuffix(" is not set").split(", ")
            )
            gaps.append(
                Gap(
                    "missing_environment",
                    DISCLOSED,
                    check.id,
                    ("**",),
                    f"check {check.id} needs {names}, which the checks' environment doesn't provide, "
                    "so it reads UNVERIFIED",
                    f"{names} provided to the checks' environment",
                )
            )
    if configuration.commands.start is None:
        gaps.append(
            Gap(
                "no_start_declaration",
                DISCLOSED,
                None,
                ("**",),
                "the Development Configuration declares no start (contract 7), so Outcome "
                "Evaluation reads every scenario blocked_unverified",
                "a start declaration in the Development Configuration",
            )
        )
    gaps += _untested(tree, runners)
    gaps += _unscopable(runners, owner)
    for kind in dict.fromkeys(r.runner for r in runners if r.test_ids is None):
        gaps.append(
            Gap(
                "no_test_id_reader",
                DISCLOSED,
                kind,
                ("**",),
                f"no findings reader names {kind}'s tests one by one, so each criterion is read by "
                "its own test file's result",
                f"a {kind} reader in squadops.sandbox.findings",
            )
        )
    for entry in lint:
        if entry.findings is None:
            gaps.append(
                Gap(
                    "lint_without_reader",
                    DISCLOSED,
                    entry.check,
                    ("**",),
                    f"lint check {entry.check} ({entry.tool}) declares no findings reader, so a "
                    "failure on both sides is compared whole",
                    "a findings reader declared on the check (H.5)",
                )
            )
    return tuple(gaps)


def _toolchain_gap(toolchain: Toolchain, runners: Sequence[Runner], ran: Sequence[str]) -> Gap:
    """Blocking when the runners that need it leave their paths no other runner able to run."""
    needing = [r for r in runners if set(r.checks) & set(toolchain.required_by)]
    covers = tuple(dict.fromkeys(c for r in needing for c in r.covers))
    others = [r for r in runners if r not in needing and set(r.checks) & set(ran)]
    served = any(_overlaps(a, b) for a in covers for r in others for b in r.covers)
    blocking = bool(covers) and not served
    checks = ", ".join(toolchain.required_by)
    return Gap(
        "missing_toolchain",
        BLOCKING if blocking else DISCLOSED,
        toolchain.name,
        covers if blocking else ("**",),
        f"{toolchain.name} isn't in the sandbox's image, so {checks} can't run",
        f"{toolchain.name} in the sandbox's image",
    )


def _untested(tree: _Tree, runners: Sequence[Runner]) -> list[Gap]:
    """Each part of the tree with a manifest of its own that no runner's tests cover."""
    manifests = [
        p
        for p in tree.paths
        if PurePosixPath(p).name in ("package.json", *_PYTHON_MANIFESTS, *_OTHER_MANIFESTS)
    ]
    dirs = dict.fromkeys(_parent(p) for p in manifests)
    covered = [c for r in runners for c in r.covers]
    gaps = []
    for d in dirs:
        if d == "." and runners:
            continue
        paths = ("**",) if d == "." else (f"{d}/**",)
        if not any(_overlaps(paths[0], c) for c in covered):
            where = "the product" if d == "." else f"{d}/"
            gaps.append(
                Gap(
                    "no_test_runner",
                    DISCLOSED,
                    None,
                    paths,
                    f"no runner's tests cover {where}, so the squad's changes there are verified by "
                    "the product's checks alone",
                    f"a check that runs {where}'s tests, declared in the Development Configuration",
                )
            )
    return gaps


def _unscopable(runners: Sequence[Runner], owner: Mapping[str, Runner]) -> list[Gap]:
    gaps: dict[str, Gap] = {}
    for r in runners:
        names = [PurePosixPath(p).name for p, o in owner.items() if o.runner == r.runner]
        if r.single_file_argv is None:
            why = f"{r.runner}'s command can't be scoped to one test file"
        elif any("{name}" in a for a in r.single_file_argv) and len(names) != len(set(names)):
            why = f"{r.runner}'s one-file command names a file by its name, and two of its files share one"
        else:
            continue
        gaps.setdefault(
            r.runner,
            Gap(
                "runner_not_scopable",
                DISCLOSED,
                r.runner,
                ("**",),
                f"{why}, so a frozen criterion runs only as part of the whole suite",
                "a one-file command that names the file by its path",
            ),
        )
    return list(gaps.values())


def _overlaps(a: str, b: str) -> bool:
    if "**" in (a, b):
        return True
    a, b = a.removesuffix("/**"), b.removesuffix("/**")
    return _within(a, b) or _within(b, a)


def _names(names: Iterable[str]) -> str:
    names = list(names)
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"
