---
template_id: request.source_repository_deletion_tests
version: "1"
required_variables:
  - example_path
optional_variables: []
---

To remove a test a new one replaces, emit a `delete` fence naming it as the map writes it, with
nothing inside:

````
```delete:{{example_path}}
```
````

The product's own checks verify the change without that file. You can remove only a test one of
the product's runners holds, under its roots and by its file name, and not one this same answer
writes. Any other removal is refused, and the rest of your answer with it.
