A Python **FastAPI** backend and a **React** frontend built with Vite, in two trees.

- **Server endpoints live in `backend/routes.py`** — one module holding every route, declared
  with decorators (`@router.post("/runs")`).
- **A path parameter is written in braces** — `/runs/{run_id}` — and the same name is used by
  every endpoint addressing that resource.
- **Views are `.jsx` components under `frontend/src/views/`**, one file per declared route,
  wired through the frontend's own router.
- **Shared server code sits beside the routes** in `backend/` — models, an in-memory store,
  and the error envelope.
- **Tests are pytest for the backend** under `backend/tests/`, and vitest for the frontend
  under `frontend/src/__tests__/`.
- **The frontend builds with Vite** and reaches the API through a relative base, never a
  hardcoded host.
