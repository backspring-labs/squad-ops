"""The kept copy of a cycle's skills, and which of them a task loads (SIP-0116 §7, §10).

A cycle whose work requires skillsets keeps a copy of their skills when it is created: each
skill's text and resources, and which skills each capability loads. Every task, repair, retry
and resume loads from that copy, never from the tree, so a redeploy that edits a skill doesn't
reach a cycle already created.

- **The record names the content, by digest** (its ``content`` part): each kept skill and each
  of its files. The digests are a function of the equipment alone, so two cycles created with
  the same equipment have the same record digest.
- **The copy is one vault artifact of the cycle,** of type ``skillset_content``.
- **A copy is checked before anything is loaded from it.** Its skills hash to the digests it
  states, and what it holds is exactly what the record names. A copy that fails either is
  refused with the difference. Nothing is read from the tree in its place.

Which skills a task loads is decided here from the record and the copy alone (§7):

- a task that names a contract loads that contract's skills, from the skillset its agent was
  assigned to supply;
- a task that names none loads the skills of every required contract that runs as its task
  type, from the skillsets its agent supplies;
- a task whose agent supplies nothing for it loads none. A skillset another agent carries, or
  one this cycle's work doesn't require, adds nothing.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from squadops.capabilities.skillsets import SKILLS_INPUT, Skillset, skill_files_digest
from squadops.core.hashing import canonical_json
from squadops.cycles.models import ArtifactRef

if TYPE_CHECKING:
    from squadops.cycles.skillset_coverage import Assignment
    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort

SKILLSET_CONTENT_SCHEMA = "squadops.skillset-content/v1"
SKILLSET_CONTENT_ARTIFACT_TYPE = "skillset_content"
SKILLSET_CONTENT_FILENAME = "skillset_content.json"


__all__ = [
    "SKILLSET_CONTENT_ARTIFACT_TYPE",
    "SKILLSET_CONTENT_SCHEMA",
    "SKILLS_INPUT",
    "LoadedSkill",
    "SkillsetContentError",
    "content_entries",
    "keep_skillset_content",
    "kept_document",
    "kept_document_of",
    "read_kept_document",
    "skills_for",
    "skills_input",
]


class SkillsetContentError(ValueError):
    """A cycle's skills can't be kept, or its kept copy can't be loaded from."""


@dataclass(frozen=True)
class LoadedSkill:
    """One skill a task loads: its files as text, from the cycle's kept copy."""

    skillset: str
    version: int
    skill: str
    digest: str
    files: Mapping[str, str]


def kept_document(
    assignments: Iterable[Assignment], catalog: Mapping[str, Skillset]
) -> dict[str, Any]:
    """The copy a cycle keeps: every skill of each skillset its agents were assigned to
    supply, and which skills each of that skillset's capabilities loads.

    The whole of an assigned skillset is kept, not only the contracts the work names: a repair
    loads the skills of the step it revises, and that step's capability is the same skillset's.
    Raises when the catalog holds a skill's digest without its text, or text that doesn't
    hash to it: a copy that couldn't be checked later is never written.
    """
    skillsets: list[dict[str, Any]] = []
    for skillset_id in dict.fromkeys(a.skillset for a in assignments):
        skillset = catalog.get(skillset_id)
        if skillset is None:
            raise SkillsetContentError(
                f"skillset {skillset_id} was assigned, and the catalog doesn't hold it"
            )
        names = list(dict.fromkeys(s for c in skillset.capabilities for s in c.skills))
        skills = []
        for name in names:
            files = skillset.skill_files.get(name)
            stated = skillset.skill_digests.get(name)
            if files is None or stated is None:
                raise SkillsetContentError(
                    f"skillset {skillset_id} names the skill {name}, and the catalog holds "
                    "no text for it"
                )
            if skill_files_digest(files) != stated:
                raise SkillsetContentError(
                    f"skill {name} of skillset {skillset_id}: its text doesn't hash to the "
                    f"digest the catalog states ({stated})"
                )
            skills.append({"skill": name, "digest": stated, "files": dict(sorted(files.items()))})
        skillsets.append(
            {
                "skillset": skillset.id,
                "version": skillset.version,
                "capabilities": [
                    {"contract": c.contract, "skills": list(c.skills)}
                    for c in skillset.capabilities
                ],
                "skills": skills,
            }
        )
    return {"schema": SKILLSET_CONTENT_SCHEMA, "skillsets": skillsets}


def content_entries(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The record's ``content`` part for ``document``: each kept skill and each of its files,
    by digest. Empty when the assigned skillsets load no skill."""
    return [
        {
            "skillset": skillset["skillset"],
            "version": skillset["version"],
            "skill": skill["skill"],
            "digest": skill["digest"],
            "files": {
                path: hashlib.sha256(text.encode("utf-8")).hexdigest()
                for path, text in sorted(skill["files"].items())
            },
        }
        for skillset in document["skillsets"]
        for skill in skillset["skills"]
    ]


async def keep_skillset_content(
    vault: ArtifactVaultPort | None, *, project_id: str, cycle_id: str, document: Mapping[str, Any]
) -> ArtifactRef:
    """Store ``document`` as the cycle's kept copy. Refused when no vault is configured: a
    cycle created without its copy would load nothing, or today's tree, at its first task."""
    if vault is None:
        raise SkillsetContentError(
            f"cycle {cycle_id}'s work requires skillsets, and no artifact vault is configured "
            "to keep their skills"
        )
    content = canonical_json(document).encode("utf-8")
    return await vault.store(
        ArtifactRef(
            artifact_id=f"art_{uuid4().hex[:12]}",
            project_id=project_id,
            artifact_type=SKILLSET_CONTENT_ARTIFACT_TYPE,
            filename=SKILLSET_CONTENT_FILENAME,
            content_hash=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            media_type="application/json",
            created_at=datetime.now(UTC),
            cycle_id=cycle_id,
            metadata={"schema": SKILLSET_CONTENT_SCHEMA},
        ),
        content,
    )


async def kept_document_of(
    vault: ArtifactVaultPort | None, *, cycle_id: str, record: Mapping[str, Any]
) -> dict[str, Any] | None:
    """The cycle's kept copy, read from the vault and checked against ``record``. ``None``
    when the record names no content: the cycle's work loads no skill, and nothing was kept.
    A record that names content with no copy to load it from raises: the tree is never read
    in the copy's place."""
    if not _record_content(record):
        return None
    if vault is None:
        raise SkillsetContentError(
            f"cycle {cycle_id}'s record names skills, and no artifact vault is configured to "
            "read their kept copy from"
        )
    refs = await vault.list_artifacts(
        cycle_id=cycle_id, artifact_type=SKILLSET_CONTENT_ARTIFACT_TYPE
    )
    if len(refs) != 1:
        raise SkillsetContentError(
            f"cycle {cycle_id}'s record names skills, and the vault holds {len(refs)} kept "
            "copies of them: one is written when the cycle is created"
        )
    _, content = await vault.retrieve(refs[0].artifact_id)
    return read_kept_document(content, record)


def read_kept_document(content: bytes, record: Mapping[str, Any]) -> dict[str, Any]:
    """The kept copy in ``content``, checked against the cycle's ``record``. Raises
    ``SkillsetContentError`` naming what is wrong: a document that isn't the schema's, a skill
    whose text doesn't hash to its digest, or content other than what the record names."""
    try:
        document = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise SkillsetContentError(f"the kept copy isn't a JSON document: {exc}") from exc
    if not isinstance(document, dict) or document.get("schema") != SKILLSET_CONTENT_SCHEMA:
        found = document.get("schema") if isinstance(document, dict) else type(document).__name__
        raise SkillsetContentError(
            f"the kept copy's schema is {found!r}, not {SKILLSET_CONTENT_SCHEMA!r}"
        )
    try:
        for skillset in document["skillsets"]:
            for capability in skillset["capabilities"]:
                _texts(capability["skills"], f"{skillset['skillset']}/{capability['contract']}")
            for skill in skillset["skills"]:
                where = f"{skillset['skillset']}/{skill['skill']}"
                files = skill["files"]
                if not isinstance(files, dict) or not all(
                    isinstance(k, str) and isinstance(v, str) for k, v in files.items()
                ):
                    raise SkillsetContentError(f"the kept copy's {where} holds files not text")
                if skill_files_digest(files) != skill["digest"]:
                    raise SkillsetContentError(
                        f"the kept copy's {where} doesn't hash to the digest it states "
                        f"({skill['digest']})"
                    )
        kept = content_entries(document)
    except (KeyError, TypeError, AttributeError) as exc:
        raise SkillsetContentError(
            f"the kept copy is missing a part the schema requires: {exc!r}"
        ) from exc
    named = _record_content(record)
    if kept != named:
        raise SkillsetContentError(
            "the kept copy isn't the content the cycle's record names: the record names "
            f"{_summary(named)}, and the copy holds {_summary(kept)}"
        )
    return document


def skills_for(
    document: Mapping[str, Any],
    record: Mapping[str, Any],
    *,
    task_type: str,
    agent_id: str,
    contract: str = "",
) -> tuple[LoadedSkill, ...]:
    """The skills a task loads (§7), from the cycle's record and its kept copy.

    ``document`` has been read by ``read_kept_document``. ``contract`` is the contract the
    plan task names, or empty for a task that names none.
    """
    offered = record.get("offered")
    if not isinstance(offered, list):
        raise SkillsetContentError("the cycle's record has no list of offered contracts")
    rows = [
        row
        for row in offered
        if row["agent_id"] == agent_id
        and (row["contract"] == contract if contract else row["task_type"] == task_type)
    ]
    loaded: dict[tuple[str, str], LoadedSkill] = {}
    for skillset_id, row_contract in dict.fromkeys((r["skillset"], r["contract"]) for r in rows):
        skillset = _kept_skillset(document, skillset_id)
        by_name = {s["skill"]: s for s in skillset["skills"]}
        names = next(
            (c["skills"] for c in skillset["capabilities"] if c["contract"] == row_contract), None
        )
        if names is None:
            raise SkillsetContentError(
                f"the kept copy's {skillset_id} has no capability for {row_contract}, which "
                "the record says it supplies"
            )
        for name in names:
            if name not in by_name:
                raise SkillsetContentError(
                    f"the kept copy's {skillset_id} names the skill {name} for "
                    f"{row_contract} and doesn't hold it"
                )
            skill = by_name[name]
            loaded.setdefault(
                (skillset_id, name),
                LoadedSkill(
                    skillset=skillset_id,
                    version=skillset["version"],
                    skill=name,
                    digest=skill["digest"],
                    files=dict(skill["files"]),
                ),
            )
    return tuple(loaded.values())


def skills_input(skills: Iterable[LoadedSkill]) -> list[dict[str, Any]]:
    """``skills`` as the envelope input a handler renders: each skill with its files as text,
    and the digest the cycle's record names it by."""
    return [
        {
            "skillset": s.skillset,
            "version": s.version,
            "skill": s.skill,
            "digest": s.digest,
            "files": dict(s.files),
        }
        for s in skills
    ]


def _kept_skillset(document: Mapping[str, Any], skillset_id: str) -> Mapping[str, Any]:
    for skillset in document["skillsets"]:
        if skillset["skillset"] == skillset_id:
            return skillset
    raise SkillsetContentError(
        f"the kept copy doesn't hold {skillset_id}, which the record says an agent supplies"
    )


def _record_content(record: Mapping[str, Any]) -> list[Any]:
    content = record.get("content")
    if not isinstance(content, list):
        raise SkillsetContentError("the cycle's record has no list of content")
    return content


def _texts(value: Any, where: str) -> None:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise SkillsetContentError(f"the kept copy's {where} doesn't list its skills by name")


def _summary(entries: list[Any]) -> str:
    if not entries:
        return "none"
    return ", ".join(
        f"{e.get('skillset')}/{e.get('skill')}@{str(e.get('digest'))[:12]}"
        if isinstance(e, dict)
        else repr(e)
        for e in entries
    )
