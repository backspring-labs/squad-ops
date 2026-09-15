---
template_id: request.cycle_repair_closing_scoped
version: "1"
required_variables: []
optional_variables: []
---
Emit the repair now. For each existing file you change, write one ` ```edit:<path> ` fence holding
structural or anchored blocks, as described above, with the file's own path. Use a
` ```language:<path> ` fence only for a file that does not exist yet — never for an existing one.
Do not include explanatory prose between fences unless it is essential.
