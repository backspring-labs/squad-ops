---
template_id: request.source_repository_conventions_node_vitest
version: "1"
required_variables: []
optional_variables: []
---

### Its stack

The product is JavaScript or TypeScript on Node, and vitest runs its tests. A change keeps to what
that expects:

- A test is vitest, run by the product's own runner: it imports what it needs from `vitest` and
  asserts with `expect`.
- A test file that imports a package the product's `package.json` doesn't declare fails to load,
  and every test in it fails with it. Import only what it declares.
- A module's form is the product's own. Read `package.json` and the module you change, and write
  what they already use: an ES module doesn't take `require` or `module.exports`.

Where a file or a test goes is the product's own, as its map and its runners show.
