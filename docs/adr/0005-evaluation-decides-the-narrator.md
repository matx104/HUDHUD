# ADR 0005: Evaluation decides which model writes the commentary

- **Status:** proposed, 2026-10-18. The rule is committed before the first run; the result and the
  decision follow below it.
- **Context:** Phase 2. Two models are deployed in the Foundry project: `gpt-5-mini` (primary
  since ADR 0003, a reasoning model) and `gpt-4.1-mini` (backup).

## Context

The primary was chosen by assumption. The control room showed that 77% of `gpt-5-mini`'s output
tokens are hidden reasoning, which costs time and money on every cue. The Reactor reference app
let evaluation pick its model and fixed its decision rule before the run (docs/reference). We do
the same, with our own measure of quality: the Critic.

## Method (`court/narrator_eval.py`, `scripts/live narrator-eval`)

- The alerts of unseen matches (seeds 60 and up, never used for tuning). At each alert, every
  model narrates from the same match state, with the same fact sheet, under the same Critic and
  the same three-attempt rewrite budget as on air, and with no backup model.
- Per model: the share of first drafts the Critic passes; the share of alerts that air within the
  budget; the share of drafts refused for an invented number; the time per cue (every call it
  needed); the cost per cue at list prices; output tokens and words per cue.

## The decision rule (fixed before any run)

1. **Gate:** a model must air at least 95% of the alerts within the rewrite budget.
2. Of the models through the gate, a **first-pass rate 5 points or more ahead** wins: every
   rewrite is a whole extra model call while the moment goes stale.
3. Otherwise a **median time per cue 20% or more lower** wins.
4. Otherwise the **cheaper cue** wins.

The winner becomes the primary; the other stays as the backup.

## Result

Pending the first run.
