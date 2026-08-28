"""The SIP filename names the SIP, not a slice of its title (update_sip_status.py)."""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

_SCRIPT = pathlib.Path(__file__).resolve().parents[3] / "scripts/maintainer/update_sip_status.py"
_spec = importlib.util.spec_from_file_location("update_sip_status", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
normalize_filename = _mod.normalize_filename


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        # The bug: the first-four-words rule cut a hyphenated compound mid-phrase.
        (
            "Atlas Provider Adapter — Config-Selected Inference Providers Behind a Conformance Gate",
            "SIP-0106-Atlas-Provider-Adapter.md",
        ),
        # A colon separates name from explainer the same way.
        (
            "Cycle Replay Harness: deterministic re-execution of stored artifacts",
            "SIP-0101-Cycle-Replay-Harness.md",
        ),
        # No separator: the title is the name, capped — never a dangling "and"/"with".
        ("Scaffolded Test Harness and Fill Slots", "SIP-0100-Scaffolded-Test-Harness.md"),
        # A short title survives whole.
        ("Squad-Authored Manifest", "SIP-0103-Squad-Authored-Manifest.md"),
        # An en dash is a separator too; a hyphenated word is not.
        ("Duty Durability via Temporal – long-running duties", "SIP-0091-Duty-Durability-via.md"),
    ],
)
def test_filename_is_the_titles_name_capped_at_three_words(title, expected):
    number = int(expected.split("-")[1])
    assert normalize_filename(number, title) == expected
