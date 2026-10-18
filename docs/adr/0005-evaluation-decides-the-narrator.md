# ADR 0005: Evaluation decides which model writes the commentary

- **Status:** accepted, 2026-10-18. The rule was committed (7519434) before the first run; the
  result and the decision follow below it.
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

## Result (2026-10-18, seeds 60–64, 50 alerts, `docs/evals/narrator-2026-10-18.json`)

| Model | First pass | Aired | Invented a number | Median s per cue | p95 s | Cost per cue | Output tokens per cue | Words |
|---|---|---|---|---|---|---|---|---|
| gpt-5-mini | 100% | 100% | 0% | 3.7 | 10.3 | $0.00077 | 332 | 24 |
| **gpt-4.1-mini** | 100% | 100% | 0% | **1.3** | 7.5 | **$0.00023** | 44 | 26 |

- Both through the gate. Neither wrote a draft the Critic refused, so the first-pass rule doesn't
  separate them: on the Critic's measure, they're equally grounded.
- **Speed decides:** gpt-4.1-mini's median cue is 1.3 s against 3.7 s, about 65% faster, the
  same on goals, chances and momentum. Most of gpt-5-mini's 332 output tokens per cue are hidden
  reasoning that never reaches the line.
- The whole run cost $0.050 (gpt-5-mini $0.038, gpt-4.1-mini $0.012).

## Decision

**gpt-4.1-mini is the primary Narrator; gpt-5-mini is the backup.** `FoundryNarrator`'s default
order, `scripts/live` and the CLI changed with this ADR. It supersedes ADR 0003's choice of primary.

## Consequences

- Cues reach air about 2.4 s sooner, at a third of the cost.
- The fact sheet does the heavy lifting: with every number computed and listed, a small,
  non-reasoning model writes lines just as grounded. That is the evidence law paying off.
- A 100% first-pass rate on both is a ceiling: this eval can't yet tell the models apart on
  quality. It measures grounding, not style. A harder set (rewrites after deliberate
  overreach, longer momentum facts, Urdu and Arabic later) belongs in the next run, under the same
  rule. Rerun it when a model, the prompt or the fact sheet changes.
