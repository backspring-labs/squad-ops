"""The clients' side of the switch to TensorFold (SIP-0111 §5.6 step 7; the owner's ruling of
2026-10-13), read as files: the overlay ``engine_switch.py`` appends, and the profile cycles name.

What bug would these catch?
- A model client the overlay leaves on Ollama: it calls a stopped engine while the rest call
  TensorFold, or a new client added to the base file that the overlay never learns of.
- A client that still waits for Ollama: compose then starts Ollama beside TensorFold whenever it
  recreates that client, and the engines must never run together.
- An overlay ``depends_on`` that drifts from the base file's, so a client starts before its database
  or queue on TensorFold and not on Ollama.
- The served id named differently in the overlay, the profile, the adapter and the registry; the
  adapter refuses an id with no frozen recipe, so every call would fail.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from adapters.llm.tensorfold import RECIPES
from squadops.llm.model_registry import get_model_spec
from tests.unit.config.compose_yaml import compose_services

REPO = Path(__file__).resolve().parents[3]


def _services(name: str) -> dict:
    return compose_services(REPO / name)


def _model_clients() -> dict:
    return {
        name: spec
        for name, spec in _services("docker-compose.yml").items()
        if "SQUADOPS__LLM__PROVIDER" in (spec.get("environment") or {})
    }


def test_every_model_client_moves_with_provider_url_key_and_model_together():
    overlay = _services("docker-compose.tensorfold.yml")
    assert set(overlay) == set(_model_clients())
    for name, spec in overlay.items():
        env = spec["environment"]
        assert env["SQUADOPS__LLM__PROVIDER"] == "tensorfold", name
        assert env["SQUADOPS__LLM__URL"] == "http://tensorfold:8080", name
        assert env["SQUADOPS__LLM__API_KEY"].startswith("${SQUADOPS_TENSORFOLD_API_KEY:?"), name
        assert env["SQUADOPS__LLM__MODEL"] in RECIPES, name


def test_no_client_waits_for_ollama_and_each_waits_for_what_the_base_file_names():
    overlay = _services("docker-compose.tensorfold.yml")
    for name, spec in _model_clients().items():
        assert overlay[name]["depends_on"] == spec["depends_on"], name
        assert "ollama" not in overlay[name]["depends_on"], name


def test_the_tensorfold_profile_is_full_38_on_the_served_id():
    profiles = {
        p["profile_id"]: p
        for p in yaml.safe_load((REPO / "config" / "squad-profiles.yaml").read_text())["profiles"]
    }
    served = {a["model"] for a in profiles["full-38-tf"]["agents"]}
    assert served == {
        _services("docker-compose.tensorfold.yml")["max"]["environment"]["SQUADOPS__LLM__MODEL"]
    }
    (model,) = served
    assert model in RECIPES and get_model_spec(model) is not None

    def without_model(profile: dict) -> list[dict]:
        return [{k: v for k, v in a.items() if k != "model"} for a in profile["agents"]]

    assert without_model(profiles["full-38-tf"]) == without_model(profiles["full-38"])
