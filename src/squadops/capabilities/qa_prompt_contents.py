"""What a ``qa.test`` prompt shows of the task's ``artifact_contents`` (#2805).

The handler renders these files, and the composer counts them in the task's prompt budget
(``squadops.capabilities.prompt_budget``, SIP-0110 Appendix A §3.6), each through
:func:`qa_test_prompt_contents`. Counted apart, the composer measured the whole tree the task's
contract hands it (the accepted product, ``ACCEPTANCE_WORKSPACE_FILTER``) while the handler showed
one package of it. On a repository-backed product larger than about half its model's window, the
budget left for memory's sections read 0, and every ``qa.test`` was held on its binding.

The two prompt paths show different files, chosen as the handler chooses its path:

- **the focused prompt** (a plan's subtask, ``subtask_focus``) shows the top-level packages the
  task's expected artifacts live in, or every file when none is expected or none matches
  (:func:`package_scoped`), and, outside those packages, the code the suite calls
  (:func:`code_under_test`);
- **the monolithic prompt** shows the validation plan (:func:`validation_plan`, the handler's
  choice too) and the stack's source and support files (:func:`source_files`), which can include
  a ``conftest.py`` or an ``index.html``, never a file the stack names a test. A source file
  whose name carries the plan's is shown twice, as the plan and as a source, and counted twice.

**A known limit** (#2809): when the plan isn't in ``artifact_contents``, the handler loads it from
the vault (D3), and no estimate of ``artifact_contents`` sees it. Since #3118 a resolution is
refused past its limit rather than stopped short, so that is a plan the filter didn't select. ``qa.test``'s
own prompt guard (``prompt_guard._guard_prompt_size``) still refuses a prompt over the window by
name.

What the suite runs against is ``qa_run_tree``'s (#2815): these source and support files on a
sample application, and the product's tree on a repository-backed product.

Pure: no I/O and no handler imports, so the runtime's composer and the agent's handler both call
it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import PurePosixPath
from typing import Any

from squadops.campaigns.evaluator_trees import imported_paths
from squadops.capabilities.context_assembly import RETAKE_CURRENT_FILES_KEY
from squadops.capabilities.handlers.source_repository import source_backed
from squadops.cycles.structural_jsx import ECMASCRIPT_SUFFIXES
from squadops.stacks.development_profiles import (
    DevelopmentProfile,
    effective_development_profile,
    get_development_profile,
    matches_test_file_patterns,
)

#: The document the monolithic prompt shows as its validation plan: the first file whose name
#: carries this (:func:`validation_plan`).
VALIDATION_PLAN = "validation_plan"
#: The name the plan is counted under when a source file shown has its name: the prompt shows the
#: file twice, in the plan's own section and among the sources (#2809).
_PLAN_SECTION = "## Validation Plan"
#: The most of a file :func:`code_under_test` shows. A larger one, a vendored engine say, is named
#: with its size: a suite that imports it needn't cost the prompt the whole of it.
CODE_UNDER_TEST_MAX_CHARS = 16_000
#: #3182 (SIP-0112 H.39): the most of a repository-backed product's tree a ``qa.test`` prompt
#: shows, in characters. The 2.8 counted run's two ``qa.test`` prompts showed 18,478 and 19,330
#: characters of the product (4 and 5 files), of a tree of 2.36 million. The cap is five times
#: that: room for a suite with several files beside it, and a twenty-fifth of the tree.
PRODUCT_CONTENTS_MAX_CHARS = 96_000
#: The files whose imports :func:`code_under_test` reads.
_READS_IMPORTS = (".py", *ECMASCRIPT_SUFFIXES)
#: A file that is its folder's module: Luau's and Python's.
_PACKAGE_MODULES = ("init", "__init__")
#: What joins a module path's parts in a task's text: a dot, or the `` > `` a game's own comments
#: write between the instances of its tree.
_MODULE_SEPARATOR = r"(?:\.|\s*>\s*)"


def qa_test_prompt_contents(inputs: Mapping[str, Any]) -> dict[str, str]:
    """The files a ``qa.test`` prompt shows of ``inputs["artifact_contents"]``, by name, on the
    path the inputs select: the focused prompt's packages (which the handler renders through this
    function), or the monolithic prompt's validation plan and source files, each chosen as the
    handler chooses it. A plan that is also a source file shown is counted twice, as it is shown
    twice: once under its section's name (#2809)."""
    contents = inputs.get("artifact_contents") or {}
    if inputs.get("subtask_focus") is not None:
        expected = inputs.get("expected_artifacts") or []
        on_a_product = source_backed(inputs)
        scoped = (
            product_scoped(contents, expected, product_runners(inputs))
            if on_a_product
            else package_scoped(contents, expected)
        )
        suite = {**scoped, **(inputs.get(RETAKE_CURRENT_FILES_KEY) or {})}
        under_test = code_under_test(
            suite,
            contents,
            _task_text(inputs),
            plan_sources=inputs.get("implementation_artifacts") or (),
        )
        if on_a_product:
            return within_the_product_cap(scoped, under_test, {str(e) for e in expected if e})
        return {**scoped, **under_test}
    profile = get_development_profile(effective_development_profile(inputs.get("resolved_config")))
    sources = source_files(contents, profile)
    plan = _validation_plan_file(contents)
    if plan is None:
        return sources
    name, content = plan
    return {(_PLAN_SECTION if name in sources else name): content, **sources}


def validation_plan(artifact_contents: Mapping[str, str]) -> str | None:
    """The monolithic prompt's validation plan: the first file, in the contents' order, whose name
    carries ``VALIDATION_PLAN``; ``None`` when none does (the handler then tries the vault). The
    one rule, for the handler and the budget (#2809)."""
    plan = _validation_plan_file(artifact_contents)
    return plan[1] if plan is not None else None


def _validation_plan_file(artifact_contents: Mapping[str, str]) -> tuple[str, str] | None:
    return next(
        ((name, content) for name, content in artifact_contents.items() if VALIDATION_PLAN in name),
        None,
    )


def package_scoped(
    artifact_contents: dict[str, str], expected_artifacts: Iterable[Any]
) -> dict[str, str]:
    """pf-33: scope the focused prompt's source dump to the top-level package(s) the task's own
    artifacts live in (the RC2 package rule at the prompt seam). m007's prompt carried all 16 files
    (~18k tokens, every frontend .jsx included) into a backend suite task: prefill cost plus
    rambling pressure against the 8192 completion clamp, and the truncation crashed collection.
    No expected artifacts or no package match: contents unchanged (never starve the prompt)."""
    packages = {
        str(e).strip().lstrip("./").partition("/")[0] for e in (expected_artifacts or []) if e
    }
    if not packages:
        return artifact_contents
    scoped = {
        name: content
        for name, content in artifact_contents.items()
        if str(name).strip().lstrip("./").partition("/")[0] in packages
    }
    return scoped or artifact_contents


def product_runners(inputs: Mapping[str, Any]) -> tuple[tuple[tuple[str, ...], str], ...]:
    """Each of the product's own runners as ``(roots, file_pattern)``, from the task's
    ``source_repository`` (``checkout.RunnerView``; contract 8 requires its roots)."""
    runners = (inputs.get("source_repository") or {}).get("runners") or ()
    return tuple(
        (tuple(str(r) for r in runner.get("roots") or ()), str(runner["file_pattern"]))
        for runner in runners
        if isinstance(runner, Mapping) and runner.get("file_pattern")
    )


def product_scoped(
    artifact_contents: Mapping[str, str],
    expected_artifacts: Iterable[Any],
    runners: Iterable[tuple[tuple[str, ...], str]],
) -> dict[str, str]:
    """SIP-0112 H.39 (#3182): what a repository-backed product's ``qa.test`` is shown of the
    product's tree before the code its text names: the files beside its suite, and the test
    infrastructure. Never a whole top-level directory, and never the whole tree.

    - **Beside its suite:** every file in the same directory as one of the task's expected
      artifacts, that directory alone. A product's tests can live beside its source, where the
      top-level directory is the source tree.
    - **The test infrastructure:** every file directly under one of the product's runners'
      roots, which is where a runner's own script and its shared setup sit. A root of ``.``
      names the repository, whose top level is no test infrastructure, and adds nothing.

    ``package_scoped`` is the sample applications' rule, whose top-level directories are a
    backend and a frontend. On a product it showed 137 files for a suite under ``src/`` and the
    whole tree, 234 files, when no directory matched (measured on #3182)."""
    beside = {_directory(str(e)) for e in expected_artifacts or [] if e}
    roots = {root.strip("/") for roots, _pattern in runners for root in roots} - {".", ""}
    return {
        name: content
        for name, content in artifact_contents.items()
        if _directory(str(name)) in beside or _directory(str(name)) in roots
    }


def _directory(path: str) -> str:
    """The directory a repository-relative path is in, or ``""`` for the repository's root."""
    return path.strip().lstrip("./").rpartition("/")[0]


def within_the_product_cap(
    scoped: Mapping[str, str], under_test: Mapping[str, str], suite: set[str]
) -> dict[str, str]:
    """The product's files a ``qa.test`` is shown, held to ``PRODUCT_CONTENTS_MAX_CHARS``.

    The suite's own files and the code its text names or imports (``under_test``) are what the
    task can't be written without, and are always shown: when they alone overrun the model's
    window, the prompt guard refuses the prompt by name (SIP-0073), which is the hold. The
    files beside the suite come after them, smallest first, while they fit. One that doesn't is
    named with its size and not shown, so nothing is left out silently."""
    essential = {name for name in scoped if name in suite} | set(under_test)
    room = PRODUCT_CONTENTS_MAX_CHARS - sum(
        len(content) for name, content in {**scoped, **under_test}.items() if name in essential
    )
    fits: set[str] = set()
    for name, content in sorted(
        ((n, c) for n, c in scoped.items() if n not in essential),
        key=lambda item: (len(item[1]), item[0]),
    ):
        if len(content) <= room:
            fits.add(name)
            room -= len(content)
    # In the order the prompt has always shown them: the suite's directory, then the code under
    # test. A product whose files all fit is shown exactly what it was.
    return {
        name: content
        if name in essential or name in fits
        else (
            f"(not shown: {len(content)} characters, past what this prompt shows of the "
            "product beside the suite)"
        )
        for name, content in {**scoped, **under_test}.items()
    }


def code_under_test(
    files: Mapping[str, str],
    tree: Mapping[str, str],
    task_text: str = "",
    *,
    plan_sources: Iterable[Any] = (),
) -> dict[str, str]:
    """The files of ``tree`` that ``files`` import or ``task_text`` names, beyond ``files`` itself:
    what a suite calls, when it lives in another package.

    Scoping a suite's prompt to its own package left it the tests beside it and none of what they
    call: battle-trainer's suite lives in ``test/``, the helper it calls in ``tools/``, and qa wrote
    ``unit.shots`` for a count the helper returns as ``shots``. It read 0, and three repairs guessed
    at the name (``cyc_8e691eb2bccf``). One hop: the helper's own imports are the helper's concern.

    The task's text names a file by its path, or by its dotted module path (#3139): a game's plan
    says ``require(Shared.Modules.SalePricing)`` for ``src/Shared/Modules/SalePricing.luau``, and
    a first spec has no suite beside it whose imports could be read.

    ``plan_sources`` are the plan's own source files (a ``qa.test`` task's
    ``implementation_artifacts``). They are never shown whole, which would undo the package
    scoping on a larger plan. One of them is named by less, though: its bare name as a whole word
    (#3146). A plan wrote "the ShopDiscount module" for ``src/Shared/Modules/ShopDiscount.luau``
    and nothing longer. The candidates are only the plan's sources, so a common word can't pull
    in a file from the rest of the tree.
    """
    present = set(tree)
    wanted = {path for path in present if path in task_text or _named_as_a_module(path, task_text)}
    wanted.update(
        path
        for path in map(str, plan_sources)
        if path in present and _named_by_its_bare_name(path, task_text)
    )
    for path, source in files.items():
        if path.endswith(_READS_IMPORTS):
            wanted.update(imported_paths(path, source, present)[0])
    return {path: _shown_or_named(tree[path]) for path in sorted(wanted - set(files))}


def _named_as_a_module(path: str, task_text: str) -> bool:
    """Whether ``task_text`` names ``path`` as a module: its folders and its name without the
    extension, joined by dots or by `` > `` (as a game's own comments write an instance
    path), two parts at least.

    The name starts at the repository's root or below its first folder, which is where a source
    root sits: ``src/Shared/Modules/SalePricing.luau`` is ``Shared.Modules.SalePricing``, and
    ``backend/app/services/pricing.py`` is ``app.services.pricing``. A shorter tail
    (``Modules.SalePricing``) names nothing, since two words match prose. A source root deeper
    than one folder isn't reached. A package's ``init.luau`` or ``__init__.py`` is its folder's
    name. The name stands alone on both sides: ``Shared.Modules.SalePricingV2`` names another
    file, and so does ``Shared.Modules.Sale`` inside it. What comes before may be a dot, so the
    full instance path (``game.ReplicatedStorage.Shared.Modules.SalePricing``) names it too."""
    if not task_text:
        return False
    parts = list(PurePosixPath(path.replace("\\", "/")).with_suffix("").parts)
    if parts and parts[-1] in _PACKAGE_MODULES:
        parts.pop()
    for anchored in (parts, parts[1:]):
        if len(anchored) < 2:
            continue
        name = _MODULE_SEPARATOR.join(re.escape(part) for part in anchored)
        if re.search(rf"(?<![A-Za-z0-9_]){name}(?![A-Za-z0-9_])", task_text):
            return True
    return False


def _named_by_its_bare_name(path: str, task_text: str) -> bool:
    """Whether ``task_text`` holds ``path``'s own name, without its folders or its extension, as a
    whole word. A package's ``init.luau`` or ``__init__.py`` is named by its folder. Asked only of
    the plan's own sources (``code_under_test``): among every file of a tree, one word matches
    too much."""
    parts = list(PurePosixPath(path.replace("\\", "/")).with_suffix("").parts)
    if parts and parts[-1] in _PACKAGE_MODULES:
        parts.pop()
    if not parts or not task_text:
        return False
    return bool(re.search(rf"(?<![A-Za-z0-9_]){re.escape(parts[-1])}(?![A-Za-z0-9_])", task_text))


def _shown_or_named(content: str) -> str:
    if len(content) <= CODE_UNDER_TEST_MAX_CHARS:
        return content
    return f"(not shown: {len(content)} characters, too large for this prompt)"


def _task_text(inputs: Mapping[str, Any]) -> str:
    """The task's own words, where a plan names the module its suite is to test."""
    criteria = [c for c in inputs.get("acceptance_criteria") or () if isinstance(c, str)]
    return "\n".join([str(inputs.get("subtask_description") or ""), *criteria])


def source_files(
    artifact_contents: Mapping[str, str], profile: DevelopmentProfile
) -> dict[str, str]:
    """The stack's source files and its build-support files (D4, D9): what the monolithic prompt
    shows, and, on a sample application, the tree the suite is built and run against
    (``qa_run_tree``, #2815).

    Source files by the profile's ``source_filter`` extension, never a test file, AND the profile's
    ``build_support_files`` (config and entry files matched by basename: package.json,
    vite.config.js, index.html, …). Without the support files the QA build/test workspace can't
    build the deliverable, and the frontend build check (#290) and vitest skip on "no
    package.json" (#296)."""
    support = set(getattr(profile, "build_support_files", ()))
    sources = {}
    for key, value in artifact_contents.items():
        basename = key.replace("\\", "/").rsplit("/", 1)[-1]
        is_source = any(key.endswith(ext) for ext in profile.source_filter) and not is_test_file(
            key, profile.test_file_patterns
        )
        if is_source or basename in support:
            sources[key] = value
    return sources


def is_test_file(path: str, patterns: tuple[str, ...]) -> bool:
    """Check if *path* matches any test file pattern or resides in __tests__/.

    The basename match is ``development_profiles.matches_test_file_patterns`` — shared with
    plan validation (#846) so both read the stack's declared conventions rather than
    each carrying its own idea of what a test file looks like.

    The ``__tests__/`` clause stays local and is not shared. Callers here use this to
    *exclude* files from a source set, where over-matching is the safe direction; plan
    validation asks the stricter question "will the runner discover this?", and a
    ``__tests__/helpers.py`` pytest never collects must not count there.

    The clause reads a **leading** ``__tests__/`` too (#1539). On the App Router stack every
    suite lives at the workspace root, so ``__tests__/helpers.ts`` carries no leading slash and
    the substring test missed it: a root-level module the runner imports but whose basename
    matches no ``*.test.ts`` pattern was handed to the qa author as application source. The
    ``f"/{path}"`` prefix is the whole fix — the convention is the directory, wherever it sits,
    and the leading slash keeps it a *path segment* rather than a bare substring, so
    ``app/my__tests__util.ts`` stays source. The dev-repair emission veto already read the
    convention this way (#1014, ``src/squadops/execution/correction_repair.py``); the two exclusions
    now agree on it.

    #2805 moved it here from ``handlers.cycle.validation``, so the composer selects the source files
    without importing the cycle handlers. Their package still exports it as ``_is_test_file``.
    """

    return matches_test_file_patterns(path, patterns) or "/__tests__/" in f"/{path}"
