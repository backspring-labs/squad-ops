"""#668's second half: a qa suite's mock of the frozen API client must honour its surface.

The first half — the DOM anchor contract — landed in 1.7.1 and arbitrates *where* a suite
looks. This arbitrates *what it looks through*. fay-14's failing assertions were an
`apiFetch` mock-signature and state-hydration mismatch against the frozen client, which
testid enforcement could never have caught: a suite that mocks a client the app does not
have passes against its own mock forever while the application it claims to test is never
invoked.

REPORTING-ONLY in 1.7.5 (plan §8 decision 4). The findings are handed to the author and
counted; nothing is rejected on them. Promotion waits on what a measured set produces.

STACK-AWARE by construction: nothing here or in the shared check names `apiFetch` or
`frontend/src/api.js`. The stack derives its surface from the bytes it freezes and the
check reads the declaration, so a stack with no client makes the check skip with a reason.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadops.capabilities.client_mock_surface import mock_surface_findings
from squadops.capabilities.client_surface import KIND_FUNCTION, ClientExport, ClientSurface
from squadops.capabilities.scaffold import client_surface_for

pytestmark = [pytest.mark.domain_capabilities]

_REPLAYS = Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"
_STACK = "fullstack_fastapi_react"


def _surface() -> ClientSurface:
    return client_surface_for(_STACK)


def _rules(content: str, surface: ClientSurface | None = None) -> set[str]:
    return {f.rule for f in mock_surface_findings(content, surface or _surface())}


class TestTheStackDeclaresItsClientFromTheBytesItFreezes:
    """The declaration cannot drift from the client, because it is read off it."""

    def test_the_declared_surface_is_the_frozen_clients(self):
        """Bug caught: a hand-maintained declaration going stale against the template — the
        check would then judge suites against a client that no longer exists, which is the
        very defect it exists to find, one level up."""
        surface = _surface()

        assert {e.name for e in surface.exports} == {"apiFetch", "ApiError"}
        api_fetch = next(e for e in surface.exports if e.name == "apiFetch")
        assert api_fetch.kind == KIND_FUNCTION
        assert api_fetch.param_names == ("path", "options")
        assert surface.path_prefix == "/api"
        assert surface.error_envelope_key == "error"
        assert surface.default_export is None

    def test_a_stack_with_no_declared_client_is_not_judged(self):
        """The stack seam's whole point. Next.js declares no client of this shape, so the
        check has nothing to compare against and must skip rather than invent a rule. Bug
        caught: stack #1's client leaking into a stack that never had one."""
        assert client_surface_for("nextjs_ts") is None


class TestRealEmissions:
    """Replayed against suites the squad actually wrote (the standing rule). The vault no
    longer holds fay-14's own artifact, but it holds eight suites of its class; two are
    pinned here with an accepted roll's suite as the control.
    """

    def test_a_suite_mocking_a_client_that_never_existed_is_flagged(self):
        """`cyc_71748d091367` / `art_27c87dc5939d`, a qa repair. It imports AND mocks
        `getRuns, getRun, createRun, joinRun, leaveRun` — the client exports `apiFetch` and
        `ApiError`. Every assertion in it passes against its own mock while the application
        is never invoked."""
        content = (_REPLAYS / "668-repair-mocks-a-client-that-never-existed.test.jsx").read_text()

        rules = _rules(content)

        assert "client_import_undeclared" in rules
        assert "client_mock_exports_undeclared" in rules
        detail = next(
            f.detail
            for f in mock_surface_findings(content, _surface())
            if f.rule == "client_import_undeclared"
        )
        assert "getRuns" in detail and "apiFetch" in detail, "name what was asked and what exists"

    def test_the_same_class_from_a_dev_repair_is_flagged(self):
        """`cyc_76bbec332912` / `art_5eb97fb4b7b4`, a development.correction_repair: a
        default import of a client with no default export. Two producers, one class — which
        is why the check binds to the suite rather than to a role."""
        content = (_REPLAYS / "668-repair-default-imports-the-client.test.jsx").read_text()

        assert "client_import_undeclared" in _rules(content)

    def test_an_accepted_rolls_suite_is_not_flagged(self):
        """THE over-rejection control: `cyc_05935ffcb572` / `art_d1034eefbb83` mocks the
        client correctly, by name. A check that flags a suite which shipped is wrong about
        the rule, not about the suite."""
        content = (_REPLAYS / "668-green-mocks-the-real-client.test.jsx").read_text()

        assert _rules(content) == set()


class TestTheRulesIndividually:
    """One synthetic case per rule, so a failure names which rule moved."""

    _MOCK = "vi.mock('../api', () => ({ %s }))\n"

    def test_a_mock_of_the_declared_call_passes(self):
        assert _rules(self._MOCK % "apiFetch: vi.fn()") == set()

    def test_a_mock_of_an_undeclared_export_is_flagged(self):
        assert "client_mock_exports_undeclared" in _rules(self._MOCK % "getRuns: vi.fn()")

    def test_a_mock_providing_none_of_the_clients_calls_is_flagged(self):
        """Replacing the module whole and providing no call means every import of it
        resolves to undefined at runtime — the suite tests nothing and still goes green."""
        assert "client_mock_omits_calls" in _rules(self._MOCK % "ApiError: class {}")

    def test_an_import_of_an_undeclared_name_is_flagged(self):
        assert "client_import_undeclared" in _rules("import { getRuns } from '../api'\n")

    def test_a_suite_that_never_touches_the_client_is_not_judged(self):
        """Bug caught: flagging a suite that has nothing to do with the client — the check
        must be silent on a component test that renders and asserts."""
        assert _rules("import { render } from '@testing-library/react'\n") == set()

    def test_the_check_reads_the_declaration_not_a_hardcoded_client(self):
        """The stack-seam invariant, proven by swapping the declaration: with a different
        client declared, the SAME suite is judged against the new surface. Bug caught: the
        rule keyed on `apiFetch` by name somewhere in the shared path."""
        other = ClientSurface(
            path="src/gateway.ts",
            module_specifier=r"(?:\.\./|\./)+gateway",
            exports=(ClientExport("callGateway", KIND_FUNCTION, ("route",)),),
        )
        suite = "vi.mock('../gateway', () => ({ apiFetch: vi.fn() }))\n"

        assert "client_mock_exports_undeclared" in _rules(suite, other)
        assert _rules("vi.mock('../gateway', () => ({ callGateway: vi.fn() }))\n", other) == set()
