"""The product's repository, as one rendering for every authoring stage (SIP-0112 E.4.3).

A source-backed run's task is handed a ``source_repository`` input: the map of the product's tree,
the product's own checks and the test runners they run (SIP-0112 H.4 point 3), its own instruction
files, and the current content of the files the task names. Each authoring
stage shows it through the same managed asset (#448), beside the prior-cycle brief.

A product made from a blueprint runs under that blueprint's development profile (H.13), and is
shown here what the blueprint's conventions are for a product, from the profile's own asset. It is
never shown the profile's prose for the skeleton, which places files and tests by the skeleton's
layout: where a product's file or test goes is shown by its map and its runners.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from squadops.projects.derived_profile import JAVASCRIPT_RUNNERS
from squadops.stacks.development_profiles import (
    effective_development_profile,
    get_development_profile,
)
from squadops.tasks.task_types import DeletionGrant, deletion_grant


def source_backed(inputs: Mapping[str, Any]) -> bool:
    """Whether the task is a source-backed run's: it carries the product's repository (E.4.3).
    The one marker a task reads for a repository-backed product's run: the conventions it is
    shown (H.13) and the tree a qa suite runs on (``qa_run_tree``, #2815). A sample application's
    task carries none."""
    return isinstance(inputs.get("source_repository"), Mapping)


async def source_repository_section(
    renderer: Any, inputs: dict[str, Any], *, task_type: object = None
) -> str:
    """The product's repository as an appendix, or ``""`` for a run that has none. ``task_type``
    is the step reading it: one that may remove a file is shown the deletion form (#2612), and a
    stage that authors no product file (a plan's, the framing's) passes none and is shown none."""
    repository = inputs.get("source_repository")
    if renderer is None or not isinstance(repository, Mapping):
        return ""
    variables = {"commit": str(repository["commit"]), "repository_map": str(repository["map"])}
    conventions = product_conventions_template(inputs)
    if conventions:
        variables["conventions"] = (await renderer.render(conventions, {})).content
    checks = repository.get("checks") or []
    if checks:
        checks_variables = {
            "checks": "\n".join(f"- `{c['id']}`: `{' '.join(c['argv'])}`" for c in checks)
        }
        runners = repository.get("runners") or []
        if runners:
            block = await renderer.render(
                "request.source_repository_runners_block",
                {"runners": "\n".join(_runner(r) for r in runners)},
            )
            checks_variables["runners"] = block.content
        block = await renderer.render("request.source_repository_checks_block", checks_variables)
        variables["checks"] = block.content
    instructions = repository.get("instructions") or {}
    if instructions:
        block = await renderer.render(
            "request.source_repository_instructions_block", {"files": _files(instructions)}
        )
        variables["instructions"] = block.content
    existing = repository.get("existing_files") or {}
    if existing:
        block = await renderer.render(
            "request.source_repository_existing_files_block", {"files": _files(existing)}
        )
        variables["existing_files"] = block.content
    deletion = await _deletion_block(renderer, repository, task_type)
    if deletion:
        variables["deletion"] = deletion
    rendered = await renderer.render("request.source_repository_appendix", variables)
    return rendered.content


async def _deletion_block(renderer: Any, repository: Mapping[str, Any], task_type: object) -> str:
    """How the step removes a file, in its own grant's terms, or ``""`` for a step that may not.
    A test step of a product with no runner holds no test it could remove, so it is shown none."""
    grant = deletion_grant(task_type)
    if grant is DeletionGrant.PRODUCT:
        block = await renderer.render("request.source_repository_deletion_product", {})
        return block.content
    example = _replaced_test_path(repository) if grant is DeletionGrant.TESTS else None
    if example is None:
        return ""
    block = await renderer.render(
        "request.source_repository_deletion_tests", {"example_path": example}
    )
    return block.content


def _replaced_test_path(repository: Mapping[str, Any]) -> str | None:
    """A path the product's first runner would hold, in that runner's own terms, so the example a
    test step is shown is a test of this product's kind (#2876). No file of the product's."""
    for runner in repository.get("runners") or ():
        roots = runner.get("roots") or ()
        pattern = str(runner.get("file_pattern") or "")
        if roots and pattern:
            name = pattern.replace("*", "replaced")
            return name if roots[0] == "." else f"{roots[0]}/{name}"
    return None


def suite_language(inputs: Mapping[str, Any]) -> str:
    """The language a run's worked suite examples are written in (#2876): ``"javascript"`` for a
    source-backed run whose product tests only with JavaScript runners, else ``"python"``. A
    sample application's run, a product with no runner, or one with any other runner keeps the
    prompt it had."""
    if source_backed(inputs):
        runners = {str(r.get("runner")) for r in inputs["source_repository"].get("runners") or ()}
        if runners and runners <= JAVASCRIPT_RUNNERS:
            return "javascript"
    return "python"


def product_conventions_template(inputs: Mapping[str, Any]) -> str:
    """The asset of the run's stack conventions for a product, or ``""`` (SIP-0112 H.13).

    A source-backed run's only: a sample application's tasks fill the skeleton that the profile's
    own prose describes. ``""`` for a profile that declares none (the default ``python_cli``, which
    a product with no blueprint runs under), and for one that doesn't resolve, which the handler
    refuses on its own. Where one is declared, the developer's system prompt leaves out the
    profile's prose for the skeleton, since this asset says what the product keeps of it."""
    if not source_backed(inputs):
        return ""
    try:
        profile = get_development_profile(
            effective_development_profile(inputs.get("resolved_config"))
        )
    except ValueError:
        return ""
    return profile.product_conventions_template


def _runner(runner: Mapping[str, Any]) -> str:
    """One runner as data: what runs it, the files it takes, where, and what they test."""
    return (
        f"- `{runner['runner']}`, run by {_listed(runner['checks'])}: a file named "
        f"`{runner['file_pattern']}` under {_listed(runner['roots'])}, testing "
        f"{_listed(runner['covers'])}"
    )


def _listed(items: Any) -> str:
    return ", ".join(f"`{i}`" for i in items)


def _files(files: Mapping[str, str]) -> str:
    return "\n\n".join(f"**{path}:**\n```\n{content}\n```" for path, content in files.items())
