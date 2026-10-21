"""Football metrics, computed one way only. The Scout uses these to detect and the
Critic uses the same functions to recompute every number a claim asserts."""

import math
from collections.abc import Iterable

from match_events import (
    PITCH_LENGTH,
    MatchEvent,
    Pass,
    PassOutcome,
    PossessionChange,
    Pressure,
    Shot,
    ShotOutcome,
    Side,
    Tackle,
)

from .contracts import Assertion
from .state import MatchState

GOAL_Y = 34.0
BOX_X = 88.5
BOX_Y = (13.84, 54.16)
PENALTY_XG = 0.76
FINAL_THIRD_X = 70.0


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


def is_final_third_pass(event: MatchEvent) -> bool:
    """A completed pass that ends in the attacking third."""
    return (
        isinstance(event, Pass)
        and event.outcome is PassOutcome.COMPLETE
        and event.end_x >= FINAL_THIRD_X
    )


def is_ball_win(event: MatchEvent) -> bool:
    """A possession won off the opponent: a tackle or an interception, not a restart."""
    return isinstance(event, PossessionChange) and event.reason in ("interception", "tackle")


def is_high_ball_win(event: MatchEvent) -> bool:
    """The ball won in the attacking third (the winning side's frame): the press paying off."""
    return is_ball_win(event) and event.x >= FINAL_THIRD_X


def is_high_pressure(event: MatchEvent) -> bool:
    """A press on the ball in the attacking third (the pressing side's frame)."""
    return isinstance(event, Pressure) and event.x >= FINAL_THIRD_X


def compute(
    metric: str, team: Side, events: Iterable[MatchEvent], player_id: str | None = None
) -> float:
    """A side's count, or with `player_id` one player's: only the events that player made."""
    mine = [
        e
        for e in events
        if getattr(e, "team", None) == team
        and (player_id is None or getattr(e, "player_id", None) == player_id)
    ]
    if metric == "goals":
        return sum(isinstance(e, Shot) and e.outcome is ShotOutcome.GOAL for e in mine)
    if metric == "shots":
        return sum(isinstance(e, Shot) for e in mine)
    if metric == "xg":
        return round(sum(shot_xg(e) for e in mine if isinstance(e, Shot)), 2)
    if metric == "box_entries":
        return sum(is_box_entry(e) for e in mine)
    if metric == "passes":
        return sum(isinstance(e, Pass) for e in mine)
    if metric == "passes_completed":
        return sum(isinstance(e, Pass) and e.outcome is PassOutcome.COMPLETE for e in mine)
    if metric == "final_third_passes":
        return sum(is_final_third_pass(e) for e in mine)
    if metric == "ball_wins":
        return sum(is_ball_win(e) for e in mine)
    if metric == "high_ball_wins":
        return sum(is_high_ball_win(e) for e in mine)
    if metric == "high_pressures":
        return sum(is_high_pressure(e) for e in mine)
    if metric == "tackles_won":
        return sum(isinstance(e, Tackle) and e.outcome == "won" for e in mine)
    if metric == "fouls":
        return sum(isinstance(e, Tackle) and e.outcome == "foul" for e in mine)
    raise ValueError(f"unknown metric {metric!r}")


# Metrics of one event, as a broadcast states them. The Scout, the Narrator and the Critic all
# read them here, so a claim's number and its recomputation can't drift apart.
EVENT_METRICS = {
    "shot_xg": (Shot, lambda e: round(shot_xg(e), 2)),
    "shot_speed": (Shot, lambda e: round(e.shot_speed_kmh)),
    "pass_distance": (Pass, lambda e: round(e.distance_m)),
    "pass_difficulty": (Pass, lambda e: round(100 * e.difficulty)),
    "pass_accuracy": (Pass, lambda e: round(100 * e.accuracy)),
    "ball_speed": (Pass, lambda e: round(e.ball_speed_kmh)),
}


def event_metric(metric: str, event: MatchEvent) -> float:
    kind, value = EVENT_METRICS[metric]
    if not isinstance(event, kind):
        raise ValueError(f"{metric} is measured on a {kind.__name__.lower()}")
    return value(event)


def measure(assertion: Assertion, state: MatchState, as_of_seq: int) -> float | None:
    """Recompute an assertion from raw events. None means it can't be measured."""
    if assertion.metric in EVENT_METRICS:
        event = state.get(assertion.event_id or "")
        kind, value = EVENT_METRICS[assertion.metric]
        if not isinstance(event, kind) or event.seq > as_of_seq:
            return None
        return value(event)
    if assertion.window is None:
        events: Iterable[MatchEvent] = state.until(as_of_seq)
    else:
        events = state.in_window(assertion.window, as_of_seq=as_of_seq)
    return compute(assertion.metric, assertion.team, events, assertion.player_id)
