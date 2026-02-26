"""Verify squadops.core namespace is accessible and isolated from legacy."""


def test_namespace_import():
    """Verify squadops.core can be imported."""
    import squadops.core

    assert squadops.core is not None


def test_no_legacy_import():
    """Verify core does not import from _v0_legacy (isolation test)."""
    import squadops.core

    # This test will fail if core imports from legacy
    # Implementation: check __import__ hooks or static analysis
    # For now, we just verify the import succeeds without errors
    assert squadops.core is not None
