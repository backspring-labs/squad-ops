# The Continuum fit check for 2.6's Track G (#2896)

Read 2026-11-04 against main at `2da8e096` and the pinned shell. **Verdict: every Track G view fits the pinned shell
as it is.** No Continuum change is needed; two plugin-side defects in the console's existing write path are named in §3.

**The pin.** Continuum `v1.0.2`, sha `43369054b7a5…` (`console/continuum.lock:3-5`), fetched by the image build from that
ref (`console/Dockerfile:6-19`; `docker-compose.yml:818-819` reads the lock through `scripts/dev/ops/rebuild_and_deploy.sh:328`).
The shell was read at that tag; `src/continuum/…` and `web/src/…` below are its paths. "Zero shell modification" is
SIP-0069 principle 5 (`sips/implemented/SIP-0069-SquadOps-Console-Control-Plane.md:135`) and the 2.6 plan's D13.

## 1. What the shell offers, and what the console relies on today

| concern | the pinned shell | what the console does with it |
|---|---|---|
| plugin contract | a directory with `plugin.toml` and `__init__.py`; `register(ctx)` calls `ctx.register_contribution(kind, dict)` (`src/continuum/app/loader.py:37-57`); kinds `nav`, `panel`, `drawer`, `command`, `diagnostic`, `theme` (`domain/manifest.py:109-117`); slots `left_nav`, `header`, `main`, `right_rail`, `footer`, `modal`, `drawer`, `toast_stack` (`domain/regions.py:18-28`), of which the shell renders `left_nav`, `main`, `right_rail` and one drawer (`web/src/lib/components/Shell.svelte:144-209, 237-242`) | eleven `squadops.*` plugins; the image builds every `squadops.*/ui` and installs each plugin's manifest, entrypoint and `dist/` (`console/Dockerfile:37-45, 74-87`). A new plugin is a directory. Guards: manifest and `register()` agree (`tests/unit/console/test_plugin_manifests_agree.py`), paged lists go through `shared/paging.js` (`test_paged_lists.py`) |
| perspectives | five built in (`domain/perspectives.py:11-18`); a nav target `panel` sets the active perspective (`Shell.svelte:99-103`, `web/src/lib/stores/registry.ts:146-148`); `main` and `right_rail` panels are filtered by it (`registry.ts:88-103`); an unknown perspective is only a manifest warning (`domain/manifest.py:210-219`) | the console appends its own at boot: `cycles`, `squad`, `memory` (`console/app/main.py:306-319, 374-382`); `tests/unit/console/test_console_main.py:264` fails a nav that opens one neither side knows |
| routing | **none.** One page (`web/src/routes/+page.svelte`); the active perspective is an in-memory store defaulting to `signal` (`registry.ts:75`); `route_prefix` is carried (`perspectives.py:31`) but nothing in `web/src` reads it; a nav target of type `route` is accepted by the manifest (`manifest.py:40`) and ignored by the shell (`Shell.svelte:96-117` handles `panel`, `command`, `drawer`). The arch spec intends deep links (`docs/CONTINUUM_V1_ARCH_SPEC.md:396-398`); v1.0.2 has none | a view per Project or per Campaign is selection state inside one composite element: the Cycles perspective's master–detail (`squadops.cycles/ui/src/CyclesPerspective.svelte:30-34, 114-148`; SIP-0074 §5.2), the Memory perspective's project filter (`squadops.memory/ui/src/MemoryPerspective.svelte:34-97`) |
| props and events | a panel is mounted bare: `<svelte:element this={component} />` with no attributes (`web/src/lib/components/ComponentLoader.svelte:113`). The shell exposes `window.continuum.onLogout` and listens to `continuum:theme-apply` only (`Shell.svelte:64, 251`) | plugins talk through window `CustomEvent`s (`squadops:select-artifact`, `squadops:view-artifact`, `squadops:select-project`: `squadops.artifacts/ui/src/ArtifactsDetail.svelte:21`, `squadops.projects/ui/src/ProjectsList.svelte:49-58`) and by embedding another bundle's element (`CyclesPerspective.svelte:205`) |
| the API call | the shell has no API client; its own fetches are `/api/registry` and `/api/commands/*` (`registry.ts:133`, `web/src/lib/services/commandService.ts:77`) | the console's `/config.js` defines `window.__SQUADOPS_CONFIG__` (`apiBaseUrl: ""`) and `window.squadops.apiFetch`: Bearer from an in-memory access token, a 401 answered by `POST /auth/refresh` (`console/app/main.py:619-699`). A relative `/api/v1/…` reaches the runtime API through the console's passthrough (`main.py:588-615`) or Caddy (`console/Caddyfile:26-28`), carrying the caller's own token (#2068, `main.py:93-107`). Plugins may call `/api/v1/*` only (`docs/architecture/api-route-lanes.md:22`); viewer, operator and admin all hold `campaigns:read` and `cycles:read` (`src/squadops/auth/models.py:83-126`) |
| refresh | **nothing.** No SSE, WebSocket or push in `web/src` (grep: none); the `EventBus` is server-side Python (`domain/events.py:42`). SIP-0069 §12.2 and SIP-0074 §4 keep polling | every live view polls with `setInterval`, cleared on `onDestroy`: 10 s (`squadops.agents/ui/src/AgentsStatus.svelte:38`), 15 s (`squadops.cycles/ui/src/CyclesList.svelte:69`), 20 s (`CyclesPerspective.svelte:107`), 30 s (`ProjectsList.svelte:42`, home, observability, system). The one stream is chat SSE relayed by the console BFF (`main.py:479-544`), a console-app pattern, not the shell's |
| writes | `POST /api/commands/execute` with `{command_id, args, dry_run, confirmed}` (`adapters/web/api.py:78-84`); lookup → policy (the user is a fixed operator with `*`, `api.py:20-32`) → schema → **a `confirm`/`danger` command with `confirmed` false answers `PENDING, requires_confirmation` and does not run** (`app/command_bus.py:293-303`) → handler called with `request.args` (`:357`) → audit (`:384-390`; `GET /api/commands/audit`, `api.py:253`). Levels `safe`, `confirm`, `danger` (`domain/contributions.py:12-17`) | the handlers are the console app's (`main.py:285-297`), each calling the runtime API as the caller (`main.py:427-438`), so authorization is the API's scope check, not the shell's. Plugins post to the route directly (`squadops.cycles/ui/src/GateDecisionCard.svelte:27-40`); the squad and chat plugins write to `/api/v1` without the bus (`squadops.squad/ui/src/ModelsTab.svelte:59, 98`; SIP-0074 §5.1 says mutations go through it) |

## 2. The views

| view | fits? | mechanism | change needed | evidence |
|---|---|---|---|---|
| **1. the goals panel** (slice 4, #2887): goal, expected results, backlog with per-Campaign status, candidates; editing writes a revision | **fits as is** | a `panel` contributed to the `discovery` perspective, which the Projects nav opens (`squadops.projects/plugin.toml:18-32`), listening to `squadops:select-project` (dispatched today with no listener, `ProjectsList.svelte:49-58`). Reads `GET /api/v1/projects/{id}/goal-set` and its revisions (`src/squadops/api/routes/cycles/goal_sets.py:64-93`); per-Campaign status from `GET /api/v1/campaigns/{id}/backlog` for each Campaign in `GET /api/v1/campaigns?project_id=` (`routes/campaigns/campaigns.py:328`, paged). The ordered list edited in place is the component's own UI, as the create modal is (`squadops.cycles/ui/src/index.js:1-4`). The write is a new console-app command handler posting `POST /api/v1/projects/{id}/goal-set/revisions` with `expected_revision` (`goal_sets.py:36-61`), `danger_level = "confirm"` | plugin-side: the panel; console-app-side: one handler in `COMMAND_HANDLERS` and one command contribution. The write needs `admin:write` (`goal_sets.py:41`; admin only, `models.py:84-106`): the shell has no role filter, so the panel hides its editor by reading `/auth/userinfo` itself; the API refuses a viewer regardless | the backlog route is on PR #2901, **open at the time of reading, not on main**; the shell's part is §1 rows 2, 4, 5, 7 |
| **2. a read-only Campaigns plugin** (`squadops.campaigns`): state, current increment, ledger, digest, open escalations, the crew's assessments | **fits as is** | a new plugin directory with a nav to a new `campaigns` perspective, one tuple in `CUSTOM_PERSPECTIVES` (the Memory plugin is the precedent: `main.py:310-319`, `squadops.memory/plugin.toml:12-26`); one master–detail element holding the selected Campaign (`CyclesPerspective.svelte:30-34`). Reads, all `campaigns:read`: `GET /api/v1/campaigns?project_id=` (`campaigns.py:328`), `/{id}` for `state`, `outcome`, `accepted` (`:342`; `src/squadops/api/campaign_schemas.py:201-213`), `/control-log` (`:351`; the current increment is read from its latest entries), `/ledger` (`:617`), `/package` for the digest (`:984`; the CLI's `digest`, `src/squadops/cli/commands/campaigns.py:207-209`), `/escalations` (`:557`), `/backlog` (PR #2901). Read-only means registering no `command` contribution: nothing then enters the bus or the palette (`app/registry.py:85-86`, `Shell.svelte:229-235`) | plugin-side and one console-app tuple. **The crew's assessments have no endpoint on main** (slice 5, #2888, unbuilt); SIP-0115 §8.1 places them under the goal-set resource, and the panel reads them when they exist | §1 rows 1–3, 5, 6 |
| **3. a list that refreshes while a Campaign runs** | **fits** | polling, the shell's only mechanism: the panel's own `setInterval`, cleared on `onDestroy`, as every live view does (§1 row 6). Cost: one request per endpoint per interval per open panel; a Campaign view reading five endpoints at 15 s is 20 requests a minute through the console passthrough (`main.py:588`), less than today's cycle stats poll, which reads every project's cycles every 20 s (`CyclesPerspective.svelte:59-108`). Only the open perspective's panels are mounted (`registry.ts:88-95`), so a closed view costs nothing | none. Push would be a runtime-api stream relayed by the console BFF as chat is (`main.py:479-544`), still no shell change, and a new API surface not in 2.6 | SIP-0069 §12.2; SIP-0074 §4, §13 |
| **4. Project setup views** (validate, configure, baseline, sync, gaps), deferrable | **fits as is** | reads and writes on the Projects routes: `POST /{id}/validate` (`routes/cycles/projects.py:107`), `/development-configurations` (`:149`), `/baselines` (`:204`), `/contributions` (`:260`), `/initializations` (`:303`), `/syncs` (`:352`, listed at `:383`). Each write is a `confirm` command with a console-app handler, as the cycle commands are (`main.py:130-206`) | plugin-side and six console-app handlers (#2834's parity debt). The endpoint behind "the gaps" was not identified in this read | the pattern is §1 row 7 |
| **5. what stays out**: `scenarios draft`/`review` and `acquire`/`release` | **fits** (nothing to build) | not registering a panel or a command keeps a surface out. The scenario-suite routes (`src/squadops/api/routes/scenarios.py:38-130`) need `scenarios:*`, which only admin and the campaign supervisor hold (`models.py:84-106, 132-142`); no plugin calls them (grep of `console/`: none). The lease routes are `GET/POST /{id}/lease`, `/lease/release` (`campaigns.py:761-809`) | docs only: SIP-0069 §9's stability rule (`:610`) requires exceptions to parity be documented, and the SIP has no amendment section yet (the file ends at Appendix B). D13 names the amendment | #2834 |

## 3. Shell changes, if any

**None required.** Every mechanism above is in the pinned shell or in this repository's plugins and console app.

Two defects in the console's existing write path were found while tracing the bus (filed as #2903 and #2904), and
the goals panel's edit would inherit them. They are plugin-side, not shell changes. Traced in source; not reproduced on a deploy (no box time), and
no unit test posts to `/api/commands/execute` (grep of `tests/`: none; `test_console_main.py:22-24` stubs `continuum`):

- **The body key.** The plugins send `{command_id, params}` (`GateDecisionCard.svelte:31`, `CycleCreateModal.svelte:38`,
  `squadops.projects/ui/src/ProjectsProfiles.svelte:46-47`); the shell's body model is `args`, with unknown keys
  ignored (`api.py:78-84`), so a handler receives `{}` (`command_bus.py:357`), `args["project_id"]` raises
  (`main.py:132, 179-182`), and the bus answers **200 with `status: "failed"`** (`command_bus.py:401-421`). The plugins
  read `resp.ok` only (`GateDecisionCard.svelte:33`), so the failure is silent and the view re-fetches an unchanged record.
- **Confirmation.** `gate_reject`, `cancel_cycle`, `cancel_run` and `set_active_profile` are `confirm`
  (`squadops.cycles/plugin.toml:40-50, 58-62`, `squadops.projects/plugin.toml:34-38`); the bus runs one only with
  `confirmed: true` (`command_bus.py:293-303`), and no plugin sends it (grep: none). The browser `confirm()` at
  `GateDecisionCard.svelte:49` is not the bus's confirmation.

**Both fixed** by the PR for #2903/#2904: the body is built in `console/continuum-plugins/shared/commands.js` alone
(`executeCommand` posts `args`, reads `status`, and on `requires_confirmation` asks and re-posts with `confirmed: true`);
`tests/unit/console/test_command_bus_bodies.py` refuses a plugin that names the route or a `params` key, the helper's
own tests run under node, and `test_cycle_command_handlers.py::TestTheBodyThePluginsPost` enters the console app's route
with the plugins' bodies. The goals panel's edit inherits the helper, not the defects. Still not reproduced on a deploy.

What would come back to the owner only if wanted, not for 2.6's views: **a URL per Project or per Campaign.** The shell has
no router (§1 row 3). A plugin can keep its selection in `location.hash` itself (the Systems plugin already reads
`location`, `squadops.system/ui/src/SystemHost.svelte:74`) with no shell change; a real route per perspective is a
Continuum release.

**Found while building view 2 (2026-11-04, #2834): an event can't reach a panel in another perspective.** This read
missed it. The shell mounts only the open perspective's panels (§1 row 2), so a `squadops:select-campaign` dispatched
from the Campaigns view reaches no listener: the goals panel lives in `discovery` and isn't mounted. A plugin also has
no call that opens a perspective. The fix is plugin-side, with no shell change.
`console/continuum-plugins/shared/selection.js` records the selection before dispatching it. The goals panel takes it
when it mounts. The Projects perspective is opened by clicking the shell's own `.nav-item` entry labelled
`Projects`. That last step reads the shell's rendered markup, which is stable at the pin, and answers false when the
entry isn't found, so the view can say so. A Continuum call to open a perspective would remove the markup read, and
would be a Continuum release.

## 4. Not verified in this read

- Live behaviour of the deployed console: this is a source read, with the shell taken from the tag's tarball.
- `GET /api/v1/campaigns/{id}/backlog`: on PR #2901 (`feat/2885-campaign-on-a-goal-set`), open when read; main `2da8e096` has no backlog route.
- The crew's assessments: no endpoint exists yet (slice 5).
- Which endpoint the "gaps" setup view reads.
- `docs/architecture/overview.md` has no console entry (its only "console" is the telemetry console adapter, `:257`);
  the console lives outside `src/` and `adapters/`, which that map covers.
