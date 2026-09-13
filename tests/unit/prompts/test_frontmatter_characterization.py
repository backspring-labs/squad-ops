"""What every frontmatter parser returns, pinned before #579 extracts them into one.

Five copies of the same ``^---\\s*\\n(.*?)\\n---\\s*\\n`` split sat on the tree, and they were
not identical: two compiled it with ``re.MULTILINE``, the fragment repository loaded an empty
header as ``None`` where the renderer and the asset adapter used ``{}``, and the two handler
copies were strict with their own error messages. A refactor that promises byte-identical
behaviour needs the behaviour written down first, from the code being replaced.

This golden was captured from main before the extraction. It records, for every prompt
asset in the tree, what each reader derives: the fragment repository's id, layer, version,
roles and content hash; the request-template renderer's body hash and variable contract;
the asset adapter's content hash and version; the strict handler parser's keys or error.
It records the same for edge-case inputs, a crash included by exception type, so a changed
edge reads as a named diff rather than a surprise.

Bug caught: a prompt that renders different bytes, hashes differently against the manifest,
or loses a declared variable because the shared parser differs from the copy it replaced.

Regenerate only for a DELIBERATE behaviour change, in the PR that makes it:
    UPDATE_FRONTMATTER_GOLDENS=1 pytest tests/unit/prompts/test_frontmatter_characterization.py
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from adapters.prompts.filesystem import FileSystemPromptRepository
from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.capabilities.handlers.wrapup_tasks import _parse_frontmatter
from squadops.prompts.renderer import _parse_template_contract

pytestmark = [pytest.mark.domain_contracts]

_PROMPTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"
_FRAGMENTS = _PROMPTS / "fragments"
_TEMPLATES = _PROMPTS / "request_templates"
_GOLDEN = Path(__file__).parent / "goldens" / "frontmatter_characterization.json"

#: Inputs no stored asset exercises, each chosen for a way the copies could differ.
EDGE_INPUTS: dict[str, str] = {
    "empty": "",
    "no_block": "Plain body.\n",
    "valid": "---\nversion: '2'\nrequired_variables: [a]\n---\nBody {{a}}\n",
    "empty_header": "---\n\n---\nBody\n",
    "invalid_yaml": "---\na: [unclosed\n---\nBody\n",
    "list_header": "---\n- a\n- b\n---\nBody\n",
    "scalar_header": "---\njust text\n---\nBody\n",
    "leading_blank_line": "\n---\na: 1\n---\nBody\n",
    "text_before_block": "Intro\n---\na: 1\n---\nBody\n",
    "crlf": "---\r\na: 1\r\n---\r\nBody\r\n",
    "trailing_space_fences": "---  \na: 1\n---  \nBody\n",
    "no_newline_after_close": "---\na: 1\n---",
    "second_block_in_body": "---\na: 1\n---\nBody\n---\nb: 2\n---\nmore\n",
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _outcome(fn: Callable[[], Any]) -> dict[str, Any]:
    """The value, or the exception type a reader raised — a crash is behaviour too."""
    try:
        return {"ok": fn()}
    except Exception as exc:  # noqa: BLE001 — recording, not handling
        return {"raises": type(exc).__name__}


def _repository_reading(repo: FileSystemPromptRepository, path: Path) -> dict[str, Any]:
    def read() -> dict[str, Any]:
        fragment = repo._parse_fragment_file(path, None)
        return {
            "fragment_id": fragment.fragment_id,
            "layer": fragment.layer,
            "version": str(fragment.version),
            "roles": list(fragment.roles),
            "sha256_hash": fragment.sha256_hash,
        }

    return {
        "extract_content_sha": _sha(FileSystemPromptRepository.extract_content(path.read_text())),
        "parse_fragment": _outcome(read),
    }


def _template_reading(adapter: FilesystemPromptAssetAdapter, template_id: str, raw: str) -> dict:
    def contract() -> dict[str, Any]:
        body, required, optional = _parse_template_contract(raw)
        return {"body_sha": _sha(body), "required": sorted(required), "optional": sorted(optional)}

    def resolved() -> dict[str, Any]:
        asset = asyncio.run(adapter.resolve_request_template(template_id))
        return {"content_hash": asset.content_hash, "version": asset.version}

    def version() -> str | None:
        info = asyncio.run(adapter.get_asset_version(template_id))
        return info.version if info else None

    return {
        "renderer_contract": _outcome(contract),
        "adapter_resolve": _outcome(resolved),
        "adapter_version": _outcome(version),
    }


#: The strict parser appends PyYAML's own error text. That wording is the library's, so the
#: golden pins our prefix and that a detail followed it, not the library's phrasing.
_YAML_DETAIL_PREFIX = "invalid YAML frontmatter: "


def _strict_reading(raw: str) -> dict[str, Any]:
    fm, error = _parse_frontmatter(raw)
    if error and error.startswith(_YAML_DETAIL_PREFIX) and error[len(_YAML_DETAIL_PREFIX) :]:
        error = _YAML_DETAIL_PREFIX + "<the YAML error>"
    return {"keys": sorted(fm) if fm is not None else None, "error": error}


def _observe(tmp_path: Path) -> dict[str, Any]:
    repo = FileSystemPromptRepository(base_path=_FRAGMENTS)
    observed: dict[str, Any] = {"fragments": {}, "templates": {}, "edges": {}}

    for path in sorted(_FRAGMENTS.rglob("*.md")):
        rel = path.relative_to(_FRAGMENTS).as_posix()
        observed["fragments"][rel] = {
            **_repository_reading(repo, path),
            "strict": _strict_reading(path.read_text()),
        }

    adapter = FilesystemPromptAssetAdapter(fragments_path=_FRAGMENTS, templates_path=_TEMPLATES)
    for path in sorted(_TEMPLATES.glob("*.md")):
        raw = path.read_text()
        observed["templates"][path.stem] = {
            **_template_reading(adapter, path.stem, raw),
            "strict": _strict_reading(raw),
        }

    # Edge inputs go through every reader. The repository and the adapter read files, so each
    # edge is written once as a fragment and once as a template.
    edge_templates = tmp_path / "templates"
    edge_templates.mkdir()
    edge_adapter = FilesystemPromptAssetAdapter(
        fragments_path=_FRAGMENTS, templates_path=edge_templates
    )
    for name, raw in EDGE_INPUTS.items():
        fragment_file = tmp_path / f"{name}.md"
        fragment_file.write_bytes(raw.encode("utf-8"))
        (edge_templates / f"{name}.md").write_bytes(raw.encode("utf-8"))
        observed["edges"][name] = {
            **_repository_reading(repo, fragment_file),
            **_template_reading(edge_adapter, name, raw),
            "strict": _strict_reading(raw),
        }
    return observed


def test_every_reader_matches_the_pre_extraction_golden(tmp_path):
    observed = json.loads(json.dumps(_observe(tmp_path)))

    if os.environ.get("UPDATE_FRONTMATTER_GOLDENS") == "1":
        _GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        _GOLDEN.write_text(json.dumps(observed, indent=1, sort_keys=True) + "\n")
        return

    golden = json.loads(_GOLDEN.read_text())
    for section in ("fragments", "templates", "edges"):
        assert sorted(observed[section]) == sorted(golden[section]), (
            f"{section}: the set of inputs changed — a new prompt asset needs the golden "
            "regenerated deliberately"
        )
        for key, reading in observed[section].items():
            assert reading == golden[section][key], (
                f"{section}/{key}: a frontmatter reader changed what it returns. If the change "
                "is DELIBERATE, regenerate the golden in the same PR so it reads as a "
                "behaviour change, never as a refactor side effect."
            )


def test_the_golden_covers_the_tree_and_is_not_hollow(tmp_path):
    """A golden over zero files, or one where every read failed, would pin nothing."""
    golden = json.loads(_GOLDEN.read_text())
    assert len(golden["fragments"]) >= 30
    assert len(golden["templates"]) >= 50
    read_ok = [r for r in golden["fragments"].values() if "ok" in r["parse_fragment"]]
    assert len(read_ok) == len(golden["fragments"]), "a stored fragment failed to parse"
    declared = [
        t
        for t in golden["templates"].values()
        if t["renderer_contract"].get("ok", {}).get("required")
    ]
    assert declared, "no template declared a required variable — the contract read is untested"
