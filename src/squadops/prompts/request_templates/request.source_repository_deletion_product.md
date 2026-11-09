---
template_id: request.source_repository_deletion_product
version: "1"
required_variables: []
optional_variables: []
---

To remove a file, emit a `delete` fence naming it as the map writes it, with nothing inside. When a
change folds one file into another, emit the file you keep, whole, and this for the one it replaces:

````
```delete:docs/old-setup-notes.md
```
````

The product's own checks verify the change without that file. Only a path the map lists can be
removed, and not one this same answer writes: a removal that isn't, or a binary or generated file,
is refused, and the rest of your answer with it.
