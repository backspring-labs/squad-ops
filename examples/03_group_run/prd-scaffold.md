# PRD: group_run — Scaffold Only
**Version:** v0.1
**Purpose:** Validate fullstack pipeline (FastAPI + React/Vite) before attempting full group_run scope
**Status:** Draft
**Stack Constraint:** FastAPI + React (Vite)

---

## 1) Product Summary

This is a **reduced-scope companion** to the full `group_run` PRD. It produces the minimum viable fullstack skeleton: a FastAPI backend with one endpoint and a React frontend that calls it and renders the result.

Same stack, same directory structure, same pipeline — just enough functionality to confirm the pipeline works before committing to the full build.

---

## 2) Objective

Deliver a startable fullstack skeleton with:

1. A backend health endpoint
2. A frontend that renders data from that endpoint
3. One backend test
4. Both services start locally with documented commands

### Success Definition

A reviewer can:
- start the backend and confirm the health endpoint responds
- start the frontend and see rendered content from the backend
- run the backend test and see it pass
- do all of the above following only the `qa_handoff` artifact

---

## 3) Functional Requirements

### 3.1 Backend (FastAPI)

One endpoint:

- `GET /api/health` — returns `{"status": "ok", "app": "group_run"}`

CORS must be configured to allow requests from `http://localhost:5173` (Vite dev server default).

### 3.2 Frontend (React + Vite)

One view:

- On load, fetches `GET http://localhost:8000/api/health`
- Displays the response status and app name on the page
- If the fetch fails, displays a clear error message

No routing, no navigation, no forms, no state management beyond a single `fetch` call.

### 3.3 Styling

None required. Unstyled HTML is acceptable.

---

## 4) Technical Constraints

### Backend
- Python 3.11+
- FastAPI + Uvicorn
- No database, no models, no persistence, no authentication

### Frontend
- React (Vite) — JavaScript, not TypeScript
- Plain `fetch` API
- No UI component library, no routing library

### Testing
- One backend test: verify `GET /api/health` returns 200 with expected JSON body
- Frontend tests are not required

---

## 5) File Structure

```
backend/
  main.py              # FastAPI app with /api/health and CORS
  requirements.txt     # fastapi, uvicorn
frontend/
  index.html           # Vite entry HTML
  package.json         # react, react-dom, vite, @vitejs/plugin-react
  vite.config.js       # Vite config with proxy to backend
  src/
    main.jsx           # React root mount
    App.jsx            # Fetches /api/health and renders result
```

---

## 6) API Contract

| Method | Path | Response |
|--------|------|----------|
| GET | `/api/health` | `{"status": "ok", "app": "group_run"}` |

---

## 7) Acceptance Criteria

- [ ] Backend starts with `cd backend && pip install -r requirements.txt && uvicorn main:app --port 8000`
- [ ] Frontend starts with `cd frontend && npm install && npm run dev`
- [ ] `GET /api/health` returns 200 with `{"status": "ok", "app": "group_run"}`
- [ ] Frontend on `:5173` can fetch from backend on `:8000` without CORS errors
- [ ] Frontend renders health check data from backend
- [ ] `cd backend && pytest` passes
- [ ] `qa_handoff` artifact includes startup commands for both services

---

## 8) Explicit Non-Requirements

- No data models or CRUD
- No database or persistence
- No authentication
- No multiple views or routing
- No frontend tests
- No Docker (Bob may produce these as packaging artifacts, but they are not acceptance criteria)

---

## 9) Relationship to Full group_run PRD

This scaffold validates the same stack and directory structure (`backend/` + `frontend/`) the full PRD requires. Once this succeeds, the full `prd.md` runs on proven infrastructure — the pipeline can produce, classify, test, and assemble fullstack artifacts.
