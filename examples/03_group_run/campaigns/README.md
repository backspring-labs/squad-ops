# group_run campaign definitions

The files `squadops campaigns create --file` reads, for the campaigns SquadOps runs on `group_run` to
verify itself: the live shakeouts, the recovery diagnostics (#1803), the box lease's deployed proof
(#1802), and the 2.0 counted set (`2-0-0-set-1.yaml`, `2-0-0-set-2.yaml`, pinned by #1908).
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

**Outputs stay under the main checkout's `var/campaigns/<campaign>/`:** the log windows
(`campaign_log_archive.py`), the diagnostics' records, the proof logs. They are not inputs, and are not
tracked here. The canonical evidence of a campaign is its close-time package and digest in the vault.
