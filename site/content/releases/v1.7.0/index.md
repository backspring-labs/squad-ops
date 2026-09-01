---
title: v1.7.0
---

# v1.7.0

**Released 2026-09-01** · [tag `v1.7.0`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.7.0)

**The Reasoning line opens.** Plan: `docs/plans/1-7-0-plan.md` (rev 3). Cut record:
`docs/plans/1-7-0-cut-record.md`.

Gated on a two-stack shakeout pair on frozen deploy `bbf42f8d`, **zero code drift between
the deploy and the tag**: Next.js+TS `cyc_2a88dabad94b` 15/15 and FastAPI+React
`cyc_cb49b16c2fa6` 15/15, both accepted, zero correction rounds, both boot audits PASS.

It took six rolls. Rolls 3–5 produced five rejections across four distinct causes, every one
a real defect the shakeouts surfaced — recorded in the cut record §3 because the plan's
calibration assumes a line's rolls mostly pass and this one did not.

### Changed — the LLM provider is required configuration (#1157, SIP-0106 Ruling 3)
- **`SQUADOPS__LLM__PROVIDER` is required and never defaulted.** Two adapters were in the
  tree while the factory defaulted `provider="ollama"`, the agent entrypoint never passed
  one and `LLMConfig` had no field — the vLLM adapter was unreachable by any configuration
  since it landed. Now `LLMConfig.provider` and `create_llm_provider(provider, …)` have no
  default; a missing value fails at config load the way an unknown one fails in the
  factory. Every deploy surface writes the value: the eight SquadOps service blocks in
  `docker-compose.yml`, `.env.example` (uncommented), the test fixtures. The switch to
  another provider is one PR changing that value (SIP-0106 §5).
- **Both composition roots go through the factory**: the runtime-api no longer constructs
  `OllamaAdapter` directly (the LLM half of #301), and the cycle-create model preflight asks
  the port for `MODEL_LISTING` instead of `isinstance(OllamaAdapter)` — on any other
  provider it was silently unverifiable.
- The mis-nested `SQUADOPS__LLM__USE__LOCAL` example and the `use_local` field it never
  reached are gone.

### Added — the Atlas adapter (#1159, SIP-0106 P4)
- **`adapters/llm/atlas.py`**, selected by `SQUADOPS__LLM__PROVIDER=atlas`: its own file,
  not a subclass of the vLLM adapter (SIP-0106 §3.5a), because the dialect diverges where
  it matters — every item measured on the Spark on 2026-08-28. A bearer token is mandatory
  once the server is bound off localhost (`SQUADOPS__LLM__API_KEY`, a `secret://` ref the
  loader resolves; a 401 names that setting rather than reporting a network failure); the
  engine's own `response_token/s` is reported instead of a wall-clock derivation;
  `reasoning_tokens` are counted separately (`thinking_tokens: True`); the port's level
  maps onto Atlas's `reasoning_effort` ladder verbatim except `high → xhigh`, which the
  served Qwen3.8 template requires; streamed `reasoning_content` deltas never reach the
  text. Registered as the conformance suite's third case, with the measured shapes.
- `ChatMessage` / `LLMResponse` gain `reasoning_tokens` (None when not reported, never
  zero); `Qwen/Qwen3.8-27B-FP8` joins the model registry with the window the A/B recipe
  serves — 64K, raised from the first recipe's 32K because that left the prompt guard a
  24,576-token budget and 5.9% of the arm's real prompts run longer (#1160 §1.4).

### Added — reasoning is a level on the port (#927)
- **The port carries `reasoning: none | low | medium | high`**, never a provider's
  switch. Ollama maps `none → think:false` and any graded level → `think:true`; vLLM
  maps by the dial the model spec declares (`chat_template_kwargs.enable_thinking`
  for a toggle model, `reasoning_effort` for an effort model, nothing for a model
  with no channel). `LLMCapability.REASONING_CONTROL` declares whether a level
  reaches the wire, and the conformance suite asserts the declaration against the
  request bodies for every adapter. No level sent ⇒ the wire is byte-identical to
  what it was before this change.
- **Every capability declares how much reasoning its output wants**
  (`capabilities/reasoning_policy.py`): a transcription — filling scaffold slots,
  a repair verdict, a stored report — is `none`; an argument — the manifest, the
  analyses, the plan — is `high`. #924 measured the difference on the deployed qa
  fill brief: 5,727 completion tokens with the channel on, 413 with it off, the same
  eight fences. No default: an undeclared capability raises, and a test over the
  handler registry makes the gap a CI failure.
- **Resolution is the chain every other knob uses**: the declaration →
  `config_overrides.reasoning` (a new allowed key, value validated at the profile
  boundary) → the model's dial (`ModelSpec.reasoning_control`, required on every
  registry entry; qwen3.x `toggle`, qwen2.5/llama3 `none` — a model with no channel
  gets no level, since Ollama rejects `think` for it).
- **`GenerationRecord.reasoning`** carries the sent level to LangFuse, so "how
  much did this call think" is read per generation rather than inferred from a
  token count.

## Merged pull requests (44)

| PR | Title | Closes |
|---|---|---|
| [#1227](https://github.com/backspring-labs/squad-ops/pull/1227) | chore(release): 1.7.0 — the Reasoning line | — |
| [#1226](https://github.com/backspring-labs/squad-ops/pull/1226) | docs(plan): the 1.7.0 cut record — what the shakeouts did not exercise | — |
| [#1225](https://github.com/backspring-labs/squad-ops/pull/1225) | fix(correction): a repair that can never be verified stops being retried | [#1221](https://github.com/backspring-labs/squad-ops/issues/1221) |
| [#1224](https://github.com/backspring-labs/squad-ops/pull/1224) | fix(qa): a failing contract probe fails its task, so the correction loop engages | [#1223](https://github.com/backspring-labs/squad-ops/issues/1223) |
| [#1222](https://github.com/backspring-labs/squad-ops/pull/1222) | fix(checks): a path alias is not a scoped package — declared_imports stops failing every Next.js route | — |
| [#1220](https://github.com/backspring-labs/squad-ops/pull/1220) | ci: a docs-only PR stops paying for the integration lane | — |
| [#1219](https://github.com/backspring-labs/squad-ops/pull/1219) | feat(checks): a coverage gap is declared with its reason, or CI fails | [#1216](https://github.com/backspring-labs/squad-ops/issues/1216) |
| [#1218](https://github.com/backspring-labs/squad-ops/pull/1218) | feat(checks): a JS/TS emission's npm imports must be declared | [#1217](https://github.com/backspring-labs/squad-ops/issues/1217) |
| [#1215](https://github.com/backspring-labs/squad-ops/pull/1215) | fix(sandbox): a crashed app keeps its logs, and stops being called a timeout | [#1214](https://github.com/backspring-labs/squad-ops/issues/1214) |
| [#1212](https://github.com/backspring-labs/squad-ops/pull/1212) | fix(verification): a submodule is not an unbound name — the import pre-gate stops refusing valid repairs | [#1211](https://github.com/backspring-labs/squad-ops/issues/1211) |
| [#1210](https://github.com/backspring-labs/squad-ops/pull/1210) | docs(plan): §6.1 stops asking for two things the system cannot do, and drops a deferred issue | — |
| [#1209](https://github.com/backspring-labs/squad-ops/pull/1209) | docs(plan): the same-task none/high measurement, and the headroom claim it qualifies | — |
| [#1208](https://github.com/backspring-labs/squad-ops/pull/1208) | feat(llm): top_p reaches the provider, so temperature stops being half a pair | [#901](https://github.com/backspring-labs/squad-ops/issues/901) |
| [#1207](https://github.com/backspring-labs/squad-ops/pull/1207) | docs(plan): the reasoning budget re-read, and the #924 split that does not reproduce | — |
| [#1203](https://github.com/backspring-labs/squad-ops/pull/1203) | chore(deps): the images install what CI tests — 42 divergences down to 2, both documented | [#237](https://github.com/backspring-labs/squad-ops/issues/237) [#1041](https://github.com/backspring-labs/squad-ops/issues/1041) |
| [#1202](https://github.com/backspring-labs/squad-ops/pull/1202) | fix(maintainer): one home for what counts as a closing reference | [#1135](https://github.com/backspring-labs/squad-ops/issues/1135) |
| [#1201](https://github.com/backspring-labs/squad-ops/pull/1201) | feat(observability): the reasoning text's length stands in where the provider reports no count | [#1195](https://github.com/backspring-labs/squad-ops/issues/1195) |
| [#1200](https://github.com/backspring-labs/squad-ops/pull/1200) | chore(llm): delete LLMRouter — 139 lines never constructed, maintained four times | [#944](https://github.com/backspring-labs/squad-ops/issues/944) |
| [#1199](https://github.com/backspring-labs/squad-ops/pull/1199) | fix(driver): a cycle that never builds anything ends the drive loop instead of outlasting it | [#1168](https://github.com/backspring-labs/squad-ops/issues/1168) |
| [#1198](https://github.com/backspring-labs/squad-ops/pull/1198) | fix(llm): the reasoning channel survives the streaming path, which is the one cycles use | [#1194](https://github.com/backspring-labs/squad-ops/issues/1194) [#1196](https://github.com/backspring-labs/squad-ops/issues/1196) |
| [#1193](https://github.com/backspring-labs/squad-ops/pull/1193) | docs(plan): the ollama sets describe the rebuild they now validate, and their checks can tell a stale image | — |
| [#1192](https://github.com/backspring-labs/squad-ops/pull/1192) | docs(plan): the ollama sets' gate and launch notes stop claiming an Atlas A/B that was stopped | — |
| [#1191](https://github.com/backspring-labs/squad-ops/pull/1191) | feat(cycles): the cycle/CRP reasoning override — #927's fourth rung | [#927](https://github.com/backspring-labs/squad-ops/issues/927) |
| [#1190](https://github.com/backspring-labs/squad-ops/pull/1190) | fix(llm): an unregistered model stops degrading silently on all three paths | [#1145](https://github.com/backspring-labs/squad-ops/issues/1145) |
| [#1189](https://github.com/backspring-labs/squad-ops/pull/1189) | fix(agents): the boot log names the fallback model as a fallback, not as the model in use | [#930](https://github.com/backspring-labs/squad-ops/issues/930) |
| [#1188](https://github.com/backspring-labs/squad-ops/pull/1188) | feat(observability): the emission log reports the reasoning split, so #924's two failures stop looking identical | [#924](https://github.com/backspring-labs/squad-ops/issues/924) |
| [#1187](https://github.com/backspring-labs/squad-ops/pull/1187) | feat(ops): back up the deployment database, and prove the backup restores | [#1181](https://github.com/backspring-labs/squad-ops/issues/1181) |
| [#1186](https://github.com/backspring-labs/squad-ops/pull/1186) | feat(llm): the reasoning channel reaches the port and LangFuse instead of being dropped | [#410](https://github.com/backspring-labs/squad-ops/issues/410) |
| [#1185](https://github.com/backspring-labs/squad-ops/pull/1185) | test(architecture): ratchet the image-vs-CI dependency divergence so it cannot widen silently | — |
| [#1183](https://github.com/backspring-labs/squad-ops/pull/1183) | fix(tests)+ci: the integration suite stops targeting the deployment database, the sixteen go green, and CI runs them | [#242](https://github.com/backspring-labs/squad-ops/issues/242) [#1099](https://github.com/backspring-labs/squad-ops/issues/1099) |
| [#1179](https://github.com/backspring-labs/squad-ops/pull/1179) | docs(plan): the Atlas A/B returns a negative — the record, the SIP amendment, and vLLM as the second arm | [#1160](https://github.com/backspring-labs/squad-ops/issues/1160) |
| [#1175](https://github.com/backspring-labs/squad-ops/pull/1175) | docs(plan): Atlas A/B §1.5 — the third shakeout, the 14-configuration replay matrix, and the arm-A control (#1160) | — |
| [#1174](https://github.com/backspring-labs/squad-ops/pull/1174) | fix: the framing half of a cycle is observable and correctly budgeted — one seam for generation records, per-attempt manifest telemetry, and a completion budget that accounts for declared thinking | [#1171](https://github.com/backspring-labs/squad-ops/issues/1171) [#1172](https://github.com/backspring-labs/squad-ops/issues/1172) [#1173](https://github.com/backspring-labs/squad-ops/issues/1173) |
| [#1170](https://github.com/backspring-labs/squad-ops/pull/1170) | fix(llm): the Atlas arm's served window covers its own prompts — 32K left the prompt guard 24,576 tokens (#1160 §1.4) | — |
| [#1169](https://github.com/backspring-labs/squad-ops/pull/1169) | docs(plan): Atlas A/B pre-registration §1.2 — the content-loop watchdog cut long YAML; serve line adds --content-loop-watchdog false, --lm-head-dtype bf16 (#1160) | — |
| [#1167](https://github.com/backspring-labs/squad-ops/pull/1167) | fix(llm): Atlas's server-side request cut is a timeout, not a complete message; serve line sets --request-timeout (#1160 shakeout) | — |
| [#1166](https://github.com/backspring-labs/squad-ops/pull/1166) | docs(plan): 1.7.0 Atlas A/B pre-registration — two deploys, arm B tuned (FP8 + MTP K=4); full-38-atlas profile; the compose override that points the deploy at Atlas (#1160) | — |
| [#1165](https://github.com/backspring-labs/squad-ops/pull/1165) | feat(llm): Atlas adapter — the DGX Spark engine behind LLMPort, from the measured dialect (#1159, SIP-0106 P4) | [#1159](https://github.com/backspring-labs/squad-ops/issues/1159) |
| [#1164](https://github.com/backspring-labs/squad-ops/pull/1164) | feat(config): the LLM provider is required configuration — selected by name through the factory at both composition roots (#1157) | [#1157](https://github.com/backspring-labs/squad-ops/issues/1157) |
| [#1163](https://github.com/backspring-labs/squad-ops/pull/1163) | fix(maintainer): SIP files are named for the SIP — the title's name, at most three words | — |
| [#1162](https://github.com/backspring-labs/squad-ops/pull/1162) | docs(sip): accept SIP-0106 Atlas Provider Adapter — rev 2 (§10.2 settled live, owner rulings, Appendix B measured); plan rev 3.1 | — |
| [#1161](https://github.com/backspring-labs/squad-ops/pull/1161) | feat(llm): reasoning is a level on the port, declared per capability, mapped by each adapter (#927, 1.7.0 Reasoning) | — |
| [#1156](https://github.com/backspring-labs/squad-ops/pull/1156) | docs(plan): 1.7.0 rev 3 — name the 1.7.0 line (Reasoning), renumber 1.7.0–1.7.4, split the cut criteria | — |
| [#1155](https://github.com/backspring-labs/squad-ops/pull/1155) | docs(release): capture the v1.6.6 release package | — |

## Improvement proposals

| Proposal | From | To |
|---|---|---|
| [SIP-0106-Atlas-Provider-Adapter](../../design/sips/SIP-0106-Atlas-Provider-Adapter.md) | new | accepted |

## Cycle evidence

### `cyc_2a88dabad94b`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:declared_imports, acceptance:frontend_compiles, acceptance:regex_match, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-join, vc-probe-api-runs-join-duplicate, vc-probe-api-runs-leave, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |
