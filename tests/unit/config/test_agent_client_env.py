"""
Env addressability of auth.agent_client (#326).

agent_client exists as a first-class AuthConfig field precisely because the
schema-authoritative env loader cannot address keys inside dict-valued fields
(auth.service_clients). If agent_client is ever folded back into the dict,
these resolutions break and agent containers silently lose their service
identity — this test makes that failure loud.
"""

from __future__ import annotations

import pytest

from squadops.config.loader import _get_schema_path_map, _resolve_env_var_path


@pytest.mark.parametrize(
    "env_path,dot_path",
    [
        ("AUTH__AGENT_CLIENT__CLIENT_ID", "auth.agent_client.client_id"),
        ("AUTH__AGENT_CLIENT__CLIENT_SECRET", "auth.agent_client.client_secret"),
    ],
)
def test_agent_client_env_vars_resolve(env_path, dot_path):
    info = _resolve_env_var_path(env_path, _get_schema_path_map())
    assert info is not None, (
        f"SQUADOPS__{env_path} does not resolve — agent containers configure "
        "their service identity through this path (docker-compose.yml, #326)"
    )
    assert info.dot_path == dot_path
