"""
Unit tests for SIP-0084 prompt exceptions.

Validates error messages and exception behavior.
"""

import pytest

from squadops.prompts.exceptions import (
    PromptAssetNotFoundError,
    PromptDomainError,
    PromptRegistryUnavailableError,
    TemplateMissingVariableError,
)


class TestPromptAssetNotFoundError:
    def test_message_without_environment(self):
        err = PromptAssetNotFoundError("request.cycle_task_base")
        assert "request.cycle_task_base" in str(err)
        assert err.asset_id == "request.cycle_task_base"
        assert err.environment is None

    def test_message_with_environment(self):
        err = PromptAssetNotFoundError("identity", "staging")
        assert "staging" in str(err)
        assert err.environment == "staging"

    def test_catchable_as_prompt_domain_error(self):
        """Callers using ``except PromptDomainError`` catch asset-not-found."""
        with pytest.raises(PromptDomainError, match="identity"):
            raise PromptAssetNotFoundError("identity", "production")


class TestPromptRegistryUnavailableError:
    def test_message_without_reason(self):
        err = PromptRegistryUnavailableError("langfuse")
        assert "langfuse" in str(err)
        assert err.provider == "langfuse"
        assert err.reason is None

    def test_message_with_reason(self):
        err = PromptRegistryUnavailableError("langfuse", "connection refused")
        assert "connection refused" in str(err)

    def test_catchable_as_prompt_domain_error(self):
        with pytest.raises(PromptDomainError, match="langfuse"):
            raise PromptRegistryUnavailableError("langfuse", "timeout")


class TestTemplateMissingVariableError:
    def test_message_includes_template_and_variable(self):
        err = TemplateMissingVariableError("request.dev.code_generate", "prd")
        assert "prd" in str(err)
        assert "request.dev.code_generate" in str(err)
        assert err.template_id == "request.dev.code_generate"
        assert err.variable == "prd"

    def test_catchable_as_prompt_domain_error(self):
        with pytest.raises(PromptDomainError, match="prd"):
            raise TemplateMissingVariableError("request.dev.code_generate", "prd")
