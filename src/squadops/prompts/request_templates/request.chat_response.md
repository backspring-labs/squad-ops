---
template_id: request.chat_response
version: "1"
required_variables:
  - user_message
optional_variables:
  - status_context
  - memory_context
---
{{status_context}}
{{memory_context}}

## User Message

{{user_message}}

Respond helpfully based on the context above. If the context does not contain enough information to answer, say: "I don't have that detail right now."
