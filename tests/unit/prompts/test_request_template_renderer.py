"""
Unit tests for RequestTemplateRenderer (SIP-0084 Phase 2).

Tests rendering, variable injection, contract validation (missing required,
unknown variable warning, optional skip), and caching behavior.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import pytest

from squadops.prompts.asset_models import RenderedRequest, ResolvedAsset
from squadops.prompts.exceptions import PromptAssetNotFoundError, TemplateMissingVariableError
from squadops.prompts.renderer import RequestTemplateRenderer, _parse_template_contract

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_source(templates: dict[str, str]) -> AsyncMock:
    """Create a mock PromptAssetSourcePort with the given templates."""
    source = AsyncMock()

    async def resolve_template(template_id, environment="production"):
        if template_id not in templates:
            raise PromptAssetNotFoundError(template_id, environment)
        content = templates[template_id]
        return ResolvedAsset(
            asset_id=template_id,
            content=content,
            version="1",
            environment=environment,
            content_hash=ResolvedAsset.compute_hash(content),
        )

    source.resolve_request_template = AsyncMock(side_effect=resolve_template)
    return source


_SIMPLE_TEMPLATE = (
    "---\n"
    "template_id: request.test\n"
    "required_variables:\n"
    "  - prd\n"
    "  - role\n"
    "optional_variables:\n"
    "  - prior_outputs\n"
    "---\n"
    "## PRD\n\n{{prd}}\n{{prior_outputs}}\nRole: {{role}}\n"
)


# ---------------------------------------------------------------------------
# _parse_template_contract
# ---------------------------------------------------------------------------


class TestParseTemplateContract:
    def test_parses_required_and_optional(self):
        body, required, optional = _parse_template_contract(_SIMPLE_TEMPLATE)
        assert required == {"prd", "role"}
        assert optional == {"prior_outputs"}
        assert "{{prd}}" in body

    def test_no_frontmatter_returns_empty_sets(self):
        body, required, optional = _parse_template_contract("Just plain text {{var}}")
        assert required == set()
        assert optional == set()
        assert "{{var}}" in body

    def test_empty_contract_lists(self):
        template = "---\ntemplate_id: test\n---\nContent {{x}}\n"
        body, required, optional = _parse_template_contract(template)
        assert required == set()
        assert optional == set()


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


class TestRendering:
    async def test_renders_required_and_optional_variables(self):
        source = _make_source({"request.test": _SIMPLE_TEMPLATE})
        renderer = RequestTemplateRenderer(source)

        result = await renderer.render(
            "request.test",
            {"prd": "Build a game", "role": "dev", "prior_outputs": "\n\n## Analysis\nDone"},
        )

        assert isinstance(result, RenderedRequest)
        assert "Build a game" in result.content
        assert "Role: dev" in result.content
        assert "## Analysis" in result.content
        assert result.template_id == "request.test"
        assert result.template_version == "1"
        assert result.render_hash == RenderedRequest.compute_hash(result.content)

    async def test_missing_optional_replaced_with_empty(self):
        source = _make_source({"request.test": _SIMPLE_TEMPLATE})
        renderer = RequestTemplateRenderer(source)

        result = await renderer.render(
            "request.test",
            {"prd": "Build a game", "role": "dev"},
        )

        assert "Build a game" in result.content
        assert "Role: dev" in result.content
        # prior_outputs placeholder replaced with empty string
        assert "{{prior_outputs}}" not in result.content

    async def test_collapses_excess_blank_lines(self):
        template = (
            "---\ntemplate_id: t\nrequired_variables:\n  - a\n"
            "optional_variables:\n  - b\n---\n"
            "Start\n{{b}}\n\n\n\nEnd\n"
        )
        source = _make_source({"t": template})
        renderer = RequestTemplateRenderer(source)

        result = await renderer.render("t", {"a": "val"})
        # 3+ blank lines collapsed to 2
        assert "\n\n\n" not in result.content

    async def test_deterministic_hash(self):
        source = _make_source({"request.test": _SIMPLE_TEMPLATE})
        renderer = RequestTemplateRenderer(source)

        r1 = await renderer.render("request.test", {"prd": "X", "role": "dev"})
        r2 = await renderer.render("request.test", {"prd": "X", "role": "dev"})
        assert r1.render_hash == r2.render_hash

    async def test_different_variables_produce_different_hashes(self):
        source = _make_source({"request.test": _SIMPLE_TEMPLATE})
        renderer = RequestTemplateRenderer(source)

        r1 = await renderer.render("request.test", {"prd": "A", "role": "dev"})
        r2 = await renderer.render("request.test", {"prd": "B", "role": "dev"})
        assert r1.render_hash != r2.render_hash


# ---------------------------------------------------------------------------
# Contract Validation
# ---------------------------------------------------------------------------


class TestContractValidation:
    async def test_missing_required_variable_raises(self):
        source = _make_source({"request.test": _SIMPLE_TEMPLATE})
        renderer = RequestTemplateRenderer(source)

        with pytest.raises(TemplateMissingVariableError, match="prd"):
            await renderer.render("request.test", {"role": "dev"})

    async def test_missing_multiple_required_reports_first_alphabetically(self):
        source = _make_source({"request.test": _SIMPLE_TEMPLATE})
        renderer = RequestTemplateRenderer(source)

        with pytest.raises(TemplateMissingVariableError, match="prd"):
            await renderer.render("request.test", {})

    async def test_unknown_variable_logs_warning(self, caplog):
        source = _make_source({"request.test": _SIMPLE_TEMPLATE})
        renderer = RequestTemplateRenderer(source)

        with caplog.at_level(logging.WARNING):
            await renderer.render(
                "request.test",
                {"prd": "X", "role": "dev", "unknown_var": "surprise"},
            )

        assert any("unknown_var" in record.message for record in caplog.records)

    async def test_no_contract_allows_any_variable(self):
        """Templates without frontmatter accept any variables without warning."""
        template = "Hello {{name}}, your role is {{role}}."
        source = _make_source({"t": template})
        renderer = RequestTemplateRenderer(source)

        result = await renderer.render("t", {"name": "Neo", "role": "dev"})
        assert "Hello Neo" in result.content


# ---------------------------------------------------------------------------
# Error Handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    async def test_missing_template_raises(self):
        source = _make_source({})
        renderer = RequestTemplateRenderer(source)

        with pytest.raises(PromptAssetNotFoundError, match="nonexistent"):
            await renderer.render("nonexistent", {})


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


class TestCaching:
    async def test_resolves_once_then_caches(self):
        source = _make_source({"request.test": _SIMPLE_TEMPLATE})
        renderer = RequestTemplateRenderer(source)

        await renderer.render("request.test", {"prd": "A", "role": "dev"})
        await renderer.render("request.test", {"prd": "B", "role": "dev"})

        # Should have resolved only once
        assert source.resolve_request_template.call_count == 1

    async def test_clear_cache_forces_re_resolve(self):
        source = _make_source({"request.test": _SIMPLE_TEMPLATE})
        renderer = RequestTemplateRenderer(source)

        await renderer.render("request.test", {"prd": "A", "role": "dev"})
        renderer.clear_cache()
        await renderer.render("request.test", {"prd": "B", "role": "dev"})

        assert source.resolve_request_template.call_count == 2

    async def test_different_environments_cached_separately(self):
        source = _make_source({"request.test": _SIMPLE_TEMPLATE})
        renderer = RequestTemplateRenderer(source)

        await renderer.render("request.test", {"prd": "A", "role": "dev"}, environment="staging")
        await renderer.render(
            "request.test", {"prd": "A", "role": "dev"}, environment="production"
        )

        assert source.resolve_request_template.call_count == 2
