"""The runtime API's registry cutover at start-up (SIP-0112 FR-03, R3; #2408).

Entered at ``_cut_over_project_registry``, the step ``_init_cycle_subsystem`` runs before any
reader is handed the registry, with the repository's real config/projects.yaml. The writable
registry is a recorder: its database behaviour is the integration test's.
"""

from __future__ import annotations

import pytest

from adapters.cycles import postgres_project_registry
from adapters.cycles.config_project_registry import ConfigProjectRegistry
from squadops.api.runtime.main import _cut_over_project_registry
from squadops.projects.cutover import RegistryCutoverRefused
from squadops.projects.models import ProjectProvenance

SEEDED = ProjectProvenance.SEEDED
REGISTERED = ProjectProvenance.REGISTERED


class _Writable:
    """The writable registry's cutover surface: seeds what it is told unless told to drop some."""

    def __init__(self, records=None, drop=(), referenced=()):
        self.records = dict(records or {})
        self.drop = set(drop)
        self.referenced = set(referenced)
        self.seeded_with = None

    async def seed_from_config(self, projects, *, source):
        self.seeded_with = ([p.project_id for p in projects], source)
        new = [
            p.project_id
            for p in projects
            if p.project_id not in self.records and p.project_id not in self.drop
        ]
        self.records.update({pid: SEEDED for pid in new})
        return new

    async def provenances(self):
        return dict(self.records)

    async def referenced_project_ids(self):
        return self.referenced


def _table(monkeypatch, records):
    async def read(pool):
        return records

    monkeypatch.setattr(postgres_project_registry, "writable_registry_provenances", read)


async def _config_ids():
    return [p.project_id for p in await ConfigProjectRegistry().list_projects()]


async def test_the_cutover_seeds_every_config_project_in_the_files_order(monkeypatch):
    _table(monkeypatch, {})
    registry = _Writable()

    await _cut_over_project_registry("postgres", registry, pool=object())

    config_ids = await _config_ids()
    assert len(config_ids) == 5
    assert registry.seeded_with == (config_ids, "config/projects.yaml")
    assert registry.records == {pid: SEEDED for pid in config_ids}


async def test_a_config_project_the_seed_did_not_place_stops_the_runtime_api(monkeypatch):
    """Bug caught: the squad-profile precedent's non-fatal seed, under which play_game would
    serve as 404 for as long as anyone tried (IR-1)."""
    _table(monkeypatch, {})

    with pytest.raises(RegistryCutoverRefused, match="play_game: named by config"):
        await _cut_over_project_registry("postgres", _Writable(drop={"play_game"}), pool=object())


async def test_a_missing_table_is_named_before_any_seed(monkeypatch):
    """The migration runner logs a failed migration and carries on: the cutover names it."""
    _table(monkeypatch, None)
    registry = _Writable()

    with pytest.raises(RegistryCutoverRefused, match="migration 1800 has not applied"):
        await _cut_over_project_registry("postgres", registry, pool=object())
    assert registry.seeded_with is None


async def test_unknown_referenced_ids_are_reported_and_the_cutover_serves(monkeypatch, caplog):
    _table(monkeypatch, {})
    registry = _Writable(referenced={"play_game", "retired_app"})

    await _cut_over_project_registry("postgres", registry, pool=object())

    assert "retired_app" in caplog.text and "kept as they are" in caplog.text


@pytest.mark.parametrize(
    ("records", "refused"),
    [
        (None, False),  # never cut over: no table
        ({"hello_squad": SEEDED}, False),  # rolled back with only seeded rows
        ({"hello_squad": SEEDED, "prj-tally": REGISTERED}, True),
    ],
    ids=["no-table", "only-seeded", "a-registered-project"],
)
async def test_the_config_provider_serves_only_when_it_hides_nothing(monkeypatch, records, refused):
    """R3. Bug caught: a rollback to the config file hiding a Project registered after the
    cutover from every reader."""
    _table(monkeypatch, records)
    config = ConfigProjectRegistry()

    if refused:
        with pytest.raises(RegistryCutoverRefused, match="prj-tally: registered"):
            await _cut_over_project_registry("config", config, pool=object())
    else:
        await _cut_over_project_registry("config", config, pool=object())


async def test_the_config_provider_without_a_database_has_nothing_to_hide():
    await _cut_over_project_registry("config", ConfigProjectRegistry(), pool=None)
