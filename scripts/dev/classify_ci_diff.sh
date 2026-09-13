#!/usr/bin/env bash
# Is this diff prose only? Reads changed paths on stdin, prints `code=true` or `code=false`.
#
# CI runs every lane when `code=true` and, on a prose-only diff, the prose lane instead of
# the full regression suite, skipping the jobs prose cannot reach. The rule is deliberately
# an ALLOW-list of prose, so a path nobody thought about counts as code and runs everything:
#
#   docs/**              plans, architecture notes, verification-set configs, images
#   sips/**              SIP drafts and the registry
#   site/content/**.md   the published pages (the release-package check still runs)
#   <root>/*.md          README, CHANGELOG, CLAUDE, CONTRIBUTING
#
# A `.md` file anywhere else is NOT prose. Until this script, the filter treated every
# `.md` as documentation, so the prompt assets under src/squadops/prompts (request
# templates, fragments, narratives — what the model is told), the stored reports under
# tests/fixtures and the PRDs under examples/ all rode a docs-only diff.
#
# An empty diff counts as code: nothing to prove prose-only, so nothing is skipped.
set -euo pipefail

PROSE='^(docs/|sips/|site/content/.+\.md$|[^/]+\.md$)'

paths="$(grep -v '^[[:space:]]*$' || true)"
if [ -z "$paths" ]; then
  echo "code=true"
elif printf '%s\n' "$paths" | grep -qvE "$PROSE"; then
  echo "code=true"
else
  echo "code=false"
fi
