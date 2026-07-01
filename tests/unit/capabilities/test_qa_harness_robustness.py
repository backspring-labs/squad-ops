"""qa.test harness robustness helpers (#303).

Guards the fixes found by cyc_1d2e21ab0cfb: package.json discovery (don't assume
a fixed ``frontend/``) and backend ``PYTHONPATH`` so a nested app's
``from main import app`` resolves when pytest runs from the workspace root.
"""

from __future__ import annotations

import os

import pytest

from squadops.capabilities.handlers.test_runner import (
    _find_package_json_dir,
    _source_dir_pythonpath,
)

pytestmark = [pytest.mark.domain_capabilities]


class TestFindPackageJsonDir:
    def test_in_frontend_subdir(self):
        files = [
            {"path": "frontend/src/package.json", "content": "{}"},
            {"path": "frontend/src/App.jsx", "content": ""},
        ]
        assert _find_package_json_dir(files) == "frontend/src"

    def test_at_frontend_root(self):
        files = [{"path": "frontend/package.json", "content": "{}"}]
        assert _find_package_json_dir(files) == "frontend"

    def test_at_workspace_root(self):
        assert _find_package_json_dir([{"path": "package.json", "content": "{}"}]) == ""

    def test_shallowest_wins(self):
        files = [
            {"path": "frontend/src/package.json", "content": "{}"},
            {"path": "frontend/package.json", "content": "{}"},
        ]
        assert _find_package_json_dir(files) == "frontend"

    def test_none_when_absent(self):
        assert _find_package_json_dir([{"path": "frontend/src/App.jsx", "content": ""}]) is None


class TestSourceDirPythonpath:
    def test_nested_backend_dir_on_path(self, monkeypatch):
        monkeypatch.delenv("PYTHONPATH", raising=False)
        parts = _source_dir_pythonpath("/ws", [{"path": "backend/main.py", "content": ""}]).split(
            os.pathsep
        )
        assert "/ws" in parts
        assert os.path.join("/ws", "backend") in parts  # so `from main import app` resolves

    def test_only_python_source_dirs_counted(self, monkeypatch):
        monkeypatch.delenv("PYTHONPATH", raising=False)
        # A non-.py file contributes no import dir → just the workspace root.
        parts = _source_dir_pythonpath(
            "/ws", [{"path": "frontend/src/App.jsx", "content": ""}]
        ).split(os.pathsep)
        assert parts == ["/ws"]

    def test_preserves_existing_pythonpath(self, monkeypatch):
        monkeypatch.setenv("PYTHONPATH", "/existing")
        parts = _source_dir_pythonpath("/ws", [{"path": "main.py", "content": ""}]).split(
            os.pathsep
        )
        assert "/existing" in parts
