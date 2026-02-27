"""
Synchronous httpx API client for the SquadOps CLI (SIP-0065 §6, D1, D10).

Thin wrapper with error-to-exit-code mapping. Accepts an optional injected
httpx.Client for testability (D10).
"""

from __future__ import annotations

from pathlib import Path

import httpx

from squadops import __version__
from squadops.cli import exit_codes
from squadops.cli.config import CLIConfig, resolve_token


class CLIError(Exception):
    """CLI error with exit code for structured error reporting."""

    def __init__(self, message: str, exit_code: int, detail: dict | None = None):
        super().__init__(message)
        self.exit_code = exit_code
        self.detail = detail


class APIClient:
    """Synchronous API client for the SquadOps runtime-api.

    Args:
        config: CLI configuration.
        client: Optional injected httpx.Client (D10). If None, creates one.
        token_flag: Explicit --token flag value for D4 auth hierarchy.
    """

    def __init__(
        self,
        config: CLIConfig,
        client: httpx.Client | None = None,
        token_flag: str | None = None,
    ):
        self._config = config
        if client is not None:
            self._client = client
        else:
            headers = {"User-Agent": f"squadops-cli/{__version__}"}
            token = resolve_token(config, token_flag)
            if token:
                headers["Authorization"] = f"Bearer {token}"
            self._client = httpx.Client(
                base_url=config.base_url,
                timeout=config.timeout,
                verify=config.tls_verify,
                headers=headers,
            )

    def get(self, path: str, params: dict | None = None) -> dict:
        """Send GET request, return parsed JSON."""
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict | None = None) -> dict:
        """Send POST request with JSON body, return parsed JSON."""
        return self._request("POST", path, json=json)

    def put(self, path: str, json: dict | None = None) -> dict:
        """Send PUT request with JSON body, return parsed JSON."""
        return self._request("PUT", path, json=json)

    def delete(self, path: str) -> dict:
        """Send DELETE request, return parsed JSON."""
        return self._request("DELETE", path)

    def upload(self, path: str, file_path: Path, fields: dict) -> dict:
        """Send multipart POST with file upload."""
        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f)}
                response = self._client.post(path, files=files, data=fields)
        except httpx.ConnectError:
            raise CLIError(
                f"Error: cannot reach {self._config.base_url} — connection refused",
                exit_codes.NETWORK_ERROR,
            ) from None
        except httpx.TimeoutException:
            raise CLIError(
                f"Error: request to {self._config.base_url} timed out after {self._config.timeout}s",
                exit_codes.NETWORK_ERROR,
            ) from None
        return self._handle_response(response)

    def download(self, path: str) -> tuple[bytes, str]:
        """Download binary content. Returns (content, filename)."""
        try:
            response = self._client.get(path)
        except httpx.ConnectError:
            raise CLIError(
                f"Error: cannot reach {self._config.base_url} — connection refused",
                exit_codes.NETWORK_ERROR,
            ) from None
        except httpx.TimeoutException:
            raise CLIError(
                f"Error: request to {self._config.base_url} timed out after {self._config.timeout}s",
                exit_codes.NETWORK_ERROR,
            ) from None
        if response.status_code >= 400:
            self._handle_error_status(response)
        # Extract filename from content-disposition or use fallback
        cd = response.headers.get("content-disposition", "")
        filename = "download"
        if "filename=" in cd:
            filename = cd.split("filename=")[-1].strip('"')
        return response.content, filename

    def close(self):
        """Close the underlying httpx client."""
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json: dict | None = None,
    ) -> dict:
        """Core request method with error handling."""
        try:
            response = self._client.request(method, path, params=params, json=json)
        except httpx.ConnectError:
            raise CLIError(
                f"Error: cannot reach {self._config.base_url} — connection refused",
                exit_codes.NETWORK_ERROR,
            ) from None
        except httpx.TimeoutException:
            raise CLIError(
                f"Error: request to {self._config.base_url} timed out after {self._config.timeout}s",
                exit_codes.NETWORK_ERROR,
            ) from None
        return self._handle_response(response)

    def _handle_response(self, response: httpx.Response) -> dict:
        """Parse JSON response or raise CLIError for error status codes."""
        if response.status_code >= 400:
            self._handle_error_status(response)
        try:
            return response.json()
        except Exception:
            raise CLIError(
                f"Error: unexpected response (HTTP {response.status_code}) — {response.text[:200]}",
                exit_codes.GENERAL_ERROR,
            ) from None

    def _handle_error_status(self, response: httpx.Response) -> None:
        """Map HTTP error status to CLIError with appropriate exit code."""
        status = response.status_code
        request_id = response.headers.get("x-request-id", "")

        try:
            body = response.json()
            error_msg = body.get("error", {}).get("message", "") if isinstance(body, dict) else ""
            detail = body.get("error", {}).get("details") if isinstance(body, dict) else None
        except Exception:
            error_msg = response.text[:200]
            detail = None

        suffix = f" [request_id={request_id}]" if request_id else ""

        if status in (401, 403):
            raise CLIError(
                f"Error: authentication failed — {error_msg}{suffix}",
                exit_codes.AUTH_ERROR,
                detail=detail,
            )
        elif status == 404:
            raise CLIError(
                f"Error: not found — {error_msg}{suffix}",
                exit_codes.NOT_FOUND,
                detail=detail,
            )
        elif status == 409:
            raise CLIError(
                f"Error: conflict — {error_msg}{suffix}",
                exit_codes.CONFLICT,
                detail=detail,
            )
        elif status == 422:
            raise CLIError(
                f"Error: validation failed — {error_msg}{suffix}",
                exit_codes.VALIDATION_ERROR,
                detail=detail,
            )
        elif status == 413:
            raise CLIError(
                f"Error: file too large (max 50 MB){suffix}",
                exit_codes.VALIDATION_ERROR,
            )
        else:
            raise CLIError(
                f"Error: unexpected response (HTTP {status}) — {error_msg}{suffix}",
                exit_codes.GENERAL_ERROR,
                detail=detail,
            )
