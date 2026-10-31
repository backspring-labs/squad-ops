"""The runtime API's sandbox client is its own required selector (#2451, the owner's ruling of
2026-10-18), apart from the service's and the preflight's ``SQUADOPS__SANDBOX__PROVIDER``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from squadops.config.schema import SandboxClientConfig

pytestmark = [pytest.mark.domain_contracts]


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"provider": "http", "service_token": "tok"}, "names its service"),
        ({"provider": "http", "service_url": "http://x:8002"}, "names its service"),
        ({"provider": "docker"}, "Input should be 'none' or 'http'"),
        ({}, "Field required"),
    ],
    ids=["http-without-a-url", "http-without-a-token", "the-services-vocabulary", "no-provider"],
)
def test_a_client_that_cannot_reach_its_service_is_refused(values, message):
    """#1568: required, never defaulted. Bug caught: an http client with nowhere to call (every
    seed then fails at its first call, not at startup), or the service's own vocabulary
    (`docker`) accepted where the runtime's client is meant."""
    with pytest.raises(ValidationError, match=message):
        SandboxClientConfig(**values)
