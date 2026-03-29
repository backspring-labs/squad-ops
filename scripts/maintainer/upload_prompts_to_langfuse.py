#!/usr/bin/env python3
"""Upload governed prompt assets to Langfuse (SIP-0084 Phase 6, maintainer-only).

Reads all system fragments and request templates from the filesystem,
uploads each to Langfuse via the public REST API (no SDK required),
and reports a summary with asset count, version, and content hash.

Naming convention (SIP-0084 §9):
  - System fragments: ``{fragment_id}`` for shared, ``{fragment_id}--{role}`` for role-specific
  - Request templates: ``{template_id}`` (e.g., ``request.cycle_task_base``)

Usage:
    # Dry-run (show what would be uploaded, no Langfuse calls)
    python scripts/maintainer/upload_prompts_to_langfuse.py --dry-run

    # Upload to local Langfuse
    python scripts/maintainer/upload_prompts_to_langfuse.py \\
        --host http://localhost:3001 \\
        --public-key pk-lf-... \\
        --secret-key sk-lf-...

    # Upload with environment label
    python scripts/maintainer/upload_prompts_to_langfuse.py \\
        --environment local \\
        --host http://localhost:3001 \\
        --public-key pk-lf-... \\
        --secret-key sk-lf-...
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent.parent
FRAGMENTS_DIR = REPO_ROOT / "src" / "squadops" / "prompts" / "fragments"
MANIFEST_PATH = FRAGMENTS_DIR / "manifest.yaml"
TEMPLATES_DIR = REPO_ROOT / "src" / "squadops" / "prompts" / "request_templates"


@dataclass
class UploadEntry:
    """Single asset to upload."""

    name: str
    content: str
    content_hash: str
    asset_type: str  # "fragment" or "template"
    source_path: str


def _compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def collect_fragments() -> list[UploadEntry]:
    """Read manifest and collect all system fragments for upload."""
    if not MANIFEST_PATH.exists():
        print(f"ERROR: manifest not found at {MANIFEST_PATH}", file=sys.stderr)
        sys.exit(1)

    manifest = yaml.safe_load(MANIFEST_PATH.read_text())
    fragments = manifest.get("fragments", [])
    entries: list[UploadEntry] = []

    for frag in fragments:
        frag_id = frag["fragment_id"]
        frag_path = FRAGMENTS_DIR / frag["path"]
        roles = frag.get("roles", ["*"])

        if not frag_path.exists():
            print(f"WARNING: fragment file missing: {frag_path}", file=sys.stderr)
            continue

        content = frag_path.read_text()

        if roles == ["*"]:
            # Shared fragment — upload as-is
            entries.append(
                UploadEntry(
                    name=frag_id,
                    content=content,
                    content_hash=_compute_hash(content),
                    asset_type="fragment",
                    source_path=str(frag_path.relative_to(REPO_ROOT)),
                )
            )
        else:
            # Role-specific — upload with role suffix
            for role in roles:
                langfuse_name = f"{frag_id}--{role}"
                entries.append(
                    UploadEntry(
                        name=langfuse_name,
                        content=content,
                        content_hash=_compute_hash(content),
                        asset_type="fragment",
                        source_path=str(frag_path.relative_to(REPO_ROOT)),
                    )
                )

    return entries


def collect_templates() -> list[UploadEntry]:
    """Collect all request templates for upload."""
    if not TEMPLATES_DIR.exists():
        print(f"ERROR: templates directory not found at {TEMPLATES_DIR}", file=sys.stderr)
        sys.exit(1)

    entries: list[UploadEntry] = []
    for template_path in sorted(TEMPLATES_DIR.glob("*.md")):
        content = template_path.read_text()

        # Extract template_id from frontmatter
        template_id = template_path.stem
        try:
            # Parse YAML frontmatter for template_id
            if content.startswith("---"):
                end = content.index("---", 3)
                header = yaml.safe_load(content[3:end])
                if header and "template_id" in header:
                    template_id = header["template_id"]
        except (ValueError, yaml.YAMLError):
            pass

        entries.append(
            UploadEntry(
                name=template_id,
                content=content,
                content_hash=_compute_hash(content),
                asset_type="template",
                source_path=str(template_path.relative_to(REPO_ROOT)),
            )
        )

    return entries


def _basic_auth_header(public_key: str, secret_key: str) -> str:
    """Build HTTP Basic Auth header value."""
    credentials = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    return f"Basic {credentials}"


def upload_to_langfuse(
    entries: list[UploadEntry],
    host: str,
    public_key: str,
    secret_key: str,
    environment: str,
) -> tuple[int, int]:
    """Upload entries to Langfuse via the public REST API. Returns (success_count, error_count)."""
    auth = _basic_auth_header(public_key, secret_key)
    url = f"{host.rstrip('/')}/api/public/v2/prompts"
    success = 0
    errors = 0

    for entry in entries:
        payload = json.dumps({
            "name": entry.name,
            "prompt": entry.content,
            "labels": [environment],
            "type": "text",
        }).encode()

        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", auth)

        try:
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read().decode())
                version = result.get("version", "?")
                success += 1
                print(f"  OK  {entry.name} v{version} ({entry.content_hash[:12]}...)")
        except urllib.error.HTTPError as exc:
            errors += 1
            body = exc.read().decode() if exc.fp else ""
            print(f"  FAIL {entry.name}: HTTP {exc.code} {body[:120]}", file=sys.stderr)
        except Exception as exc:
            errors += 1
            print(f"  FAIL {entry.name}: {exc}", file=sys.stderr)

    return success, errors


def print_dry_run(entries: list[UploadEntry], environment: str) -> None:
    """Print what would be uploaded without making API calls."""
    print(f"\n{'='*70}")
    print(f"DRY RUN — {len(entries)} assets would be uploaded (environment: {environment})")
    print(f"{'='*70}\n")

    fragments = [e for e in entries if e.asset_type == "fragment"]
    templates = [e for e in entries if e.asset_type == "template"]

    if fragments:
        print(f"System fragments ({len(fragments)}):")
        for e in fragments:
            print(f"  {e.name:<45} {e.content_hash[:12]}...  ({e.source_path})")

    if templates:
        print(f"\nRequest templates ({len(templates)}):")
        for e in templates:
            print(f"  {e.name:<45} {e.content_hash[:12]}...  ({e.source_path})")

    print(f"\nTotal: {len(entries)} assets")


def _default_environment() -> str:
    """Derive environment from DEPLOYMENT_PROFILE or SQUADOPS_PROFILE."""
    return os.environ.get(
        "DEPLOYMENT_PROFILE",
        os.environ.get("SQUADOPS_PROFILE", "dev"),
    )


def main() -> None:
    if not os.environ.get("SQUADOPS_MAINTAINER"):
        print("ERROR: This script is maintainer-only. Set SQUADOPS_MAINTAINER=1.", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Upload governed prompt assets to Langfuse (SIP-0084)."
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be uploaded")
    parser.add_argument("--host", default="http://localhost:3001", help="Langfuse host URL")
    parser.add_argument("--public-key", default=os.environ.get("LANGFUSE_PUBLIC_KEY", ""))
    parser.add_argument("--secret-key", default=os.environ.get("LANGFUSE_SECRET_KEY", ""))
    parser.add_argument(
        "--environment",
        default=_default_environment(),
        help="Environment label (default: from DEPLOYMENT_PROFILE or SQUADOPS_PROFILE)",
    )
    args = parser.parse_args()

    # Collect all assets
    fragments = collect_fragments()
    templates = collect_templates()
    all_entries = fragments + templates

    if not all_entries:
        print("No assets found to upload.", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print_dry_run(all_entries, args.environment)
        return

    # Validate credentials
    if not args.public_key or not args.secret_key:
        print(
            "ERROR: --public-key and --secret-key required (or set "
            "LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY env vars).",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Uploading {len(all_entries)} assets to {args.host} (environment: {args.environment})")
    print()

    success, errors = upload_to_langfuse(
        all_entries, args.host, args.public_key, args.secret_key, args.environment
    )

    print(f"\nDone: {success} uploaded, {errors} failed.")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
