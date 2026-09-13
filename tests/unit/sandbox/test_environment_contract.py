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


class TestTheSandboxImageIsNamedForWhatItIs:
    """#1197: the image serves every registered stack and its name lands verbatim in
    boot-audit evidence, so a stack's name in the tag asserts an identity the image does
    not have."""

    def test_every_registered_stack_pins_the_one_image(self):
        """Bug caught: the two contracts disagreeing on the image — one retagged, one still
        on a stale tag — which would boot-audit the two stacks in different environments
        while the record says they share one."""
        from squadops.sandbox.environment import (
            FULLSTACK_FASTAPI_REACT,
            NEXTJS_TS,
            SANDBOX_ENV_IMAGE,
            get_environment_contract,
        )

        for contract in (FULLSTACK_FASTAPI_REACT, NEXTJS_TS):
            assert contract.image == SANDBOX_ENV_IMAGE, contract.stack
            assert get_environment_contract(contract.stack).image == SANDBOX_ENV_IMAGE

    def test_the_tag_names_no_registered_stack(self):
        """Bug caught: a stack's name back in the tag (`fastapi-react-1.4-dev` was the
        defect) — the name would land in the other stack's boot-audit evidence line and a
        reader could not tell from the record which environment the audit ran in."""
        from squadops.sandbox.environment import (
            FULLSTACK_FASTAPI_REACT,
            NEXTJS_TS,
            SANDBOX_ENV_IMAGE,
        )

        tag = SANDBOX_ENV_IMAGE.split(":", 1)[1]
        for contract in (FULLSTACK_FASTAPI_REACT, NEXTJS_TS):
            for token in contract.stack.split("_"):
                assert token not in tag, f"{token!r} from stack {contract.stack!r} is in {tag!r}"

    def test_the_build_script_reads_the_tag_from_the_contract_module(self):
        """Bug caught: a second copy of the tag in the build script drifting from the
        contracts — the exact "keep them in lockstep" the script's old comment asked of a
        human, which the old tag's survival across two stacks shows nobody did."""
        from pathlib import Path

        script = (
            Path(__file__).resolve().parents[3] / "scripts" / "dev" / "build_sandbox_env_image.sh"
        ).read_text()
        assert "SANDBOX_ENV_IMAGE" in script
        assert "squadops-sandbox-env:" not in script, "the script carries its own copy of the tag"
        assert "sandbox-env.Dockerfile" in script
