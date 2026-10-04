"""An artifact is written inside its own directory, whatever filename or id it carries.

What bug would these catch? The vault writing to ``<artifact dir> / filename`` with a filename
that climbs out (``..``) or is absolute, which resolves outside the vault, so a caller (the ingest
route takes the client's filename) could write wherever the runtime process can. And the guard
refusing a legitimate nested name, which every agent emission is (``backend/routes.py``).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
from squadops.cycles.artifact_names import artifact_filename_refusal
from squadops.cycles.models import ArtifactRef


def _ref(filename: str, project_id: str = "group_run") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="art_0123456789ab",
        project_id=project_id,
        artifact_type="document",
        filename=filename,
        content_hash="",
        size_bytes=0,
        media_type="text/plain",
        created_at=datetime(2026, 10, 4, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    "filename",
    ["../escaped.txt", "a/../../escaped.txt", "nested/../../../escaped.txt"],
)
async def test_a_filename_that_climbs_out_is_refused_and_nothing_is_written(tmp_path, filename):
    vault_dir = tmp_path / "vault"
    vault = FilesystemArtifactVault(base_dir=vault_dir)

    with pytest.raises(ValueError, match="refused"):
        await vault.store(_ref(filename), b"payload")

    assert [p for p in tmp_path.rglob("escaped.txt")] == []


async def test_an_absolute_filename_is_refused_and_its_target_is_untouched(tmp_path):
    target = tmp_path / "outside" / "owned.txt"
    vault = FilesystemArtifactVault(base_dir=tmp_path / "vault")

    with pytest.raises(ValueError, match="absolute path"):
        await vault.store(_ref(str(target)), b"payload")

    assert not target.exists()


async def test_a_project_id_that_climbs_out_is_refused(tmp_path):
    """The artifact directory comes from the URL's project id too: ``..`` there must not escape."""
    vault = FilesystemArtifactVault(base_dir=tmp_path / "vault")

    with pytest.raises(ValueError, match="outside the vault"):
        await vault.store(_ref("report.md", project_id="../.."), b"payload")

    assert [p for p in tmp_path.rglob("report.md")] == []


async def test_a_nested_relative_filename_is_stored_inside_its_artifact(tmp_path):
    vault_dir = tmp_path / "vault"
    vault = FilesystemArtifactVault(base_dir=vault_dir)

    stored = await vault.store(_ref("backend/routes.py"), b"x = 1\n")

    written = vault_dir / "group_run" / "_unattached" / "art_0123456789ab" / "backend" / "routes.py"
    assert written.read_bytes() == b"x = 1\n"
    assert stored.vault_uri == str(written)


@pytest.mark.parametrize(
    ("filename", "refused"),
    [
        ("backend/routes.py", False),
        ("change_request.yaml", False),
        ("notes..md", False),  # dots inside a name are not a segment
        ("", True),
        ("   ", True),
        ("/etc/passwd", True),
        ("../x", True),
        ("a/../b", True),
        ("bad\x00name", True),
    ],
)
def test_the_one_rule_both_seams_apply(filename, refused):
    assert (artifact_filename_refusal(filename) is not None) is refused
