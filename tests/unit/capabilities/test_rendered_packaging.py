"""The container packaging each stack renders, and the guard over it (#598, SIP-0105 A1).

``container_packaging`` banked pf-38's three build/run defects reporting-only on every roll the
builder authored packaging for; it could see them and never stop them. With the packaging now
rendered by the scaffold, the same findings run here, over every registered stack's full
expansion, as a gate on the rendering itself. The pf-38 and pf-39 replays in
``tests/unit/cycles/test_container_packaging.py`` are this guard's negative control: the same
function reports all three defects on the bytes that carried them.

Not covered here: building or starting the image (``package_builds`` stays declared unbuilt).
Both renderings were built and run against accepted 1.7.5 deliverables when this landed.
"""

from __future__ import annotations

import dataclasses

import pytest

from squadops.capabilities.rendered_packaging import render_packaging
from squadops.capabilities.scaffold import _STACKS, expand
from squadops.cycles.container_packaging import packaging_findings
from squadops.sandbox import environment
from tests.unit.capabilities._stack_fixtures import manifest_for_stack

pytestmark = [pytest.mark.domain_capabilities]


@pytest.mark.parametrize("stack", sorted(_STACKS))
def test_every_stack_ships_packaging_the_packaging_check_finds_nothing_in(stack):
    """Bug caught: a rendering reintroducing a pf-38 defect — `npm ci` with no lockfile, a copy
    out of dist-packages, apt's nginx default site left in place — which would now ship on
    every roll of the stack instead of on some."""
    files = {f["name"]: f["content"] for f in expand(manifest_for_stack(stack))}
    assert "Dockerfile" in files, f"{stack}: an expanding stack must ship its packaging"

    findings = packaging_findings(files["Dockerfile"], "Dockerfile", sorted(files), files.get)

    assert findings == []


def test_versions_and_port_come_from_the_environment_contract(monkeypatch):
    """Bug caught: a template hardcoding the runtime version or port, so the packaging drifts
    from the contract the sandbox builds and tests the application against."""
    real = environment.get_environment_contract

    def bumped(stack: str):
        contract = real(stack)
        tools = tuple(
            (tool, "3.13" if tool == "python" else "22" if tool == "node" else version)
            for tool, version in contract.required_tools
        )
        return dataclasses.replace(contract, required_tools=tools, app_port=8100)

    monkeypatch.setattr(environment, "get_environment_contract", bumped)
    react = {f["name"]: f["content"] for f in render_packaging("fullstack_fastapi_react")}
    nextjs = {f["name"]: f["content"] for f in render_packaging("nextjs_ts")}

    assert "FROM node:22-slim AS frontend" in react["Dockerfile"]
    assert "FROM python:3.13-slim" in react["Dockerfile"]
    assert "proxy_pass http://127.0.0.1:8100/;" in react["nginx.conf"]
    assert "--port 8100" in react["start.sh"]
    assert '"--port", "8100"' in nextjs["Dockerfile"]
    assert "EXPOSE 8100" in nextjs["Dockerfile"]


def test_a_stack_without_a_rendering_is_refused_not_defaulted():
    with pytest.raises(ValueError, match="no packaging rendering for stack 'django_htmx'"):
        render_packaging("django_htmx")


def test_the_packaging_is_frozen_never_a_fill_slot():
    """A rendered file in the fill set would be author-editable, and the builder's per-roll
    packaging would come back through the other door."""
    from squadops.capabilities.scaffold import fill_slot_paths

    for stack in sorted(_STACKS):
        manifest = manifest_for_stack(stack)
        rendered = {f["name"] for f in render_packaging(stack)}
        assert not rendered & set(fill_slot_paths(manifest)), stack
