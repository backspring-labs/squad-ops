"""
Health infrastructure routes.

Part of SIP-0.8.9 Health Check refactor.
"""

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

if TYPE_CHECKING:
    from squadops.api.health_app import HealthChecker

router = APIRouter(prefix="/health", tags=["health"])

# These will be injected at startup
_health_checker: "HealthChecker | None" = None
_templates: Jinja2Templates | None = None


def init_routes(health_checker: "HealthChecker", templates: Jinja2Templates) -> None:
    """Initialize routes with dependencies."""
    global _health_checker, _templates
    _health_checker = health_checker
    _templates = templates


@router.get("/infra")
async def health_infra():
    """Get infrastructure health status"""
    if not _health_checker:
        raise RuntimeError("Health checker not initialized")

    infra_checks = await asyncio.gather(
        _health_checker.check_rabbitmq(),
        _health_checker.check_postgres(),
        _health_checker.check_redis(),
        _health_checker.check_prefect(),
        _health_checker.check_prometheus(),
        _health_checker.check_grafana(),
        _health_checker.check_otel_collector(),
        _health_checker.check_langfuse(),
    )
    return infra_checks


@router.get("")
async def health_dashboard(request: Request):
    """Get health dashboard HTML"""
    if not _health_checker or not _templates:
        raise RuntimeError("Health checker or templates not initialized")

    # Import here to avoid circular imports
    from squadops.api.routes.agents import health_agents

    infra_status = await health_infra()
    agent_status = await health_agents()

    return _templates.TemplateResponse(
        "health_dashboard.html",
        {
            "request": request,
            "infra_status": infra_status,
            "agent_status": agent_status,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
