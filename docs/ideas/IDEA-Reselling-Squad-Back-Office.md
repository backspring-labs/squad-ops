# IDEA: The Reselling Squad — Agents Operating a Backspring Back Office

## Target Release
Vision item for the 2.0 era. Nothing here lands in squad-ops before the 2.0 line opens:
1.8.x takes patches only and 1.9 is feature-free. Two of the starting steps (§9) need no
squad-ops code at all and can begin now.

### Status
Idea draft — distilled from a design conversation, no SIP yet.

### Owner
Architecture / Vision

### Origin
Distilled 2026-09-25 from a conversation that began at "can a SquadOps agent sit in a Buzz
channel", moved to "how would a campaign run an n8n workflow", and arrived at the goal
behind both: pointing a squad at online reselling — defining products, listing them,
managing inventory, tracking deliveries. This is the "duty work" domain named in the
Backspring vision, made concrete enough to design against.

Companion documents:
- `IDEA-Governed-Outputs-Beyond-Apps.md` — n8n flows as a governed output the squad
  produces and duty agents operate. This doc is its near-term, hand-built precursor.
- `sips/proposed/SIP-Capability-Backed-Agents.md` — the 2.0 capability-pack umbrella; the
  seam a reselling pack needs (§7.1).
- `sips/proposed/SIP-Campaign-Orchestration.md` — the 2.0 headline; campaigns over cycles.
- SIP-0089 (runtime modes and duty windows), SIP-0090 (embodiment and its action-authority
  boundary), SIP-0091 (duty durability via Temporal — re-decided by §8).

---

## 1. The claim

The squad runs the reselling back office. The work splits into three layers, and the split
settles most of the design:

| Layer | What it is | Where it lives |
|---|---|---|
| **Record** | products, inventory, listings, orders, shipments | a Backspring service with its own database |
| **Squad** | agents that do the work on the record | SquadOps, as a reselling capability pack |
| **Plumbing** | marketplace and carrier connections, event flows | marketplace adapters and n8n |

The record lives outside squad-ops for two reasons:

1. **It has to outlive every agent, model and tool.** This is the insulation-from-proprietary-
   products principle applied to the business itself. Marketplaces, models and automation
   tools will all change; the record of what Backspring owns and sold stays.
2. **squad-ops stays a general framework.** Reselling is one pack alongside software
   development, entering through the same seam any other domain would use.

## 2. The record

A small model, shaped by the fact that most resale items are one of a kind:

| Entity | Holds |
|---|---|
| **Product** | what the item is — category, brand, attributes, condition, photos |
| **Unit** | the physical item — cost basis, storage location, status (in stock → listed → sold → shipped), age |
| **Listing** | one unit offered on one marketplace — price, the marketplace's listing ID, status |
| **Order** | buyer, sale price, marketplace fees, the unit sold |
| **Shipment** | carrier, tracking number, label, delivery status and events |

Each product usually has exactly one unit. The record is the source of truth for what is
listed where; marketplaces are reconciled against it, and a disagreement between the two is
a finding to act on.

## 3. Who does what

Agents decide; tools act. This is the SIP-0090 §6 authority boundary applied to commerce:
an adapter executes an already-authorized action, and SquadOps decides whether the action
happens.

| Capability | Agent (judgement) | Tools and n8n (mechanics) | Runs as |
|---|---|---|---|
| **Define products** | identify the item from photos, fill in attributes, research recent sale prices | store photos, assign SKUs | a cycle per intake batch |
| **List** | write the title and description per marketplace, set the price, choose marketplaces | post, revise and end listings; take listings down after a sale | a cycle; the take-down in n8n |
| **Manage inventory** | markdowns, bundles, what to source more of | aging reports, counts, reconciliation against marketplaces | a scheduled cycle; a campaign for goals like "clear Q4 stock" |
| **Track deliveries** | handle late, lost and returned items; message the buyer | buy labels, pull tracking updates, change statuses | n8n, with a duty agent for exceptions |
| **Answer buyers** | respond to offers within floor-price rules; draft replies to messages | receive offers and messages, send responses | n8n calling a duty agent |

Anything that moves money goes through a gate (SIP-0064 `Gate`): a price below the item's
floor, a refund, the first listing on a new marketplace.

## 4. Three execution shapes

| Shape | Engine | Reselling example |
|---|---|---|
| **Bounded batch** | a cycle, run by Prefect | "list these twenty items" |
| **Objective across batches** | a campaign over cycles | "clear Q4 stock by 31 December" |
| **Always-on events** | an n8n flow, calling duty agents for judgement | an item sells; an offer arrives; a package is late |

Prefect runs the squad's work: recruitment, dispatch, retries, gates, the correction loop,
evidence. n8n runs integrations: connectors, credentials, deterministic plumbing. Each
engine stays in its own lane.

### 4.1 Cycle calls a flow

Inside a campaign, the cycle is in charge and an n8n flow is a tool. One flow run is **one
cycle task**, and the sequence "agent work, then a flow, then more agent work" lives inside
a single cycle:

```
Campaign   objective: e.g. "list this week's inventory"
 └─ Cycle N  (one Prefect run)
      prep tasks        agents do the judgement: pick items, write copy, set prices
      workflow.run      one task: trigger the flow, wait, collect the execution record
      follow-up tasks   agents check the outputs, analyse, report
 └─ continuation decision → next batch · repair cycle · stop · escalate
```

One cycle, because a cycle is one bounded effort with one acceptance boundary: the Prefect
task graph already orders the steps, and the correction loop repairs within the run. The
campaign decides between cycles. Splitting each segment into its own cycle would turn the
continuation policy into a step sequencer, which the Campaign SIP keeps it from being.

Two shapes to avoid:
- **Each n8n node as a cycle task** rebuilds n8n inside Prefect and throws away its
  connectors (the Embodiment Runtime SIP's invariant 8).
- **n8n calling agents directly, outside SquadOps**, makes the flow the orchestrator:
  agents get work with no lease, budget or record. §4.2 is the governed version.

Flows that finish in minutes suit this shape. A flow that runs for hours, or waits on a
human approval inside n8n, would hold a run and an agent's lease open the whole time; that
case needs its own design.

### 4.2 Flow calls a duty agent

In always-on operations the flow is in charge and calls on an agent who is on shift
(SIP-0089 duty mode):

1. The flow reaches a judgement step and pauses at n8n's Wait node, which provides a URL to
   resume on.
2. It sends SquadOps the request along with that resume URL.
3. An agent on duty does the work as a duty activity — identity, lease, budget, record and
   checks all applying.
4. SquadOps posts the result to the resume URL, and the flow carries on.

**The rule in both directions:** whichever side starts it, agent work runs under SquadOps.

Small stateless transforms — pulling the fields out of a sale email — can call a model
straight from n8n. That is a model call, and it needs no agent. The test: if a step needs
the agent's role, memory or rules, or should be recorded and checked, it goes to a
SquadOps agent.

A usable shortcut exists today: a flow can call an agent's chat endpoint
(`POST /api/v1/chat/{agent_id}`; Joi answered on it on the 1.8.1 local deploy, 2026-09-24).
A chat call skips the lease, the budget and the checks, so it suits drafts a human reviews
and nothing more.

## 5. What n8n is for here

The clearest single flow: **an item sells** → mark it sold in the record → take down its
other listings → buy the shipping label → notify. It has to run at any hour, quickly, the
same way every time, and it needs no agent. It is also the protection against the costliest
cross-listing failure: selling one item twice.

n8n brings Gmail, Sheets, Discord and HTTP nodes, schedules, retries and credential
storage. It reaches eBay through its generic HTTP Request node; it has no dedicated eBay
node. The flow can be hand-built and run today, entirely outside squad-ops.

The larger payoff — the squad authoring and maintaining flows itself — is the
governed-outputs idea, and it is far easier once hand-built flows have shown what real
Backspring flows look like.

## 6. Constraints that decide whether this works

External facts as of 2026-09-25; each needs re-checking before anything is built on it.

1. **Marketplace reach.** eBay has a full seller API. Poshmark and Mercari publish no
   official seller API; tools that cross-list to them drive the browser or use unofficial
   routes. Taking down a listing on those platforms after a sale needs browser automation
   or a cross-listing service, with or without n8n. Each platform's terms need reading:
   automated activity is where accounts get restricted.
2. **Sold-price data.** eBay's sold-items API (Marketplace Insights) is closed to new
   developers, and sold listings on the site now require a login. Recent sale prices feed
   the squad's most valuable decision — the price — and are the hardest input to obtain
   legitimately.
3. **An image-capable model.** Identifying an item from photos needs one. The models on the
   dev Mac (llama3.1:8b, qwen2.5:7b and 3b) read text only.

## 7. What SquadOps is missing

1. **A place for domain task types.** Every task type (39 today) is defined in the
   framework core, `squadops.tasks.task_types.TaskType`. Adding `listing.draft` there would
   build reselling into the framework. The Capability-Backed Agents SIP is the seam: packs
   publish capabilities, and skills operate tools through ports with permissions,
   approvals, budgets and evidence. Everything below depends on it.
2. **Tools that reach the record** — a port and adapter for the Backspring service's API.
3. **Duty work intake.** Duty mode today opens and closes windows on a schedule, and
   `duty_handler` exists as a runtime-activity kind; nothing hands a duty agent a request or
   returns its answer. Needed: an authenticated `/api/v1` route that receives requests, a
   duty handler that runs them, and the callback to the flow's resume URL.
4. **An n8n adapter** behind a new port in `ports/tools/` (beside `vcs`, `container`,
   `filesystem`), for §4.1. It carries:
   - an idempotency key built from the run and task IDs, so a Prefect retry cannot post the
     same listing twice;
   - the version of the flow that ran, recorded on the execution (drift detection starts
     here);
   - credentials that stay in n8n, with SquadOps holding only the n8n API key as a
     `secret://` reference.
5. **Checks against reality.** n8n reporting "execution succeeded" is the flow vouching for
   itself, the same class of self-report SIP-0096 refuses to credit from agents. A listing
   counts as live when it is read back from the marketplace at the decided price.
   Sell-through, days-to-sell and margin are the natural business measures for the 1.8
   scorecard (SIP-0108) to grade on.
6. **An image-capable model** in the reselling squad's profile (§6.3).

## 8. Roadmap fit and the decisions it forces

- **1.9** is feature-free; nothing here lands.
- **2.0** is Campaign's release, with Capability-Backed Agents sequenced behind it by the
  2.0 plan. The reselling pack enters through that seam.
- **Capability-Backed Agents has one worked example today** — design, with Iris and Glyph.
  Reselling as a second reference pack, drawn from the actual business, tests whether the
  pack model holds outside design before it is frozen.
- **SIP-0091 needs re-deciding.** It is accepted, has no code, and plans Temporal for duty
  durability. With n8n arriving as the integration runtime, that makes three workflow
  engines — Prefect, Temporal, n8n. n8n's scheduled triggers and wait steps may cover part
  of what Temporal was brought in for.
- **SIP-0090 §6** governs every commerce action: adapters execute, SquadOps authorizes.

## 9. Where to start

1. **Now, outside squad-ops — the record.** Design it (§2) and stand up the service. A
   first version is a database-backed web app, the shape the build squad has delivered
   since 1.4 — which would make it the first thing the squad builds that Backspring uses.
2. **Now, outside squad-ops — the first flow.** Run n8n and hand-build the eBay "item sold"
   flow against the record. This is also the "one real Backspring flow" probe from
   `IDEA-Governed-Outputs-Beyond-Apps.md` §8.
3. **Once the pack seam exists — the first reselling cycle, eBay only.** Photos →
   identification → recent sale prices → price → draft listing → a gate for approval → a
   tool posts it. eBay first because it is the one large marketplace with a full seller API.
4. **At the 2.0 design review** — reselling as a reference pack in the Capability-Backed
   Agents SIP (§8).

## 10. Open questions

- Which marketplaces beyond eBay, and by what route: browser automation (SIP-0090 Phase 4
  is read-only by design) or a cross-listing service?
- Where recent sale prices come from, given §6.2.
- Where n8n runs (the Spark, the Jetson, the Mac) and who holds its credentials.
- Which image-capable model, and whether the reselling profile runs on the Mac or only on
  the Spark.
- Whether the build squad produces the record service, or it is written by hand.
- Where approvals and notifications land. A Buzz channel is the natural place once a
  SquadOps agent is present there (the bridge discussed 2026-09-24: `buzz-acp` plus a thin
  ACP shim over the chat endpoint).

## Sources

- [Poshmark vs Mercari — Crosslist](https://crosslist.com/blog/poshmark-vs-mercari)
- [Poshmark API — an independent tool, not affiliated with Poshmark](https://poshmarkapi.com/)
- [n8n eBay seller-account template, built on the HTTP Request node](https://n8n.io/workflows/5571-ebay-seller-account-management-with-ai-agent-integration-36-operations/)
- [n8n community — syncing with eBay](https://community.n8n.io/t/can-i-sync-with-ebay-using-n8n-io/20201)
- [eBay developer forum — Marketplace Insights API access](https://community.ebay.com/forum/talk-to-your-fellow-developers-57970/topic/marketplace-insights-api-access-168586/)
- [eBay sold listings now require a login — Scavio](https://scavio.dev/blog/ebay-sold-listings-api-login-wall-2026)
