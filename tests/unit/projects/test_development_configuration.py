"""The Development Configuration and its start declaration (SIP-0112 §B.5, contract 7; E.4.2).

The shared fixture's recordings are the contract's shape. The reader must round-trip the valid
one exactly and refuse the other forms the way §8.2.1 says. Everything a runner will execute is
refused at recording if it is malformed, rather than mangled later into a "start failed".
"""

import copy

import pytest

from squadops.projects.development_configuration import (
    ConfigurationInvalid,
    UnknownConfigurationVersion,
    checks_needing,
    discover_instruction_sources,
    parse_configuration,
    parse_technical,
)
from tests.fixtures.shared_contract.repository import (
    build_repository,
    recorded,
    tracked_files,
)


def test_the_fixtures_recorded_configuration_reads_back_exactly():
    """Contract 7. Bug caught: a key renamed, dropped or defaulted on its way through the
    reader, so the document a runner reads isn't the one the fixture froze."""
    valid = recorded("development_configuration", "valid")

    configuration = parse_configuration(valid)

    assert configuration.to_document() == valid
    start = configuration.commands.start
    assert start.start == (
        "python3",
        "-m",
        "tally",
        "serve",
        "--host",
        "0.0.0.0",
        "--port",
        "18407",
    )
    assert start.build == (("python3", "tools/build.py"),)
    assert start.evaluation_environment == (
        ("TALLY_ADMIN_TOKEN", "secret://tally_evaluation_admin_token"),
    )


def test_the_fixtures_bad_forms_are_refused_or_left_for_the_consumer():
    with pytest.raises(UnknownConfigurationVersion):
        parse_configuration(recorded("development_configuration", "unknown_major"))
    with pytest.raises(ConfigurationInvalid) as missing:
        parse_configuration(recorded("development_configuration", "missing_field"))
    stale = parse_configuration(recorded("development_configuration", "stale_commit"))
    current = parse_configuration(recorded("development_configuration", "valid"))

    assert missing.value.field == "configuration.revision"
    # Whether a record is stale is a comparison with the unit's pin, which only the consumer
    # holds: the reader reads it as recorded.
    assert stale.validated_at_commit != current.validated_at_commit


def _technical(**start_overrides):
    technical = copy.deepcopy(
        recorded("development_configuration", "valid")["configuration"]["technical"]
    )
    technical["commands"]["start"].update(start_overrides)
    return technical


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"start": "python3 -m tally serve"}, "technical.commands.start.start"),
        ({"build": ["python3", "tools/build.py"]}, "technical.commands.start.build[0]"),
        ({"working_directory": "../../.."}, "technical.commands.start.working_directory"),
        (
            {"readiness": {"kind": "smoke", "target": "x", "timeout_seconds": 5}},
            "technical.commands.start.readiness.kind",
        ),
        (
            {"readiness": {"kind": "http", "target": "http://127.0.0.1:18407/healthz"}},
            "technical.commands.start.readiness.timeout_seconds",
        ),
        (
            {"readiness": {"kind": "http", "target": "/healthz", "timeout_seconds": 5}},
            "technical.commands.start.readiness.target",
        ),
        ({"entry_points": []}, "technical.commands.start.entry_points"),
        (
            {"evaluation_environment": {"TALLY_ADMIN_TOKEN": "hunter2"}},
            "technical.commands.start.evaluation_environment.TALLY_ADMIN_TOKEN",
        ),
    ],
    ids=[
        "shell-string-start",
        "flat-build-list",
        "escaping-directory",
        "unknown-readiness",
        "undeclared-timeout",
        "relative-readiness-url",
        "no-entry-point",
        "secret-as-a-value",
    ],
)
def test_a_start_declaration_a_runner_would_misread_is_refused_naming_its_field(change, field):
    """Bugs caught: `"python3 -m tally"` run as the argv p, y, t…; a flat build list run as
    one-letter commands; a working directory outside the repository; a secret's value written
    into a record, which Q40 forbids."""
    with pytest.raises(ConfigurationInvalid) as refused:
        parse_technical(_technical(**change))
    assert refused.value.field == field


def test_the_checks_own_install_and_build_round_trip_and_are_argvs():
    """#2468's review. Bugs caught: the checks' setup dropped on its way to the record, so every
    check of a product that needs its dependencies records FAIL inherited; a shell string run as
    one-letter commands; the start declaration's steps standing in for the checks'."""
    doc = copy.deepcopy(recorded("development_configuration", "valid"))
    commands = doc["configuration"]["technical"]["commands"]
    commands["install"] = [["pip", "install", "-e", "."]]
    commands["build"] = [["python3", "tools/build.py"]]

    configuration = parse_configuration(doc)

    assert configuration.to_document() == doc
    assert configuration.commands.check_setup == (
        ("pip", "install", "-e", "."),
        ("python3", "tools/build.py"),
    )
    assert (
        parse_configuration(recorded("development_configuration", "valid")).commands.check_setup
        == ()
    )
    commands["install"] = ["pip install -e ."]
    with pytest.raises(ConfigurationInvalid) as refused:
        parse_configuration(doc)
    assert refused.value.field == "technical.commands.install[0]"


def test_checks_are_unique_and_their_environment_is_named():
    technical = _technical()
    technical["commands"]["checks"].append({"id": "parse", "argv": ["true"]})
    with pytest.raises(ConfigurationInvalid, match="unique"):
        parse_technical(technical)

    technical = _technical()
    technical["commands"]["checks"][0]["requires_environment"] = ["lowercase"]
    with pytest.raises(ConfigurationInvalid, match="environment variable names"):
        parse_technical(technical)


def test_a_project_not_evaluated_needs_no_start_declaration():
    technical = _technical()
    del technical["commands"]["start"]

    *_, commands = parse_technical(technical)

    assert commands.start is None
    assert [c.id for c in commands.checks] == [
        "build",
        "parse",
        "ledger",
        "server",
        "report",
        "notify",
    ]


def test_a_check_needing_absent_environment_is_named_by_its_declaration():
    """The inherited baseline's UNVERIFIED comes from the declaration: notify exits 0 with
    `OK (skipped=1)` when TALLY_SMTP_HOST is unset, which an exit status would read as PASS."""
    *_, commands = parse_technical(_technical())

    assert checks_needing({"PATH"}, commands) == ["notify"]
    assert checks_needing({"TALLY_SMTP_HOST"}, commands) == []


def test_the_repositorys_instruction_sources_are_found_with_their_digests(tmp_path):
    repo = build_repository(tmp_path / "tally")
    files = tracked_files(repo.path, repo.second_commit)

    sources = discover_instruction_sources(files, repo.second_commit)

    assert sources == tuple(
        parse_configuration(recorded("development_configuration", "valid")).instruction_sources
    )
    assert discover_instruction_sources({"README.md": b"x"}, repo.second_commit) == ()


def test_a_checks_findings_reader_round_trips_and_one_that_doesnt_exist_is_refused():
    """#2609. Bugs caught: a declared reader dropped on its way to the record, so a check that
    already fails is read whole and a regression inside it passes; a misspelt reader stored and
    sent to the sandbox, which refuses the check at run time instead of at configure."""
    doc = copy.deepcopy(recorded("development_configuration", "valid"))
    checks = doc["configuration"]["technical"]["commands"]["checks"]
    [parse] = [c for c in checks if c["id"] == "parse"]
    parse["findings"] = "lines"

    configuration = parse_configuration(doc)

    assert configuration.to_document() == doc
    assert {c.id: c.findings for c in configuration.commands.checks}["parse"] == "lines"
    assert {c.id: c.findings for c in configuration.commands.checks}["ledger"] is None
    parse["findings"] = "eslint"
    with pytest.raises(ConfigurationInvalid) as refused:
        parse_configuration(doc)
    assert refused.value.field.endswith(".findings")
    assert "eslint" in str(refused.value)
