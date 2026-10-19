# ADR 0004: The audit trail lives in Azure Cosmos DB's free tier

- **Status:** accepted, 2026-10-18 (revised the same day: first drafted as Cosmos DB *in* Fabric).
  Revised 2026-10-19: the Fabric mirror is out of scope, kept as the route for later
- **Context:** Phase 3, keeping every claim, verdict and cue after the match

## Context

Every claim the Narrator drafts, every verdict the Critic returns and every cue that airs should be
kept, with its evidence, model and cost, and stay queryable after the match. Writes must never slow
the broadcast. The project runs on a $100 student credit that also has to carry the models and the
judges' live demo through Nov 10, and it should keep running after the hackathon. Microsoft Fabric
is a named technology in the official rules, and the owner first chose it for the audit trail.

## Options (prices and limits checked 2026-10-18)

| | Write path | After the match | Cost now | Cost once a trial ends |
|---|---|---|---|---|
| Cosmos DB in Fabric | Same engine as Azure Cosmos DB: single-digit-millisecond writes | Copied into OneLake automatically | $0 on the 60-day Fabric trial | A Fabric capacity: F2 in UAE North is $0.44 an hour, about $321 a month running |
| Fabric Eventhouse (KQL) | Seconds with streaming ingestion | The strongest for time-series queries and live dashboards | $0 on the trial | The same capacity |
| **Azure Cosmos DB, free tier** | Single-digit-millisecond writes | Mirroring into Fabric OneLake (the replication compute is free) | $0 | $0: 1,000 RU/s and 25 GB free for the account's lifetime |

## Decision

- **The system of record is Azure Cosmos DB's free tier** (`hudhud-audit`, API for NoSQL):
  database `hudhud` with 1,000 RU/s shared, container `audit` partitioned by `/matchId`. The account's
  total throughput is capped at 1,000 RU/s, so it can't leave the free tier. It costs nothing now,
  nothing after any trial, and needs no second identity: the project's own Entra sign-in writes
  with the built-in Data Contributor role. Keys are disabled.
- **Fabric is out of scope for the hackathon** (revised 2026-10-19). Mirroring the container into
  OneLake, for SQL queries and Power BI over every match, was considered and is the route the
  project's analytics would take as it grows. Nothing is built on Fabric. The account is ready for
  it: continuous 7-day backup, which mirroring requires, is on and free.
- **Region: Central India.** UAE North, beside the Foundry resource, refused new Cosmos DB accounts
  for high demand on 2026-10-18. Central India is the nearest allowed region. Audit writes are off
  the hot path, so the distance never touches a cue. A Fabric capacity, if the mirror is ever
  built, belongs in Central India too: mirroring across regions pays egress.
- **Off the hot path** (`court/audit.py`): the trail tees the Orchestrator's sink. Each output
  reaches the broadcast first, then a queue that a background task writes. A failing store stops
  the trail, counts what it dropped and reports it at the end of the run; the match goes on.
- **A run is a story:** a `run` record (product, narrator, seed, teams), one record per output
  (cue, rejection with the Critic's reasons, spiked claim, degradation), then a `summary` (stats,
  handovers, model cost). Since 2026-10-19 a viewer's question and its answer join the run as an
  `answer` record, with every draft the Critic refused (ADR 0010); a question can come after full
  time, so each is written on its own, off the viewer's path.

## Why the first draft changed

The first draft put the trail in Cosmos DB *in* Fabric, to make Fabric the store. That made the
audit trail depend on a 60-day trial, a second identity and a Fabric tenant setting, with a $321 a
month capacity as the only way to keep it. Asked whether the free tier would be better from the
start, the answer was yes: the same engine, the same speed, $0 for good, and Fabric can still read
every record through mirroring, later.

## Consequences

- First live run (2026-10-18, seed 21 on Foundry): 11 records kept (run, 9 cues, summary) and read
  back by query; model cost $0.0067.
- One free-tier account per subscription: this is it. A failed create in UAE North left a shell
  account holding the free-tier slot; it was deleted before the Central India create.
- Continuous backup can't be turned off once on. That is fine for an audit trail.
- The member user made for Fabric (`hudhud@…`, Fabric Administrator) has no role on the account
  and no job while Fabric is out of scope (docs/azure.md).
