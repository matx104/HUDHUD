# ADR 0007: The Critic as an MCP server

- **Status:** accepted, 2026-10-18
- **Context:** Phase 3. The rules' Agentic Design criterion names "MCP integration", and Azure MCP is
  a named technology. The Critic is the part of HUDHUD worth sharing: any assistant that talks
  about football should have its claims checked.

## Decision

- **`court/mcp_server.py`**, built on the MCP Python SDK (2.x, `MCPServer`), offers five tools:
  `list_matches`, `match_events` (raw events with the ids a claim cites), `match_stats` (statistics
  code computed, returned as assertions ready to use), `match_moments` (the court's own verified
  claims, as worked examples) and `verify_claim` (the Critic's verdict, as of the end of a minute).
- **All read-only and deterministic,** annotated as such: no model calls, no keys, nothing written.
- **The evidence law holds for outside callers.** Inside the pipeline, a claim's figures are trusted
  because code computed them. An outside caller can't send figures: every number in its text must be
  backed by an assertion the Critic recomputes from raw events, by a value a cited event carries
  (computed here: a shot's xG, distance and speed, a pass's length and speed), by the claim's minute,
  or by the minutes bounding an assertion's window. A caller can't vouch for its own numbers.
- **Two transports.** stdio (`python -m court.mcp_server`) for GitHub Copilot agent mode in VS Code
  (`.vscode/mcp.json`, server `hudhud-critic`), and streamable HTTP mounted on the live studio at
  `/mcp/` (stateless, JSON responses), so any MCP client can use the Critic remotely
  (`hudhud-critic-live`).
- **No DNS-rebinding protection on `/mcp/`.** It guards local servers from web pages; this one is
  public, read-only and holds nothing private, so anyone may call it directly anyway.
- **Traced:** each tool call is a span (`mcp <tool>`) with the verdict and the rejection codes, in
  Application Insights beside the matches.

## Consequences

- Copilot in VS Code can read a match, draft a claim and have it checked, with the Critic's reasons
  in its own words when it refuses. The Azure MCP Server (`scripts/azure-mcp`) sits beside it in the
  same `mcp.json`.
- The tools only serve the demo matches (seeds 21, 7, 33); a match is generated once and cached.
- Next: an audit record for each `tools/call` (the client, the tool, the verdict), as the Reactor
  presenter's MCP authorization talk recommends, once the studio has a per-call audit writer.
