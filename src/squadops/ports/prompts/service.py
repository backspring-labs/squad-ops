"""
Driving port for prompt assembly service.

This interface defines the contract used by BaseAgent to request
prompt assembly based on the current context.
"""

from abc import ABC, abstractmethod

from squadops.prompts.models import AssembledPrompt


class PromptService(ABC):
    """
    Abstract contract for BaseAgent to request prompt assembly.

    This is the driving port - the interface through which the
    application layer (agents) interact with the prompt domain.
    """

    @abstractmethod
    def assemble(
        self,
        role: str,
        hook: str,
        task_type: str | None = None,
        recovery: bool = False,
    ) -> AssembledPrompt:
        """
        Assemble a prompt for the given context.

        Combines fragments from multiple layers in deterministic order:
        1. Identity Layer
        2. Global Constraints
        3. Lifecycle Layer (based on hook)
        4. Task Type Layer (if task_type provided)
        5. Recovery Layer (if recovery=True)

        Args:
            role: Agent role ID (e.g., "lead", "dev", "qa")
            hook: Lifecycle hook (e.g., "agent_start", "task_complete")
            task_type: Optional ACI task type (e.g., "code_generate")
            recovery: Whether to include recovery layer

        Returns:
            AssembledPrompt with content and lineage

        Raises:
            MandatoryLayerMissingError: If required layers cannot be resolved
            HashMismatchError: If any fragment fails integrity check
        """
        pass

    @abstractmethod
    def get_system_prompt(self, role: str) -> AssembledPrompt:
        """
        Get assembled system prompt for agent initialization.

        Convenience method that assembles the prompt for the
        agent_start hook with no task type or recovery.

        Args:
            role: Agent role ID

        Returns:
            AssembledPrompt for system initialization
        """
        pass

    @abstractmethod
    def assemble_task_only(self, role: str, task_type: str) -> AssembledPrompt:
        """
        Assemble a system prompt from ONLY the task_type fragment.

        Skips identity, global constraints, and lifecycle layers.
        Used by handlers whose system prompt must contain only the
        task instructions — no role identity preamble.

        Cycle cyc_a867cbf02205 (2026-05-05) showed that the lead and
        data role-identity fragments cause spark-squad models
        (qwen3.6:27b) to enter "agent role-play initialization mode"
        before doing the requested task. The result: handlers that
        ask for JSON output get back markdown narratives like
        "### Initialization Verification / Role Configuration: Loaded ✅"
        instead of the structured response. The fix is to suppress
        the role-identity layer for these JSON-emitting handlers
        while keeping the externalized task_type fragment as the
        single source of truth for the prompt content.

        Args:
            role: Agent role ID. Used only for role-specific fragment
                override lookup; identity content is NOT prepended.
            task_type: ACI task type whose fragment becomes the
                entire system prompt.

        Returns:
            AssembledPrompt containing only the task_type fragment.

        Raises:
            MandatoryLayerMissingError: If the task_type fragment
                doesn't exist for the given role.
            HashMismatchError: If the fragment fails integrity check.
        """
        pass

    @abstractmethod
    def get_version(self) -> str:
        """
        Get the current prompt system version.

        Returns:
            Version string from the active manifest
        """
        pass
