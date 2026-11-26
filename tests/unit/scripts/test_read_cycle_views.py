"""``scripts/dev/read_cycle_views.py``: every view of a Campaign cycle, and where they differ.

The responses below are shaped as the live deploy's were on 2026-11-26, when the script read
the Roblox project's 28 cycles and named three: the two repair cycles of #3244 and the
gate-ended cycle #3224's filter drops.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "read_cycle_views", REPO_ROOT / "scripts" / "dev" / "read_cycle_views.py"
)
views = importlib.util.module_from_spec(_spec)
sys.modules["read_cycle_views"] = views  # dataclasses resolve annotations via it
_spec.loader.exec_module(views)

PROJECT = "prj-game"
LAST_RUN_CANCELLED = (
    "its last run ended cancelled and the route names no ending. "
    "From 2.9 the route names every recorded ending (#3244), so none is on record"
)


class Deploy:
    """A runtime API's answers to the five reads, as ``APIClient.get`` gives them."""

    def __init__(self) -> None:
        self.campaigns: dict[str, dict] = {}
        self.cycles: dict[str, dict] = {}
        #: A cycle the status-filtered list leaves out, whatever status its route gives.
        self.unlisted: set[str] = set()
        self.asked: list[tuple[str, dict]] = []

    def cycle(
        self,
        cycle_id: str,
        campaign_id: str,
        *,
        status: str,
        ending: str | None,
        runs: tuple[str, ...] = ("completed",),
        ledger: str | None = None,
        log: str | None = None,
    ) -> None:
        self.cycles[cycle_id] = {
            "cycle_id": cycle_id,
            "status": status,
            "recorded_ending": ending,
            "status_conflict": None,
            "runs": [{"run_number": n, "status": s} for n, s in enumerate(runs, 1)],
        }
        campaign = self.campaigns.setdefault(campaign_id, {"ledger": [], "log": []})
        if ledger is not None:
            campaign["ledger"].append(
                {"cycles": [{"cycle_id": cycle_id, "ending": ledger, "verdict": "accepted"}]}
            )
        # The row that claims the cycle's decision, then the row that decides it.
        campaign["log"].append({"operation": "mark_launched", "binding": {"cycle_id": cycle_id}})
        if log is not None:
            campaign["log"].append({"operation": "decide", "binding": {"cycle_id": cycle_id}})
            campaign["log"].append(
                {"operation": "decide", "binding": {"cycle_id": cycle_id, "ending": log, "row": 3}}
            )

    def get(self, path: str, params: dict | None = None):
        params = params or {}
        self.asked.append((path, params))
        if path == "/api/v1/campaigns":
            items = [{"campaign_id": c} for c in self.campaigns]
        elif path.endswith("/ledger"):
            return self.campaigns[path.split("/")[4]]["ledger"]
        elif path.endswith("/control-log"):
            return self.campaigns[path.split("/")[4]]["log"]
        elif path == f"/api/v1/projects/{PROJECT}/cycles":
            items = [
                c
                for c in self.cycles.values()
                if c["status"] == params["status"] and c["cycle_id"] not in self.unlisted
            ]
        else:
            return self.cycles[path.rsplit("/", 1)[1]]
        return items[params["offset"] : params["offset"] + params["limit"]]


def _read(deploy: Deploy) -> dict[str, list[str]]:
    return {v.cycle_id: v.disagreements for v in views.read_project(deploy.get, PROJECT)}


def test_a_cycle_every_view_agrees_on_has_nothing_to_say():
    deploy = Deploy()
    deploy.cycle(
        "cyc_a",
        "cmp_1",
        status="completed",
        ending="sequence_completed",
        ledger="assessed",
        log="assessed",
    )

    [seen] = views.read_project(deploy.get, PROJECT)

    assert (seen.disagreements, seen.notes) == ([], [])
    assert (seen.route_status, seen.route_ending, seen.listed_under_status) == (
        "completed",
        "sequence_completed",
        True,
    )
    assert (seen.ledger_ending, seen.ledger_verdict, seen.log_ending, seen.log_row) == (
        "assessed",
        "accepted",
        "assessed",
        3,
    )


def test_the_three_cases_the_live_read_named_are_each_named_in_a_sentence():
    """#3244's two repair cycles and #3224's gate-ended cycle. Bug caught: a rule that reads a
    silent view as agreement everywhere, so the repair cycle an aborted Campaign left (no log
    row, no ledger row) passes with a route that names no ending."""
    deploy = Deploy()
    deploy.cycle(
        "cyc_repair_accepted",
        "cmp_1",
        status="completed",
        ending=None,
        ledger="assessed",
        log="assessed",
    )
    deploy.cycle(
        "cyc_repair_aborted", "cmp_2", status="cancelled", ending=None, runs=("cancelled",)
    )
    deploy.cycle(
        "cyc_gate_ended",
        "cmp_3",
        status="failed",
        ending="revision_unavailable",
        ledger="rejected_at_gate",
        log="rejected_at_gate",
    )
    deploy.unlisted.add("cyc_gate_ended")

    assert _read(deploy) == {
        "cyc_repair_accepted": [
            "the control log says it ended (assessed) and the route names no ending"
        ],
        "cyc_repair_aborted": [LAST_RUN_CANCELLED],
        "cyc_gate_ended": ["the list filtered by status failed doesn't return it"],
    }


def test_a_silent_view_is_not_a_disagreement_and_a_different_ending_is():
    """The ledger has a row only where a proposal was submitted. Bug caught: a cycle whose
    proposal run failed reading as a disagreement in every Campaign that never proposed."""
    deploy = Deploy()
    deploy.cycle(
        "cyc_never_proposed", "cmp_1", status="failed", ending="run_failed", log="proposal_failed"
    )
    deploy.cycle(
        "cyc_two_endings",
        "cmp_1",
        status="failed",
        ending="run_failed",
        ledger="assessed",
        log="proposal_failed",
    )

    assert _read(deploy) == {
        "cyc_never_proposed": [],
        "cyc_two_endings": ["the ledger says assessed and the control log says proposal_failed"],
    }


def test_a_cycle_cancelled_between_workloads_is_noted_and_agrees():
    """Its one run completed and the Campaign's abort cancelled the cycle at the gate: no
    record names an ending, and no view claims one."""
    deploy = Deploy()
    deploy.cycle("cyc_at_the_gate", "cmp_1", status="cancelled", ending=None, runs=("completed",))

    [seen] = views.read_project(deploy.get, PROJECT)

    assert seen.disagreements == []
    assert seen.notes == [
        "cancelled with its last run completed: the cycle's own cancel, which records no ending"
    ]


def test_the_last_run_is_the_highest_numbered_whatever_order_the_route_gives():
    deploy = Deploy()
    deploy.cycle("cyc_a", "cmp_1", status="cancelled", ending=None, runs=("completed", "cancelled"))
    deploy.cycles["cyc_a"]["runs"].reverse()

    assert _read(deploy) == {"cyc_a": [LAST_RUN_CANCELLED]}


def test_a_full_page_asks_for_the_next(monkeypatch):
    """Bug caught: the list read as one page, so a cycle on the second reads as one the
    status filter dropped, and a Campaign on the second is never read at all."""
    monkeypatch.setattr(views, "PAGE", 2)
    deploy = Deploy()
    for n in range(5):
        deploy.cycle(
            f"cyc_{n}",
            f"cmp_{n}",
            status="completed",
            ending="sequence_completed",
            ledger="assessed",
            log="assessed",
        )

    assert _read(deploy) == {f"cyc_{n}": [] for n in range(5)}
    offsets = [p["offset"] for path, p in deploy.asked if path == "/api/v1/campaigns"]
    assert offsets == [0, 2, 4]


@pytest.mark.parametrize(
    ("disagrees", "exit_code"),
    [(False, 0), (True, 1)],
    ids=["every cycle agrees", "one cycle disagrees"],
)
def test_the_exit_code_says_whether_every_cycle_agrees(capsys, disagrees, exit_code):
    deploy = Deploy()
    deploy.cycle(
        "cyc_a",
        "cmp_1",
        status="completed",
        ending=None if disagrees else "sequence_completed",
        ledger="assessed",
        log="assessed",
    )

    assert views.main([PROJECT], get=deploy.get) == exit_code

    out = capsys.readouterr().out
    assert f"{0 if disagrees else 1} of 1 cycles agree in every view" in out
    assert ("DISAGREES:" in out) is disagrees


def test_a_project_with_no_campaign_cycle_is_not_an_agreement(capsys):
    """Bug caught: a mistyped project id, or a deploy that answers an empty list, printing
    '0 of 0 cycles agree' and exiting 0, which reads as the done-when met."""
    assert views.main([PROJECT], get=Deploy().get) == 2
    assert f"project {PROJECT} has no Campaign cycle to read" in capsys.readouterr().err


def test_a_read_that_fails_is_named_and_is_not_an_agreement(capsys):
    def refused(path, params=None):
        raise RuntimeError("Error: not authenticated")

    assert views.main([PROJECT], get=refused) == 2
    assert "a read failed: RuntimeError: Error: not authenticated" in capsys.readouterr().err
