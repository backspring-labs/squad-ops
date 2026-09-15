---
template_id: request.cycle_repair_output_scoped
version: "2"
required_variables:
  - editable_files
  - new_files
optional_variables: []
---
### Required Output: Revise the Existing Files in Place

These named files already exist in the workspace. **Change them with edit fences only**: one
` ```edit:<path> ` fence per file you change, holding the blocks described in the edit-fence
section below.

{{editable_files}}

- **Do not emit a ` ```language:<path> ` fence for any of these files.** Re-emitting an existing
  file whole is not a repair: every line you did not mean to change is written again, and any of
  them can break.
- A file above that you are not fixing: emit nothing for it. It stays exactly as it is.
- A file the task names that does not exist yet is emitted whole, with a
  ` ```language:<path> ` fence:

{{new_files}}

**This is a repair, not a rewrite.** Change the minimum necessary to fix the named failure. Keep
each file's structure as it is: the router construction, every route decorator with its literal
path, every function name and its signature.
