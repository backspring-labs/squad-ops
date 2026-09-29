"""The prompt pack is verified against its build stamp, not against hashes kept in source (#353).

Bug classes guarded:

- **#327:** a shipped prompt set that is not the one the image was built with produced one
  WARNING line and then ran anyway. In an image the repository must refuse it — at manifest
  load, and on a fragment read after the load (SIP-0057 §8.3).
- **#195/#327's cause:** the hashes lived in ``manifest.yaml`` beside the files they described,
  so every fragment edit needed a second, hand-made edit or the tree refused to load. A source
  checkout must serve an edited fragment as it is.
- **A stale stamp:** a stamp taken from a different manifest must not be half-applied.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from adapters.prompts.factory import create_prompt_repository
from adapters.prompts.filesystem import FileSystemPromptRepository
from squadops.prompts.exceptions import HashMismatchError, ManifestValidationError
from squadops.prompts.fragment_stamp import (
    PACKAGED_FRAGMENTS_DIR,
    STAMP_FILENAME,
    hash_fragment_file,
    main,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]

_MANIFEST = """\
version: 1.0.0
updated_at: '2026-01-01'
fragments:
  - fragment_id: identity.test
    path: shared/identity.test.md
    layer: identity
    roles: ["*"]
"""


def _fragment(body: str) -> str:
    return f'---\nfragment_id: identity.test\nlayer: identity\nroles: ["*"]\n---\n{body}\n'


def _tree(base: Path, *, stamped: bool) -> Path:
    (base / "shared").mkdir(parents=True)
    (base / "shared" / "identity.test.md").write_text(_fragment("As built."), encoding="utf-8")
    (base / "manifest.yaml").write_text(_MANIFEST, encoding="utf-8")
    if stamped:
        assert main([str(base)]) == 0
    return base


def _edit(base: Path, body: str = "Edited in the container.") -> None:
    (base / "shared" / "identity.test.md").write_text(_fragment(body), encoding="utf-8")


class TestAnImageRefusesAPackItWasNotBuiltWith:
    def test_an_edited_fragment_fails_the_manifest_load(self, tmp_path):
        _edit(_tree(tmp_path, stamped=True))
        repo = FileSystemPromptRepository(base_path=tmp_path)

        with pytest.raises(HashMismatchError) as exc_info:
            repo.get_manifest()

        assert exc_info.value.fragment_id == "identity.test (shared/identity.test.md)"
        assert exc_info.value.actual == hash_fragment_file(tmp_path / "shared/identity.test.md")

    def test_a_fragment_edited_after_the_load_is_refused_when_read(self, tmp_path):
        repo = FileSystemPromptRepository(base_path=_tree(tmp_path, stamped=True))
        repo.get_manifest()
        _edit(tmp_path)

        with pytest.raises(HashMismatchError) as exc_info:
            repo.get_fragment("identity.test")

        assert "identity.test.md" in exc_info.value.fragment_id

    def test_a_file_the_build_never_stamped_is_refused(self, tmp_path):
        repo = FileSystemPromptRepository(base_path=_tree(tmp_path, stamped=True))
        (tmp_path / "roles" / "dev").mkdir(parents=True)
        (tmp_path / "roles" / "dev" / "identity.test.md").write_text(
            _fragment("Added after the build."), encoding="utf-8"
        )

        with pytest.raises(HashMismatchError) as exc_info:
            repo.get_fragment("identity.test", role="dev")

        assert exc_info.value.expected == "<not in the build stamp>"

    @pytest.mark.parametrize(
        "change, named",
        [
            (lambda m: m.replace("version: 1.0.0", "version: 1.0.1"), "1.0.1"),
            (
                lambda m: (
                    m + "  - fragment_id: identity.late\n"
                    "    path: shared/identity.late.md\n"
                    "    layer: identity\n"
                    '    roles: ["*"]\n'
                ),
                "shared/identity.late.md",
            ),
        ],
        ids=["version-moved", "fragment-registered-after-the-build"],
    )
    def test_a_stamp_of_another_manifest_is_refused(self, tmp_path, change, named):
        _tree(tmp_path, stamped=True)
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text(change(manifest.read_text()), encoding="utf-8")
        (tmp_path / "shared" / "identity.late.md").write_text(_fragment("Late."), "utf-8")

        with pytest.raises(ManifestValidationError) as exc_info:
            FileSystemPromptRepository(base_path=tmp_path).get_manifest()

        assert STAMP_FILENAME in str(exc_info.value)
        assert named in str(exc_info.value)


class TestASourceCheckoutServesItsFiles:
    def test_an_edited_fragment_is_served_as_edited(self, tmp_path):
        _edit(_tree(tmp_path, stamped=False), "Edited in the checkout.")
        repo = FileSystemPromptRepository(base_path=tmp_path)

        assert repo.get_fragment("identity.test").content == "Edited in the checkout."
        assert repo.validate_integrity() is True


class TestTheImageBuildStep:
    def test_the_shipped_pack_stamps_and_is_served(self, tmp_path):
        """The command the Dockerfiles run, on a copy of the real pack, then the factory the
        agents build their repository with: every registered fragment is stamped as its file
        reads, and the stamped pack verifies whole."""
        pack = shutil.copytree(PACKAGED_FRAGMENTS_DIR, tmp_path / "fragments")
        (pack / STAMP_FILENAME).unlink(missing_ok=True)

        assert main([str(pack)]) == 0

        stamp = json.loads((pack / STAMP_FILENAME).read_text())
        repo = create_prompt_repository("filesystem", base_path=pack)
        registered = {m.path for m in repo.get_manifest().fragments}
        assert set(stamp["fragments"]) == registered
        assert stamp["fragments"] == {p: hash_fragment_file(pack / p) for p in registered}
        assert repo.validate_integrity() is True

    def test_the_build_stamps_the_directory_the_agents_read(self):
        """The entrypoint builds its repository with the factory's default path. Were that to
        move off the directory the build stamps, every image would run unverified."""
        agent_repo = create_prompt_repository("filesystem")

        assert agent_repo.base_path.resolve() == PACKAGED_FRAGMENTS_DIR

    def test_a_manifest_naming_a_missing_file_fails_the_build(self, tmp_path, capsys):
        _tree(tmp_path, stamped=False)
        (tmp_path / "shared" / "identity.test.md").unlink()

        assert main([str(tmp_path)]) == 1

        assert not (tmp_path / STAMP_FILENAME).exists()
        assert "shared/identity.test.md" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "dockerfile", ["agents/Dockerfile", "src/squadops/api/runtime/Dockerfile"]
    )
    def test_each_image_stamps_the_source_it_copied(self, dockerfile):
        """An image that skips the step ships with verification off and nothing says so; one
        that stamps before its last ``COPY src/`` describes a tree it then replaced."""
        lines = (_REPO_ROOT / dockerfile).read_text().splitlines()
        stamp_at = [i for i, line in enumerate(lines) if "squadops.prompts.fragment_stamp" in line]
        copies = [i for i, line in enumerate(lines) if re.match(r"COPY src/ ", line)]

        assert len(stamp_at) == 1, f"{dockerfile} does not stamp the prompt pack exactly once"
        assert lines[stamp_at[0]].startswith("RUN ")
        assert stamp_at[0] > copies[-1]
