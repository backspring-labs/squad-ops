"""The ``roblox-studio`` provider (SIP-0117 phase 2d, #3039): Roblox Studio, driven through its own
MCP server (``StudioMCP``) on the worker's machine.

The first slice is the read side only (the 2.8 plan §5): a session to Studio's MCP server, the tool
check, identity as far as reading allows, and the paged read-back of the three synced folders. It
writes nothing into Studio and publishes nothing. The transaction's writes, play, capture, the
baseline digest and reset from the read-only file are the adapter's next parts.
"""
