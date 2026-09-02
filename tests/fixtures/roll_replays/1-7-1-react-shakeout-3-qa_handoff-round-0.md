# group_run — QA Handoff

This document is the operational handoff for the `group_run` full-stack MVP (FastAPI + React/Vite).

## How to Run

### Option A — Docker (preferred, single container)

```bash
docker build -t group_run .
docker run -p 8000:8000 group_run
```

Open http://localhost:8000 — the frontend is served and `/api/*` calls are handled by the backend.

### Option B — Local dev (two terminals)

**Backend** (port 8000):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

**Frontend** (port 5173, proxies `/api` → backend):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

### CORS Configuration

The backend reads `CORS_ORIGINS` (comma-separated) at startup. In dev, leave it as `*` or unset to allow all origins. In production, set it to the exact frontend origin(s), e.g.:
