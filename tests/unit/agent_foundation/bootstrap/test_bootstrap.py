"""Unit tests for bootstrap system.

Tests skill/handler auto-registration and system creation.
Part of SIP-0.8.8 Phase 7.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.agents.base import PortsBundle
from squadops.bootstrap.handlers import (
    create_handler_registry,
    get_all_handlers,
)
from squadops.bootstrap.skills import (
    create_skill_registry,
    get_all_skills,
    get_skills_for_role,
)
from squadops.bootstrap.system import (
    SquadOpsSystem,
    SystemConfig,
    create_orchestrator,
    create_system,
)


@pytest.fixture
def mock_ports():
    """Create mock ports for testing."""
    llm = MagicMock()
    llm.chat = AsyncMock()
    llm.health = AsyncMock(return_value={"healthy": True})

    memory = MagicMock()
    memory.store = AsyncMock(return_value="mem-123")
    memory.search = AsyncMock(return_value=[])

    filesystem = MagicMock()
    filesystem.read = MagicMock(return_value="content")
    filesystem.write = MagicMock()

    return PortsBundle(
        llm=llm,
        memory=memory,
        prompt_service=MagicMock(),
        queue=MagicMock(),
        metrics=MagicMock(),
        events=MagicMock(),
        filesystem=filesystem,
    )


class TestSkillBootstrap:
    """Tests for skill bootstrap functions."""

    def test_get_all_skills(self):
        """Should return all skill classes."""
        skills = get_all_skills()

        # Should have skills from all modules
        assert len(skills) >= 10  # At least 10 skills across all modules

        # Should include shared skills
        skill_names = [s().name for s in skills]
        assert "llm_query" in skill_names
        assert "file_read" in skill_names
        assert "memory_store" in skill_names

    def test_get_skills_for_role_lead(self):
        """Should return skills for lead role."""
        skills = get_skills_for_role("lead")

        skill_names = [s().name for s in skills]

        # Should have shared skills
        assert "llm_query" in skill_names

        # Should have lead-specific skills
        assert "task_analysis" in skill_names
        assert "task_delegation" in skill_names

    def test_get_skills_for_role_dev(self):
        """Should return skills for dev role."""
        skills = get_skills_for_role("dev")

        skill_names = [s().name for s in skills]

        # Should have shared skills
        assert "file_write" in skill_names

        # Should have dev-specific skills
        assert "code_generation" in skill_names

    def test_get_skills_for_unknown_role(self):
        """Should return shared skills for unknown role."""
        skills = get_skills_for_role("unknown")

        # Should return shared skills only
        skill_names = [s().name for s in skills]
        assert "llm_query" in skill_names

    def test_create_skill_registry_all(self):
        """Should create registry with all skills."""
        registry = create_skill_registry()

        skills = registry.list_skills()

        # Should have many skills
        assert len(skills) >= 10

        # Should include key skills
        assert "llm_query" in skills
        assert "task_analysis" in skills
        assert "code_generation" in skills

    def test_create_skill_registry_filtered(self):
        """Should create registry with filtered skills."""
        registry = create_skill_registry(roles=["lead"])

        skills = registry.list_skills()

        # Should have shared + lead skills
        assert "llm_query" in skills
        assert "task_analysis" in skills

        # Should NOT have dev-only skills
        # (code_generation is dev-only if not in shared)

    def test_create_skill_registry_no_shared(self):
        """Should create registry without shared skills."""
        registry = create_skill_registry(roles=["lead"], include_shared=False)

        skills = registry.list_skills()

        # Should have lead skills only
        assert "task_analysis" in skills


class TestBuilderHandlerRegistration:
    """Tests for builder handler registration (SIP-0071)."""

    def test_builder_assemble_handler_in_configs(self):
        """BuilderAssembleHandler should be registered in HANDLER_CONFIGS."""
        from squadops.capabilities.handlers.cycle_tasks import BuilderAssembleHandler

        handler_classes = [hc for hc, _ in get_all_handlers()]
        assert BuilderAssembleHandler in handler_classes

    def test_builder_assemble_handler_assigned_to_builder_role(self):
        """BuilderAssembleHandler should be assigned to builder role only."""
        from squadops.capabilities.handlers.cycle_tasks import BuilderAssembleHandler

        for handler_class, roles in get_all_handlers():
            if handler_class is BuilderAssembleHandler:
                assert roles == ("builder",)
                return
        pytest.fail("BuilderAssembleHandler not found in handler configs")

    def test_warmboot_includes_builder_role(self):
        """WarmbootHandler should include builder in its role tuple."""
        from squadops.capabilities.handlers.warmboot import WarmbootHandler

        for handler_class, roles in get_all_handlers():
            if handler_class is WarmbootHandler:
                assert "builder" in roles
                return
        pytest.fail("WarmbootHandler not found in handler configs")

    def test_context_sync_includes_builder_role(self):
        """ContextSyncHandler should include builder in its role tuple."""
        from squadops.capabilities.handlers.warmboot import ContextSyncHandler

        for handler_class, roles in get_all_handlers():
            if handler_class is ContextSyncHandler:
                assert "builder" in roles
                return
        pytest.fail("ContextSyncHandler not found in handler configs")

    def test_builder_does_not_shadow_development_develop(self):
        """BuilderAssembleHandler and DevelopmentDevelopHandler should coexist."""
        from squadops.capabilities.handlers.cycle_tasks import (
            BuilderAssembleHandler,
            DevelopmentDevelopHandler,
        )

        handler_classes = [hc for hc, _ in get_all_handlers()]
        assert BuilderAssembleHandler in handler_classes
        assert DevelopmentDevelopHandler in handler_classes

    def test_builder_assemble_handler_capability_id(self):
        """BuilderAssembleHandler in registry should have correct capability_id."""
        registry = create_handler_registry()
        capabilities = registry.list_capabilities()
        assert "builder.assemble" in capabilities

    def test_builder_role_filter_includes_builder_handler(self):
        """Filtering by builder role should include builder.assemble."""
        registry = create_handler_registry(roles=["builder"])
        capabilities = registry.list_capabilities()
        assert "builder.assemble" in capabilities
        # Should NOT include dev-only handlers
        assert "development.code_generation" not in capabilities


class TestHandlerBootstrap:
    """Tests for handler bootstrap functions."""

    def test_get_all_handlers(self):
        """Should return all handler configs."""
        handlers = get_all_handlers()

        # Should have multiple handlers
        assert len(handlers) >= 8

        # Each entry should be (handler_class, roles)
        for handler_class, roles in handlers:
            assert hasattr(handler_class, "capability_id")
            assert isinstance(roles, tuple)

    def test_create_handler_registry_all(self):
        """Should create registry with all handlers."""
        registry = create_handler_registry()

        capabilities = registry.list_capabilities()

        # Should have all capabilities
        assert len(capabilities) >= 8

        # Should include key capabilities
        assert "governance.task_analysis" in capabilities
        assert "development.code_generation" in capabilities
        assert "qa.validation" in capabilities

    def test_create_handler_registry_filtered(self):
        """Should create registry with filtered handlers."""
        registry = create_handler_registry(roles=["lead"])

        capabilities = registry.list_capabilities()

        # Should have lead capabilities
        assert "governance.task_analysis" in capabilities

        # Should have warmboot (available to all)
        assert "agent.warmboot" in capabilities

    def test_handler_role_assignments(self):
        """Should assign handlers to correct roles."""
        registry = create_handler_registry()

        # Lead should have governance
        lead_caps = registry.list_by_role("lead")
        assert "governance.task_analysis" in lead_caps

        # Dev should have development
        dev_caps = registry.list_by_role("dev")
        assert "development.code_generation" in dev_caps

        # QA should have qa
        qa_caps = registry.list_by_role("qa")
        assert "qa.test_execution" in qa_caps

    def test_correction_protocol_capabilities_registered(self):
        """Issue #93: every capability the executor's correction protocol
        dispatches MUST be in the bootstrap registry. An unregistered
        capability fails fast with HandlerNotFoundError (~13ms, no LLM
        call), which masquerades as a queue/agent issue. Catch the
        wiring gap at startup-test time, not in production cycles.
        """
        from squadops.cycles.task_plan import (
            CORRECTION_TASK_STEPS,
            REPAIR_TASK_STEPS,
            WRAPUP_TASK_STEPS,
        )

        registry = create_handler_registry()
        capabilities = set(registry.list_capabilities())

        all_dispatched: list[tuple[str, str]] = (
            CORRECTION_TASK_STEPS + REPAIR_TASK_STEPS + WRAPUP_TASK_STEPS
        )
        missing = [cap for cap, _role in all_dispatched if cap not in capabilities]
        assert not missing, (
            f"Capabilities dispatched by the executor are not registered "
            f"in bootstrap.handlers: {missing}. Add them to HANDLER_CONFIGS "
            f"or remove them from the corresponding *_TASK_STEPS list."
        )

    def test_qa_validate_repair_registered_for_qa_role(self):
        """Issue #93 regression: qa.validate_repair must be available to
        the qa role specifically. Adding it to the registry without the
        right role would still 13ms-fail when dispatched to eve.
        """
        registry = create_handler_registry()
        qa_caps = registry.list_by_role("qa")
        assert "qa.validate_repair" in qa_caps


class TestSystemBootstrap:
    """Tests for system bootstrap functions."""

    def test_create_orchestrator(self, mock_ports):
        """Should create configured orchestrator."""
        orchestrator = create_orchestrator(mock_ports)

        # Should have capabilities
        caps = orchestrator.get_available_capabilities()
        assert len(caps) >= 8

    def test_create_orchestrator_with_roles(self, mock_ports):
        """Should create orchestrator with filtered roles."""
        orchestrator = create_orchestrator(mock_ports, roles=["lead", "dev"])

        caps = orchestrator.get_available_capabilities()

        # Should have lead and dev capabilities
        assert "governance.task_analysis" in caps
        assert "development.code_generation" in caps

    def test_create_system(self, mock_ports):
        """Should create complete system."""
        system = create_system(
            llm=mock_ports.llm,
            memory=mock_ports.memory,
            prompt_service=mock_ports.prompt_service,
            queue=mock_ports.queue,
            metrics=mock_ports.metrics,
            events=mock_ports.events,
            filesystem=mock_ports.filesystem,
        )

        assert isinstance(system, SquadOpsSystem)
        assert system.skill_registry is not None
        assert system.handler_registry is not None
        assert system.orchestrator is not None
        assert system.task_service is not None
        assert system.agent_service is not None

    def test_create_system_with_config(self, mock_ports):
        """Should create system with custom config."""
        config = SystemConfig(
            roles=["lead"],
            enable_warmboot=True,
            default_timeout=60.0,
        )

        system = create_system(
            llm=mock_ports.llm,
            memory=mock_ports.memory,
            prompt_service=mock_ports.prompt_service,
            queue=mock_ports.queue,
            metrics=mock_ports.metrics,
            events=mock_ports.events,
            filesystem=mock_ports.filesystem,
            config=config,
        )

        assert system.config.roles == ["lead"]
        assert system.config.default_timeout == 60.0

    @pytest.mark.asyncio
    async def test_system_health(self, mock_ports):
        """Should report system health."""
        system = create_system(
            llm=mock_ports.llm,
            memory=mock_ports.memory,
            prompt_service=mock_ports.prompt_service,
            queue=mock_ports.queue,
            metrics=mock_ports.metrics,
            events=mock_ports.events,
            filesystem=mock_ports.filesystem,
        )

        health = await system.health()

        assert health["status"] == "healthy"
        assert "skills" in health
        assert "handlers" in health
        assert health["skills"] >= 10
        assert health["handlers"] >= 8


class TestSystemConfig:
    """Tests for SystemConfig."""

    def test_default_config(self):
        """Should have sensible defaults."""
        config = SystemConfig()

        assert config.roles is None  # All roles
        assert config.enable_warmboot is True
        assert config.default_timeout == 300.0
        assert config.metadata == {}

    def test_custom_config(self):
        """Should accept custom values."""
        config = SystemConfig(
            roles=["lead", "dev"],
            enable_warmboot=False,
            default_timeout=60.0,
            metadata={"env": "test"},
        )

        assert config.roles == ["lead", "dev"]
        assert config.enable_warmboot is False
        assert config.default_timeout == 60.0
        assert config.metadata["env"] == "test"
