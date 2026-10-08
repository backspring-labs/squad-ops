"""The envelope verifier's exposure reading (SIP-0110 §0.2, #2162).

What bug would this catch? The readout matching an envelope to its task's first exposure whatever
its attempt, so a re-dispatched authoring with no exposure of its own reads as covered. That is how
the rebuild 5 and 6 Next.js regression cycles' re-takes went unread. The ids below are the ones the
deploy stored for `run_7fabca91826f`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


verify = _load("verify_authoring_envelopes_exposures", "scripts/dev/verify_authoring_envelopes.py")

_RUN = "run_7fabca91826f"
_RETAKEN = "task-run_7fabca91-m007-qa.test"
#: What the rebuild 6 deploy recorded for that task: one exposure, its first dispatch's.
_STORED = {"exp_dcf598a011e0244f"}


def test_a_re_taken_task_without_its_own_exposure_is_named_by_its_attempt():
    envelopes = [
        {"task_id": _RETAKEN, "inputs": {}},
        {"task_id": _RETAKEN, "inputs": {"prior_attempts": 1}},
    ]

    assert verify.own_exposures(_RUN, envelopes, _STORED) == [
        (_RETAKEN, 1, True),
        (_RETAKEN, 2, False),
    ]


def test_an_envelope_with_no_inputs_is_a_first_attempt_and_a_run_with_none_recorded_has_none():
    envelopes = [{"task_id": _RETAKEN}]

    assert verify.own_exposures(_RUN, envelopes, _STORED) == [(_RETAKEN, 1, True)]
    assert verify.own_exposures(_RUN, envelopes, set()) == [(_RETAKEN, 1, False)]
