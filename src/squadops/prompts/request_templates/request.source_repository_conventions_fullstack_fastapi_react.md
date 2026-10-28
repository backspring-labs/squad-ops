---
template_id: request.source_repository_conventions_fullstack_fastapi_react
version: "1"
required_variables: []
optional_variables: []
---

### The blueprint it was made from

The product was made from SquadOps's `fullstack_fastapi_react` blueprint: a Python FastAPI backend
and a React frontend built with Vite. Its code has kept the blueprint's conventions since, and a
change keeps them too:

- A backend test is pytest, and calls the application through FastAPI's `TestClient` or
  `httpx.AsyncClient`, never a running server.
- A frontend test is vitest, and uses Testing Library only where the frontend's `package.json`
  declares it.
- A test file that imports a package none of the product's manifests declare fails to load, and
  every test in it fails with it. Import only what they declare.
- The frontend reaches the backend through a relative API base, read from `VITE_API_BASE`, and the
  backend reads its allowed CORS origins from configuration. Neither names a host, so the app runs
  unchanged wherever it is served.

Where a file or a test goes is the product's own, as its map shows, never the blueprint's starting
layout.
