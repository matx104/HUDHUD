# ADR 0003: The model writes the line, code owns every number

- **Status:** accepted, 2026-10-18
- **Context:** Phase 2, the first narrator on models deployed in Microsoft Foundry (`court/foundry.py`)
- **Superseded in part:** ADR 0005 made `gpt-4.1-mini` the primary, by evaluation.

## Context

A language model writes livelier commentary than a template, and it also states numbers that aren't
true. HUDHUD's promise is that nothing unverified reaches the screen, so a model narrator must not
weaken the evidence law. The Reactor reference app (docs/reference/reactor-27536.md) takes the same
line ("the model is not the source of the numbers") but stops at a sanity check.

## Decision

- **Facts in, prose out.** For each alert, the template narrator composes the faithful claim: its
  citations, the assertions the Critic recomputes, and its **figures** (every number the line may
  state, computed by code). The model gets these as a fact sheet and returns JSON with one field, the
  line (structured output on `FoundryChatClient`). Citations, assertions and figures stay the
  alert's; the model never chooses its evidence.
- **A sixth Critic check: grounded numbers.** Any number in the text that is neither a figure nor an
  assertion is rejected (`ungrounded_number`) and sent back for a rewrite, with the Critic's reasons
  in the prompt. The template's lines are fully grounded, so the check costs them nothing.
- **Deployments hand over.** `gpt-5-mini` is primary (low reasoning effort for live latency) and
  `gpt-4.1-mini` is the backup. A timeout, throttling or an outage moves the request to the next
  model; if every model fails, `NarrationUnavailable` reaches the Orchestrator, which falls back to
  detection-only cues.
- **Metered from the first call:** tokens and estimated cost per model, printed with every live run.
- **Entra ID only.** Keys are disabled on the Foundry resource. The caller needs **Cognitive Services
  User** for the project endpoint's data actions: Azure AI Developer covers only OpenAI, Speech,
  Content Safety and model-catalog actions, and was replaced. Locally the credential is the project's
  Azure CLI with the tenant pinned (`scripts/live`).

## Consequences

- First live match (seed 21, 2026-10-18): seven verified cues written by the model, every number
  grounded, 35 seconds, **$0.0066** for the match. An earlier run showed the recovery path on a real
  fault: before the role fix, every model call returned 403, and the broadcast carried on with
  detection-only cues and announced it.
- The grounding check once rejected a true number (an assisting pass's length) that was in the cited
  events but not the figures; cited pass lengths are now figures. A rejection of a true fact is a
  bug in the figures, not in the model.
- Tests stay offline: a fake agent stands in for Foundry, and CI never installs the `foundry` extra.
