"""The referee's likely call on a foul: Law 12 read as far as event data can see it.

The roadmap's bridge item ("Ref's call", roadmap.md): the Scout flags a foul that matters, the
Narrator states the likely decision, and the Critic recomputes it from the cited foul under the
competition's strictness profile before the line airs. It is a reading of the Law for an event
feed, not a referee: it sees where the foul happened and what the fouled side was doing, never the
force or the speed of the challenge, so a line always says "likely".

- Restart: a penalty kick when the foul is inside the fouling side's own penalty area, otherwise a
  direct free kick. The generator awards penalties the same way, so this part has ground truth.
- Card, by profile:
  - a goal-scoring chance denied: the foul within GOAL_CHANCE_M of goal and central. Outside the
    area that is a red card; inside it, a challenge for the ball is a yellow (Law 12, since 2016).
  - a promising attack stopped: the fouled side was in its attacking third (strict: anywhere in
    the opponent's half). A yellow; the lenient profile lets it go.
"""

import math
from typing import Literal

from match_events import Tackle

from .contracts import RefCall

Profile = Literal["lenient", "standard", "strict"]
PROFILES: tuple[Profile, ...] = ("lenient", "standard", "strict")

# Metres from goal inside which a foul denies a clear chance, by how strictly the game is called.
# The area's edge is 16.5 m out, so a foul just outside it can be a red.
GOAL_CHANCE_M: dict[Profile, float] = {"lenient": 18.0, "standard": 21.0, "strict": 24.0}
CENTRAL_M = 12.0  # off the middle of the goal: wider than this, the angle isn't a clear chance
# How far up the pitch a stopped attack counts as promising, in the fouling side's frame (its own
# goal at x=0): the fouled side's attacking third, or for the strict profile the whole half.
PROMISING_X: dict[Profile, float] = {"lenient": 0.0, "standard": 35.0, "strict": 52.5}
AREA_X, AREA_Y = 16.5, (13.84, 54.16)
GOAL_Y = 34.0

REASONS = {
    "goal_chance": "denying a goal-scoring chance",
    "promising_attack": "stopping a promising attack",
    "in_the_area": "a foul in the penalty area",
}


def distance_to_goal(foul: Tackle) -> float:
    """Metres from the foul to the middle of the fouling side's goal (in its frame, at x=0)."""
    return math.hypot(foul.x, foul.y - GOAL_Y)


def call(foul: Tackle, profile: Profile = "standard") -> RefCall | None:
    """The likely decision on a foul, or None when the tackle wasn't one."""
    if foul.outcome != "foul":
        return None
    in_area = foul.x <= AREA_X and AREA_Y[0] <= foul.y <= AREA_Y[1]
    restart = "penalty" if in_area else "free_kick"
    central = abs(foul.y - GOAL_Y) <= CENTRAL_M
    goal_chance = central and distance_to_goal(foul) <= GOAL_CHANCE_M[profile]
    promising = foul.x <= PROMISING_X[profile]
    if goal_chance:
        card, reason = ("yellow" if in_area else "red"), "goal_chance"
    elif promising:
        card, reason = "yellow", "promising_attack"
    else:
        card, reason = "none", "in_the_area" if in_area else ""
    return RefCall(restart=restart, card=card, profile=profile, reason=reason)


def matters(decision: RefCall | None) -> bool:
    """A call worth a line on air: a card or a penalty. Most fouls are neither."""
    return decision is not None and (decision.card != "none" or decision.restart == "penalty")


def words(decision: RefCall) -> tuple[str, str]:
    """How a line says the restart and the card; the Critic looks for these words."""
    restart = "a penalty" if decision.restart == "penalty" else "a direct free kick"
    card = {"none": "no card", "yellow": "a yellow card", "red": "a red card"}[decision.card]
    return restart, card
