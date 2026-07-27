"""Sandbox environment preflight (SIP-0102 — phase 102.2c).

The advertised-vs-provided reconciliation on the SIP-0095 seam: when the
sandbox provider is configured, a cycle must not dispatch into an environment
that is unknown, skewed, or missing its image — the roll-4 failure class
caught at create time, never at task time.

Pure over caller-fetched evidence (the SIP-0095 D26 pattern): the
cycle-create route and the doctor both fetch the sandbox service's ``/health``
environment report and pass it in, so both surfaces render the SAME decision.
Evidence doctrine mirrors SIP-0095 §6.2: unverifiable ⇒ warn and allow;
verifiable absence or skew ⇒ block. Provider "noop" contributes nothing
(dormant — the inert posture).
"""

from __future__ import annotations

from collections.abc import Mapping

from squadops.cycles.preflight import Finding, PreflightDecision


def sandbox_environment_decision(
    *,
    provider: str,
    expected_contract_id: str | None,
    report: Mapping | None,
) -> PreflightDecision:
    """Reconcile the deployment's expected environment contract against what
    the sandbox service actually reports."""
    if provider != "docker":
        return PreflightDecision()

    if expected_contract_id is None:
        return PreflightDecision(
            blocking=(
                Finding(
                    code="sandbox_environment_unknown",
                    severity="block",
                    message=(
                        "sandbox provider 'docker' is configured but the configured stack "
                        "has no checked-in environment contract. Fix "
                        "SQUADOPS__SANDBOX__ENVIRONMENT or add the contract to "
                        "squadops.sandbox.environment."
                    ),
                ),
            )
        )

    if report is None:
        return PreflightDecision(
            warnings=(
                Finding(
                    code="sandbox_unverifiable",
                    severity="warning",
                    message=(
                        "could not query the sandbox service — its environment was not "
                        "verified and sandbox operations may fail at task time. Verify "
                        "sandbox-service is up (GET /health) and reachable."
                    ),
                ),
            )
        )

    blocking: list[Finding] = []
    warnings: list[Finding] = []

    reported = report.get("contract_id")
    if reported != expected_contract_id:
        blocking.append(
            Finding(
                code="sandbox_contract_mismatch",
                severity="block",
                message=(
                    f"the sandbox service runs environment contract `{reported}`, but this "
                    f"deployment expects `{expected_contract_id}` — the service is skewed "
                    "against the current tree. Rebuild/restart sandbox-service so the "
                    "contracts match."
                ),
            )
        )

    image_present = report.get("image_present")
    if image_present is False:
        blocking.append(
            Finding(
                code="sandbox_image_missing",
                severity="block",
                message=(
                    f"the sandbox environment image `{report.get('image')}` is not present "
                    "on the sandbox host. Build it: ./scripts/dev/build_sandbox_env_image.sh "
                    "(local-build decision, SIP-0102 plan)."
                ),
            )
        )
    elif image_present is None:
        warnings.append(
            Finding(
                code="sandbox_image_unverifiable",
                severity="warning",
                message=(
                    "the sandbox service could not verify its environment image — sandbox "
                    "operations may fail at task time."
                ),
            )
        )

    return PreflightDecision(blocking=tuple(blocking), warnings=tuple(warnings))
