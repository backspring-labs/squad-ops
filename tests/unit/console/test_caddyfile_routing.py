"""Tests for Phase 4 Caddyfile routing rules and security headers.

Validates the Caddyfile at console/Caddyfile by static parsing —
actual proxy behaviour requires a running Caddy container.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_caddyfile_path = Path(__file__).parents[3] / "console" / "Caddyfile"


@pytest.fixture()
def caddyfile():
    return _caddyfile_path.read_text()


class TestCaddyfileRouting:
    """Verify all 8 routing rules are present and use correct backends."""

    def test_api_v1_routes_to_runtime_api(self, caddyfile):
        """Rule 1: /api/v1/* → runtime-api:8001 (preserve path via handle, not handle_path)."""
        match = re.search(r"handle\s+/api/v1/\*\s*\{[^}]*reverse_proxy\s+(\S+)", caddyfile)
        assert match, "/api/v1/* route missing"
        assert match.group(1) == "runtime-api:8001"

    def test_auth_userinfo_routes_to_runtime_api(self, caddyfile):
        """Rule 2: /auth/userinfo → runtime-api:8001 (explicit exception)."""
        match = re.search(r"handle\s+/auth/userinfo\s*\{[^}]*reverse_proxy\s+(\S+)", caddyfile)
        assert match, "/auth/userinfo route missing"
        assert match.group(1) == "runtime-api:8001"

    def test_auth_routes_to_console_backend(self, caddyfile):
        """Rule 3: /auth/* → squadops-console:4040 (BFF)."""
        match = re.search(r"handle\s+/auth/\*\s*\{[^}]*reverse_proxy\s+(\S+)", caddyfile)
        assert match, "/auth/* route missing"
        assert match.group(1) == "squadops-console:4040"

    def test_health_infra_routes_to_runtime_api(self, caddyfile):
        """Rule 4: /health/infra → runtime-api:8001."""
        match = re.search(r"handle\s+/health/infra\s*\{[^}]*reverse_proxy\s+(\S+)", caddyfile)
        assert match, "/health/infra route missing"
        assert match.group(1) == "runtime-api:8001"

    def test_health_agents_routes_to_runtime_api(self, caddyfile):
        """Rule 5: /health/agents* → runtime-api:8001."""
        match = re.search(r"handle\s+/health/agents\*\s*\{[^}]*reverse_proxy\s+(\S+)", caddyfile)
        assert match, "/health/agents* route missing"
        assert match.group(1) == "runtime-api:8001"

    def test_prefect_strips_prefix(self, caddyfile):
        """Rule 6: /prefect/* → prefect-server:4200 (strip prefix via handle_path)."""
        match = re.search(r"handle_path\s+/prefect/\*\s*\{[^}]*reverse_proxy\s+(\S+)", caddyfile)
        assert match, "/prefect/* handle_path route missing"
        assert match.group(1) == "prefect-server:4200"

    def test_langfuse_strips_prefix(self, caddyfile):
        """Rule 7: /langfuse/* → squadops-langfuse:3000 (strip prefix via handle_path)."""
        match = re.search(r"handle_path\s+/langfuse/\*\s*\{[^}]*reverse_proxy\s+(\S+)", caddyfile)
        assert match, "/langfuse/* handle_path route missing"
        assert match.group(1) == "squadops-langfuse:3000"

    def test_default_routes_to_console_backend(self, caddyfile):
        """Rule 8: everything else → squadops-console:4040."""
        # The default handle block (no path matcher)
        match = re.search(r"handle\s*\{[^}]*reverse_proxy\s+(\S+)", caddyfile)
        assert match, "Default catch-all handle block missing"
        assert match.group(1) == "squadops-console:4040"


class TestCaddyfileRoutePrecedence:
    """Verify route ordering ensures most-specific-first."""

    def test_auth_userinfo_before_auth_wildcard(self, caddyfile):
        """Specific /auth/userinfo must appear before generic /auth/*."""
        userinfo_pos = caddyfile.find("handle /auth/userinfo")
        auth_wildcard_pos = caddyfile.find("handle /auth/*")
        assert userinfo_pos < auth_wildcard_pos, (
            "/auth/userinfo must be declared before /auth/* for correct precedence"
        )

    def test_api_v1_before_default_handler(self, caddyfile):
        """/api/v1/* must appear before the default catch-all."""
        api_pos = caddyfile.find("handle /api/v1/*")
        # Default handler is a bare 'handle {' without a path matcher
        default_match = re.search(r"\n\thandle\s*\{", caddyfile)
        assert default_match, "Default catch-all handle block not found"
        assert api_pos < default_match.start(), (
            "/api/v1/* must appear before default catch-all handler"
        )


class TestCaddyfileSecurityHeaders:
    """Verify security headers are configured."""

    def test_csp_header_present(self, caddyfile):
        assert "Content-Security-Policy" in caddyfile

    def test_csp_default_src_self(self, caddyfile):
        assert "default-src 'self'" in caddyfile

    def test_csp_script_src_self(self, caddyfile):
        assert "script-src 'self'" in caddyfile

    def test_csp_style_unsafe_inline(self, caddyfile):
        assert "style-src 'self' 'unsafe-inline'" in caddyfile

    def test_x_content_type_options(self, caddyfile):
        assert "X-Content-Type-Options" in caddyfile
        assert "nosniff" in caddyfile

    def test_x_frame_options(self, caddyfile):
        assert "X-Frame-Options" in caddyfile
        assert "DENY" in caddyfile


class TestCaddyfileSingleOrigin:
    """Verify single-origin architecture — no CORS directives needed."""

    def test_no_cors_directives(self, caddyfile):
        """Single-origin proxy eliminates the need for CORS headers."""
        assert "Access-Control-Allow-Origin" not in caddyfile
        assert "cors" not in caddyfile.lower()

    def test_listens_on_4040(self, caddyfile):
        assert ":4040" in caddyfile


class TestCaddyfilePathPreservation:
    """Verify handle vs handle_path usage is correct."""

    def test_api_v1_uses_handle_not_handle_path(self, caddyfile):
        """API routes must preserve the path prefix (handle, not handle_path)."""
        # Should NOT strip /api/v1 prefix
        assert "handle_path /api/v1" not in caddyfile
        assert "handle /api/v1/*" in caddyfile

    def test_auth_uses_handle_not_handle_path(self, caddyfile):
        assert "handle_path /auth" not in caddyfile
        assert "handle /auth/*" in caddyfile

    def test_health_uses_handle_not_handle_path(self, caddyfile):
        assert "handle_path /health" not in caddyfile
        assert "handle /health/infra" in caddyfile
        assert "handle /health/agents*" in caddyfile

    def test_prefect_uses_handle_path(self, caddyfile):
        """Prefect routes strip /prefect/ prefix (handle_path)."""
        assert "handle_path /prefect/*" in caddyfile

    def test_langfuse_uses_handle_path(self, caddyfile):
        """LangFuse routes strip /langfuse/ prefix (handle_path)."""
        assert "handle_path /langfuse/*" in caddyfile


class TestCaddyfileServiceNameConsistency:
    """Verify service names match docker-compose service names."""

    def test_runtime_api_service_name(self, caddyfile):
        assert "runtime-api:8001" in caddyfile

    def test_console_backend_service_name(self, caddyfile):
        """Console backend uses the docker-compose service name."""
        assert "squadops-console:4040" in caddyfile
        # Must NOT reference the old placeholder name
        assert "console-backend" not in caddyfile

    def test_prefect_service_name(self, caddyfile):
        assert "prefect-server:4200" in caddyfile

    def test_langfuse_service_name(self, caddyfile):
        """LangFuse uses the container name (cross-compose-file reference)."""
        assert "squadops-langfuse:3000" in caddyfile
        # Must NOT reference the old placeholder name
        assert "langfuse-server" not in caddyfile
