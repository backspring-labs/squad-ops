"""#1241: the capabilities adapter package imports, and its dead executor is gone.

``adapters/capabilities/__init__.py`` imported ``ACICapabilityExecutor``, whose own import
named a package that never existed — so the whole package was unimportable and nothing
noticed, because nothing constructed it. The #582 mirror test carried the broken import as
a documented exception keyed to this issue; that entry is retired here, and its two-sided
check would fail if the import returned.
"""

from __future__ import annotations

import importlib

import pytest

pytestmark = [pytest.mark.domain_capabilities]


def test_the_package_imports_whole():
    """Bug caught: a module-level import of something that cannot import — the shape that
    hid for a year because no test entered at the package."""
    pkg = importlib.import_module("adapters.capabilities")
    assert pkg.create_capability_repository is not None
    assert pkg.FileSystemCapabilityRepository is not None


def test_the_dead_executor_and_its_factory_entry_are_gone():
    from adapters.capabilities import factory

    assert not hasattr(factory, "create_capability_executor")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("adapters.capabilities.aci_executor")


def test_the_repository_factory_still_builds_the_filesystem_provider(tmp_path):
    from adapters.capabilities import create_capability_repository

    repo = create_capability_repository(base_path=tmp_path, validate_schemas=False)
    assert type(repo).__name__ == "FileSystemCapabilityRepository"
    with pytest.raises(ValueError, match="Unknown capability repository provider"):
        create_capability_repository(provider="nowhere")
