"""The Campaign definitions a pre-registration commits beside itself (#2892).

A pre-registration fixes its Campaign's definition before the Campaign is created, and the
definition is created from the committed file (``squadops campaigns create --file``). Entered at
the request the CLI builds from that file: the API's own create schema, and the packaged script
library a deploy built from this tree resolves every pin against.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from squadops.api.campaign_schemas import CampaignCreateRequest
from squadops.llm.script import ScriptLibrary, ScriptReference, ScriptVersionMismatchError

pytestmark = [pytest.mark.domain_orchestration]

_SETS = Path(__file__).resolve().parents[3] / "docs" / "plans" / "verification-sets"
_DEFINITIONS = sorted(_SETS.glob("*-campaign.yaml"))


def _request(path: Path) -> CampaignCreateRequest:
    spec = yaml.safe_load(path.read_text())
    return CampaignCreateRequest(**spec, reason="pre-registered", idempotency_key="k")


@pytest.mark.parametrize("path", _DEFINITIONS, ids=lambda p: p.name)
def test_a_committed_definition_is_one_the_api_takes_and_its_scripts_are_packaged(path):
    """Bugs caught: a definition the create route refuses on the launch day, after its commit
    registered the soak; a script re-recorded after its pin was written, so the pin names bytes
    this tree's deploy doesn't hold and the Campaign's creation is refused (422); and one script
    named for two launches, so the second replays the first's answers."""
    request = _request(path)
    library = ScriptLibrary.packaged()

    pins = [library.resolve(ScriptReference.parse(p)) for p in request.policy.llm_scripts or []]

    assert len(pins) == len({p.name for p in pins})  # no launch replays another's answers


def test_a_pin_to_a_script_the_library_holds_at_another_version_is_refused():
    """The edge, on the committed soak definition's own first pin: the library refuses a version
    it doesn't hold, so the guard above can't pass on a stale pin."""
    first = _request(_SETS / "2-7-0-soak-campaign.yaml").policy.llm_scripts[0]
    name, _version = first.split("@")

    with pytest.raises(ScriptVersionMismatchError):
        ScriptLibrary.packaged().resolve(ScriptReference(name, "000000000000"))


def test_the_soak_definitions_are_found():
    """Bug caught: the glob above matching nothing (a rename, a moved file), so the guard
    parametrizes over no definition and passes."""
    assert {p.name for p in _DEFINITIONS} >= {
        "2-7-0-soak-campaign.yaml",
        "2-7-0-soak-dry-run-campaign.yaml",
    }
