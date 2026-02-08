"""
Tests for SIP-0064 port ABCs.
"""

import inspect

import pytest

from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
from squadops.ports.cycles.cycle_registry import CycleRegistryPort
from squadops.ports.cycles.flow_execution import FlowExecutionPort
from squadops.ports.cycles.project_registry import ProjectRegistryPort
from squadops.ports.cycles.squad_profile import SquadProfilePort

pytestmark = [pytest.mark.domain_orchestration]


_PORTS = [
    ProjectRegistryPort,
    CycleRegistryPort,
    SquadProfilePort,
    ArtifactVaultPort,
    FlowExecutionPort,
]


class TestPortsAreABCs:
    @pytest.mark.parametrize("port_cls", _PORTS)
    def test_cannot_instantiate(self, port_cls):
        with pytest.raises(TypeError):
            port_cls()

    @pytest.mark.parametrize("port_cls", _PORTS)
    def test_has_abstract_methods(self, port_cls):
        abstract = {
            name
            for name, method in inspect.getmembers(port_cls, predicate=inspect.isfunction)
            if getattr(method, "__isabstractmethod__", False)
        }
        assert len(abstract) > 0, f"{port_cls.__name__} has no abstract methods"


class TestProjectRegistryPort:
    def test_list_projects_is_abstract(self):
        assert getattr(ProjectRegistryPort.list_projects, "__isabstractmethod__", False)

    def test_get_project_is_abstract(self):
        assert getattr(ProjectRegistryPort.get_project, "__isabstractmethod__", False)


class TestCycleRegistryPort:
    _EXPECTED_METHODS = [
        "create_cycle",
        "get_cycle",
        "list_cycles",
        "cancel_cycle",
        "create_run",
        "get_run",
        "list_runs",
        "update_run_status",
        "cancel_run",
        "record_gate_decision",
    ]

    @pytest.mark.parametrize("method_name", _EXPECTED_METHODS)
    def test_method_is_abstract(self, method_name):
        method = getattr(CycleRegistryPort, method_name)
        assert getattr(method, "__isabstractmethod__", False)


class TestSquadProfilePort:
    _EXPECTED_METHODS = [
        "list_profiles",
        "get_profile",
        "get_active_profile",
        "set_active_profile",
        "resolve_snapshot",
    ]

    @pytest.mark.parametrize("method_name", _EXPECTED_METHODS)
    def test_method_is_abstract(self, method_name):
        method = getattr(SquadProfilePort, method_name)
        assert getattr(method, "__isabstractmethod__", False)


class TestArtifactVaultPort:
    _EXPECTED_METHODS = [
        "store",
        "retrieve",
        "get_metadata",
        "list_artifacts",
        "set_baseline",
        "get_baseline",
        "list_baselines",
    ]

    @pytest.mark.parametrize("method_name", _EXPECTED_METHODS)
    def test_method_is_abstract(self, method_name):
        method = getattr(ArtifactVaultPort, method_name)
        assert getattr(method, "__isabstractmethod__", False)


class TestFlowExecutionPort:
    _EXPECTED_METHODS = ["execute_run", "cancel_run"]

    @pytest.mark.parametrize("method_name", _EXPECTED_METHODS)
    def test_method_is_abstract(self, method_name):
        method = getattr(FlowExecutionPort, method_name)
        assert getattr(method, "__isabstractmethod__", False)
