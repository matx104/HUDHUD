# ADR 0012: HUD², one match through three lenses

- **Status:** accepted, 2026-10-20
- **Context:** the studio shows a match as a broadcast gallery: a feed of lines, a small shot map
  and the Critic's desk. The Monarch's brief for HUD² (2026-10-20): a heads-up display for
  referees, commentators and fans, "think augmented reality". In its evolved state it is worn, on
  glasses, then lenses, then further out on neural interfaces, and each person sees the match
  through an interface shaped to their needs and preferences. The starting point is one central
  screen with overlays, markings and annotations, and a different view for each role.

## Decision

- **One page, `/hud`, three lenses.** A lens is a starting set of layers, not a separate app:
  - **Referee:** fouls (each with its distance from the goal the fouling side defends), pressing,
    the ball, who is on it, and the referee's zones (penalty areas, the goal-chance zone and the
    promising-attack line) under the match's strictness profile. Lines: the ref's calls and goals.
  - **Commentator:** the ball and its path, recent passes, shots sized by xG, who is on the ball, and
    the last five minutes against the match so far, both sides on one bar. Every line.
  - **Fan:** where each side has played lately, the chances, who's on top, plain words for
    newcomers by the kind of moment, the viewer's club lit up. Every line, in casual mode.
- **The viewer's own choices sit on top.** Every layer can be switched on or off in any lens, and
  the choice is kept per lens in that browser. A recording can fix lens, layers and camera in the
  address. This is the seed of the evolved state: the lens as a preference, not a role.
- **The server places, the page draws.** With `hud=1` the studio stream adds a `play` for every
  action, placed in one camera frame (`court/hud.py`: each event's own-team frame turned to the
  camera's, the ends changing at half-time), and a `pulse` each minute: both sides' counts for the
  last five minutes and the match so far, counted by `court.metrics`, the functions the Critic
  recomputes with. The page computes no number. Geometry (lines, rings, heat) is drawn from where
  the events say things happened.
- **Words only through the Critic.** The HUD's words are verified cues, refusals and answers, plus
  the product's own fixed sentences (the newcomer explainers, the strictness rule, the facts of the
  last foul). Each checked line is pinned where the last event it cites happened, with the Critic's
  lock closing on the spot; each refusal is struck where it was aimed.
- **Two cameras.** From the stand (a perspective view, as glasses would see it) or from above (a
  tactics board). Both are one pure function, tested.
- **Plain web, no new dependency.** HTML, CSS and a 2D canvas, like the rest of the studio. The pure
  parts (`studio/hud-core.js`: lenses, layers, the camera, pins) run under `node --test` in CI.

## Consequences

- The data limits what can be drawn: events, not video. HUD² knows where each action happened, not
  where all 22 players are, so it marks the play, not the shape. Tracking (roadmap Stage 3) is what
  lets a mark sit on a real player in a real stadium.
- The stream is about 1,800 more small messages a match (about 360 KB), only for a HUD session.
- Words stay under one law across surfaces: the studio, the recap, questions, MCP, A2A and the HUD
  all show only what the Critic passed.
