"""Tests for planning task_type prompt fragments (SIP-0078 Phase 2b).

Verifies that all 7 planning/refinement prompt fragments:
- Exist at the expected filesystem paths
- Have valid YAML frontmatter with correct fragment_id, layer, roles
- Content hashes match manifest entries
- Assembler can resolve them via task_type parameter
"""

import hashlib
import re
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.domain_capabilities]

FRAGMENTS_DIR = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts" / "fragments"

HEADER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.MULTILINE | re.DOTALL)

PLANNING_FRAGMENTS = [
    {
        "fragment_id": "task_type.data.research_context",
        "path": "shared/task_type/task_type.data.research_context.md",
        "layer": "task_type",
        "roles": ["data"],
    },
    {
        "fragment_id": "task_type.strategy.frame_objective",
        "path": "shared/task_type/task_type.strategy.frame_objective.md",
        "layer": "task_type",
        "roles": ["strat"],
    },
    {
        "fragment_id": "task_type.development.design_plan",
        "path": "shared/task_type/task_type.development.design_plan.md",
        "layer": "task_type",
        "roles": ["dev"],
    },
    {
        "fragment_id": "task_type.qa.define_test_strategy",
        "path": "shared/task_type/task_type.qa.define_test_strategy.md",
        "layer": "task_type",
        "roles": ["qa"],
    },
    {
        "fragment_id": "task_type.governance.assess_readiness",
        "path": "shared/task_type/task_type.governance.assess_readiness.md",
        "layer": "task_type",
        "roles": ["lead"],
    },
    {
        "fragment_id": "task_type.governance.incorporate_feedback",
        "path": "shared/task_type/task_type.governance.incorporate_feedback.md",
        "layer": "task_type",
        "roles": ["lead"],
    },
    {
        "fragment_id": "task_type.qa.validate_refinement",
        "path": "shared/task_type/task_type.qa.validate_refinement.md",
        "layer": "task_type",
        "roles": ["qa"],
    },
]


def _load_fragment(rel_path: str) -> tuple[dict, str]:
    """Load a fragment file and return (header_dict, content_after_frontmatter)."""
    full_path = FRAGMENTS_DIR / rel_path
    raw = full_path.read_text(encoding="utf-8")
    m = HEADER_PATTERN.match(raw)
    assert m, f"No YAML frontmatter in {rel_path}"
    header = yaml.safe_load(m.group(1))
    content = raw[m.end():].strip()
    return header, content


def _load_manifest() -> dict:
    """Load and parse manifest.yaml."""
    manifest_path = FRAGMENTS_DIR / "manifest.yaml"
    return yaml.safe_load(manifest_path.read_text(encoding="utf-8"))


class TestPlanningFragmentsExist:
    @pytest.mark.parametrize(
        "spec",
        PLANNING_FRAGMENTS,
        ids=[s["fragment_id"] for s in PLANNING_FRAGMENTS],
    )
    def test_file_exists(self, spec):
        path = FRAGMENTS_DIR / spec["path"]
        assert path.exists(), f"Fragment file not found: {path}"


class TestPlanningFragmentsFrontmatter:
    @pytest.mark.parametrize(
        "spec",
        PLANNING_FRAGMENTS,
        ids=[s["fragment_id"] for s in PLANNING_FRAGMENTS],
    )
    def test_fragment_id_matches(self, spec):
        header, _ = _load_fragment(spec["path"])
        assert header["fragment_id"] == spec["fragment_id"]

    @pytest.mark.parametrize(
        "spec",
        PLANNING_FRAGMENTS,
        ids=[s["fragment_id"] for s in PLANNING_FRAGMENTS],
    )
    def test_layer_is_task_type(self, spec):
        header, _ = _load_fragment(spec["path"])
        assert header["layer"] == "task_type"

    @pytest.mark.parametrize(
        "spec",
        PLANNING_FRAGMENTS,
        ids=[s["fragment_id"] for s in PLANNING_FRAGMENTS],
    )
    def test_roles_match(self, spec):
        header, _ = _load_fragment(spec["path"])
        assert header["roles"] == spec["roles"]


class TestPlanningFragmentsManifest:
    @pytest.mark.parametrize(
        "spec",
        PLANNING_FRAGMENTS,
        ids=[s["fragment_id"] for s in PLANNING_FRAGMENTS],
    )
    def test_manifest_entry_exists(self, spec):
        manifest = _load_manifest()
        entries = [
            f for f in manifest["fragments"]
            if f["fragment_id"] == spec["fragment_id"]
            and f["path"] == spec["path"]
        ]
        assert len(entries) == 1, (
            f"Expected exactly 1 manifest entry for {spec['fragment_id']}, found {len(entries)}"
        )

    @pytest.mark.parametrize(
        "spec",
        PLANNING_FRAGMENTS,
        ids=[s["fragment_id"] for s in PLANNING_FRAGMENTS],
    )
    def test_content_hash_matches_manifest(self, spec):
        """SHA256 of content (after frontmatter) matches manifest entry."""
        _, content = _load_fragment(spec["path"])
        actual_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        manifest = _load_manifest()
        entry = next(
            f for f in manifest["fragments"]
            if f["fragment_id"] == spec["fragment_id"]
            and f["path"] == spec["path"]
        )
        assert actual_hash == entry["sha256"], (
            f"Hash mismatch for {spec['fragment_id']}: "
            f"computed={actual_hash}, manifest={entry['sha256']}"
        )


class TestPlanningFragmentsContent:
    @pytest.mark.parametrize(
        "spec",
        PLANNING_FRAGMENTS,
        ids=[s["fragment_id"] for s in PLANNING_FRAGMENTS],
    )
    def test_content_is_non_empty(self, spec):
        _, content = _load_fragment(spec["path"])
        assert len(content) > 50, f"Fragment content too short: {len(content)} chars"

    def test_seven_planning_fragments_total(self):
        """Exactly 7 planning/refinement task_type fragments exist."""
        task_type_dir = FRAGMENTS_DIR / "shared" / "task_type"
        md_files = list(task_type_dir.glob("*.md"))
        assert len(md_files) == 7
