---
title: v1.4.2
---

# v1.4.2

**Released 2026-08-04** · [tag `v1.4.2`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.4.2)

**Correction Aim + Authoring Prevention** — the correction chain aims true, and known
authoring classes can't be authored. Every fix traces to shk-2's diagnosed loss chain,
where a one-line defect survived two correction attempts: **#688** repair targeting now
leads with the owning fill slot (failed probe → endpoint → contract's endpoint→slot map);
**#691** scaffold-frozen paths excluded from interface-drift detection; **#689**
`undefined_names` (pyflakes F821) framework-injected at emission acceptance on `.py` fill
slots — the call-time NameError class every prior gate missed; **#686** plan-shape rules
rendered into the four authoring prompts.

**Corrected premise, recorded:** #691's filing blamed an unauthorized dev write;
provenance showed the artifacts were scaffold-seeded and hash-identical to the contract's
frozen entries. The real defect was drift detection reporting the scaffold's own probe as
producer drift — a permanent false positive on every bind-mode cycle that corrects. The
issue was rewritten before it was built.

Confirmation **shk-3 green**, zero corrections; #686 confirmed at framing in its strongest
form (a compliant plan on the first roll, where shk-1 needed a rejection plus a re-roll).

## Merged pull requests (12)

| PR | Title | Closes |
|---|---|---|
| [#703](https://github.com/backspring-labs/squad-ops/pull/703) | chore(release): bump framework version to 1.4.2 | — |
| [#702](https://github.com/backspring-labs/squad-ops/pull/702) | docs(roadmap): record the #670 fork-1 ruling; correct #689's stated scope | — |
| [#701](https://github.com/backspring-labs/squad-ops/pull/701) | docs(plan): amend 1.4.3 — add #561, retitle the #605 rider, declare pyflakes | — |
| [#700](https://github.com/backspring-labs/squad-ops/pull/700) | docs(plan): 1.4.3 patch line — the loop can't strand or hide | — |
| [#699](https://github.com/backspring-labs/squad-ops/pull/699) | docs(sip): record #571 as a hard prerequisite for Cross-Cycle Memory | — |
| [#698](https://github.com/backspring-labs/squad-ops/pull/698) | feat(planning): state the plan-shape rules in the authoring prompts (#686) | [#686](https://github.com/backspring-labs/squad-ops/issues/686) |
| [#697](https://github.com/backspring-labs/squad-ops/pull/697) | feat(acceptance): catch used-but-never-imported names on emitted Python (#689) | [#689](https://github.com/backspring-labs/squad-ops/issues/689) |
| [#696](https://github.com/backspring-labs/squad-ops/pull/696) | fix(correction): stop reporting scaffold-frozen invariants as producer drift (#691) | [#691](https://github.com/backspring-labs/squad-ops/issues/691) |
| [#695](https://github.com/backspring-labs/squad-ops/pull/695) | fix(correction): aim repairs at the fill slot that owns the failing probe (#688) | [#688](https://github.com/backspring-labs/squad-ops/issues/688) |
| [#694](https://github.com/backspring-labs/squad-ops/pull/694) | docs(1.4.2): rule #689's seam + vehicle, correct two stale plan references | — |
| [#693](https://github.com/backspring-labs/squad-ops/pull/693) | docs: reshuffle follow-ups — lever slotting, Cross-Cycle Memory rev 2, #686 pull-forward | — |
| [#692](https://github.com/backspring-labs/squad-ops/pull/692) | docs: 1.4.2 patch plan — correction aim + authoring prevention (#688/#691/#689/#686) | — |

## Improvement proposals

| Proposal | From | To |
|---|---|---|
| [SIP-Cross-Cycle-Memory](../../design/sips/SIP-Cross-Cycle-Memory.md) | new | proposed |
