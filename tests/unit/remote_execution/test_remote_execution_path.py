"""The remote-execution path end to end, with its faults, on the memory store (#3050, slice 1).

The cases are ``remote_path.RemotePathContract``'s; the integration job runs them on Postgres
(``tests/integration/remote_execution/test_remote_execution_path_postgres.py``).
"""

from __future__ import annotations

import pytest

from tests.unit.remote_execution.remote_path import RemotePathContract

pytestmark = [pytest.mark.auth]


class TestRemoteExecutionPathInMemory(RemotePathContract):
    @pytest.fixture
    def store(self):
        return None
