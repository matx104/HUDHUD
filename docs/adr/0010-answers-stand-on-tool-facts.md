# ADR 0010: Ask the match: answers stand on the tools' facts

- **Status:** accepted, 2026-10-19
- **Context:** the original fusion plan (ideas.md) paired the live feed with "Ask the Match", a
  cited answer to a fan's question; the recap shipped, the questions hadn't. A free-form question
  invites a model to answer from what it imagines a match is like. The broadcast's law (code
  computes, the model writes, the Critic checks: ADR 0003) has to hold for answers too.

## Decision

- **The model learns numbers only from tools.** The Narrator answers with function tools on
  Microsoft Agent Framework: the score, a side's counts (several at once, for one side or both, over
  the match, a half or the last minutes), a player's counts and the moments of a kind. They count
  the events up to the moment of the question with `court.metrics`, the same functions the Critic
  recomputes with.
- **Each tool result is a fact with an id.** The answer returns its text and the ids of the facts it
  uses. Code builds the claim from those facts (their events, counts and numbers), never from the
  model's words. An id the tools never returned is cited as given, and the Critic refuses it.
- **The Critic reviews an answer like a line**, with hindsight (it may look back over the match):
  counts recomputed, now per player too (`Assertion.player_id`); every number in the text one the
  facts hold; a count of the match so far must cite the moment it stops (`answer_rule`); and a new
  check for every claim that lists its players (`Claim.names`): any player of the match the text
  names must be one its facts are about.
- **What the events can't answer gets fixed words.** The model may only say why it can't
  (beyond the data, not yet happened, off topic); the words shown are the product's, never the
  model's.
- **Never a betting tool** (added 2026-10-20, roadmap principle 8). A question about bets, odds or
  gambling, in English, Urdu or Arabic, is held back by code before any model reads it, and gets
  fixed words that steer away from gambling. The model is told the same, should one slip past.
- **Never go dark.** Offline, or when the models fail, a rule-based answerer handles the common
  questions through the same tools and the same Critic.

## Consequences

- Live, seed 21 at 70', gpt-4.1-mini: five questions, about $0.001 an answer and 3 to 6 seconds.
  "Who has been the better side by the numbers?" first hit the per-tool call cap (one call per
  number per side), cited facts that were never counted, and was refused; counting several things
  in one call fixed it (one call, one attempt, ten counts recomputed).
- The Critic proves an answer's numbers, names and citations, not its judgment words ("dominated",
  "the better side"); the site's limits say so.
- Measured (`court ask-eval`, docs/ask-eval.md): on two unseen matches the first run got 39 of 39
  answerable questions right but twice inferred "no signs of injury" from pass counts. Code now
  holds back what event data can't see before any model is asked (`ask.beyond_the_data`), and a
  ranking (the biggest chance) is a fact of its own: 18 of 18 held back after, groundedness 5.0.
- **Prompt Shields first** (`court/shield.py`, 2026-10-19). A question is free text for a model, so
  Azure AI Content Safety's Prompt Shields reads it first: flagged, it gets fixed words and no model
  reads it; with the shield down the offline answerer takes it, so a model only reads what the
  shield passed.
