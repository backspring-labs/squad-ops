"""The product's repository, as one rendering for every authoring stage (SIP-0112 E.4.3).

A source-backed run's task is handed a ``source_repository`` input: the map of the product's tree,
the product's own checks and the test runners they run (SIP-0112 H.4 point 3), its own instruction
files, and the current content of the files the task names. Each authoring
stage shows it through the same managed asset (#448), beside the prior-cycle brief.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


async def source_repository_section(renderer: Any, inputs: dict[str, Any]) -> str:
    """The product's repository as an appendix, or ``""`` for a run that has none."""
    repository = inputs.get("source_repository")
    if renderer is None or not isinstance(repository, Mapping):
        return ""
    variables = {"commit": str(repository["commit"]), "repository_map": str(repository["map"])}
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
