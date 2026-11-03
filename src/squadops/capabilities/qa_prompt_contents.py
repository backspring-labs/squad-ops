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
  (:func:`package_scoped`);
- **the monolithic prompt** shows the validation plan (:func:`validation_plan`, the handler's
  choice too) and the stack's source and support files (:func:`source_files`), which can include
  a ``conftest.py`` or an ``index.html``, never a file the stack names a test. A source file
  whose name carries the plan's is shown twice, as the plan and as a source, and counted twice.

**A known limit** (#2809): when the executor's 512 KB resolution limit stops before the plan, the
handler loads it from the vault (D3), and no estimate of ``artifact_contents`` sees it. ``qa.test``'s
own prompt guard (``prompt_guard._guard_prompt_size``) still refuses a prompt over the window by
name.

What the suite runs against is ``qa_run_tree``'s (#2815): these source and support files on a
sample application, and the product's tree on a repository-backed product.

Pure: no I/O and no handler imports, so the runtime's composer and the agent's handler both call
it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

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


def qa_test_prompt_contents(inputs: Mapping[str, Any]) -> dict[str, str]:
    """The files a ``qa.test`` prompt shows of ``inputs["artifact_contents"]``, by name, on the
    path the inputs select: the focused prompt's packages (which the handler renders through this
    function), or the monolithic prompt's validation plan and source files, each chosen as the
    handler chooses it. A plan that is also a source file shown is counted twice, as it is shown
    twice: once under its section's name (#2809)."""
    contents = inputs.get("artifact_contents") or {}
    if inputs.get("subtask_focus") is not None:
        return package_scoped(contents, inputs.get("expected_artifacts") or [])
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
