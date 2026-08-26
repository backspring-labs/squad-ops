"""One home for the success-status default — #772, the seventh site of a rule that
recurred five times in three weeks (#1067).

Bug caught: the contract deriver asserts 201 for an undeclared collection POST while the
skeleton's decorator omits ``status_code`` and FastAPI answers 200 — a contract no
correct application can win. It was gate-mitigated (an undeclared status is rejected at
framing) and never fixed; on stack #1 it would have been a framing re-roll on every roll
whose author forgot the line.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from squadops.capabilities.scaffold import InterfaceManifest, expand
from squadops.capabilities.scaffold_contract import emit_contract_dict
from squadops.capabilities.success_status import derived_success_status, success_status_for
from squadops.cycles.verification_contract import VerificationContract
from tests.unit.capabilities._stack_fixtures import manifest_dict_for_stack

pytestmark = [pytest.mark.domain_capabilities]

_SRC = Path(__file__).resolve().parents[3] / "src" / "squadops"


class TestTheSeam:
    @pytest.mark.parametrize(
        "method, path, declared, expected",
        [
            ("POST", "/runs", None, 201),
            ("POST", "/runs/{run_id}/join", None, 200),
            ("POST", "/runs", 202, 202),
            ("GET", "/runs", None, 200),
            ("GET", "/runs", 203, 203),
            ("DELETE", "/runs/{run_id}", None, 200),
        ],
    )
    def test_declared_wins_then_derived_then_http_default(self, method, path, declared, expected):
        ep = SimpleNamespace(method=method, path=path, success_status=declared)
        assert success_status_for(ep) == expected

    def test_derived_is_none_where_no_status_probe_exists(self):
        assert derived_success_status("GET", "/runs") is None
        assert derived_success_status("post", "/runs") == 201
        assert derived_success_status("POST", "/runs/{id}/leave") == 200

    def test_a_child_row_is_a_post_by_construction(self):
        child = SimpleNamespace(path="/runs/{run_id}/join", success_status=None)
        assert success_status_for(child, "POST") == 200


def _undeclared_collection_post(stack: str) -> InterfaceManifest:
    """The stack's reference manifest with the collection POST's status REMOVED."""
    raw = manifest_dict_for_stack(stack)
    for ep in raw["api"]["endpoints"]:
        if ep["method"] == "POST" and "{" not in ep["path"]:
            ep.pop("success_status", None)
    return InterfaceManifest.from_yaml(yaml.safe_dump(raw, sort_keys=False))


class TestSkeletonAndContractAgree:
    def test_stack1_decorator_pins_the_status_the_contract_asserts(self):
        """The #772 property, end to end: undeclared collection POST -> the derived
        contract probe expects 201 AND the seeded decorator carries status_code=201."""
        manifest = _undeclared_collection_post("fullstack_fastapi_react")
        contract = VerificationContract.from_dict(emit_contract_dict(manifest))
        create = next(p for p in contract.behavioral.probes if p.request.get("path") == "/runs")
        assert create.expect["status"] == 201

        routes = next(f["content"] for f in expand(manifest) if f["name"] == "backend/routes.py")
        assert re.search(r'@router\.post\("/runs",[^\n]*status_code=201\)', routes), routes

    def test_nextjs_stub_tells_the_dev_the_status_the_contract_asserts(self):
        manifest = _undeclared_collection_post("nextjs_ts")
        contract = VerificationContract.from_dict(emit_contract_dict(manifest))
        create = next(p for p in contract.behavioral.probes if p.request.get("path") == "/api/runs")
        route = next(f["content"] for f in expand(manifest) if f["name"] == "app/api/runs/route.ts")
        assert create.expect["status"] == 201
        assert "POST /api/runs — respond 201" in route


def test_the_rule_has_no_second_home():
    """Structural: a re-introduced ``success_status or 201`` / ``201 if ... else 200``
    anywhere outside the seam is the defect this file exists to end."""
    copies = []
    pattern = re.compile(
        r"success_status(?:\", None\))?\s+or\s+20[01]\b|\b201 if [^\n]* else 200\b"
    )
    for path in _SRC.rglob("*.py"):
        if path.name == "success_status.py":
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if line.lstrip().startswith("#") or '"""' in line:
                continue
            if pattern.search(line):
                copies.append(f"{path.relative_to(_SRC)}:{lineno}: {line.strip()}")
    assert copies == [], "\n".join(copies)
