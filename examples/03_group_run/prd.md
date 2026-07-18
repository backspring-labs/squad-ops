# PRD: group_run (1-Hour Cycle MVP+)
**Version:** v0.4 (SIP-0098 §6.7 split — product-only content; technical contract externalized)
**Purpose:** Define a testable full-stack MVP for a 1-hour SquadOps cycle
**Status:** Draft for cycle planning
**Timebox Target:** 1-hour autonomous cycle (5-agent squad)

---

## 0) Technical Contract (owned elsewhere — do not restate here)

Per SIP-0098 §6.7, this PRD carries **product content only**: features, behaviors,
scope, and priorities. The technical fill contract lives in two sibling artifacts:

- **`interface_manifest.yaml`** — entities, API endpoints and request/error shapes,
  frontend routes/views, stack, persistence mode, and the pinned interface decisions
  the earlier PRD delegated to implementation.
- **`verification_contract.yaml`** (emitted by the scaffold expander) — frozen-file
  protection, per-fill-file criteria, test-suite expectations, and behavioral probes.

Change interfaces by amending the manifest and re-expanding the skeleton — never by
adding endpoint tables, data models, file lists, or test mechanics back into this
document. Sections below marked *moved* are tombstones kept so existing §-references
resolve.

---

## 1) Product Summary

**group_run** is a lightweight app for coordinating a group run with friends:
- create a run event
- browse upcoming runs
- join or leave a run
- view event details and participants

This PRD is intentionally scoped to support a **1-hour autonomous build attempt** by an agent squad.
The goal is a **coherent, runnable full-stack vertical slice** (FastAPI + React) with validation and basic tests.

---

## 2) Objective (for this cycle)

Deliver a runnable full-stack MVP (FastAPI backend + React frontend) that allows a user to:

1. Create a group run event
2. View a list of upcoming group runs
3. View run details
4. Join a run with a participant name
5. Leave a run
6. Prevent duplicate participant names on the same run

### Success Definition (Cycle-Level)
A reviewer can:
- start backend and frontend locally
- create at least one run from the UI
- view the run in the list and open the detail page
- join the run with a participant name
- leave the run
- confirm duplicate-name join is rejected
- run basic tests for core API behavior (and optional UI test if completed)
- review a clear `qa_handoff` artifact

---

## 3) Target User (MVP)

### Primary User
A casual runner organizing a small local group run (friends / club members).

### User Need
"I want a simple way to set up a run and quickly see who's in."

---

## 4) User Stories (MVP Scope)

### Core Stories (Must Have)
1. **As an organizer**, I can create a run event with basic details so others can join.
2. **As a participant**, I can view upcoming runs so I can choose one.
3. **As a participant**, I can open a run and see event details and attendees.
4. **As a participant**, I can join a run by entering my name.
5. **As a participant**, I can leave a run.
6. **As an organizer/participant**, I can see participant count and participant names.
7. **As a user**, I receive a clear error if I try to join the same run twice with the same name.

### Time-Permitting Expansion Scope
See **§4.1 Time-Permitting Expansion Scope (Pre-Approved)** for pre-approved additions that may be implemented if core scope is stable and on track.

---

## 4.1 Time-Permitting Expansion Scope (Pre-Approved)

If all core acceptance criteria are met or clearly on track within the cycle, the team may implement items from this pre-approved list **in priority order**.

### Rules for using expansion scope
- Expansion work is allowed only after core scope is stable and integration is working (API + UI happy path).
- Expansion items must not introduce new external dependencies or major architectural changes.
- Expansion items must not break or delay completion of core tests and `qa_handoff`.
- If time becomes constrained, expansion work should be cut immediately without affecting core scope.

---

### Expansion Tier 1 (Preferred if time permits)
These add meaningful UX and product completeness with low implementation risk.

1. **Capacity Limit (Per Run)**
   - Add optional `capacity` field on run creation
   - Prevent joins when capacity is reached
   - Show capacity status in run detail (`3 / 8 joined`)

2. **Basic Datetime Sorting**
   - Sort runs in list by `datetime` string (best-effort lexical sort acceptable for MVP)
   - Document sort assumptions in `qa_handoff`

3. **Seed Sample Run Action**
   - Add a simple dev-only button or endpoint to create sample run data
   - Helps QA and demo speed

4. **Improved Error Messaging**
   - Show clear UI messages for:
     - duplicate participant name
     - run not found
     - participant not found on leave
     - validation errors

---

### Expansion Tier 2 (Only if Tier 1 is complete and stable)
These are useful but should not displace tests or handoff quality.

5. **Participant Name Normalization**
   - Trim whitespace before join/leave comparisons
   - Apply duplicate-name checks using normalized values
   - Preserve original display casing if practical

6. **Leave Button Next to Participant Names**
   - Add per-participant leave/remove action in UI (instead of only text input leave form)
   - Keep MVP unauthenticated model (no permissions logic)

7. **Run Distance / Pace Display Enhancements**
   - Improve formatting of optional fields in list/detail views
   - Hide empty optional fields cleanly

8. **Basic Frontend Test Coverage**
   - Add at least one UI test for:
     - create flow, or
     - join/duplicate-name error behavior, or
     - detail view render

---

### Expansion Tier 3 (Nice-to-Have Demo Polish Only)
Only attempt if core scope, tests, and handoff are already complete.

9. **Simple Toast/Banner Notifications**
   - Success/error banners for create/join/leave actions

10. **Empty-State Polish**
   - Improved messaging and CTA for no runs / no participants

11. **Small UX Quality Improvements**
   - Disable submit while request is in flight
   - Clear form after successful submit
   - Basic loading state text

---

## 5) Functional Requirements (MVP+)

## 5.1 Run Event Creation (Backend + UI)
User can create a run with:
- **title** (required)
- **date/time** (required; string input acceptable for MVP)
- **meeting location** (required)
- **distance** (optional string, e.g., "5K", "6 mi")
- **pace target** (optional string, e.g., "9:00-10:00/mi")
- **route notes** (optional)

### Behavior
- Successful create returns created run with generated `id`
- Created run appears in UI list immediately after creation flow completes

### Validation (MVP)
- Required fields must not be empty
- Backend validates request payload
- Frontend performs basic required-field validation before submit

---

## 5.2 Upcoming Runs List (Backend + UI)
App displays a list of runs showing at minimum:
- title
- date/time
- meeting location
- participant count

### Behavior
- Empty state shown when no runs exist
- Newly created run appears in list without manual data editing
- Basic list refresh behavior is supported (page reload okay)

---

## 5.3 Run Detail View (Backend + UI)
User can open a run and see:
- all event details
- participant list (names)
- join form
- leave action (by name)

### Behavior
- Unknown run ID shows a clear error/not-found state

---

## 5.4 Join Run (Backend + UI)
User can join a run by entering:
- participant name (required)

### Behavior
- Joined participant appears in participant list immediately
- Participant count updates
- Duplicate participant names on the same run are rejected

### Validation
- Name cannot be empty
- Name must be unique within the selected run (case sensitivity behavior should be defined in implementation; default recommendation: case-insensitive uniqueness)

---

## 5.5 Leave Run (Backend + UI)
User can leave a run using participant name (MVP simplification; no auth/user identity).

### Behavior
- Participant is removed from the selected run
- Participant count updates
- If participant name does not exist on the run, backend returns clear error (or no-op with clear response; choose one and document in QA handoff)

### Validation
- Name cannot be empty

---

## 6) API Requirements — *moved* (SIP-0098 §6.7)

Endpoints, request/response shapes, status codes, and the error-payload contract are
owned by `interface_manifest.yaml` (`api:` section, incl. `error_contract`). The
product behaviors they serve remain in §5.

---

## 7) Frontend Requirements

### Required Views / Routes — *moved* (SIP-0098 §6.7)

Routes, view names, and view purposes are owned by `interface_manifest.yaml`
(`frontend:` section). The user-facing behaviors of each view remain in §5.

### UI Constraints (for 1-hour build)
- Minimal styling only (functional > polished)
- No UI component library required
- No animations
- No auth/session state
- Prefer simple `fetch` calls over heavier client abstractions

---

## 8) Data Model — *moved* (SIP-0098 §6.7)

Entities, fields, and the persistence mode are owned by `interface_manifest.yaml`
(`entities:` and `persistence:`). Product-level persistence scope: this cycle ships
without a database — SQLite/migrations/production storage remain out of scope (see
§13 for the post-MVP path).

---

## 9) Technical Scope Guidance — *moved* (SIP-0098 §6.7)

Stack, toolchain, and test mechanics are owned by `interface_manifest.yaml` (stack,
language, api_client) and `verification_contract.yaml` (suite expectations, probes).

### Product Scope Constraints (retained — to prevent drift)
- No authentication
- No external APIs/maps
- No WebSocket/realtime features

---

## 10) Acceptance Criteria (Binary, Cycle-Ready)

### Core Product Behavior
- [ ] User can create a run from the UI with required fields
- [ ] Created run appears in runs list
- [ ] User can open run detail view
- [ ] User can join run with a participant name
- [ ] Participant list updates and displays joined name
- [ ] Participant count updates on detail and/or list view
- [ ] User can leave a run
- [ ] Participant is removed from participant list after leave
- [ ] Duplicate participant join is rejected with clear user-visible or documented error behavior

### Validation
- [ ] Empty required fields are rejected on create (frontend and backend)
- [ ] Empty participant name is rejected on join
- [ ] Empty participant name is rejected on leave

### API — *moved* (SIP-0098 §6.7)
Endpoint-level acceptance (implemented endpoints, error responses) is verified by the
verification contract's criteria and behavioral probes, not restated here.

### Runability
- [ ] Backend starts locally with documented commands
- [ ] Frontend starts locally with documented commands
- [ ] UI can communicate with backend in local dev setup

### Tests — *moved* (SIP-0098 §6.7)
Test-suite expectations (happy paths, error cases, isolation) are owned by the
verification contract's `behavioral.suite.coverage_expectations`.

### Handoff / QA Friendliness
- [ ] Build includes a clear `qa_handoff` artifact (or equivalent) with:
  - how to run backend
  - how to run frontend
  - how to test
  - expected behavior
  - implemented scope
  - known limitations

---

## 10.1 Expansion Acceptance Notes (If Implemented)
If any expansion items are completed, `qa_handoff` should include:
- which expansion items were implemented
- any behavioral assumptions (e.g., datetime sort behavior, name normalization)
- any known limitations introduced by time-permitting scope

---

## 11) Suggested Task Decomposition — *moved* (SIP-0098 §6.7)

Decomposition is framing's job (SIP-0098 §5), performed against the scaffold's fill
slots; the earlier workstream sketch restated interface content and is retired.
Scope-discipline rules it carried live on in §4.1 (expansion rules) and §14 (scope
lock).

---

## 12) Risks (1-Hour Cycle Specific)

### Primary Risks
- Over-scoping (auth/maps/polish creep)
- Backend/frontend integration mismatch
- Frontend routing/state complexity slows progress
- Time lost on persistence upgrades
- Insufficient test coverage / unclear handoff
- Unplanned expansion work displacing core scope completion

### Mitigations
- Scope lock to the interface manifest's declared views and endpoints — nothing more
- Prefer in-memory persistence for this cycle
- Keep the API contract simple and explicit (owned by the manifest)
- Use minimal styling
- Prioritize end-to-end happy path before refinements
- Use only pre-approved expansion items (§4.1) and only after core stability
- Require `qa_handoff` completion before cycle close

---

## 13) Future Enhancements (Post-MVP / Later Cycles)

- User accounts / authentication
- RSVP states (going / maybe / not going)
- Capacity limits + waitlist (if not implemented as expansion)
- Route map integration
- Pace groups / filters
- Datetime parsing + sorting improvements (if not implemented as expansion)
- Comments/chat
- Recurring runs
- Notifications / reminders
- Calendar export
- Persistent backend database + migrations
- Mobile-first / native clients

---

## 14) Scope Lock Statement (Important)

This PRD is optimized for a **1-hour autonomous cycle**.
If implementation risk increases, the team should preserve the following in order:

1. Create run
2. List runs
3. Run detail
4. Join run
5. Leave run
6. Duplicate-name prevention
7. Validation
8. Backend tests
9. `qa_handoff`
10. Optional frontend tests / polish / expansion items

If core scope is completed early, only pre-approved expansion items from **§4.1** may be added.

No out-of-scope features should be added unless all core acceptance criteria are already met.
