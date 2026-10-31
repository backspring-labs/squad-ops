from pathlib import Path

import pytest

from tests.fixtures.shared_contract.repository import FixtureRepository, build_repository


@pytest.fixture
def repository(tmp_path: Path) -> FixtureRepository:
    return build_repository(tmp_path / "tally")
