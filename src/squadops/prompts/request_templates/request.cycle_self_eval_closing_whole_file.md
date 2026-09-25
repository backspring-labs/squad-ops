---
template_id: request.cycle_self_eval_closing_whole_file
version: "1"
required_variables: []
optional_variables: []
---
Fix every failure above now. Emit each file you add or change, whole, in a
` ```language:<path> ` fence with the file's own path. Do not reproduce a file you are not
changing.
