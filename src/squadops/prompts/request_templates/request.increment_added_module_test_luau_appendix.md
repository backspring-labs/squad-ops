---
template_id: request.increment_added_module_test_luau_appendix
version: "1"
required_variables: []
optional_variables: []
---

### A criterion's test for a module this change adds

Each criterion's test runs twice: on the product before this change, where one of its tests must
fail, and on the built change, where that test must pass. Before the change, a module the change
adds isn't there. A spec that requires it at the top of the file can't load, so the run shows the
file failing to load and none of its tests failing. That never counts as the criterion failing,
and the increment is refused however correct the build.

So a spec for a module this change adds looks the module up inside each test, in a way that gives
`nil` when it is absent (in a Roblox instance tree, `FindFirstChild`), checks that it is there,
and only then requires it. Before the change that check is the assertion that fails. A module the
product already has is required at the top of the file, as the product's own specs do.

A design or a plan for such a spec says the same: it never asks that the spec begin with the
`require` of the new module, and its draft of the spec doesn't.
