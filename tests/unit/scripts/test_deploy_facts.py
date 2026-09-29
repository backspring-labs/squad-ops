"""The host's half of a deploy record (#1720): which image each running service runs.

Bug classes guarded: a service's revision guessed where its image carries no label (an
infrastructure image, or one built without the deploy script), and a Compose release's output
format read as no services at all. ``docker`` is never run: its answers are handed in.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "deploy_facts",
    Path(__file__).resolve().parents[3] / "scripts" / "dev" / "ops" / "deploy_facts.py",
)
deploy_facts = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(deploy_facts)

_ROWS = [
    {"Service": "neo", "ID": "c-neo", "State": "running"},
    {"Service": "postgres", "ID": "c-pg", "State": "running"},
    {"Service": "joi", "ID": "c-joi", "State": "exited"},
]


@pytest.mark.parametrize(
    "printed",
    ["\n".join(json.dumps(r) for r in _ROWS), json.dumps(_ROWS)],
    ids=["one-object-per-line", "json-array"],
)
def test_the_running_services_are_read_in_either_compose_format(monkeypatch, printed):
    monkeypatch.setattr(deploy_facts, "_docker", lambda *args: printed)

    assert deploy_facts.running_services() == [("neo", "c-neo"), ("postgres", "c-pg")]


def test_each_service_carries_its_images_revision_label_or_none():
    facts = deploy_facts.facts(
        [("postgres", "c-pg"), ("neo", "c-neo"), ("langfuse", "c-lf")],
        {"c-neo": "sha256:neo", "c-pg": "sha256:pg", "c-lf": "sha256:lf"},
        {
            "sha256:neo": {deploy_facts.REVISION_LABEL: "7acc2bc1-dirty", "squadops.role": "dev"},
            "sha256:pg": None,  # `docker image inspect` prints null for an image with no labels
            "sha256:lf": {"maintainer": "upstream"},
        },
        "rebuild_and_deploy.sh agents neo",
        "",
    )

    assert facts == {
        "recorded_by": "rebuild_and_deploy.sh agents neo",
        "source_revision": None,
        "services": [
            {"service": "langfuse", "image_id": "sha256:lf", "revision": None},
            {"service": "neo", "image_id": "sha256:neo", "revision": "7acc2bc1-dirty"},
            {"service": "postgres", "image_id": "sha256:pg", "revision": None},
        ],
    }


def test_no_running_service_is_a_refusal_not_an_empty_record(monkeypatch, capsys):
    monkeypatch.setattr(deploy_facts, "running_services", lambda: [])

    assert deploy_facts.main(["deploy_facts.py", "probe", "abc"]) == 1
    assert "no running services" in capsys.readouterr().err
