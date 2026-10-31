# Nebulus: the proving Project, and how its environment is provisioned

**Status: DRAFT (2026-10-31), for the owner's review.** Nothing in it is executed: no repository is created and
no infrastructure is provisioned until the owner says go. It fills in the 2.6 plan's Track F (the financial
application, D2) and records the owner's direction of the same day.

## 1. What Nebulus is

**The owner, 2026-10-31:** "a legit personal financial platform that I can test new financial tech techniques
in … a platform for personal financial / banking for a consumer to login, make payments, buy and sell
equities or crypto … use as much of the spark infra as possible: db, redis, rabbit mq, idp for iam … a
fictional bank in the digital cloud." It is the product the squad builds on every night, with the Nostromo
crew running the Campaigns. (Spelling corrected.)

**Names, the owner's choices that day:**

| name | what |
|---|---|
| **Nebulus** (product: **Nebulus Financial**) | the bank. It matches `nebulus-landscape` and its triad's `nebulus-financial` |
| **Nimbus** | the transactional account (checking) |
| **Accumulus** | savings |
| **Stratus** | a premium tier, if one is ever wanted |

The code uses them (`NimbusAccount`, `AccumulusAccount`), not generic names.

**Its design authority is `nebulus-landscape`** (`backspring-labs/nebulus-landscape`). That repository models six
domains (customer, identity and access, accounts, ledger-core, payments, risk and fraud), each with
capabilities, journeys and processes under stable ids. Its README names this product as the reference
application of the triad (`nebulus-landscape`, `nebulus-financial`, `guiderail`). Each backlog item names the
landscape journey it realizes, so guiderail can link the two by id.

**Synthetic only** (the 2.6 plan's D10): a fictional bank. No real money, account, identity or credential is
in the repository, a prompt, a fixture or a record.

## 2. What it builds first: the ledger, through one thin slice

Every later feature is a posting to a ledger: payments, P2P, and later equities and crypto. So the first
Campaign builds a thin path through the six modelled domains that ends in money moving correctly. That means
double-entry, balances derived from entries, idempotent posting, and a full audit trail.

| # | backlog item | landscape journey |
|---|---|---|
| 1 | a customer signs in through the IdP, and the API knows who they are | `journey.authenticate_customer_login` |
| 2 | minimal onboarding: profile and consent, with a synthetic identity check | `journey.customer_onboarding` |
| 3 | open a **Nimbus** account | `journey.open_checking_account` |
| 4 | **the ledger:** a deposit posts balanced double entries, and the balance is derived from them | `journey.post_deposit_transaction` |
| 5 | open an **Accumulus** account, and move money Nimbus → Accumulus as one atomic posting | `journey.open_savings_account`, `journey.transfer_between_own_accounts` |
| 6 | pay another Nebulus customer, with a simple risk limit that can decline it | `journey.send_instant_payment`, `journey.approve_or_decline_high_risk_transfer` |

**After the first slice,** in roughly this order: statements and history, an ACH stub, sanctions screening,
interest accrual, reconciliation breaks.

**Equities and crypto come last.** The landscape doesn't model investments or digital assets yet, so the
research adds those domains before the squad builds them.

**The goals live in a goal set** (Project Goals and Backlog, PR #2833) once its slices land. Until then they
live in a goals file in the product's own repository, as the 2.6 spike's Shelfnote goals do.

## 3. How it is built

- **Created from scratch by SquadOps** (`projects initialize`, from the `fullstack_fastapi_react` blueprint), as
  `z_shelfnote` was, into its own repository, **`nebulus-financial`**.
- **Ports and adapters,** as SquadOps itself is. The in-cycle tests and the sandbox can't reach the Spark's live
  services without network and secret wiring (#2421's unbuilt secrets half). So each external service sits
  behind a port. The squad's tests run against in-process fakes (an in-memory or SQLite store, a fake bus, a
  fake token issuer). The real Postgres, Redis, RabbitMQ and Keycloak adapters run in a dev deployment,
  checked by their own integration tests.
- **Backend first.** UI items wait for #2799 (a vitest page criterion for a page the change adds).
- **Nightly, crew-run Campaigns** after the first attended one holds. Plan gates go to the tier (#2796), and
  increments to the crew's rulings.

## 4. Its environment: declared by the product, applied by the platform, recorded each time (#2847)

**No infrastructure is created by hand.** The owner, the same day: "should the infra provisioning … be more
managed / scripted instead of just one-off activities … I don't want to lose record of important tasks that
might need better enterprise discipline."

| concern | lives in | owned by |
|---|---|---|
| **what the product needs:** its Postgres database, Keycloak realm (clients, roles, synthetic test users), RabbitMQ vhost and queues, Redis key space | `infra/environment.yaml` in the product's repository, with the realm export beside it | changed by PR, ruled by the owner or the crew. The Campaign's `allowed_scope` excludes `infra/**`, so the squad never changes its own infrastructure |
| **applying it:** create what is missing, report what drifted | `provision_project_env.py <project> --check / --apply`, one idempotent SquadOps script. It never deletes without an explicit flag | the platform (the supervisor first, the crew later) |
| **secrets** | generated at apply, held on the host (`~/.config/<project>/secrets.env`, mode 600), referenced as `secret://…`, never written to a repository | the host. Delivering them to the running app is #2421's secrets half |
| **the record** | one per apply: the spec's commit, what changed, who applied it, and the checks | kept beside the deploy records |
| **nightly safety** | `--check` before each nightly Campaign; drift is a blocking gap, so a Campaign never starts on a broken environment | the crew's launch preflight |

**Isolation, in every service:** its own Postgres role and database, with no rights on SquadOps's; its own
Keycloak realm; its own RabbitMQ vhost and user; and a Redis ACL user limited to `nebulus:*`. Each one is
tested by trying to reach SquadOps's data with it.

**Three checks before the first apply is called done:**
1. **Keycloak persistence.** SquadOps's realm is imported from JSON at startup. If Keycloak's store doesn't
   persist, a realm created through the API is lost on restart. In that case the realm is loaded from its
   export the same way, which may need a compose mount. That is the owner's call.
2. **Backup coverage.** Whether the nightly verified backup covers every database or only SquadOps's. A new
   database isn't covered until it is.
3. **Isolation,** as above, tested rather than assumed.

## 5. The order, when the owner says go

1. **#2847:** the spec format and `provision_project_env.py`, with Nebulus as the first user.
2. **Create `nebulus-financial`** from the blueprint, with its first `infra/environment.yaml` and realm export.
3. **Apply,** then the three checks, then the first record.
4. **The product's goals file:** the six items of §2, with their landscape ids.
5. **The first attended Campaign.** Nightly crew-run Campaigns after it holds.

## 6. Decisions for the owner

| # | decision | recommendation |
|---|---|---|
| N1 | the first slice (§2) | **the six items as listed:** the ledger as the foundation, equities and crypto after their research |
| N2 | the repository | **`nebulus-financial`**, a new repository, as the landscape's triad names it. `nebulus` stays as it is |
| N3 | provisioning (§4, #2847) | **declared, scripted, recorded:** nothing created by hand |
| N4 | who applies it | **the supervisor first, then the crew,** with the owner ruling changes to `infra/**` |

## 7. Not decided here

- The product's architecture beyond ports and adapters. The squad proposes it, inside the blueprint.
- Equities and crypto: their landscape research comes first.
- A compose change for Keycloak, if check 1 needs one. That would be the owner's.
