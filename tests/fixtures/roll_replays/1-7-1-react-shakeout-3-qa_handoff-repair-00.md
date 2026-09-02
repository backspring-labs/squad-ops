# QA Handoff — group_run MVP

## How to Run the Backend

1. Install Python 3.11+
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # or venv\Scripts\activate  # Windows
   ```
3. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
4. Start the backend:
   ```bash
   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```
5. The API is available at `http://localhost:8000`.

## How to Run the Frontend

1. Install Node.js 18+
2. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```
3. Start the Vite dev server:
   ```bash
   npm run dev
   ```
4. The frontend is available at `http://localhost:5173`.
5. Proxy configuration: Vite proxies `/api` requests to `http://localhost:8000`. See `frontend/vite.config.ts` for the proxy config.

## How to Test

### Backend Tests (pytest)

```bash
cd backend
pip install -r requirements.txt
pip install pytest httpx
python -m pytest tests/ -v
```

### Frontend Tests (vitest)

```bash
cd frontend
npm install
npm test
```

Expected test behavior:
- Backend tests verify create, list, detail, join, leave, duplicate-reject, and validation errors.
- Frontend tests (if implemented) verify create flow and/or join/duplicate error behavior.
- Tests use in-memory store isolation via `reset()` in `backend/store.py`.

## Expected Behavior

### Create Run
- POST `/api/runs` with valid payload returns the created run object with a generated `id`.
- Required fields: `title`, `datetime`, `location`.
- Optional fields: `distance`, `pace_target`, `route_notes`.
- Validation errors (empty required fields) return HTTP 422 with a clear error message.

### List Runs
- GET `/api/runs` returns an array of runs, each with `id`, `title`, `datetime`, `location`, and `participants` (array).
- Empty state: returns an empty array `[]` when no runs exist.
- Newly created runs appear in the list.

### Run Detail
- GET `/api/runs/{run_id}` returns the full run object including all fields and the participant list.
- Unknown run ID returns HTTP 404 with error code `run_not_found`.

### Join Run
- POST `/api/runs/{run_id}/join` with `{"name": "Alice"}` adds the participant.
- Participant appears in the list and count updates.
- Duplicate name on the same run is rejected with HTTP 409 and error code `duplicate_participant`.
- Empty name is rejected with HTTP 422 and error code `validation_error`.
- Unknown run ID returns HTTP 404 with error code `run_not_found`.

### Leave Run
- DELETE `/api/runs/{run_id}/leave` with `{"name": "Alice"}` removes the participant.
- Participant is removed from the list and count updates.
- Unknown participant name returns HTTP 404 with error code `participant_not_found`.
- Empty name is rejected with HTTP 422 and error code `validation_error`.
- Unknown run ID returns HTTP 404 with error code `run_not_found`.

### Duplicate-Reject
- Joining with a name that already exists on the run (case-insensitive) returns HTTP 409.
- The error response includes a human-readable message indicating the name is already joined.

## Implemented Scope

Core PRD §5 features implemented:
- Run event creation (backend + UI)
- Upcoming runs list (backend + UI)
- Run detail view (backend + UI)
- Join run with participant name (backend + UI)
- Leave run by participant name (backend + UI)
- Duplicate participant prevention (case-insensitive)
- Validation for required fields and empty names

No §4.1 expansion items were implemented due to time constraints in the 1-hour cycle.

## Known Limitations

- In-memory persistence: all data is lost on server restart.
- No authentication or user identity: any user can join/leave with any name.
- Case-insensitive duplicate check: "Alice" and "alice" are considered the same participant.
- Datetime is a free-form string: no parsing or validation of format.
- No capacity limits, sorting, or seed data (expansion items not implemented).
- Basic error messaging only; no toast/banner notifications.
- No per-participant leave buttons in UI; leave requires manual name input.

## Behavioral Assumptions

- Datetime is accepted as any non-empty string; no validation of date/time format.
- Leave returns an error (HTTP 404, code `participant_not_found`) for unknown names, not a no-op.
- Participant names are compared case-insensitively for duplicate and leave operations.
- The store is reset between tests using `reset()` from `backend/store.py`.
- CORS is enabled for local development to allow frontend-to-backend communication.