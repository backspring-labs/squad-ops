"""The skillset spec: its shape, its validation and its digest (SIP-0116 §4).

A skillset is one directory: ``skillset.yaml`` and the skills it loads, each a directory
holding a ``SKILL.md``. It specializes capability contracts for one platform and a role. It is
data: read, validated and digested without running anything, which is what lets a capability
pack carry the same directory unchanged later (§4.3).

    <id>/
      skillset.yaml
      skills/<skill>/SKILL.md
    _shared/<skill>/SKILL.md        # included by reference, as ``shared/<skill>``

In 2.x the tree holds skillsets under the prompts seam (Q61), since a skill's text is prompt
content. None is shipped yet, so the packaged catalog is empty and a missing directory reads as
that. Whether an agent may carry a skillset, and whether a squad covers what a cycle's work
requires, are cycle preflight's checks (§9), not this module's.
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from squadops.capabilities.capability_contracts import (
    CapabilityContractDeclaration,
    VerificationMode,
    capability_contract,
)
from squadops.core.hashing import canonical_sha256
from squadops.prompts import __file__ as _prompts_pkg
from squadops.prompts.frontmatter import FrontmatterError, parse_frontmatter
from squadops.remote_execution.scenario import ScenarioVocabulary

SKILLSET_API_VERSION = "squadops.skillset/v1"
#: The envelope input a task's skills are handed on, by the runtime, at each dispatch (§7):
#: a list of skills, each with its files as text.
SKILLS_INPUT = "skills"
PACKAGED_SKILLSETS_DIR = Path(_prompts_pkg).parent / "skillsets"
SPEC_FILE = "skillset.yaml"
SKILL_FILE = "SKILL.md"
#: The directory shared skills live in, beside the skillsets, and the prefix that names one.
SHARED_DIR = "_shared"
SHARED_PREFIX = "shared/"
#: Where a tool's operation runs (§8).
TOOL_LOCATIONS = ("agent", "sandbox", "worker")
#: §17g: the one resource a skill may hold that the framework reads as data: the vocabulary of
#: the scenario reader its capability's provider executes (SIP-0117 R5.8), at the skill's root.
#: A scenario is validated against it when it is frozen. Kept and digested as any skill file.
SCENARIO_VOCABULARY_FILE = "scenario_vocabulary.json"

_SPEC_FIELDS = frozenset(
    {"id", "version", "description", "roles", "platform", "prerequisites", "capabilities"}
)
_CAPABILITY_FIELDS = frozenset({"contract", "modes", "skills", "tools"})
_TOOL_FIELDS = frozenset({"id", "provider", "location"})


class SkillsetError(ValueError):
    """A skillset directory that isn't a valid spec. ``errors`` lists everything wrong with
    it, so its author fixes it in one pass."""

    def __init__(self, skillset: str, errors: list[str]) -> None:
        self.skillset = skillset
        self.errors = list(errors)
        super().__init__(f"skillset {skillset}: " + "; ".join(errors))


@dataclass(frozen=True)
class ToolRequest:
    """An operation a capability's handler may request. A request within the authority that
    already governs the operation, never a grant (§8)."""

    id: str
    provider: str
    location: str


@dataclass(frozen=True)
class SkillsetCapability:
    """One contract the skillset specializes: the modes it supports for it, the skills loaded
    for its tasks, and the tools its handler may request. Empty means none."""

    contract: str
    modes: tuple[VerificationMode, ...] = ()
    skills: tuple[str, ...] = ()
    tools: tuple[ToolRequest, ...] = ()


@dataclass(frozen=True)
class Skillset:
    id: str
    version: int
    description: str
    roles: tuple[str, ...]
    platform_id: str
    platform_variants: tuple[str, ...]
    #: The providers it needs: a runner, an editor on a worker.
    prerequisites: tuple[str, ...]
    capabilities: tuple[SkillsetCapability, ...]
    #: Each skill it loads, by the name the spec uses, with the digest of its content.
    skill_digests: Mapping[str, str]
    #: Covers the spec and every skill's content, so any change to either moves it.
    digest: str
    #: Each skill's files as text, by the skill's name and then the file's path within it: its
    #: ``SKILL.md`` and each resource beside it. Read once with the catalog, so the text a
    #: cycle keeps a copy of (§10) is the text its digest was taken from.
    skill_files: Mapping[str, Mapping[str, str]] = field(default_factory=dict)

    def capability_for(self, contract: str) -> SkillsetCapability | None:
        return next((c for c in self.capabilities if c.contract == contract), None)


def skill_directory(root: Path, skillset_id: str, skill: str) -> Path:
    """Where the skill a spec names lives: its own, or a shared one included by reference."""
    if skill.startswith(SHARED_PREFIX):
        return root / SHARED_DIR / skill[len(SHARED_PREFIX) :]
    return root / skillset_id / "skills" / skill


def skill_digest(directory: Path) -> str:
    """The digest of a skill's content: its ``SKILL.md`` and every resource beside it, by
    relative path. Content is read as bytes, so the digest is the same on every platform."""
    files = sorted(p for p in directory.rglob("*") if p.is_file())
    return canonical_sha256(
        {
            p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        }
    )


def skill_files_digest(files: Mapping[str, str]) -> str:
    """The digest of a skill's content from its files as text: the same value
    ``skill_digest`` takes from the directory, since each file is UTF-8 and read byte for
    byte. A kept copy is checked against it before it is loaded (§10)."""
    return canonical_sha256(
        {
            path: hashlib.sha256(text.encode("utf-8")).hexdigest()
            for path, text in sorted(files.items())
        }
    )


def read_skill_files(directory: Path) -> tuple[dict[str, str], list[str]]:
    """A skill's files as text, by relative path, and each file that isn't UTF-8 text. A skill
    is loaded into a prompt, so a resource that can't be read as text can't be one (§7)."""
    files: dict[str, str] = {}
    unreadable: list[str] = []
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        relative = path.relative_to(directory).as_posix()
        try:
            # Bytes, decoded: ``read_text`` would rewrite line endings, and the text would
            # then no longer hash to the directory's digest.
            files[relative] = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            unreadable.append(relative)
    return files, unreadable


def read_scenario_vocabulary(text: str) -> ScenarioVocabulary:
    """A skill's ``SCENARIO_VOCABULARY_FILE``, read strictly. Raises ``ValueError``."""
    try:
        document = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"isn't JSON: {e}") from e
    return ScenarioVocabulary.from_document(document)


def load_skillset(
    directory: Path, *, contracts: Mapping[str, CapabilityContractDeclaration] | None = None
) -> Skillset:
    """Read and validate the skillset in ``directory``. Raises ``SkillsetError`` naming every
    defect. ``contracts`` are the declared capability contracts to check it against (the
    registered ones when omitted)."""
    skillset_id = directory.name
    errors: list[str] = []
    spec = _read_spec(directory, errors)
    version, description = _identity(spec, skillset_id, errors)
    roles = _names(spec.get("roles"), "roles", errors, required=True)
    platform_id, variants = _platform(spec.get("platform"), errors)
    prerequisites = _prerequisites(spec.get("prerequisites"), errors)
    capabilities = _capabilities(spec.get("capabilities"), errors, contracts)

    skill_digests: dict[str, str] = {}
    skill_files: dict[str, dict[str, str]] = {}
    for skill in dict.fromkeys(s for c in capabilities for s in c.skills):
        location = skill_directory(directory.parent, skillset_id, skill)
        problem = _skill_problem(location)
        if problem:
            errors.append(f"skill {skill}: {problem}")
            continue
        files, unreadable = read_skill_files(location)
        if unreadable:
            errors.append(
                f"skill {skill}: {', '.join(unreadable)} is not UTF-8 text, and a skill's "
                "files are loaded into a prompt"
            )
            continue
        skill_digests[skill] = skill_files_digest(files)
        skill_files[skill] = files

    for capability in capabilities:
        holders = [
            s for s in capability.skills if SCENARIO_VOCABULARY_FILE in skill_files.get(s, {})
        ]
        if len(holders) > 1:
            errors.append(
                f"capability {capability.contract}: skills {', '.join(holders)} each hold a "
                f"{SCENARIO_VOCABULARY_FILE}, and a capability's provider reads one vocabulary"
            )
    for skill, files in skill_files.items():
        if SCENARIO_VOCABULARY_FILE in files:
            try:
                read_scenario_vocabulary(files[SCENARIO_VOCABULARY_FILE])
            except ValueError as e:
                errors.append(f"skill {skill}: {SCENARIO_VOCABULARY_FILE}: {e}")

    if errors:
        raise SkillsetError(skillset_id, errors)
    return Skillset(
        id=skillset_id,
        version=version,
        description=description,
        roles=roles,
        platform_id=platform_id,
        platform_variants=variants,
        prerequisites=prerequisites,
        capabilities=capabilities,
        skill_digests=dict(sorted(skill_digests.items())),
        digest=canonical_sha256({"spec": spec, "skills": skill_digests}),
        skill_files={name: skill_files[name] for name in sorted(skill_files)},
    )


def _read_spec(directory: Path, errors: list[str]) -> dict[str, Any]:
    """The ``skillset`` mapping of the directory's spec file. A file that can't be read as
    one raises at once, since nothing further can be checked."""
    skillset_id = directory.name
    spec_path = directory / SPEC_FILE
    if not spec_path.is_file():
        raise SkillsetError(skillset_id, [f"no {SPEC_FILE}"])
    try:
        document = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SkillsetError(skillset_id, [f"{SPEC_FILE} is not valid YAML: {exc}"]) from exc
    if not isinstance(document, dict):
        raise SkillsetError(skillset_id, [f"{SPEC_FILE} must be a mapping"])
    if document.get("api_version") != SKILLSET_API_VERSION:
        errors.append(
            f"api_version must be {SKILLSET_API_VERSION!r}, not {document.get('api_version')!r}"
        )
    unknown_top = sorted(set(document) - {"api_version", "skillset"})
    if unknown_top:
        errors.append(f"unknown top-level field: {', '.join(unknown_top)}")
    spec = document.get("skillset")
    if not isinstance(spec, dict):
        raise SkillsetError(skillset_id, [*errors, "`skillset` must be a mapping"])
    unknown = sorted(set(spec) - _SPEC_FIELDS)
    if unknown:
        # §4.1: a further field is added only by a SIP.
        errors.append(f"unknown field: {', '.join(unknown)}")
    return spec


def _identity(spec: dict[str, Any], skillset_id: str, errors: list[str]) -> tuple[int, str]:
    if spec.get("id") != skillset_id:
        errors.append(f"id {spec.get('id')!r} must be its directory's name, {skillset_id!r}")
    version = spec.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        errors.append(f"version must be a positive integer, not {version!r}")
        version = 0
    description = spec.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append("description is required")
        description = ""
    return version, description.strip()


def _platform(platform: Any, errors: list[str]) -> tuple[str, tuple[str, ...]]:
    if not isinstance(platform, dict) or set(platform) - {"id", "variants"}:
        errors.append("platform must be a mapping of `id` and `variants`")
        return "", ()
    declared_id = platform.get("id")
    platform_id = declared_id if isinstance(declared_id, str) else ""
    if not platform_id.strip():
        errors.append("platform.id is required")
    variants = _names(platform.get("variants"), "platform.variants", errors, required=True)
    return platform_id, variants


def load_skillsets(
    root: Path | None = None,
    *,
    contracts: Mapping[str, CapabilityContractDeclaration] | None = None,
) -> dict[str, Skillset]:
    """Every skillset under ``root`` (the packaged directory when omitted), by id. A missing
    directory is an empty catalog. One invalid skillset raises: a catalog that silently drops
    one would turn its author's mistake into a coverage refusal on someone else's cycle."""
    base = PACKAGED_SKILLSETS_DIR if root is None else root
    if not base.is_dir():
        return {}
    return {
        entry.name: load_skillset(entry, contracts=contracts)
        for entry in sorted(base.iterdir())
        if entry.is_dir() and entry.name != SHARED_DIR and not entry.name.startswith(".")
    }


@functools.cache
def packaged_skillsets() -> Mapping[str, Skillset]:
    """The skillsets this deployment holds, read once. An agent carries the version the
    deployment holds (§5.2), so the catalog is fixed for the life of the process."""
    return MappingProxyType(load_skillsets())


def _names(value: Any, field: str, errors: list[str], *, required: bool) -> tuple[str, ...]:
    """A list of distinct, non-empty names, or ``()`` with the defect recorded."""
    if value is None and not required:
        return ()
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
        errors.append(f"{field} must be a list of names")
        return ()
    if required and not value:
        errors.append(f"{field} must name at least one")
    if len(set(value)) != len(value):
        errors.append(f"{field} lists a name more than once")
    return tuple(value)


def _prerequisites(value: Any, errors: list[str]) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        errors.append("prerequisites must be a list of `{provider: <name>}`")
        return ()
    providers: list[str] = []
    for entry in value:
        provider = entry.get("provider") if isinstance(entry, dict) else None
        if not isinstance(provider, str) or not provider.strip() or set(entry) != {"provider"}:
            errors.append("prerequisites must be a list of `{provider: <name>}`")
            return ()
        providers.append(provider)
    if len(set(providers)) != len(providers):
        errors.append("prerequisites lists a provider more than once")
    return tuple(providers)


def _capabilities(
    value: Any, errors: list[str], contracts: Mapping[str, CapabilityContractDeclaration] | None
) -> tuple[SkillsetCapability, ...]:
    if not isinstance(value, list) or not value:
        errors.append("capabilities must list at least one contract the skillset specializes")
        return ()
    parsed: list[SkillsetCapability] = []
    seen: set[str] = set()
    for index, entry in enumerate(value):
        if not isinstance(entry, dict) or not isinstance(entry.get("contract"), str):
            errors.append(f"capabilities[{index}]: names no contract")
            continue
        name = entry["contract"]
        where = f"capability {name}"
        unknown = sorted(set(entry) - _CAPABILITY_FIELDS)
        if unknown:
            errors.append(f"{where}: unknown field: {', '.join(unknown)}")
        if name in seen:
            errors.append(f"{where}: listed more than once")
        seen.add(name)
        modes = _modes(entry.get("modes"), where, errors, capability_contract(name, contracts))
        skills = _names(entry.get("skills"), f"{where}: skills", errors, required=False)
        tools = _tools(entry.get("tools"), where, errors)
        parsed.append(SkillsetCapability(name, modes, skills, tools))
    return tuple(parsed)


def _modes(
    value: Any, where: str, errors: list[str], contract: CapabilityContractDeclaration | None
) -> tuple[VerificationMode, ...]:
    if contract is None:
        # A skillset specializes; it never defines (§4.1).
        errors.append(f"{where}: no such capability contract")
    names = _names(value, f"{where}: modes", errors, required=False)
    modes: list[VerificationMode] = []
    for name in names:
        try:
            mode = VerificationMode(name)
        except ValueError:
            known = ", ".join(m.value for m in VerificationMode)
            errors.append(f"{where}: {name!r} is not a verification mode ({known})")
            continue
        if contract is not None and mode not in contract.modes:
            errors.append(f"{where}: the contract doesn't run in {name} mode")
        modes.append(mode)
    return tuple(modes)


def _tools(value: Any, where: str, errors: list[str]) -> tuple[ToolRequest, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        errors.append(f"{where}: tools must be a list")
        return ()
    tools: list[ToolRequest] = []
    for entry in value:
        fields = (
            [entry.get(f) for f in ("id", "provider", "location")]
            if isinstance(entry, dict)
            else []
        )
        if (
            not isinstance(entry, dict)
            or set(entry) != _TOOL_FIELDS
            or any(not isinstance(f, str) or not f.strip() for f in fields)
        ):
            errors.append(f"{where}: a tool is `{{id, provider, location}}`")
            continue
        if entry["location"] not in TOOL_LOCATIONS:
            errors.append(
                f"{where}: tool {entry['id']}: location {entry['location']!r} is not one of "
                f"{', '.join(TOOL_LOCATIONS)}"
            )
            continue
        tools.append(ToolRequest(entry["id"], entry["provider"], entry["location"]))
    if len({t.id for t in tools}) != len(tools):
        errors.append(f"{where}: a tool is requested more than once")
    return tuple(tools)


def _skill_problem(directory: Path) -> str:
    """Why ``directory`` isn't a skill, or ``""``. A skill is a directory holding a
    ``SKILL.md`` whose front matter gives its ``name`` and ``description`` (§7)."""
    skill_file = directory / SKILL_FILE
    if not skill_file.is_file():
        return f"no {SKILL_FILE} in {directory.name}/"
    try:
        header, _body = parse_frontmatter(skill_file.read_bytes().decode("utf-8"))
    except UnicodeDecodeError:
        return f"{SKILL_FILE} is not UTF-8 text"
    except FrontmatterError as exc:
        return f"{SKILL_FILE} front matter: {exc}"
    missing = [k for k in ("name", "description") if not str(header.get(k) or "").strip()]
    if missing:
        return f"{SKILL_FILE} front matter lacks {', '.join(missing)}"
    try:
        _supersedes(header)
    except ValueError as exc:
        return f"{SKILL_FILE} front matter: {exc}"
    return ""


#: A lesson pattern's id, as ``memory.lessons.pattern_id_for`` writes it.
_PATTERN_ID = re.compile(r"pat_[0-9a-f]{16}")


def skill_supersedes(skill_md: str) -> tuple[str, ...]:
    """The lesson patterns a skill's ``SKILL.md`` says it supersedes (§10a): its front matter's
    ``supersedes``, a list of pattern ids, or ``()`` when it names none. The skillset's load
    refused any other value, so a kept copy's text reads here as it was checked."""
    header, _body = parse_frontmatter(skill_md)
    return _supersedes(header)


def _supersedes(header: Mapping[str, Any]) -> tuple[str, ...]:
    value = header.get("supersedes")
    if value is None:
        return ()
    if not isinstance(value, list) or not all(
        isinstance(v, str) and _PATTERN_ID.fullmatch(v) for v in value
    ):
        raise ValueError(
            f"supersedes is a list of lesson pattern ids (pat_ and 16 hex digits), not {value!r}"
        )
    return tuple(value)
