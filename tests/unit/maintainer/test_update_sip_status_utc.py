"""#2710: every stamp ``update_sip_status`` writes is UTC, whatever zone the box is in.

The script stamped ``datetime.now().isoformat() + "Z"``: the machine's local time, labelled UTC.
On an EDT box every ``updated_at`` read four hours early (SIP-0114, promoted at 22:44Z on
2026-10-23, was stamped ``18:44:13Z``). Each test runs the script in a zone well away from UTC
and reads the stamps it wrote against the UTC clock.
"""

from __future__ import annotations

import importlib.util
import os
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "maintainer" / "update_sip_status.py"

# The stamps' shape since the script was written: ISO 8601, naive, with a ``Z`` suffix. A fix
# that appended ``Z`` to an aware isoformat would write ``…+00:00Z``.
_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z")


@pytest.fixture
def zone():
    """Set the process's local zone, and put the original back afterwards."""
    original = os.environ.get("TZ")

    def set_zone(name: str) -> None:
        os.environ["TZ"] = name
        time.tzset()
        # Without the zone's data the C library falls back to UTC, and every assertion
        # below would pass on the bug.
        assert datetime.now().astimezone().utcoffset() != timedelta(0), f"{name} is UTC here"

    yield set_zone
    if original is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = original
    time.tzset()


@pytest.fixture
def tool(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("update_sip_status_2710", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sips = tmp_path / "sips"
    for d in ("proposed", "accepted", "implemented", "deprecated"):
        (sips / d).mkdir(parents=True)
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(mod, "REGISTRY_FILE", sips / "registry.yaml")
    for name in ("PROPOSED", "ACCEPTED", "IMPLEMENTED", "DEPRECATED"):
        monkeypatch.setattr(mod, f"{name}_DIR", sips / name.lower())
    monkeypatch.setattr(
        mod,
        "STATUS_TO_FOLDER",
        {s: sips / s for s in ("proposed", "accepted", "implemented", "deprecated")},
    )
    monkeypatch.setenv("SQUADOPS_MAINTAINER", "1")
    return mod, tmp_path


def _sip(root: Path, folder: str, head: dict) -> Path:
    path = root / "sips" / folder / "SIP-Clock-Demo.md"
    status = head["status"].capitalize()
    path.write_text(f"---\n{yaml.safe_dump(head)}---\n\n# Clock Demo\n\n**Status:** {status}\n")
    return path


def _frontmatter(path: Path) -> dict:
    return yaml.safe_load(path.read_text().split("---\n")[1])


def _as_utc(stamp: str) -> datetime:
    assert _STAMP.fullmatch(stamp), stamp
    return datetime.fromisoformat(stamp.removesuffix("Z")).replace(tzinfo=UTC)


def _proposed(root: Path) -> tuple[Path, Path]:
    head = {"sip_uid": "uid-clock", "title": "Clock Demo", "status": "proposed", "author": "a"}
    sip = _sip(root, "proposed", head)
    (root / "sips" / "registry.yaml").write_text(yaml.safe_dump({"last_assigned": 7, "sips": []}))
    return sip, root / "sips"


def _accepted(root: Path) -> tuple[Path, Path]:
    head = {"sip_uid": "uid-clock", "sip_number": 7, "title": "Clock Demo", "status": "accepted"}
    sip = _sip(root, "accepted", head)
    row = {
        "sip_uid": "uid-clock",
        "sip_number": 7,
        "path": "sips/accepted/SIP-Clock-Demo.md",
        "status": "accepted",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    (root / "sips" / "registry.yaml").write_text(
        yaml.safe_dump({"last_assigned": 7, "sips": [row]})
    )
    return sip, root / "sips"


# (the SIP before, the transition, where it lands, the registry fields it stamps). Between them
# the three transitions reach all five sites that stamp: the frontmatter's ``updated_at``, a new
# SIP's ``created_at`` on acceptance, the accepted row, a deprecated proposal's row, and an
# implemented row.
_TRANSITIONS = [
    pytest.param(
        _proposed,
        "accepted",
        "accepted/SIP-0008-Clock-Demo.md",
        ("created_at", "updated_at"),
        id="proposed to accepted",
    ),
    pytest.param(
        _proposed,
        "deprecated",
        "deprecated/SIP-Clock-Demo.md",
        ("created_at", "updated_at"),
        id="proposed to deprecated",
    ),
    pytest.param(
        _accepted,
        "implemented",
        "implemented/SIP-Clock-Demo.md",
        ("updated_at",),
        id="accepted to implemented",
    ),
]


@pytest.mark.parametrize(("make", "new_status", "lands", "row_fields"), _TRANSITIONS)
def test_every_stamp_a_transition_writes_is_utc_on_a_box_away_from_utc(
    tool, zone, make, new_status, lands, row_fields
):
    """Bug caught: a stamp of local time labelled ``Z``. In New York it reads four or five
    hours before the UTC clock that bracketed the call."""
    mod, root = tool
    sip, sips = make(root)
    zone("America/New_York")

    before = datetime.now(UTC)
    assert mod.update_sip_status(sip, new_status)
    after = datetime.now(UTC)

    [row] = yaml.safe_load((sips / "registry.yaml").read_text())["sips"]
    stamps = {"frontmatter updated_at": _frontmatter(sips / lands)["updated_at"]}
    stamps |= {f"registry {field}": row[field] for field in row_fields}
    off_the_clock = {
        where: stamp for where, stamp in stamps.items() if not before <= _as_utc(stamp) <= after
    }
    assert off_the_clock == {}, f"UTC window {before.isoformat()} .. {after.isoformat()}"


@pytest.mark.parametrize("name", ["America/New_York", "Asia/Kolkata"])
def test_the_stamp_is_utc_on_either_side_of_utc(zone, tool, name):
    """Bug caught: a stamp that follows the local zone, behind UTC (New York) or ahead of it by
    a half-hour offset (Kolkata), or that writes ``+00:00`` before its ``Z``."""
    mod, _ = tool
    zone(name)

    before = datetime.now(UTC)
    stamp = mod.utc_stamp()
    after = datetime.now(UTC)

    assert before <= _as_utc(stamp) <= after


def test_a_proposal_that_states_its_created_at_keeps_it(tool, zone):
    """Edge: the clock stamps ``created_at`` only when the proposal has none. A fix that stamped
    it always would rewrite when the SIP was written to when it was accepted."""
    mod, root = tool
    head = {
        "sip_uid": "uid-clock",
        "title": "Clock Demo",
        "status": "proposed",
        "created_at": "2026-03-04T05:06:07Z",
    }
    sip = _sip(root, "proposed", head)
    (root / "sips" / "registry.yaml").write_text(yaml.safe_dump({"last_assigned": 7, "sips": []}))
    zone("America/New_York")

    assert mod.update_sip_status(sip, "accepted")

    [row] = yaml.safe_load((root / "sips" / "registry.yaml").read_text())["sips"]
    assert row["created_at"] == "2026-03-04T05:06:07Z"
