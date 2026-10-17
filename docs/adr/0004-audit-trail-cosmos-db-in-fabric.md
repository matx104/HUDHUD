# ADR 0004: The audit trail lives in Cosmos DB in Fabric

- **Status:** accepted, 2026-10-18; building starts once the Fabric trial is active
- **Context:** Phase 3, keeping every claim, verdict and cue after the match

## Context

Microsoft Fabric is a named technology in the official rules, and the owner chose it for the audit
trail. Every claim the Narrator drafts, every verdict the Critic returns and every cue that airs
should be kept, with its evidence, model, tokens, latency and cost, and stay queryable after the
match. Writes must never slow the broadcast: they leave the hot path and a failed write degrades the
audit, not the match. Budget: the $100 student credit, which also has to carry the models and the
judges' live demo through Nov 10.

## Options (prices and limits checked 2026-10-18)

| | Write path | After the match | Cost now | Cost once a trial ends |
|---|---|---|---|---|
| **Cosmos DB in Fabric** | Same engine as Azure Cosmos DB: single-digit-millisecond writes | Copied into OneLake automatically: SQL endpoint, Power BI, notebooks | $0 on the 60-day Fabric trial | A Fabric capacity: F2 in UAE North is $0.44 an hour, about $321 a month running |
| Fabric Eventhouse (KQL) | Seconds with streaming ingestion, longer when batched | The strongest for time-series queries and live dashboards | $0 on the trial | The same capacity |
| Azure Cosmos DB, free tier | Single-digit-millisecond writes | Mirroring into Fabric when a capacity exists (the replication compute is free) | $0 | $0: 1,000 RU/s and 25 GB free for the account's lifetime, one account per subscription |

## Decision

- **Cosmos DB in Fabric**, one database, one container partitioned by match. It gives the fastest
  writes of the Fabric options and puts every record in OneLake with no pipeline to build.
- **The Fabric trial pays for it:** 60 days from activation, which covers judging (to Nov 10) and
  the winners' announcement (Nov 20). A paid capacity is out of reach on this budget.
- **The exit is built in.** When the trial ends, the same code points at an Azure Cosmos DB
  free-tier account in `rg-hudhud`: the same SDK and the same documents, at $0. Fabric can mirror
  it back whenever a capacity exists.
- **Identity:** Microsoft Entra only (Cosmos DB in Fabric has no keys). Fabric doesn't accept a
  personal Microsoft account, so a member user in the project's tenant owns the workspace (the
  documented route for personal-email trials). Locally the audit writer signs in as that user; in
  Azure Container Apps, the app's managed identity is added to the workspace.
- **Off the hot path:** the Orchestrator queues audit records; a failed write becomes a
  `Degradation` notice ("audit trail unavailable"), never a dropped cue.

## Consequences

- Fabric covers the rules' named technology with a store that is also the fastest of its options.
- One owner step is needed before the build: create the member user, sign in to Fabric with it
  and start the trial (docs/azure.md, "Fabric").
- A `Spiked` or rejected claim is kept too: the audit trail shows what the Critic refused, not only
  what aired.
