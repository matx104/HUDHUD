# ADR 0002: Momentum is judged against each side's own baseline, and must hold before it's called

- **Status:** accepted, 2026-10-18 (operating point chosen by the Monarch: "sure calls")
- **Context:** Phase 2 Scout rework; `court/evals.py` scores calls against the generator's hidden ground truth

## Context

A momentum line passes the Critic when its numbers are right, but right numbers don't make the
call right: "five shots in five minutes" can be a real swing or a random cluster. The generator
hides *momentum spells* in its ground truth (never streamed), so calls can be scored: a call is a
hit when a spell for that side covers at least half of the window it talks about.

The first Scout called a swing when one side's threat (xG, box entries, final-third passes) dominated
the window in absolute terms. Scored on seeds 60–99, 64% of its calls were noise. Two causes:

1. **Strength isn't momentum.** The better side keeps the ball all match. Absolute dominance flags it
   over and over.
2. **Sparse signals.** About 29 shots a match can't separate a five-minute spell from chance, while
   about 1,000 passes can. A spell lifts the leading side's pass completion by 8–18 points, cuts the
   opponent's by half that, and pushes play forward.

## Decision

- **Two signals a commentator can say out loud,** each measured against the same side's level earlier
  in the half, then against the opponent's change:
  - pass completion over the window (crosses left out: they complete about a quarter of the time
    whoever is on top);
  - completed passes into the final third per minute.
- **One scale.** Each difference is divided by its typical spread (measured on seeds 0–59) and the two
  are summed.
- **Hold before calling.** A swing is called only when the score has stayed above the threshold for
  several consecutive checks. Real spells last 6–14 minutes; noise flickers.
- **Operating point: sure calls.** Threshold 2.5, held for 6 checks (3 minutes). On a broadcast whose
  promise is "every call comes with its evidence", a call that is usually right beats more calls.
- **The narration says the same figures** ("completing 41 of 46 passes in the last 5 minutes (89%, up
  from 76% earlier in the half)"), and the Critic recomputes every count from raw events.

## Results (seeds 60–99, never tuned on; `make eval`)

| Detector | Calls per match | Precision | Recall | F1 | Median lag |
|---|---|---|---|---|---|
| Absolute threat (before) | 7.1 | 36% | 69% | 0.47 | 5.8 min |
| Relative, balanced (z 0.8, 8 checks) | 4.7 | 41% | 54% | 0.47 | 7.3 min |
| **Relative, sure calls (z 2.5, 6 checks)** | **1.5** | **62%** | 26% | 0.36 | 6.8 min |

## Consequences

- About one and a half momentum calls a match, most of them real. Seed 7, the showcase match, has
  none; **seed 21** (a 2-2 draw, two calls, both real) is the momentum demo match and the test fixture.
- `tests/test_evals.py` keeps a precision floor on seeds 60–79, so detection can't quietly regress.
- Momentum claims still fail closed until the Critic's evidence rule (`critic.momentum_rule`,
  TODO(human)) is registered; `tests/test_momentum_rule.py` switches on when it is.
- The spreads and threshold are calibrated on our own generator. Real match data would recalibrate
  them with the same harness; the method, not the constants, is the decision.
