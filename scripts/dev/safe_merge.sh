#!/usr/bin/env bash
# Merge a pull request only when the merge can't hurt the other lane's work.
#
# Two lanes merge to main, and main's CI group cancels a run in progress when a newer commit
# lands. So a merge made on a reading of main taken a moment earlier cancels the other lane's
# run (2026-10-23 and 2026-10-24), and a PR whose own CI run is still queued shows no failing
# check yet (2026-11-04). This check reads all of it in the command that merges:
#
#   1. the PR is open, isn't a draft, and its head is the full sha given;
#   2. the head's own `CI` run has completed with success, and no check on the PR is pending
#      or failed;
#   3. main's newest `CI` run is on main's current tip, and has completed with success;
#   4. then: gh pr merge --squash --delete-branch --match-head-commit <sha>.
#
# Usage:
#   scripts/dev/safe_merge.sh <pr-number> <full-head-sha> [--wait] [--fixes-red-main] [--dry-run]
#
#   --wait            poll until 2 and 3 settle: every SAFE_MERGE_POLL_SECONDS (default 30),
#                     for up to SAFE_MERGE_WAIT_SECONDS (default 3600). A failure still refuses
#                     at once.
#   --fixes-red-main  this PR is the fix for main's red. Main's newest CI run may have failed.
#                     It must still be on main's tip and completed (the 2.9 plan's D11).
#   --dry-run         run every check, and print the merge command without running it.
#
# Exit: 0 merged (or would merge); 1 refused, with the reason on stderr; 2 usage.
#
# After a merge, read every job of main's run on the merge commit (CLAUDE.md, Required checks).
# bash 3.2 and the flags BSD and GNU share (CLAUDE.md, Structure; #2402).
set -euo pipefail

usage() {
    sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//' >&2
    exit 2
}

pr=""
sha=""
wait_mode=0
fixes_red=0
dry_run=0
while [ $# -gt 0 ]; do
    case "$1" in
        --wait) wait_mode=1 ;;
        --fixes-red-main) fixes_red=1 ;;
        --dry-run) dry_run=1 ;;
        -h | --help) usage ;;
        -*)
            echo "safe_merge: unknown option '$1'" >&2
            exit 2
            ;;
        *)
            if [ -z "$pr" ]; then
                pr="$1"
            elif [ -z "$sha" ]; then
                sha="$1"
            else
                echo "safe_merge: too many arguments" >&2
                exit 2
            fi
            ;;
    esac
    shift
done
if [ -z "$pr" ] || [ -z "$sha" ]; then
    usage
fi
case "$pr" in
    *[!0-9]*)
        echo "safe_merge: the PR number is digits, and got '$pr'" >&2
        exit 2
        ;;
esac
if ! printf '%s' "$sha" | grep -Eq '^[0-9a-f]{40}$'; then
    echo "safe_merge: give the head's full 40-character sha, and got '$sha'. A short one matches no CI run." >&2
    exit 2
fi

# What a check returns: 0 it holds; 1 it fails, and waiting won't change that; 3 not yet.
REASON=""
NOTE=""

field() {
    printf '%s' "$1" | cut -f"$2"
}

check_pr() {
    local view state draft head
    if ! view=$(gh pr view "$pr" --json state,isDraft,headRefOid \
        --jq '[.state, (.isDraft | tostring), .headRefOid] | @tsv'); then
        REASON="PR #$pr couldn't be read"
        return 1
    fi
    state=$(field "$view" 1)
    draft=$(field "$view" 2)
    head=$(field "$view" 3)
    if [ "$state" != "OPEN" ]; then
        REASON="PR #$pr is $state"
        return 1
    fi
    if [ "$draft" != "false" ]; then
        REASON="PR #$pr is a draft"
        return 1
    fi
    if [ "$head" != "$sha" ]; then
        REASON="PR #$pr's head is $head, and you gave $sha: it moved after you read it"
        return 1
    fi
    return 0
}

check_head() {
    local run status conclusion checks pending failed
    if ! run=$(gh run list --workflow CI --commit "$sha" --limit 1 --json status,conclusion \
        --jq '.[0] | [(.status // "none"), (.conclusion // "")] | @tsv'); then
        REASON="the head's CI run couldn't be read"
        return 1
    fi
    status=$(field "$run" 1)
    conclusion=$(field "$run" 2)
    if [ "$status" != "completed" ]; then
        REASON="the head's CI run is '$status', so the PR isn't proved yet"
        return 3
    fi
    if [ "$conclusion" != "success" ]; then
        REASON="the head's CI run concluded '$conclusion'"
        return 1
    fi
    # Every other check on the PR: a check run has a status and a conclusion, a commit status a state.
    if ! checks=$(gh pr view "$pr" --json statusCheckRollup --jq '
        [
          ([.statusCheckRollup[]
            | select(((.status // "COMPLETED") != "COMPLETED")
                     or ((.state // "SUCCESS") | test("^(PENDING|EXPECTED)$")))]
           | length | tostring),
          ([.statusCheckRollup[]
            | select(((.conclusion // "") | test("^(FAILURE|CANCELLED|TIMED_OUT|ACTION_REQUIRED|STARTUP_FAILURE)$"))
                     or ((.state // "") | test("^(FAILURE|ERROR)$")))
            | (.name // .context // "a check")]
           | join(", "))
        ] | @tsv'); then
        REASON="PR #$pr's checks couldn't be read"
        return 1
    fi
    pending=$(field "$checks" 1)
    failed=$(field "$checks" 2)
    if [ -n "$failed" ]; then
        REASON="PR #$pr has failed checks: $failed"
        return 1
    fi
    if [ "$pending" != "0" ]; then
        REASON="PR #$pr has $pending check(s) still running"
        return 3
    fi
    return 0
}

check_main() {
    local tip run run_sha status conclusion
    if ! git fetch -q origin main; then
        REASON="origin/main couldn't be fetched"
        return 1
    fi
    tip=$(git rev-parse origin/main)
    if ! run=$(gh run list --branch main --workflow CI --limit 1 --json headSha,status,conclusion \
        --jq '.[0] | [(.headSha // "none"), (.status // "none"), (.conclusion // "")] | @tsv'); then
        REASON="main's CI run couldn't be read"
        return 1
    fi
    run_sha=$(field "$run" 1)
    status=$(field "$run" 2)
    conclusion=$(field "$run" 3)
    if [ "$run_sha" != "$tip" ]; then
        REASON="main's newest CI run is on $run_sha and main's tip is $tip: the tip's run hasn't started"
        return 3
    fi
    if [ "$status" != "completed" ]; then
        REASON="main's CI run on its tip is '$status': a merge now would cancel it"
        return 3
    fi
    if [ "$conclusion" != "success" ]; then
        if [ "$fixes_red" -eq 1 ]; then
            NOTE="main's CI on $tip concluded '$conclusion', and this merge is given as its fix (--fixes-red-main)"
            return 0
        fi
        REASON="main's CI on its tip concluded '$conclusion'. Fix main first, or pass --fixes-red-main when this PR is the fix"
        return 1
    fi
    return 0
}

check_all() {
    local rc=0
    check_pr || rc=$?
    if [ "$rc" -ne 0 ]; then
        return "$rc"
    fi
    check_head || rc=$?
    if [ "$rc" -ne 0 ]; then
        return "$rc"
    fi
    check_main || rc=$?
    return "$rc"
}

deadline=$(($(date +%s) + ${SAFE_MERGE_WAIT_SECONDS:-3600}))
while :; do
    rc=0
    check_all || rc=$?
    if [ "$rc" -eq 0 ]; then
        break
    fi
    if [ "$rc" -eq 3 ] && [ "$wait_mode" -eq 1 ] && [ "$(date +%s)" -lt "$deadline" ]; then
        sleep "${SAFE_MERGE_POLL_SECONDS:-30}"
        continue
    fi
    echo "safe_merge: refused: $REASON" >&2
    exit 1
done

if [ -n "$NOTE" ]; then
    echo "safe_merge: $NOTE" >&2
fi
if [ "$dry_run" -eq 1 ]; then
    echo "safe_merge: every check holds. Would run: gh pr merge $pr --squash --delete-branch --match-head-commit $sha"
    exit 0
fi

# gh also tries to delete the local branch, and reports a failure when another worktree holds it.
# The merge itself is what counts, so read the PR's state afterwards.
merge_rc=0
gh pr merge "$pr" --squash --delete-branch --match-head-commit "$sha" || merge_rc=$?
if ! merged=$(gh pr view "$pr" --json state,mergeCommit \
    --jq '[.state, (.mergeCommit.oid // "")] | @tsv'); then
    echo "safe_merge: the merge was asked for (gh exit $merge_rc), and PR #$pr's state couldn't be read after it" >&2
    exit 1
fi
if [ "$(field "$merged" 1)" != "MERGED" ]; then
    echo "safe_merge: refused by GitHub: PR #$pr is $(field "$merged" 1) after the merge was asked for (gh exit $merge_rc)" >&2
    exit 1
fi
echo "safe_merge: merged PR #$pr as $(field "$merged" 2). Read every job of main's run on that commit."
