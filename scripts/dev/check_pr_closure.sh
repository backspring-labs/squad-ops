#!/usr/bin/env bash
# PR closure-reference guard (#1113). Reads a PR body on stdin, exits non-zero
# unless it carries a closing reference to an OPEN issue or an explicit opt-out.
#
# CLAUDE.md: "Every PR body must include `Closes #NNN` (or `Fixes #NNN`) for each
# issue it fully resolves". GitHub auto-closes only on those keywords; `**#N**`
# headings and `Refs #N` do not. Six 1.6.4 fix PRs shipped without one and the
# issues were still open at the cut — the second recurrence of #133/#205.
#
# Passes when the body contains at least one of:
#   Closes #N | Fixes #N | Resolves #N   (any tense; N must be an OPEN issue, not a PR)
#   Refs #N … remaining: …               (partial fix — says what is left)
#   No issue: …                          (deliberately no issue behind the PR)
#
# Local use:  gh pr view 1234 --json body -q .body | scripts/dev/check_pr_closure.sh
# CI use:     .github/workflows/pr-closure.yml pipes the event body in.
# Needs `gh` authenticated (GH_TOKEN in CI) and GH_REPO or a git remote.
set -euo pipefail

body="$(cat)"
repo="${GH_REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"

closing_numbers="$(
  printf '%s' "$body" \
    | grep -oiE '\b(close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)[[:space:]]*:?[[:space:]]*#[0-9]+' \
    | grep -oE '[0-9]+$' | sort -un || true
)"
optout_count="$(
  printf '%s' "$body" \
    | grep -ciE '(refs?[[:space:]]+#[0-9]+.*remaining:[[:space:]]*[^[:space:]]|^[[:space:]]*no issue:[[:space:]]*[^[:space:]])' || true
)"

if [ -z "$closing_numbers" ] && [ "$optout_count" -eq 0 ]; then
  cat >&2 <<'MSG'
pr-closure: FAIL — the PR body carries no closing reference and no opt-out.
  Add one line per issue this PR fully resolves:   Closes #NNN
  Partial fix (say what remains):                  Refs #NNN — remaining: …
  No issue behind this PR (say why):               No issue: …
  (CLAUDE.md "Close issues from PRs"; bold headings and bare #NNN do not close — #1113)
MSG
  exit 1
fi

status=0
for n in $closing_numbers; do
  json="$(gh api "repos/${repo}/issues/${n}" 2>/dev/null || true)"
  if [ -z "$json" ]; then
    echo "pr-closure: FAIL — Closes #${n}: no such issue in ${repo}" >&2; status=1; continue
  fi
  if printf '%s' "$json" | grep -q '"pull_request"'; then
    echo "pr-closure: FAIL — Closes #${n} is a pull request, not an issue" >&2; status=1; continue
  fi
  state="$(printf '%s' "$json" | grep -oE '"state": *"[a-z]+"' | head -1 | grep -oE '[a-z]+"$' | tr -d '"')"
  if [ "$state" != "open" ]; then
    echo "pr-closure: FAIL — Closes #${n} is already ${state} (typo, duplicate, or stale reference?)" >&2; status=1; continue
  fi
  echo "pr-closure: ok — Closes #${n} (open issue)"
done
[ "$status" -eq 0 ] && [ -z "$closing_numbers" ] && echo "pr-closure: ok — explicit opt-out present, no closing reference"
exit "$status"
