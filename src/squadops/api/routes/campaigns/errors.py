"""Campaign domain errors → the standard error envelope (#576's shape)."""

from __future__ import annotations

from squadops.campaigns.models import (
    CampaignError,
    CampaignExistsError,
    CampaignNotFoundError,
    ControlOperationRefused,
    LaunchIntentNotFoundError,
    ResumeReservedToOwner,
)

_ERROR_MAP: list[tuple[type[CampaignError], int, str]] = [
    (CampaignNotFoundError, 404, "CAMPAIGN_NOT_FOUND"),
    (LaunchIntentNotFoundError, 404, "LAUNCH_INTENT_NOT_FOUND"),
    (ResumeReservedToOwner, 403, "OWNER_AUTHORITY_REQUIRED"),
    (CampaignExistsError, 409, "CAMPAIGN_EXISTS"),
    (ControlOperationRefused, 409, "CONTROL_OPERATION_REFUSED"),
]


def campaign_error_envelope(e: CampaignError) -> tuple[int, dict]:
    """The (status, detail) for a campaign error. A refusal carries its control-log row's id and
    reason, so the caller can read the recorded refusal (§12a: refused and recorded)."""
    details = None
    if isinstance(e, ControlOperationRefused):
        details = {
            "entry_id": e.entry.entry_id,
            "refusal": str(e.entry.refusal),
            "state": str(e.entry.prior_state),
        }
    for exc_type, status, code in _ERROR_MAP:
        if isinstance(e, exc_type):
            return status, {"error": {"code": code, "message": str(e), "details": details}}
    return 500, {"error": {"code": "INTERNAL_ERROR", "message": str(e), "details": None}}
