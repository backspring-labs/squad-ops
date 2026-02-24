# PRD: group_run (1-Hour Cycle MVP+)
**Version:** v0.3
**Purpose:** Define a testable full-stack MVP for a 1-hour SquadOps cycle
**Status:** Draft for cycle planning
**Timebox Target:** 1-hour autonomous cycle (5-agent squad)
**Stack Constraint (Locked):** FastAPI + React (Vite)

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

## 6) API Requirements (Locked to FastAPI)

### Required Endpoints (MVP)
- `GET /runs` — list runs
- `POST /runs` — create run
- `GET /runs/{id}` — get run details
- `POST /runs/{id}/join` — join run by participant name
- `POST /runs/{id}/leave` — leave run by participant name

### API Contract Expectations
- JSON request/response bodies
- Appropriate HTTP status codes for success and validation errors
- Clear error payloads for:
  - invalid request body
  - run not found
  - duplicate participant join
  - participant not found on leave (if treated as error)

---

## 7) Frontend Requirements (Locked to React + Vite)

### Required Views / Routes
1. **Runs List View**
   - Displays upcoming runs
   - CTA to create new run

2. **Create Run View/Form**
   - Form fields for event creation
   - Submit action
   - Basic validation messages

3. **Run Detail View**
   - Event details
   - Participant list
   - Join form
   - Leave action

### UI Constraints (for 1-hour build)
- Minimal styling only (functional > polished)
- No UI component library required
- No animations
- No auth/session state
- Prefer simple `fetch` calls over heavier client abstractions

---

## 8) Data Model (MVP)

## RunEvent
- `id` (string/uuid)
- `title` (string)
- `datetime` (string)
- `location` (string)
- `distance` (string | optional)
- `pace_target` (string | optional)
- `route_notes` (string | optional)
- `participants` (list of Participant)

## Participant
- `id` (string/uuid or generated id)
- `name` (string)

### Persistence (MVP)
**Required for this cycle:** in-memory repository/storage only.

### Persistence Non-Goal (for this cycle)
- SQLite / migrations / production database setup (unless completed as extra with no risk to core scope)

---

## 9) Technical Scope Guidance (Locked for Cycle Success)

## Backend (Required)
- Python 3.11+
- FastAPI
- Pydantic
- Uvicorn
- pytest (FastAPI test client / httpx acceptable)

## Frontend (Required)
- React (Vite)
- React Router (if multi-route implementation chosen)
- Fetch API

## Testing (Minimum)
- Backend tests for core happy path + validation/error behavior
- Frontend test optional if time allows (preferred: one basic render/flow test)

### Explicit Constraints (to prevent drift)
- No authentication
- No database migrations
- No external APIs/maps
- No WebSocket/realtime features
- No TypeScript requirement for this cycle (allowed only if templates are already mature and do not add setup risk)

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

### API
- [ ] Required endpoints are implemented and return JSON responses
- [ ] Not-found run returns clear error response
- [ ] Duplicate join returns clear error response

### Runability
- [ ] Backend starts locally with documented commands
- [ ] Frontend starts locally with documented commands
- [ ] UI can communicate with backend in local dev setup

### Tests
- [ ] Basic backend tests run successfully (happy path + at least one validation/error case)
- [ ] If frontend tests are implemented, test command and scope are documented

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

## 11) Suggested Task Decomposition (for 1-Hour Squad Cycle)

This section helps planning but does not prescribe exact implementation.

### Workstream A: Product / Planning
- confirm scope lock (must-haves vs expansion tiers)
- define API contract expectations
- define validation rules (including duplicate-name behavior)
- define acceptance checks

### Workstream B: Backend (FastAPI)
- data models / schemas
- in-memory repository
- endpoints for create/list/detail/join/leave
- backend validation + error responses
- API tests

### Workstream C: Frontend (React)
- app shell / routes/views
- runs list view
- create run form
- run detail view
- join/leave interactions
- error/empty-state handling

### Workstream D: QA / Validation
- execute run/test instructions
- verify core flows and validation behavior
- verify duplicate-name rejection behavior
- verify implemented expansion items (if any)
- produce validation summary

### Workstream E: Integration / Orchestration
- maintain scope discipline
- coordinate API/UI contract alignment
- track progress vs timebox
- pull expansion items from §4.1 in priority order only if core scope is stable
- cut expansion work immediately if time risk rises
- ensure final handoff completeness

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
- Scope lock to 3 views + 5 endpoints
- Prefer in-memory persistence for v0.3
- Keep API contract simple and explicit
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
