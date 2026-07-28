"""Environment contract (SIP-0102 §4.2 — phase 102.2)."""

import json
from pathlib import Path

import pytest
import yaml

from squadops.capabilities.scaffold import InterfaceManifest, expand
from squadops.sandbox.environment import (
    FULLSTACK_FASTAPI_REACT,
    EnvironmentContract,
    get_environment_contract,
)
from squadops.sandbox.models import OperationName

_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)


def _minimal(**overrides) -> EnvironmentContract:
    base = {
        "stack": "test_stack",
        "image": "img:pinned",
        "required_tools": (("python", "3.12"),),
        "operation_commands": ((OperationName.BUILD_FRONTEND, ("npm", "run", "build")),),
        "app_port": 8000,
        "install_network": "bridge",
    }
    return EnvironmentContract(**{**base, **overrides})


class TestContractIdentity:
    def test_contract_id_is_deterministic_and_covers_every_field(self):
        """Bug caught: identity not covering a field — a changed image or
        command would keep the same contract_id, silently invalidating §7
        items 4/15 evidence pinning."""
        assert _minimal().contract_id() == _minimal().contract_id()
        assert _minimal(image="img:other").contract_id() != _minimal().contract_id()
        changed_cmd = _minimal(
            operation_commands=((OperationName.BUILD_FRONTEND, ("npm", "run", "build2")),)
        )
        assert changed_cmd.contract_id() != _minimal().contract_id()


class TestValidation:
    @pytest.mark.parametrize(
        ("overrides", "match"),
        [
            ({"operation_commands": (("run_shell", ("sh",)),)}, "unknown operation"),
            (
                {
                    "operation_commands": (
                        (OperationName.BUILD_FRONTEND, ("a",)),
                        (OperationName.BUILD_FRONTEND, ("b",)),
                    )
                },
                "duplicate operation",
            ),
            ({"operation_commands": ((OperationName.BUILD_FRONTEND, ()),)}, "empty command"),
            ({"app_port": 0}, "invalid app_port"),
            ({"image": ""}, "requires an image"),
        ],
        ids=["unknown-op", "duplicate-op", "empty-argv", "bad-port", "no-image"],
    )
    def test_invalid_declarations_are_rejected(self, overrides, match):
        """Bug caught: a malformed checked-in contract deploying silently —
        the failure would surface mid-cycle instead of at import time."""
        with pytest.raises(ValueError, match=match):
            _minimal(**overrides)

    def test_unknown_stack_has_no_fallback(self):
        """Bug caught: an unregistered stack silently receiving some default
        environment (the no-fake-working-defaults rule)."""
        with pytest.raises(ValueError, match="no environment contract"):
            get_environment_contract("fullstack_django_vue")


class TestCanonicalContract:
    def test_canonical_provides_exactly_the_floor_operations(self):
        """Bug caught: the advertised operation set drifting — dropping an op
        breaks the golden path; adding one un-implements advertised-vs-
        provided (read_build_diagnostics is deliberately unprovided, 102.5)."""
        provided = {op for op, _ in FULLSTACK_FASTAPI_REACT.operation_commands}
        assert provided == {
            OperationName.INSTALL_DEPENDENCIES,
            OperationName.BUILD_FRONTEND,
            OperationName.RUN_BACKEND_TESTS,
            OperationName.START_APPLICATION,
        }
        assert not FULLSTACK_FASTAPI_REACT.provides(OperationName.READ_BUILD_DIAGNOSTICS)

    def test_canonical_commands_cohere_with_the_real_skeleton(self):
        """Bug caught: contract↔expander drift — commands referencing paths
        the skeleton does not emit (requirements moved, frontend renamed,
        uvicorn target changed) would fail every cycle at task time."""
        raw = yaml.safe_load(_MANIFEST_PATH.read_text(encoding="utf-8"))
        names = {f["name"] for f in expand(InterfaceManifest.from_dict(raw))}
        assert "backend/requirements.txt" in names  # install references it
        assert "backend/main.py" in names  # uvicorn backend.main:app
        assert "frontend/package.json" in names  # npm --prefix frontend
        package_json = next(
            f["content"]
            for f in expand(InterfaceManifest.from_dict(raw))
            if f["name"] == "frontend/package.json"
        )
        assert "build" in json.loads(package_json)["scripts"]  # npm run build exists
        # No lockfile in the skeleton — the contract must use `npm install`,
        # never `npm ci` (which hard-fails without package-lock.json).
        assert "frontend/package-lock.json" not in names
        install_argv = dict(FULLSTACK_FASTAPI_REACT.operation_commands)[
            OperationName.INSTALL_DEPENDENCIES
        ]
        assert "npm ci" not in " ".join(install_argv)
