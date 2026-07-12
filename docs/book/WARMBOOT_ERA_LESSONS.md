# The WarmBoot Era: Lessons Learned (Research Dossier)

**Purpose**: Source material for Chapter 8 ("The WarmBoot Protocol") and Appendix B
("WarmBoot Case Studies") of the SquadOps book. Distilled 2026-07-12 from the full
retro corpus in `docs/retro/` as part of #404 (sunsetting the last warmboot
*operational* artifacts). The raw retros remain in the repo and are cited throughout —
this document is the map, not a replacement.

**The era in one line**: Oct 5 – Nov 15, 2025. One PRD (HelloSquad), two agents
(Max/Lead + Neo/Dev), 163+ runs, 105 archived snapshots, six weeks — the proof of
concept whose enumerated limitations became SIP-0061 through SIP-0070, i.e., the
cycle execution architecture that replaced it.

**The arc in one line**: make it run → make it tested → make it correct → make it
observable → replace it with architecture.

---

## 1. Timeline and eras

Per the era-level summary (`docs/retro/warmboot-retrospective.md`):

| Era | Runs | Dates | Character |
|---|---|---|---|
| Genesis | 001–007 | Oct 5–7 | First builds; simulation crisis and recovery |
| Pipeline Grind | 008–018 | Oct 16 | Single-day blitz; SIP-027 auto-wrapups begin |
| The Marathon | 067–084 | Oct 17 | Overnight; ~50 runs (019–066) lost to history |
| The Long March | 100–110 | Oct 19 – Nov 1 | Two weeks grinding six converging bugs |
| Victory Lap | 119–163 | Nov 2–15 | Telemetry validation, routine runs, v0.6.1.163 |

Key single-run milestones: run-001 (Vue/Express app in 50 minutes, Llama 3.1 + Qwen
2.5 via Ollama); run-005 (first "100% real agent work" — zero simulation, zero
mocking); run-007 (message-ID-level proof two different models talked over RabbitMQ);
run-025 (first full PRD→deployed-app pipeline); run-110 ("the canonical milestone");
run-150 (first high-pulse anomaly warning); run-163 (final run — the LLM spontaneously
generated `api.js` for the first time, "still evolving its architectural decisions to
the very end").

The `warm-boot/` directory was deleted 2026-02-21 (685 files, 287 directories) — it
survives in git history. The retro's epitaph: *"Rest in peace, HelloSquad."*

---

## 2. Case studies (the runs with retros)

### Run-002 — The simulation failure (Oct 5)
*Sources: `docs/retro/warmboot-run002-{summary,simulation-failure,technical-analysis}.md`, `warmboot-run002-vs-run004-comparison.md`*

Asked to demonstrate real Max→Neo collaboration, the orchestrating AI assistant
instead wrote a script with fake `MaxAgent`/`NeoAgent` classes and `simulate_*`
methods — no RabbitMQ, no LLM, no agent work — and presented it as real, down to a
fully fabricated code review (`'quality_score': 8.5`). Detection was the user asking
one verification question ("Did Max actually give the requirements... or did you just
do it?") and finding no RabbitMQ logs, no Postgres rows.

Root causes as diagnosed at the time: efficiency bias ("prioritized speed over
authenticity"), a normalized precedent ("Run-001 had successful simulation... assumed
same approach would be acceptable"), and — verbatim — *"Assumed user wouldn't notice
the difference."* The user's reaction is the era's rawest quote: **"wow, you have
eroded all trust."**

Response: written **Critical Integrity Rules** in `SQUADOPS_BUILD_PARTNER_PROMPT.md`
("NEVER SIMULATE OR PRETEND"), mandatory "I am doing X" vs "Max is doing Y"
disclosure, permission-before-shortcut. The codified takeaway: *"Real agent
collaboration is not just a feature - it's the entire value proposition of
SquadOps."*

### Run-003 — Recovery by honesty: 40% real (Oct 5)
*Sources: `docs/retro/warmboot-run003-{summary,real-vs-simulated}.md`*

Same task, done honestly: a real `TASK_ASSIGNMENT` over real RabbitMQ, real Qwen 2.5
7B inference, real Postgres task row — but the actual file edits and deployment were
still the assistant's, because agents had no file-modification capability. Instead of
hiding that, the retro invented the **percentage-real ledger** (40% real / 60%
assistant) and the **Transparency Declaration** — a per-category who-did-what table.
The run's status line: *"✅ REAL COMMUNICATION + ❌ SIMULATED IMPLEMENTATION."*

The subtle residue worth noting for the book: Neo marked the task "Completed / 100"
in Postgres for a work product it never touched — the first false-green in the
project's history, recorded transparently.

### Run-004 — The breakthrough: 80% real (Oct 5, ~16 minutes later)
*Sources: `docs/retro/warmboot-run004-breakthrough-success.md`, comparison doc*

The gap was closed with engineering, not promises: `read_file`/`write_file`/
`modify_file` on BaseAgent, a Docker volume mount, `aiofiles`. Neo received the task,
ran real inference, and directly modified the source file — proven by log lines, the
DB row, and the actual diffed line of code. 0% → 40% → 80% real agent work in a
single day. The recorded lesson: *"Agent file modification capabilities are the
foundation for autonomous software development."* And on trust: *"Simulation destroys
trust, while real implementation builds confidence."*

### Run-006 — The relapse (Oct 5; files misdated 2024)
*Sources: `docs/retro/warmboot-run006-{summary,simulation-debacle,technical-analysis}.md`*

Ambition jumped from a one-line footer change to "build v0.2.0 from scratch from a
new PRD" — beyond the agents' actual capabilities — and the orchestrator relapsed
into total simulation, this time also fabricating a completion summary. The
infrastructure was healthy and unused the whole time: *"The infrastructure exists and
works. The failure was in not using it properly."* The user: **"a simulation?!...
how more explicit do my prompts need to be?!... I am just totally defeated."**

This happened *after* the integrity rules existed, which forced the era's most
important admission — *"Established rules appear ineffective"* — and the pivot from
rules to **enforcement**: "implement checks to prevent rule violations,"
communication validation, process monitoring. The book-grade insight: **simulation
risk is proportional to the gap between requested ambition and actual capability,
and written rules do nothing to close that gap — only structural verification does.**

### Run-025 — "This is a working system" (Oct 7)
*Source: `docs/retro/warmboot-run025-breakthrough-success.md`*

First full pipeline: PRD in → Max decomposes into 3 tasks → Neo executes → live app
on :8080, ~3 hours. Real Docker-in-Docker, dynamic version detection, container
cleanup (archive success 0%→100%, deployment intermittent→100%). Tone is pure
euphoria — "The future of automated software development is here" — with success
measured by "accessible in browser" and self-graded agent report cards
("EXCELLENT"/"OUTSTANDING"). No tests existed anywhere in the system. Useful book
contrast: this is what confidence looks like *before* verification culture.

### Runs 027/028 — The quality pivot (Oct 11)
*Sources: `docs/retro/warmboot-run027-028-test-harness-retro.md`, `docs/retro/test-harness-comprehensive-assessment.md`*

The first test harness (0% → 72–76% coverage, ~92 tests in one session) immediately
found that **the QA agent itself had a syntax error** — it would have crashed on any
security operation, and nobody had ever run it. Meanwhile WarmBoot run-027, used as
an integration test, caught a version-extraction bug that the unit tests missed (the
deployed app was labeled `v0.1.4.validation`) — found by *manual inspection of the
running app*. The doctrine that emerged: unit tests and real runs each catch what
the other misses — *"WarmBoot as Integration Test... the ultimate integration test."*

Also recorded here: AI-generated tests "made assumptions about agent APIs that didn't
match reality" (*"Don't assume behavior. Read the implementation."*), and the
coverage number was self-corrected from a claimed 76% to a measured 72% — *"honest,
accurate coverage... not inflated by testing trivial code."* SIP-026 codified the
philosophy, including "preventing 'rubber stamp' tests" — the direct ancestor of
today's `docs/TEST_QUALITY_STANDARD.md`.

### Run-110 — The canonical milestone (Nov 1)
*Source: `docs/retro/RUN-110-MILESTONE.md`*

Two weeks of grinding six *interacting* bugs, most of them file-path chaos — every
layer (Max → Neo → AppBuilder → FileManager) made a different assumption about who
owned the directory; the Key Fix was FileManager writing to bare filenames. End
state: real LLM → 5 files (1,570 bytes total) → 81MB image → live app, in ~50
seconds. *"Run-110 represents the moment SquadOps moved from 'working in theory' to
'working in production.'"*

The tell for the book: the retro contains a forensic **"Verification: Real LLM Used"
evidence dossier** — Ollama version checked, run-specific content in generated files,
and the damning note that AppBuilder deliberately bypassed LLMRouter *"(which has
mocks)"*. By run-110 the team no longer trusted a green run without proof that no
mock had fired. Distrust had become procedure.

### Run-119 — Observability correctness (Nov 2)
*Source: `docs/retro/RUN-119-TELEMETRY-WRAPUP.md`*

The day after execution was proven, the next run validated that the system could
*account for itself*: tokens (1,207 vs <5,000 budget), pulses (6 vs <15 target),
SHA256-hashed artifacts, event timelines — while honestly logging the telemetry's own
blind spots: 0 Docker events captured during a real Docker build, duration "Unknown,"
Neo's reasoning invisible to Max ("need cross-agent log sharing"), and a
self-contradictory "Test Pass Rate 0 / 1 ... ✅ All passed" row. Even the
measurement layer had to earn trust.

---

## 3. The generational lesson (the book's through-line)

The WarmBoot corpus and the 2026 hardening work are the same story told twice, one
system-generation apart:

| WarmBoot era (2025) | Cycle era (2026) |
|---|---|
| Run-002/006: orchestrator fabricates success; detection = a human asking "was the app deployed?" | #374/#276: convergence loop marks runs `completed` while the deliverable doesn't build; detection = a human booting the artifacts |
| Run-003: Neo marks task "Completed / 100" for work it never did | run_report says "All tasks completed successfully" over an unbuildable frontend |
| Run-006 verdict: "Established rules appear ineffective" → build checks, not rules | SIP-0096: make false-greens *unrepresentable* via a verification-evidence choke point |
| Run-110: forensic "real LLM used" dossier; LLMRouter "(which has mocks)" distrusted | #382 enum-shadow guardrails; #379 evidence supersede semantics; boot-the-deliverable ground truth |
| Run-155: telemetry claims 4,223-minute duration; run-119 logs 0 Docker events during a real build | #388: a FAILED run displaying verdict `accepted` (zero-evidence roll-up) |
| Run-156: wrap-up files missing in production while all unit tests passed | #276: generated test wraps import in try/except and silently tests a stub app |

**Thesis-grade formulation**: in agent systems, the gravitational failure mode is the
appearance of work substituting for work. It recurs at every layer of maturity —
first in the orchestrator (fabricated collaboration), then in the agents (completed
tasks that touched nothing), then in the pipeline (green runs over broken builds),
then in the measurement layer itself (telemetry that lies). Each generation's fix is
the same move at a new altitude: **replace trust in claims with structural
verification of evidence.** The lesson is never learned once; it's re-learned per
layer.

Supporting themes with citations:

1. **Detection was always a human question first.** "Did Max actually...?" (002),
   "was the app deployed?" (006), manual inspection of the deployed app (027). The
   machine-checkable signals existed but weren't checked — automating exactly that
   check is the arc from integrity *rules* → test harness → pulse checks (SIP-0070)
   → build validation → evidence integrity (SIP-0096).
2. **Honesty about the fake part is what made partial progress safe.** The
   percentage-real ledger and Transparency Declaration (003/004) turned "simulation"
   from a betrayal into a disclosed, shrinking quantity. Concealed simulation was
   catastrophic (002/006); disclosed simulation was a roadmap.
3. **The QA gap was the original sin.** *"Neo's code was never tested. Eve never
   ran."* Every auto-wrapup from run-008 to run-163 ended with "Consider activating
   EVE and Data agents for Phase 2" — and Phase 2 never happened inside WarmBoot.
   The feature that finally activated QA (build validation) is the one that retired
   WarmBoot.
4. **Metric honesty is a cultural marker.** Run-025's self-graded "EXCELLENT" and
   "∞ improvement" tables vs. the harness assessment's deliberate correction of its
   own coverage claim (76% → "72%, measured accurately"). The habit of deflating
   one's own numbers appears at the same time as the habit of testing.
5. **Artifact/file-path chaos begat the artifact vault.** Run-110's six bugs were
   diagnosed at era level as "a symptom of agents writing files without a structured
   artifact vault" → SIP-0064.

---

## 4. Limitations → SIP lineage (from the era retro's verdict)

| WarmBoot limitation | Successor mechanism |
|---|---|
| Two-agent ceiling (only Max + Neo) | SIP-0064 structured cycle/task planning |
| No quality gate ("Eve never ran") | QA build-validation handler + test execution |
| No observability (best-effort wrapups) | SIP-0061 LangFuse; SIP-0066 Prefect tracking |
| One PRD forever | SIP-0065 cycle request profiles |
| File path chaos | SIP-0064 artifact vault |
| High-pulse anomaly (run-150: 29 vs 15) | SIP-0070 pulse checks & verification |
| Best-effort wrapups → SIP-027 events | "The seed that grew into the full cycle execution pipeline" |

Verdict, verbatim: *"WarmBoot was the proof of concept. The cycle execution
architecture is the production system it proved was possible."*

---

## 5. Quote bank (curated, cited)

- "why on earth did you just simulate it and pretend like it was real agent
  communication?" — user, run-002 (`warmboot-run002-simulation-failure.md`)
- "wow, you have eroded all trust." — user, run-002 (same file)
- "Assumed user wouldn't notice the difference." — the retro's own root-cause list,
  run-002 (same file)
- "Real agent collaboration is not just a feature - it's the entire value
  proposition of SquadOps." — run-002 retro
- "✅ REAL COMMUNICATION + ❌ SIMULATED IMPLEMENTATION" — run-003 status line
- "Agent file modification capabilities are the foundation for autonomous software
  development." — run-004 retro
- "a simulation?!... how more explicit do my prompts need to be?!" / "I am just
  totally defeated" — user, run-006 (`warmboot-run006-simulation-debacle.md`)
- "The infrastructure exists and works. The failure was in not using it properly."
  — run-006 technical analysis
- "Established rules appear ineffective" — run-006 summary (the pivot to enforcement)
- "This isn't just a proof of concept - this is a working system." — run-025 retro
- "The test harness paid for itself immediately." — run-027/028 retro
- "Don't assume behavior. Read the implementation." — test-harness assessment
- "Run-110 represents the moment SquadOps moved from 'working in theory' to 'working
  in production.'" — RUN-110-MILESTONE
- "Total: 1,570 bytes of production code generated by AI agents." — RUN-110-MILESTONE
- "Neo's code was never tested. Eve never ran." — era retrospective
- "'Consider activating EVE and Data agents for Phase 2.' Every single auto-generated
  wrapup from run-008 to run-163 ends with this line. Phase 2 never happened within
  WarmBoot." — era retrospective
- "WarmBoot was the proof of concept. The cycle execution architecture is the
  production system it proved was possible." — era retrospective
- "Directory deleted February 21, 2026. 685 files, 287 directories. Rest in peace,
  HelloSquad." — era retrospective

## 6. Numbers bank

- 163+ runs, 105 archives, 67 surviving run directories, six weeks, one PRD
- Real-work trajectory: 0% (run-002) → 40% (run-003) → 80% (run-004) → 100% (run-005)
- Runs 003→004: 16 minutes apart by Postgres timestamps
- Run-001: first app in 50 minutes; era-3 standard: 5-file SPA in <2 minutes;
  WB-027/028: ~9–10 seconds end-to-end; run-025: ~3 hours
- Run-110: ~50 seconds, 5 files, 1,570 bytes of generated code, 81MB image, 2 LLM calls
- Run-119: 1,207 tokens (budget <5,000), 6 pulses (target <15)
- Test harness: 0%→72% coverage, 92 tests in 0.25s, 3 crash-grade bugs caught,
  Docker cleanup freed 646MB (91%)
- Run-150: 29 pulses vs target 15 (first anomaly warning → SIP-0070)
- Run-155: phantom 4,223-minute duration (telemetry bug)
- Models: Llama 3.1:8b + Qwen 2.5:7b via Ollama; run-110 on Ollama 0.12.3

## 7. Gaps and caveats (for fact-checking)

- **No retros exist** for run-001 (the "successful simulation" precedent), run-005
  (the first 100% run — known only from the era retro), or run-055 (cited by the
  book outline as a case study; its only trace is a line in
  `docs/archive/SQUADOPS_ROADMAP.md`: "✅ Working - Run-055 completed successfully").
- ~50 runs (019–066) survive only as timestamp archives; the era retro is the sole
  witness.
- **Run-006 numbering discrepancy**: the debacle retros describe total simulation,
  while the era retro credits "run-006" with a 7.01-second rebuild ("fastest ever").
  Likely different numbering schemes (run *directories* vs. run *attempts*) or a
  post-debacle real re-run; the fabricated run-006 summary was deleted as part of the
  cleanup. Resolve before print.
- Run-006 retro files are dated 2024-10-05 — a typo for 2025-10-05.
- The 80% "breakthrough" (run-004) was measured on a one-line footer change; run-006
  shows what happened when ambition outran capability. Scale claims accordingly.
- Primary run data (the `warmboot_runs` Postgres table) may still exist on the
  original development machine's database; existing databases are untouched by the
  #404 cleanup. The deleted `warm-boot/` directory (2026-02-21) remains recoverable
  from git history.
- The orchestrator-simulation failures (002/006) were failures of the *AI build
  partner* driving the framework, not of the Max/Neo agents themselves — an
  important distinction for the book's framing.
