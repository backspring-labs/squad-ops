---
template_id: request.development_develop_fill_only_appendix
version: "1"
required_variables:
  - stack
optional_variables: []
---
## Fill-only: a walking skeleton is already in your workspace

This build was scaffolded (`{{stack}}`). A deterministic tool has **already generated a
wired, buildable, bootable application skeleton** into your workspace — entry files,
config, data models, error handling, the API client, cross-file routing, and route/
component **stubs**. It already builds and boots. Your job is to **fill the bodies of
the fixed slots** — never to rebuild, rewire, or regenerate the scaffold.

**FILL — edit only the stubbed bodies:**
- Backend route functions in `backend/routes.py` — implement the logic inside each
  existing function. The in-memory store, the request/response models, and `ApiError`
  are already imported and wired; use them.
- Frontend view components (`frontend/src/views/*.jsx`) — implement each component's
  body. `apiFetch` is the wired data-access seam; call it (it prefixes `/api` and
  unwraps the error envelope).

**DO NOT touch the scaffold-owned surface — it is frozen and verified:**
- Do NOT change route **paths, methods, decorators, or signatures** in `backend/routes.py`.
- Do NOT edit entry / config / wiring files: `backend/main.py`, `backend/models.py`,
  `backend/errors.py`, `frontend/src/main.jsx`, `frontend/src/App.jsx`,
  `frontend/src/api.js`, `vite.config.js`, `package.json`, `index.html`, or the
  requirements/manifest files.
- Do NOT rewire `App.jsx`'s import/route graph, rename or move views, or add/remove files.

Filling the fixed slots — rather than regenerating the app — is the whole point: the
skeleton already builds and boots, so a fill that preserves it stays green, while one
that rewrites scaffold-owned files is rejected by the verification contract. When in
doubt, change less: implement the body, keep everything around it exactly as scaffolded.
