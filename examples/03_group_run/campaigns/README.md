# group_run campaign definitions

The files `squadops campaigns create --file` reads, for the campaigns SquadOps runs on `group_run` to
verify itself: the live shakeouts, the recovery diagnostics (#1803), the box lease's deployed proof
(#1802), the 2.0 counted set (`2-0-0-set-1.yaml`, `2-0-0-set-2.yaml`, pinned by #1908), and the 2.2 measurement
window's five campaigns (`2-2-0-window-1-capacity.yaml` to `2-2-0-window-5-seed.yaml`, one objective each, under the
slice 4 pre-registration, `docs/plans/2-2-0-slice4-preregistration.md` §4), and the 2.2 cut's shakeout and the
plan-review tier's diagnostic (`2-2-0-cut-shakeout.yaml`, `2-2-0-cut-tier-diag.yaml`, under
`docs/plans/2-2-0-cut-preregistration.md` §2).
Campaigns an operator runs for their own purposes are theirs to keep, wherever they like.

**A definition is the record of a campaign only when it reconciles with the stored campaign:** the same
`project_id`, objective and policy, compared as the domain objects the runtime builds. A definition that
reconciles with no campaign is an example, not evidence (#1941).
`scripts/dev/campaign_definition_provenance.py` does the comparison and writes `provenance.yaml`:
- for each campaign, the definitions that reconcile with it and each file's sha256;
- the identity of the campaign's close-time evidence package, the canonical record the file is matched to;
- the campaign's create reason, which names the run.

```bash
python scripts/dev/campaign_definition_provenance.py examples/03_group_run/campaigns --write
```

**Some files are semantically identical** (shakeout-1 and -2, -3 and -4, -6 and -7, and the set's two
files, which carry shakeout 7's policy exactly, so the set runs what the exit shakeout ran). Each of
these reconciles with every campaign of that content. That is the claim the reconciliation makes: this
file's content produced that campaign. The create reason says which run it was.

**A definition's comment says what the file is, never which deploy or round it will run on**
(#1958). Those facts belong to the pre-registration, which records them when they are read; a
definition is pinned by path, commit and sha256 before the run, so a comment naming its deploy is
already stale when a later round moves the deploy. The 2.0 set's two files say "rebuild 19, b0c25360"
and the set registered on rebuild 22. A comment may name the campaign, the issue it serves and what
it is meant to show. `tests/unit/campaigns/test_definition_comments.py` refuses a `rebuild N`, a
`round N`, a deploy id or a commit sha in the comment of any definition whose bytes `provenance.yaml`
has not pinned. A pinned file stays as it was written: editing it would break the reconciliation.

**Outputs stay under the main checkout's `var/campaigns/<campaign>/`:** the log windows
(`campaign_log_archive.py`), the diagnostics' records, the proof logs. They are not inputs, and are not
tracked here. The canonical evidence of a campaign is its close-time package and digest in the vault.
