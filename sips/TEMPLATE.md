---
sip_uid: "<ulid: python3 scripts/dev/generate_sip_uid.py>"
sip_number: null
title: "<the SIP's name>"
status: "proposed"
author: "<author>"
approver: null
created_at: "<YYYY-MM-DDT00:00:00Z>"
updated_at: "<the same as created_at>"
original_filename: "SIP-<Name>.md"
---

# SIP: <the SIP's name>

**Status:** Proposed

## Intake check

Checked against `sips/PORTFOLIO.md` before this draft was recorded (CLAUDE.md, "SIP System"):

- **Overlaps:** <each live SIP, plan placement or recorded idea this touches, at what point, and the
  boundary between them; or "none found", with what was read>.
- **Conflicts:** <where this and another document prescribe opposite things. Each waits for the owner's
  ruling, and both documents name it until then; or "none">.

The same finding goes into the portfolio's reconciliation queue and intake log.

## Delivery ledger (current as of <YYYY-MM-DD>)

One row per part that ships separately. Statuses: *shipped* (the release, the PR, and the issue it closed), *placed* (the
release and the open issue tracking it, labelled `sip:NNNN` once numbered), *unplaced* (said
deliberately), *dropped* (by the numbered amendment that dropped it), or *deferred to N.x (ruled
<date>)*. Updated in the PR that ships or re-places a part (`tests/unit/architecture/test_sip_ledgers.py`
holds it).

| part | status | where |
|---|---|---|
| <part> | **unplaced** | — |

**What closes this SIP:** <the rows that must be shipped or dropped>.

## 1. Summary

## 2. Motivation

## 3. Design

## 4. Acceptance criteria

## 5. Post-acceptance amendments

<Each a numbered section (5a, 5b, …) naming what changed, the evidence, and who ruled it, added in the
PR that diverges from the accepted text (CLAUDE.md, step 5a).>
