# How real is the synthetic football?

> Written by `scripts/realism.py` on 2026-10-19. Benchmark only: the real results are never product
> data (rules §4.7), and no team is named here.

**Real:** 7,559 competitive men's internationals since 2010 at a home venue, from
Mart Jürisoo's *International football results from 1872* (public domain, CC0 1.0,
https://github.com/martj42/international_results). **Synthetic:** the generator's matches, seeds 0-199.

- Goals: 2.98 a match, close to the real 2.77.
- Home wins: 45.0% against 50.4% real: the generator gives the home side less of an edge than real football does.
- Draws: 18.0% against 21.1% real: in line.
- Goalless draws: 2.5% against 7.7% real: too few, and the goals spread less widely than real football's.

| | Real | Synthetic |
|---|---|---|
| Matches compared | 7,559 | 200 |
| Goals a match | 2.77 | 2.98 |
| Spread of goals (sd) | 1.89 | 1.56 |
| Home wins | 50.4% | 45.0% |
| Draws | 21.1% | 18.0% |
| Away wins | 28.4% | 37.0% |
| Both sides score | 41.3% | 49.0% |

## Goals in a match

| Goals | Real | Synthetic |
|---|---|---|
| 0 | 7.7% | 2.5% |
| 1 | 18.8% | 15.5% |
| 2 | 23.6% | 23.0% |
| 3 | 20.7% | 24.0% |
| 4 | 13.4% | 19.0% |
| 5 | 7.9% | 9.5% |
| 6 | 4.0% | 4.5% |
| 7+ | 3.9% | 2.0% |

## The commonest scorelines (home-away)

| | Real | Synthetic |
|---|---|---|
| 1 | 1-0 (11.4%) | 2-0 (9.0%) |
| 2 | 1-1 (9.6%) | 1-0 (9.0%) |
| 3 | 2-0 (9.0%) | 2-1 (8.0%) |
| 4 | 0-0 (7.7%) | 0-2 (7.0%) |
| 5 | 2-1 (7.5%) | 1-1 (7.0%) |
| 6 | 0-1 (7.4%) | 2-2 (7.0%) |
| 7 | 3-0 (5.4%) | 1-2 (6.5%) |
| 8 | 0-2 (5.1%) | 0-1 (6.5%) |

## What this can't tell you

A result can't check what happens inside a match: passes, shots, pressures and possession are
calibrated separately (over 100 seeds: about 1,000 passes, 29 shots and 320 pressures a match, 78.5%
of passes completed). Internationals aren't club football: they mix strong and weak sides more
than a league does, which widens the scores. It is the closest public-domain benchmark of real
results; read it as a check on shape, not a target.
