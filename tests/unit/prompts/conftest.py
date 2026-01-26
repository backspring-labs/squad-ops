"""
Pytest configuration for prompt unit tests.

Mocks heavy dependencies to enable isolated testing.
"""

import sys
from unittest.mock import MagicMock

# Mock sqlalchemy and its submodules before any imports that need them
mock_sqlalchemy = MagicMock()
mock_sqlalchemy.Engine = MagicMock()
mock_sqlalchemy.orm = MagicMock()
mock_sqlalchemy.orm.sessionmaker = MagicMock()

sys.modules['sqlalchemy'] = mock_sqlalchemy
sys.modules['sqlalchemy.engine'] = MagicMock()
sys.modules['sqlalchemy.orm'] = mock_sqlalchemy.orm
