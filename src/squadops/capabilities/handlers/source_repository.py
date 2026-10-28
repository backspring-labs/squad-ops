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

from squadops.stacks.development_profiles import (
    effective_development_profile,
    get_development_profile,
)


async def source_repository_section(renderer: Any, inputs: dict[str, Any]) -> str:
    """The product's repository as an appendix, or ``""`` for a run that has none."""
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
    rendered = await renderer.render("request.source_repository_appendix", variables)
    return rendered.content


def product_conventions_template(inputs: Mapping[str, Any]) -> str:
    """The asset of the run's stack conventions for a product, or ``""`` (SIP-0112 H.13).

    A source-backed run's only: a sample application's tasks fill the skeleton that the profile's
    own prose describes. ``""`` for a profile that declares none (the default ``python_cli``, which
    a product with no blueprint runs under), and for one that doesn't resolve, which the handler
    refuses on its own. Where one is declared, the developer's system prompt leaves out the
    profile's prose for the skeleton, since this asset says what the product keeps of it."""
    if not isinstance(inputs.get("source_repository"), Mapping):
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
