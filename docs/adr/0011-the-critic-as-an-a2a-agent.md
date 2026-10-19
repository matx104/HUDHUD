# ADR 0011: The Critic as an A2A agent

- **Status:** accepted, 2026-10-19
- **Context:** the Critic already serves assistants over MCP (ADR 0007): tools an assistant calls.
  Agent2Agent (A2A) is the other open protocol the multi-agent brief names: agents talking to
  agents, each with a card that says what it does. A broadcaster's own agents, or anyone's, should
  be able to treat the Critic as a peer they hand a claim to, not only as a tool library.

## Decision

- **`court/a2a_server.py`**: the Critic as a Microsoft Agent Framework agent (`CriticAgent`, a
  `BaseAgent`), served by Agent Framework's `A2AExecutor` on the A2A SDK, mounted on the studio at
  `/a2a/` with its card at `/a2a/.well-known/agent-card.json` (A2A protocol 1.0, JSON-RPC).
- **No model inside.** Every reply is computed: read-only, deterministic, free, and an agent on the
  other side can't talk it round.
- **Two skills, one evidence law.** `verify-claim` takes the same claim as the MCP tool and gives the
  same verdict: an outside caller can't vouch for its own numbers. `ask-the-match` answers a
  question about a match at a minute with the offline answerer through the Critic (ADR 0010), so
  what event data can't see still gets the fixed words. Anything else gets the contract back.
- **Behind the same wall.** On Azure the studio is private (docs/azure.md, "The wall"): an agent
  needs the Access service token, as an MCP client does.
- **Pinned prerelease.** `agent-framework-a2a==1.0.0b261015` (MIT) on `a2a-sdk` (Apache-2.0),
  pinned until it is released.

## Consequences

- Tested with Agent Framework's own A2A client (`A2AAgent`) against the server in process: the card,
  a verified claim, the same claim a minute early refused as a future event, a checked answer, and
  an injury question held back.
- Two protocols for one Critic: MCP for assistants, A2A for agents. Both read the same matches and
  apply the same rules, so they can't disagree.
