# ADR 0008: Pass quality, speed and player tags (the rules' §4.1 cues)

- **Status:** accepted, 2026-10-18
- **Context:** Phase 3. The challenge lists player identification "with speed and distance tags when
  thresholds are reached", pass quality ("distance, accuracy and a difficulty rating") and ball and
  shot speed (§4.1). The generator already emitted every field; the cues didn't use them.

## Decision

- **One place for an event's numbers.** `metrics.EVENT_METRICS` states each as a broadcast says it:
  shot speed (km/h), pass distance (m), pass difficulty (0–100: 100 × the chance it fails), pass
  accuracy (%), ball speed (km/h), and xG. The Scout, the Narrator, the tags and the Critic all read
  them there, so a claim's number and its recomputation can't drift apart. Each is a new assertion
  metric with an `event_id`, recomputed by the Critic like `shot_xg`.
- **A great pass** is a new moment (`great_pass`): completed into the box, not a cross, difficulty 40
  or more (completed less than six times in ten: the hardest twentieth of passes behind a shot), and
  it made a chance. It's judged when the shot arrives, because only then is it known that the pass
  made one: 0.8 a match on seeds 0–59. The Critic's rule: the claim cites the completed pass and the
  shot it set up, both the side's own.
- **No double telling.** A goal or a big chance carries its pass in its own line instead ("set up by
  Pellby's 35 m pass, difficulty 72 of 100", when the pass was a hard one), and its shot speed when
  it reached 110 km/h ("struck at 114 km/h"), each asserted. Every shot's speed is a figure the model
  may state, so the Foundry narrator can use it too.
- **Player tags** (`Cue.players`): the players a cue's own cited events name (scorer or shooter,
  assister or passer; for a momentum spell, the two behind most of the cited actions), each with
  number, position, team and the badges a threshold earned: a 110 km/h shot, a 30 m pass, difficulty
  40. They're computed from raw fields, never written by a model, so there is nothing to check.

## Consequences

- The studio shows the tags under each line; the audit trail and the MCP tools carry the new kind
  and metrics.
- The showcase site's sample claim moved to seed 7's 5th-minute great pass, the first claim the
  Critic refused and the rewrite aired (CI regenerates it and fails on drift).
- Thresholds are calibrated on our generator (seeds 0–59), like the momentum detector: real data
  would recalibrate them with the same measurements.
