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
    ResumeNotDelegated,
    ResumeReservedToOwner,
)

_ERROR_MAP: list[ErrorRow] = [
    (CampaignNotFoundError, 404, "CAMPAIGN_NOT_FOUND"),
    (LaunchIntentNotFoundError, 404, "LAUNCH_INTENT_NOT_FOUND"),
    (ResumeReservedToOwner, 403, "OWNER_AUTHORITY_REQUIRED"),
    # §24da: a resume the campaign did not delegate to the crew's supervisor principal, refused
    # and recorded. Before its parent, so the row's reason answers as a 403, not a conflict.
    (ResumeNotDelegated, 403, "RESUME_NOT_DELEGATED"),
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
    if isinstance(e, ResumeNotDelegated):
        assert details is not None
        details |= {
            "class": e.entry.binding.get("class"),
            "escalation": e.entry.binding.get("escalation"),
        }
    return mapped_error(e, _ERROR_MAP, details)
