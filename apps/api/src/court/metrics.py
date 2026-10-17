"""Football metrics, computed one way only. The Scout uses these to detect and the
Critic uses the same functions to recompute every number a claim asserts."""

import math
from collections.abc import Iterable

from match_events import PITCH_LENGTH, MatchEvent, Pass, PassOutcome, Shot, ShotOutcome, Side

from .contracts import Assertion
from .state import MatchState

GOAL_Y = 34.0
BOX_X = 88.5
BOX_Y = (13.84, 54.16)
PENALTY_XG = 0.76


def shot_distance(shot: Shot) -> float:
    """Metres from the shot to the centre of the goal mouth."""
    return math.hypot(PITCH_LENGTH - shot.x, GOAL_Y - shot.y)


def shot_xg(shot: Shot) -> float:
    """Expected goals: logistic in distance and the angle the goal mouth subtends."""
    if shot.situation == "penalty":
        return PENALTY_XG
    dx, dy = PITCH_LENGTH - shot.x, abs(GOAL_Y - shot.y)
    angle = math.atan2(7.32 * dx, dx * dx + dy * dy - (7.32 / 2) ** 2)
    if angle < 0:
        angle += math.pi
    logit = -1.1 - 0.10 * shot_distance(shot) + 1.6 * angle
    logit -= 0.9 * (shot.body_part == "head") + 0.25 * shot.under_pressure
    return 1 / (1 + math.exp(-logit))


def in_box(x: float, y: float) -> bool:
    return x >= BOX_X and BOX_Y[0] <= y <= BOX_Y[1]


def is_box_entry(event: MatchEvent) -> bool:
    return (
        isinstance(event, Pass)
        and event.outcome is PassOutcome.COMPLETE
        and in_box(event.end_x, event.end_y)
        and not in_box(event.x, event.y)
    )


def compute(metric: str, team: Side, events: Iterable[MatchEvent]) -> float:
    mine = [e for e in events if getattr(e, "team", None) == team]
    if metric == "goals":
        return sum(isinstance(e, Shot) and e.outcome is ShotOutcome.GOAL for e in mine)
    if metric == "shots":
        return sum(isinstance(e, Shot) for e in mine)
    if metric == "xg":
        return round(sum(shot_xg(e) for e in mine if isinstance(e, Shot)), 2)
    if metric == "box_entries":
        return sum(is_box_entry(e) for e in mine)
    raise ValueError(f"unknown metric {metric!r}")


def measure(assertion: Assertion, state: MatchState, as_of_seq: int) -> float | None:
    """Recompute an assertion from raw events. None means it can't be measured."""
    if assertion.metric == "shot_xg":
        shot = state.get(assertion.event_id or "")
        if not isinstance(shot, Shot) or shot.seq > as_of_seq:
            return None
        return round(shot_xg(shot), 2)
    if assertion.window is None:
        events: Iterable[MatchEvent] = state.until(as_of_seq)
    else:
        events = state.in_window(assertion.window, as_of_seq=as_of_seq)
    return compute(assertion.metric, assertion.team, events)
