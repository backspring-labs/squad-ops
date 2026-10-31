---
template_id: request.source_repository_conventions_nextjs_ts
version: "1"
required_variables: []
optional_variables: []
---

### The blueprint it was made from

The product was made from SquadOps's `nextjs_ts` blueprint: one Next.js (App Router) application in
TypeScript, with no separate backend or frontend tree. Its code has kept the blueprint's
conventions since, and a change keeps them too:

- An endpoint is a route handler: an exported async function, one for each HTTP method.
- A test is vitest, run in a plain Node process with no server running. A test of an endpoint
  imports its route handler, calls it with a `Request`, and asserts on the `Response` it returns.
  A test that fetches a live URL fails.
- TypeScript is strict, and `next build` fails on a type error.
- A test file that imports a package the product's `package.json` doesn't declare fails to load,
  and every test in it fails with it. Import only what it declares.

Where a file or a test goes is the product's own, as its map shows, never the blueprint's starting
layout.
