"""Writes dist/manifest.json: Tally's version and each asset's digest."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tally import __version__  # noqa: E402


def main():
    assets = {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / "assets").iterdir())
        if path.is_file()
    }
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    manifest = {"version": __version__, "assets": assets}
    (dist / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {dist / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
