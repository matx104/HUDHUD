# ADR 0001: Hot path, warm path, and who owns recovery

- **Status:** accepted, 2026-10-17
- **Context:** Phase 1 skeleton; Microsoft Agent Framework (Python) 1.22.0

## Context

The system must narrate a *live* match. Two facts shape the design:

1. Detection (is this a big chance? has momentum swung?) is cheap arithmetic over events.
   Narration (an LLM writing prose, a verifier checking it) is slow, costs tokens, and can fail.
2. Agent Framework workflows do not retry. Verified against 1.22.0: an exception inside an
   executor propagates unchanged out of `Workflow.run()`, and the same workflow object runs
   cleanly afterwards. Recovery is ours to build, which suits us: failure recovery is a
   judged criterion that no competing entry claims.

## Decision

Split the system into two paths, both coordinated by the Orchestrator:

- **Hot path:** every event goes ingest → `MatchState` → Scout. It is deterministic, has no
  LLM and never waits on anything slow. It produces alerts that carry their own evidence.
- **Warm path:** each alert runs once through an Agent Framework workflow:
  Narrator → Critic → (Localizer | rewrite via the Narrator | spike). The Critic yields every
  rejection as an output, so refusals reach the stream as artifacts.
- **Supervision:** the Orchestrator wraps each warm-path run in a retry. If it still fails,
  the broadcast drops to *detection-only* cues: the Scout's computed facts, still linked to
  their evidence. The change of service level is announced, and so is the recovery.

Agent logic lives in plain classes (Scout, TemplateNarrator, Critic, Localizer). The workflow
adapters in `court/workflow.py` are thin, so the agents are testable without the framework,
and the LLM backends (Foundry) plug in behind the same `Narrator` protocol.

## Consequences

- The match never goes dark because a model is slow or down: degradation is structural.
- Phase 3's on-camera failure demo is an extension of this one code path (timeouts,
  backend reassignment, health UI), not a new mechanism.
- Phase 3 must add concurrency: today alerts are narrated in sequence on the ingest loop.
  The next step is an alert queue with workers, keeping the hot path non-blocking even
  while LLM calls are in flight.
