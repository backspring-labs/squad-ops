"""Campaign domain errors → the standard error envelope (#576's shape)."""

from __future__ import annotations

from squadops.api.errors import ErrorRow, mapped_error
from squadops.campaigns.calibration_record import CalibrationRecordRefused
from squadops.campaigns.models import (
    CampaignError,
    CampaignExistsError,
    CampaignNotFoundError,
    ControlOperationRefused,
    LaunchIntentNotFoundError,
    ResumeReservedToOwner,
)

_ERROR_MAP: list[ErrorRow] = [
    (CampaignNotFoundError, 404, "CAMPAIGN_NOT_FOUND"),
    (LaunchIntentNotFoundError, 404, "LAUNCH_INTENT_NOT_FOUND"),
    (ResumeReservedToOwner, 403, "OWNER_AUTHORITY_REQUIRED"),
    (CampaignExistsError, 409, "CAMPAIGN_EXISTS"),
    (ControlOperationRefused, 409, "CONTROL_OPERATION_REFUSED"),
    # §24bv point 1 (§24cc): a repository-backed start whose calibration record can't be written.
    # Refused before anything is written, so no row records it; the cause is in the details.
    (CalibrationRecordRefused, 409, "CALIBRATION_REFUSED"),
]


def campaign_error_envelope(e: CampaignError) -> tuple[int, dict]:
    """The (status, detail) for a campaign error. A refusal carries its control-log row's id and
    reason, so the caller can read the recorded refusal (§12a: refused and recorded)."""
    details = None
    if isinstance(e, CalibrationRecordRefused):
        details = dict(e.details)
    if isinstance(e, ControlOperationRefused):
        details = {
            "entry_id": e.entry.entry_id,
            "refusal": str(e.entry.refusal),
            "state": str(e.entry.prior_state),
        }
    return mapped_error(e, _ERROR_MAP, details)
