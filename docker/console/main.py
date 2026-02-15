"""SquadOps Console — FastAPI wrapper around Continuum shell.

Thin application layer that boots ContinuumRuntime with SquadOps plugins,
mounts the auth BFF, registers command handlers, and serves the SvelteKit shell.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from continuum.app.runtime import ContinuumRuntime
from continuum.adapters.web.api import router as continuum_api_router

from auth_bff import router as auth_bff_router, configure as configure_auth

logger = logging.getLogger("squadops.console")

# ── Environment ──────────────────────────────────────────────────────────────

SQUADOPS_API_URL = os.environ.get("SQUADOPS_API_URL", "http://runtime-api:8001")
SQUADOPS_API_PUBLIC_URL = os.environ.get("SQUADOPS_API_PUBLIC_URL", "http://localhost:8001")
PREFECT_API_URL = os.environ.get("PREFECT_API_URL", "http://prefect-server:4200")
PREFECT_API_PUBLIC_URL = os.environ.get("PREFECT_API_PUBLIC_URL", "http://localhost:4200")
LANGFUSE_API_URL = os.environ.get("LANGFUSE_API_URL", "http://squadops-langfuse:3000")
LANGFUSE_API_PUBLIC_URL = os.environ.get("LANGFUSE_API_PUBLIC_URL", "http://localhost:3001")
KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://squadops-keycloak:8080/realms/squadops-local")
KEYCLOAK_PUBLIC_URL = os.environ.get(
    "KEYCLOAK_PUBLIC_URL", "http://localhost:8180/realms/squadops-local"
)
CONSOLE_CLIENT_ID = os.environ.get("CONSOLE_CLIENT_ID", "squadops-console")
CONSOLE_REDIRECT_URI = os.environ.get("CONSOLE_REDIRECT_URI", "http://localhost:4040/auth/callback")

# Service token for internal runtime-api calls (client-credentials grant)
SERVICE_CLIENT_ID = os.environ.get("SERVICE_CLIENT_ID", "squadops-console-service")
SERVICE_CLIENT_SECRET = os.environ.get("SERVICE_CLIENT_SECRET", "")

# ── Service token management ────────────────────────────────────────────────

_service_token: str | None = None
_service_token_expires_at: float = 0


async def _get_service_token() -> str:
    """Obtain a service token via client-credentials grant.

    Cached until expiry (minus 30s buffer).
    """
    import time

    global _service_token, _service_token_expires_at

    if _service_token and time.time() < _service_token_expires_at:
        return _service_token

    if not SERVICE_CLIENT_SECRET:
        logger.warning("SERVICE_CLIENT_SECRET not set — command handlers will run unauthenticated")
        return ""

    token_url = f"{KEYCLOAK_URL}/protocol/openid-connect/token"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": SERVICE_CLIENT_ID,
                "client_secret": SERVICE_CLIENT_SECRET,
            },
        )

    if resp.status_code != 200:
        logger.error("Failed to obtain service token: %s", resp.text)
        return ""

    tokens = resp.json()
    _service_token = tokens["access_token"]
    _service_token_expires_at = time.time() + tokens.get("expires_in", 300) - 30
    return _service_token


async def _api_request(
    method: str, path: str, *, json: dict | None = None
) -> httpx.Response:
    """Make an authenticated request to the runtime API."""
    token = await _get_service_token()
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(base_url=SQUADOPS_API_URL) as client:
        return await client.request(method, path, json=json, headers=headers)


# ── Command handlers ────────────────────────────────────────────────────────


async def squadops_health_check(args: dict, context: dict) -> dict:
    """Check runtime API health."""
    resp = await _api_request("GET", "/health")
    return resp.json()


async def squadops_create_cycle(args: dict, context: dict) -> dict:
    """Create a new cycle."""
    project_id = args["project_id"]
    body = {k: v for k, v in args.items() if k != "project_id"}
    resp = await _api_request("POST", f"/api/v1/projects/{project_id}/cycles", json=body)
    if resp.status_code >= 400:
        return {"error": resp.text, "status_code": resp.status_code}
    return resp.json()


async def squadops_create_run(args: dict, context: dict) -> dict:
    """Create a new run for a cycle."""
    project_id = args["project_id"]
    cycle_id = args["cycle_id"]
    body = {k: v for k, v in args.items() if k not in ("project_id", "cycle_id")}
    resp = await _api_request(
        "POST", f"/api/v1/projects/{project_id}/cycles/{cycle_id}/runs", json=body
    )
    if resp.status_code >= 400:
        return {"error": resp.text, "status_code": resp.status_code}
    return resp.json()


async def squadops_cancel_cycle(args: dict, context: dict) -> dict:
    """Cancel a cycle."""
    project_id = args["project_id"]
    cycle_id = args["cycle_id"]
    resp = await _api_request(
        "POST", f"/api/v1/projects/{project_id}/cycles/{cycle_id}/cancel"
    )
    if resp.status_code >= 400:
        return {"error": resp.text, "status_code": resp.status_code}
    return resp.json()


async def squadops_cancel_run(args: dict, context: dict) -> dict:
    """Cancel a run."""
    project_id = args["project_id"]
    cycle_id = args["cycle_id"]
    run_id = args["run_id"]
    resp = await _api_request(
        "POST",
        f"/api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}/cancel",
    )
    if resp.status_code >= 400:
        return {"error": resp.text, "status_code": resp.status_code}
    return resp.json()


async def squadops_gate_approve(args: dict, context: dict) -> dict:
    """Approve a gate decision."""
    project_id = args["project_id"]
    cycle_id = args["cycle_id"]
    run_id = args["run_id"]
    gate_name = args["gate_name"]
    resp = await _api_request(
        "POST",
        f"/api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}/gates/{gate_name}",
        json={"decision": "approved"},
    )
    if resp.status_code >= 400:
        return {"error": resp.text, "status_code": resp.status_code}
    return resp.json()


async def squadops_gate_reject(args: dict, context: dict) -> dict:
    """Reject a gate decision."""
    project_id = args["project_id"]
    cycle_id = args["cycle_id"]
    run_id = args["run_id"]
    gate_name = args["gate_name"]
    resp = await _api_request(
        "POST",
        f"/api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}/gates/{gate_name}",
        json={"decision": "rejected"},
    )
    if resp.status_code >= 400:
        return {"error": resp.text, "status_code": resp.status_code}
    return resp.json()


async def squadops_ingest_artifact(args: dict, context: dict) -> dict:
    """Ingest an artifact via multipart form data."""
    import base64

    project_id = args["project_id"]
    filename = args.get("filename", "artifact.txt")
    artifact_type = args.get("artifact_type", "documentation")
    media_type = args.get("media_type", "text/plain")

    # Decode base64 content if provided, otherwise use raw text content
    if args.get("content_base64"):
        file_bytes = base64.b64decode(args["content_base64"])
    else:
        content = args.get("content", "")
        file_bytes = content.encode() if isinstance(content, str) else content

    token = await _get_service_token()
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(base_url=SQUADOPS_API_URL) as client:
        resp = await client.post(
            f"/api/v1/projects/{project_id}/artifacts/ingest",
            files={"file": (filename, file_bytes, media_type)},
            data={
                "artifact_type": artifact_type,
                "filename": filename,
                "media_type": media_type,
            },
            headers=headers,
        )

    if resp.status_code >= 400:
        return {"error": resp.text, "status_code": resp.status_code}
    return resp.json()


async def squadops_set_baseline(args: dict, context: dict) -> dict:
    """Set a baseline artifact."""
    project_id = args["project_id"]
    artifact_type = args["artifact_type"]
    body = {k: v for k, v in args.items() if k not in ("project_id", "artifact_type")}
    resp = await _api_request(
        "POST",
        f"/api/v1/projects/{project_id}/baseline/{artifact_type}",
        json=body,
    )
    if resp.status_code >= 400:
        return {"error": resp.text, "status_code": resp.status_code}
    return resp.json()


async def squadops_download_artifact(args: dict, context: dict) -> dict:
    """Download an artifact (returns base64-encoded content)."""
    import base64

    artifact_id = args["artifact_id"]
    resp = await _api_request("GET", f"/api/v1/artifacts/{artifact_id}/download")
    if resp.status_code >= 400:
        return {"error": resp.text, "status_code": resp.status_code}
    # Response is binary file content, not JSON
    content_type = resp.headers.get("content-type", "application/octet-stream")
    return {
        "artifact_id": artifact_id,
        "content_base64": base64.b64encode(resp.content).decode(),
        "content_type": content_type,
        "size_bytes": len(resp.content),
    }


async def squadops_set_active_profile(args: dict, context: dict) -> dict:
    """Set the active squad profile."""
    resp = await _api_request("POST", "/api/v1/squad-profiles/active", json=args)
    if resp.status_code >= 400:
        return {"error": resp.text, "status_code": resp.status_code}
    return resp.json()


# ── Command handler registry ────────────────────────────────────────────────

COMMAND_HANDLERS = {
    "squadops.health_check": squadops_health_check,
    "squadops.create_cycle": squadops_create_cycle,
    "squadops.create_run": squadops_create_run,
    "squadops.cancel_cycle": squadops_cancel_cycle,
    "squadops.cancel_run": squadops_cancel_run,
    "squadops.gate_approve": squadops_gate_approve,
    "squadops.gate_reject": squadops_gate_reject,
    "squadops.ingest_artifact": squadops_ingest_artifact,
    "squadops.set_baseline": squadops_set_baseline,
    "squadops.download_artifact": squadops_download_artifact,
    "squadops.set_active_profile": squadops_set_active_profile,
}

# ── Application lifecycle ───────────────────────────────────────────────────

_runtime: ContinuumRuntime | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _runtime

    # Configure auth BFF
    configure_auth(
        keycloak_url=KEYCLOAK_URL,
        keycloak_public_url=KEYCLOAK_PUBLIC_URL,
        client_id=CONSOLE_CLIENT_ID,
        redirect_uri=CONSOLE_REDIRECT_URI,
    )

    # Boot Continuum runtime with SquadOps plugins
    _runtime = ContinuumRuntime(plugins_dir="./plugins")

    # Register command handlers BEFORE boot so load_commands_from_registry()
    # can link them to command definitions during registry resolution.
    for command_id, handler in COMMAND_HANDLERS.items():
        _runtime._command_bus.register_handler(command_id, handler)

    await _runtime.boot()

    # Attach runtime to app state so Continuum API routes can access it
    app.state.runtime = _runtime

    logger.info("SquadOps Console started (lifecycle_state=%s)", _runtime.lifecycle.state)

    yield

    # Shutdown
    if _runtime:
        await _runtime.shutdown()
    logger.info("SquadOps Console stopped")


# ── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(title="SquadOps Console", lifespan=lifespan)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4040",
        "http://localhost:5173",
        "http://localhost:8001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Continuum API routes (/health, /api/registry, /plugins/{id}/assets/...)
app.include_router(continuum_api_router)

# Auth BFF routes (/auth/login, /auth/callback, /auth/refresh, /auth/logout)
app.include_router(auth_bff_router)


# Inject SquadOps config into shell HTML
@app.get("/config.js")
async def config_js():
    """Serve runtime configuration as a JS module for the shell."""
    from fastapi.responses import Response

    js = f"""
window.__SQUADOPS_CONFIG__ = {{
    apiBaseUrl: "{SQUADOPS_API_PUBLIC_URL}",
    prefectBaseUrl: "{PREFECT_API_PUBLIC_URL}",
    langfuseBaseUrl: "{LANGFUSE_API_PUBLIC_URL}",
    keycloakPublicUrl: "{KEYCLOAK_PUBLIC_URL}",
    consoleClientId: "{CONSOLE_CLIENT_ID}",
}};

// Authorized fetch client — plugins MUST use this instead of raw fetch()
window.squadops = window.squadops || {{}};
(function() {{
    let _accessToken = null;

    async function apiFetch(url, options = {{}}) {{
        options.headers = options.headers || {{}};
        if (_accessToken) {{
            options.headers['Authorization'] = 'Bearer ' + _accessToken;
        }}

        let resp = await fetch(url, options);

        // On 401, try refreshing the token once
        if (resp.status === 401 && _accessToken) {{
            const refreshResp = await fetch('/auth/refresh', {{
                method: 'POST',
                credentials: 'include',
            }});

            if (refreshResp.ok) {{
                const data = await refreshResp.json();
                _accessToken = data.access_token;
                options.headers['Authorization'] = 'Bearer ' + _accessToken;
                resp = await fetch(url, options);
            }} else {{
                // Refresh failed — redirect to login
                _accessToken = null;
                const loginResp = await fetch('/auth/login');
                const loginData = await loginResp.json();
                window.location = loginData.auth_url;
                return resp;
            }}
        }}

        return resp;
    }}

    window.squadops.apiFetch = apiFetch;

    window.squadops.setAccessToken = function(token) {{
        _accessToken = token;
    }};

    // Auth bootstrap — establish session on page load
    (async function() {{
        try {{
            const resp = await fetch('/auth/refresh', {{
                method: 'POST',
                credentials: 'include',
            }});
            if (resp.ok) {{
                const data = await resp.json();
                _accessToken = data.access_token;
            }} else {{
                // No session — redirect to Keycloak login
                const loginResp = await fetch('/auth/login');
                const loginData = await loginResp.json();
                window.location = loginData.auth_url;
            }}
        }} catch (e) {{
            console.warn('Auth bootstrap failed:', e);
        }}
    }})();
}})();
"""
    return Response(content=js, media_type="application/javascript")


# SvelteKit shell — mounted LAST for SPA fallback
shell_path = Path("./web/build")
if shell_path.exists():
    app.mount("/", StaticFiles(directory=str(shell_path), html=True), name="shell")
