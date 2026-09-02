---
template_id: request.qa_test_client_surface_appendix
version: "1"
required_variables:
  - client_lines
optional_variables: []
---
**FROZEN API CLIENT (authoritative — mock or stub beneath exactly this surface):**
{{client_lines}}

The views reach the backend only through this scaffold-owned client; it is frozen and
identical in every correction round. When you stub the network, stub `fetch` beneath it
or mock this module with exactly these exports and this behaviour — a mock that resolves
a different shape, throws differently, or exports a name the client does not have tests
your mock, not the view. Never re-implement the client in the suite.
