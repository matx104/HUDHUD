# ADR 0006: The studio, live on Azure Container Apps

- **Status:** accepted, 2026-10-18
- **Context:** Phase 3. The rules (§4.8) require a working demo the judges can use, free, through the
  judging period (to Nov 10). The video needs a live match in which the Critic refuses claims on
  screen and the broadcast survives a failure.

## Decision

- **One page, one stream.** `court/server.py` (FastAPI) serves `court/studio/` and streams a match as
  Server-Sent Events: the clock and score, every shot, and every output of the court. SSE over plain
  HTTP needs no client library and passes any proxy; the page only renders what the server sent.
- **Two studio controls, both honest about what they are.** *Take the narrator off air* makes every
  narrator call fail, as an outage would; the Orchestrator's own recovery does the rest. *Stress-test
  the Critic* corrupts a share of drafts on purpose (the offline narrator's three overreach styles),
  because the models, given computed facts, rarely err (ADR 0005); the page says so in its label.
- **Join from a chosen minute.** Alerts before it are detected (the Scout keeps its history for
  momentum) but not narrated: nobody pays for moments nobody sees.
- **An open demo can't run up the bill:** 200 model-narrated matches a day (then the offline narrator,
  announced on screen), 8 streams at once, 15 minutes per stream at most.
- **Hosting:** Azure Container Apps (express environment, UAE North, beside Foundry), one replica of
  0.25 vCPU and 0.5 GiB. One replica on purpose: a match's off-air switch lives in that replica's
  memory, and express environments don't offer session affinity.
- **The image stays private:** Azure Container Registry (Basic), not a free public registry, because
  the image contains the source and the repository stays private until submission. The app pulls it
  with its managed identity.
- **One identity, least privilege, no keys:** `hudhud-studio-id` holds AcrPull on the registry,
  Cognitive Services User on Foundry, Monitoring Metrics Publisher on Application Insights and the
  built-in Data Contributor role on the audit trail's Cosmos DB account. `court.identity` picks it in
  Azure and the project's CLI on a laptop.

## Consequences

- Verified in the cloud on 2026-10-18: gpt-4.1-mini narrated from 54', the Critic refused the stress
  test's corrupted drafts and the rewrites aired, the audit trail kept every record, for $0.0019.
- Cost while running: the registry about $5 a month, the app about $5 a month after the free grant,
  models at most $0.40 a day under the cap. It must stay up through Nov 10; the credit lasts to Nov 13.
- Express environments refuse Azure Monitor as a log destination, so platform logs are off; the app's
  own OpenTelemetry carries the story (control room, ADR 0004's audit trail).
- A security review of the first version found two leaks, both fixed before the deploy: exception text
  reached the page (now a fixed message and a reference), and a session could outlive an early
  disconnect or slip past the stream cap (now created only once streaming starts, registered right
  after the cap check, and removed with its task).
