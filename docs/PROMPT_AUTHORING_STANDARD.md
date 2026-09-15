# Prompt Authoring Standard

The standard for every request template, fragment and appendix under
`src/squadops/prompts/`. It is to prompts what `TEST_QUALITY_STANDARD.md` is to tests: a
review checklist with the failure it prevents named beside each rule. Prompt content lives in
managed assets via PromptService, never in Python literals (CLAUDE.md, #448); this document is
about what that content says.

## The failure this exists to prevent

On 2026-09-15 the repair prompt was found to have told the model, on every repair the
framework had ever run, to copy an anchor "exactly from the file as it is now" — about a file
the prompt never showed (#1576, SIP-0107 §46m). The model complied as well as it could: it
recalled the decorator it could not see, misquoted it six times in six, and when the anchor
was refused it rewrote every function in the file blind, legally. Fifteen amendments and ten
thousand tests had not caught it, because the prompt had a rule where it needed evidence. Once
the file was shown, the same model made a five-line edit in a quarter of the time.

## Rules

1. **Show, don't tell.** Before writing an instruction, ask what the model would need to see
   to make the instruction unnecessary, and show that instead. "Copy exactly from the file"
   is a rule; the file is evidence. A rule that survives this question names the thing it
   prevents and cites the case.
2. **The model sees what it edits.** Every file a task may change is in the prompt, verbatim,
   from the tree the result will be evaluated on. A section that tells the model about a file
   it cannot see is a defect, whatever else it says.
3. **Every error, not the first.** Evidence handed to a model is the whole diagnostic list the
   toolchain produced. A compiler that stops at the first error is a toolchain choice to work
   around, not a prompt fact to pass on (SIP-0086 §12a).
4. **One loud rule.** A 27B model obeys the loudest instruction literally. A prompt with a
   dozen prohibitions has a dozen loudest rules, and the model spends its capacity ranking
   them. Prefer one authoritative block, marked as such, and prose for the rest.
5. **A prohibition names its alternative.** "Do not re-emit the file" is complete only with
   "change it with an edit fence, described below". A bare prohibition leaves the model to
   guess the permitted form, and it guesses the one it was trained on.
6. **Verbatim content is fenced, and the renderer keeps fenced content verbatim** (SIP-0107
   §46m). A shown file rides in a fence longer than any backtick run inside it, never in the
   emission-form header the model uses for its own output.
7. **The dispute line is read or removed.** An instruction that invites the model to object
   ("say why in one line") is a contract; if nothing consumes the objection, the line is a
   lie the model cannot detect (SIP-0096 §17a).
8. **The prompt is rendered and read before it is merged.** A PR that changes a template
   renders it through the real handler on real inputs and puts the section list and the
   token count in its Evidence. Every prompt defect found in 1.7.x and 1.8.0 was visible in
   the rendered text and invisible in the template.

## The review checklist

- What does the model see, in order? (Render it.)
- What does an instruction assume the model can see that it cannot?
- Which rule could be replaced by shown data?
- Which rule is the loudest, and is it the one that matters?
- Does every prohibition name the permitted form?
- Is every objection channel consumed by something?
- How many tokens, and how many of them are rules?

## Provenance

Written 2026-09-15 from the scoped-repair readiness probes (SIP-0107 §46m–§46o) on the
owner's question of whether the framework constrains the model it runs. The rules are the
lessons of #448, #1289, #1576 and the 2026-09-15 probe, one per failure.
