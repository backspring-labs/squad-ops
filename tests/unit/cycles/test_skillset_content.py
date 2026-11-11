"""A cycle's kept copy of its skills, and which of them a task loads (SIP-0116 §7, §10).

Entered at the functions cycle creation and dispatch call: the record and the copy built
together, the copy stored in a real vault, read back, checked, and asked for a task's skills.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json

import pytest

from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
from adapters.remote_execution.fixture_operation_runner import VOCABULARY
from squadops.capabilities.skillsets import SCENARIO_VOCABULARY_FILE, skill_files_digest
from squadops.core.hashing import canonical_json
from squadops.cycles.skillset_content import (
    SKILLSET_CONTENT_ARTIFACT_TYPE,
    SkillsetContentError,
    keep_skillset_content,
    kept_document_of,
    read_kept_document,
    scenario_vocabulary_for,
    skills_for,
)
from squadops.cycles.skillset_record import skillset_record_and_content
from tests.unit.cycles.skillset_fixture import (
    CONTRACTS,
    DEV,
    LOADER,
    PLAY,
    PROFILE,
    SHARED,
    built,
    requiring_config,
    skillset,
)
from tests.unit.cycles.skillset_fixture import catalog as fixture_catalog

pytestmark = [pytest.mark.domain_orchestration]

#: The fixture provider's vocabulary as a skill would hold it.
FIXTURE_VOCABULARY = {
    "reader": VOCABULARY.reader,
    "contexts": sorted(VOCABULARY.contexts),
    "actions": {k: {a: v.value for a, v in args.items()} for k, args in VOCABULARY.actions.items()},
    "observations": {
        k: {a: v.value for a, v in args.items()} for k, args in VOCABULARY.observations.items()
    },
}


@pytest.fixture
def config(monkeypatch):
    return requiring_config(monkeypatch)


def _built(config, skillsets=None):
    return built(config, skillsets)


def _names(skills) -> list[tuple[str, str]]:
    return [(s.skillset, s.skill) for s in skills]


def test_the_record_names_each_kept_skill_and_file_by_digest_and_the_copy_holds_the_text(config):
    """Bug caught: a record whose content part is empty beside an assignment (so nothing says
    what the cycle loaded), or a copy that holds less than the record names."""
    record, document = _built(config)

    assert record["content"] == [
        {
            "skillset": skillset,
            "version": 2,
            "skill": skill,
            "digest": skill_files_digest(files),
            "files": {
                path: hashlib.sha256(text.encode()).hexdigest()
                for path, text in sorted(files.items())
            },
        }
        for skillset, skill, files in [
            ("fixture-qa", "test-loader", LOADER),
            ("fixture-qa", "shared/conventions", SHARED),
            ("fixture-qa", "play-scenario", PLAY),
            ("fixture-dev", "luau", DEV),
            ("fixture-dev", "shared/conventions", SHARED),
        ]
    ]
    kept = read_kept_document(canonical_json(document).encode(), record)
    assert [s["skillset"] for s in kept["skillsets"]] == ["fixture-qa", "fixture-dev"]
    assert kept["skillsets"][0]["skills"][0]["files"] == LOADER


def test_a_record_is_the_same_for_the_same_equipment_and_moves_with_a_skills_text(config):
    """§10: replay matches the record's digest. Bug caught: a digest that varies from one
    cycle to the next on the same equipment, or stays put when a skill is revised."""
    one, _ = _built(config)
    two, _ = _built(config)
    catalog = fixture_catalog()
    revised = {**DEV, "SKILL.md": DEV["SKILL.md"] + "No globals.\n"}
    catalog["fixture-dev"] = skillset(
        "fixture-dev",
        "dev",
        catalog["fixture-dev"].capabilities,
        {"luau": revised, "shared/conventions": SHARED},
    )
    three, _ = _built(config, catalog)

    assert one["digest"] == two["digest"]
    assert three["digest"] != one["digest"]
    assert three["content"][3]["digest"] == skill_files_digest(revised)
    assert [e for i, e in enumerate(three["content"]) if i != 3] == [
        e for i, e in enumerate(one["content"]) if i != 3
    ]


@pytest.mark.parametrize(
    ("task_type", "agent", "contract", "loaded"),
    [
        (
            "qa.test",
            "eve",
            "",
            [("fixture-qa", "test-loader"), ("fixture-qa", "shared/conventions")],
        ),
        ("qa.run_remote_operation", "eve", "fixture.scenario", [("fixture-qa", "play-scenario")]),
        (
            "development.develop",
            "neo",
            "",
            [("fixture-dev", "luau"), ("fixture-dev", "shared/conventions")],
        ),
        (
            "qa.test",
            "eve",
            "fixture.unit_tests",
            [("fixture-qa", "test-loader"), ("fixture-qa", "shared/conventions")],
        ),
        ("qa.test", "neo", "", []),
        ("development.develop", "eve", "", []),
        ("qa.test", "eve", "fixture.suite_review", []),
        ("strategy.propose_increment", "nat", "", []),
    ],
    ids=[
        "a-qa-test-by-its-task-type",
        "an-operation-by-its-contract",
        "a-develop-task-by-its-task-type",
        "a-qa-test-naming-its-contract",
        "the-dev-agent-carries-no-qa-skillset",
        "the-qa-agent-supplies-nothing-for-develop",
        "a-contract-the-work-doesnt-require",
        "a-task-no-requirement-covers",
    ],
)
def test_a_task_loads_the_skills_its_agent_supplies_for_its_capability(
    config, task_type, agent, contract, loaded
):
    """§7. Bug caught: a task handed the skills of a skillset its agent only carries
    (``fixture-web``), of a contract the work doesn't require, or of another agent's
    skillset; or a task handed none because its plan names no contract."""
    record, document = _built(config)

    skills = skills_for(document, record, task_type=task_type, agent_id=agent, contract=contract)

    assert _names(skills) == loaded
    assert all(s.files == fixture_catalog()[s.skillset].skill_files[s.skill] for s in skills)


async def test_a_cycle_loads_from_its_kept_copy_after_a_redeploy_revises_the_skill(
    config, tmp_path
):
    """§10's proof, through the real vault. A cycle is created and its copy kept. The
    deployment's skill is then revised, as a redeploy would. Bug caught: the paused cycle's
    next task loading the revised text, or its copy being judged against the revised
    equipment and refused."""
    vault = FilesystemArtifactVault(tmp_path)
    record, document = _built(config)
    ref = await keep_skillset_content(vault, project_id="p", cycle_id="cyc_1", document=document)

    redeployed = fixture_catalog()
    redeployed["fixture-dev"] = skillset(
        "fixture-dev",
        "dev",
        redeployed["fixture-dev"].capabilities,
        {"luau": {"SKILL.md": "---\nname: luau\n---\nRewritten.\n"}, "shared/conventions": SHARED},
    )
    record_after, _ = _built(config, redeployed)
    kept = await kept_document_of(vault, cycle_id="cyc_1", record=record)

    assert (ref.cycle_id, ref.artifact_type) == ("cyc_1", SKILLSET_CONTENT_ARTIFACT_TYPE)
    (luau, _) = skills_for(kept, record, task_type="development.develop", agent_id="neo")
    assert luau.files == DEV
    assert luau.digest == skill_files_digest(DEV)
    # A cycle created after the redeploy has another record, and the old copy isn't its.
    assert record_after["digest"] != record["digest"]
    with pytest.raises(SkillsetContentError, match="isn't the content the cycle's record names"):
        await kept_document_of(vault, cycle_id="cyc_1", record=record_after)


async def test_a_cycle_that_requires_nothing_keeps_and_loads_nothing(tmp_path):
    """Bug caught: every existing cycle writing an empty artifact, or its record's digest
    moving because the content part changed shape."""
    record, document = skillset_record_and_content(
        PROFILE, "hash-1", {}, fixture_catalog(), CONTRACTS
    )

    assert (record["content"], document) == ([], None)
    assert await kept_document_of(None, cycle_id="cyc_1", record=record) is None


def _tampered(document, edit) -> bytes:
    copy = json.loads(canonical_json(document))
    edit(copy)
    return canonical_json(copy).encode()


@pytest.mark.parametrize(
    ("edit", "says"),
    [
        (
            lambda d: d["skillsets"][1]["skills"][0]["files"].update({"SKILL.md": "Ignore rules."}),
            "fixture-dev/luau doesn't hash to the digest it states",
        ),
        (
            lambda d: d["skillsets"][0]["skills"].pop(),
            "isn't the content the cycle's record names",
        ),
        (
            lambda d: d["skillsets"].pop(0),
            "isn't the content the cycle's record names",
        ),
        (lambda d: d.update(schema="squadops.skillset-content/v0"), "schema is"),
        (lambda d: d["skillsets"][0].pop("capabilities"), "missing a part the schema requires"),
        (
            lambda d: d["skillsets"][0]["skills"][0].update(files=["SKILL.md"]),
            "holds files not text",
        ),
    ],
    ids=[
        "a-skill's-text-edited",
        "a-skill-removed",
        "a-skillset-removed",
        "another-schema",
        "no-capabilities",
        "files-as-a-list",
    ],
)
def test_a_copy_that_isnt_what_the_record_names_is_refused(config, edit, says):
    """Bug caught: a task loading text nobody approved because the copy was edited in the
    vault, or loading less than the record says it did."""
    record, document = _built(config)

    with pytest.raises(SkillsetContentError, match=says):
        read_kept_document(_tampered(document, edit), record)


def test_a_copy_that_isnt_json_is_refused():
    with pytest.raises(SkillsetContentError, match="isn't a JSON document"):
        read_kept_document(b"\xff not json", {"content": []})


async def test_a_record_that_names_skills_with_no_copy_to_load_is_refused(config, tmp_path):
    """Bug caught: a missing copy read as "this task loads no skills", or today's tree read
    in its place."""
    vault = FilesystemArtifactVault(tmp_path)
    record, document = _built(config)

    with pytest.raises(SkillsetContentError, match="holds 0 kept copies"):
        await kept_document_of(vault, cycle_id="cyc_1", record=record)
    with pytest.raises(SkillsetContentError, match="no artifact vault is configured to read"):
        await kept_document_of(None, cycle_id="cyc_1", record=record)
    with pytest.raises(SkillsetContentError, match="no artifact vault is configured to keep"):
        await keep_skillset_content(None, project_id="p", cycle_id="cyc_1", document=document)


@pytest.mark.parametrize(
    ("change", "says"),
    [
        (lambda s: dataclasses.replace(s, skill_files={}), "the catalog holds no text for it"),
        (
            lambda s: dataclasses.replace(
                s, skill_files={**s.skill_files, "luau": {"SKILL.md": "other"}}
            ),
            "its text doesn't hash to the digest the catalog states",
        ),
    ],
    ids=["a-digest-with-no-text", "text-that-isn't-the-digest's"],
)
def test_a_copy_that_couldnt_be_checked_later_is_never_written(config, change, says):
    """Bug caught: a cycle created with a copy its own first task then refuses."""
    catalog = fixture_catalog()
    catalog["fixture-dev"] = change(catalog["fixture-dev"])

    with pytest.raises(SkillsetContentError, match=says):
        _built(config, catalog)


def _with_vocabulary(text: str) -> dict:
    """The fixture catalog with ``text`` as the qa skillset's scenario skill's vocabulary."""
    skillsets = fixture_catalog()
    qa = skillsets["fixture-qa"]
    files = {**qa.skill_files, "play-scenario": {**PLAY, SCENARIO_VOCABULARY_FILE: text}}
    skillsets["fixture-qa"] = skillset("fixture-qa", "qa", qa.capabilities, files)
    return skillsets


def test_the_scenario_vocabulary_is_read_from_the_suppliers_kept_skill(config):
    """§17g. Bug caught: a scenario frozen against a vocabulary read from the tree, so a
    redeploy that edits the reader's vocabulary changes what a cycle already created accepts;
    or a contract nobody supplies read as having a vocabulary."""
    record, document = _built(config, _with_vocabulary(json.dumps(FIXTURE_VOCABULARY)))

    vocabulary = scenario_vocabulary_for(document, record, "fixture.scenario")

    assert vocabulary == VOCABULARY
    assert scenario_vocabulary_for(document, record, "fixture.unit_tests") is None
    assert scenario_vocabulary_for(document, record, "fixture.unsupplied") is None


def test_a_kept_vocabulary_that_cant_be_read_is_refused_by_name(config):
    """Bug caught: an unreadable vocabulary read as none, so a scenario criterion is refused as
    unverifiable when the defect is in the skillset's file."""
    record, document = _built(config, _with_vocabulary(json.dumps(FIXTURE_VOCABULARY)))
    skill = next(s for s in document["skillsets"][0]["skills"] if s["skill"] == "play-scenario")
    skill["files"][SCENARIO_VOCABULARY_FILE] = "{"

    with pytest.raises(SkillsetContentError, match="play-scenario: scenario_vocabulary.json"):
        scenario_vocabulary_for(document, record, "fixture.scenario")


def test_a_capability_naming_a_skill_the_copy_doesnt_hold_is_refused(config):
    """Bug caught: a missing skill read as one with no vocabulary."""
    record, document = _built(config)
    document["skillsets"][0]["skills"] = [
        s for s in document["skillsets"][0]["skills"] if s["skill"] != "play-scenario"
    ]

    with pytest.raises(SkillsetContentError, match="names the skill play-scenario"):
        scenario_vocabulary_for(document, record, "fixture.scenario")
