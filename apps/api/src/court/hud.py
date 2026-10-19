"""HUD²: the match as the heads-up display draws it (the studio's /hud page, ADR 0012).

The HUD is one screen with lenses: the referee's, the commentator's and the fan's. Each lens draws
the same two things. First, where every action happened, straight from the event feed. Second, the
lines the Critic verified, anchored to the events they cite. This module gives the page the
first, and the numbers it shows beside them:

- `play`: one event, placed on the pitch as the camera sees it. Every event carries coordinates in
  its own team's frame (x = 0 its own goal line); here they become one fixed frame, x from the
  left goal line and y from the far touchline, with the ends changing at half-time.
- `pulse`: each side's counts for the last five minutes and the match so far, counted by
  court.metrics, the functions the Critic recomputes with. The page computes no number itself.
- `zones`: the referee's geometry under the match's strictness profile, from court.referee, so the
  zones the referee lens shades are the ones the likely calls are read against.

Nothing here writes a word about the match: words reach the HUD only as verified cues.
"""

from collections.abc import Iterable
from typing import Any

from match_events import (
    PITCH_LENGTH,
    PITCH_WIDTH,
    MatchEvent,
    MatchMeta,
    Pass,
    PossessionChange,
    Pressure,
    Shot,
    Side,
    Tackle,
    minute_label,
)

from .metrics import compute, is_box_entry, is_final_third_pass, is_high_ball_win, shot_xg
from .referee import (
    AREA_X,
    AREA_Y,
    CENTRAL_M,
    GOAL_CHANCE_M,
    PROMISING_X,
    Profile,
    distance_to_goal,
)

WINDOW_S = 300.0  # the pulse's recent stretch: the last five minutes of the half
PULSE_METRICS = (
    "shots",
    "xg",
    "passes",
    "passes_completed",
    "final_third_passes",
    "box_entries",
    "high_pressures",
    "high_ball_wins",
    "tackles_won",
    "fouls",
    "goals",
)


def attacks_right(team: Side, period: int, meta: MatchMeta) -> bool:
    """Whether a side attacks the right-hand goal in a period, as the camera sees it."""
    home_right = meta.home_attacks_right_first == (period == 1)
    return home_right if team is Side.HOME else not home_right


def place(x: float, y: float, team: Side, period: int, meta: MatchMeta) -> tuple[float, float]:
    """A point in a team's frame, in the camera's: turned half a circle when it attacks left."""
    if not attacks_right(team, period, meta):
        x, y = PITCH_LENGTH - x, PITCH_WIDTH - y
    return round(x, 1), round(y, 1)


def play(event: MatchEvent, meta: MatchMeta, names: dict[str, tuple[str, int]]) -> dict | None:
    """One action for the HUD, or None for an event with no place on the pitch (period marks)."""
    if not isinstance(event, Pass | Shot | Tackle | Pressure | PossessionChange):
        return None
    x, y = place(event.x, event.y, event.team, event.period, meta)
    out: dict[str, Any] = {
        "id": event.id,
        "seq": event.seq,
        "t": event.t,
        "period": event.period,
        "minute": minute_label(event.t, event.period),
        "kind": event.type,
        "team": event.team.value,
        "x": x,
        "y": y,
    }
    player = getattr(event, "player_id", None)
    if player:
        out["player"], out["number"] = names.get(player, ("", 0))
    if isinstance(event, Pass):
        out["ex"], out["ey"] = place(event.end_x, event.end_y, event.team, event.period, meta)
        out |= {"outcome": event.outcome.value, "cross": event.cross, "height": event.height}
        out["to"] = names.get(event.recipient_id, ("", 0))[0]
        out["final_third"] = is_final_third_pass(event)
        out["box"] = is_box_entry(event)
    elif isinstance(event, Shot):
        out |= {"outcome": event.outcome.value, "xg": round(shot_xg(event), 2)}
        out |= {"situation": event.situation, "body_part": event.body_part}
        out["speed_kmh"] = round(event.shot_speed_kmh)
    elif isinstance(event, Tackle):
        out["outcome"] = event.outcome
        out["opponent"] = names.get(event.opponent_id, ("", 0))[0]
        if event.outcome == "foul":
            # The facts a likely call rests on (court.referee): where, not how hard.
            out["to_goal_m"] = round(distance_to_goal(event), 1)
            out["in_area"] = event.x <= AREA_X and AREA_Y[0] <= event.y <= AREA_Y[1]
    elif isinstance(event, Pressure):
        out["target"] = names.get(event.target_player_id, ("", 0))[0]
        out["duration_s"] = round(event.duration_s, 1)
    else:
        out["reason"] = event.reason
        out["high"] = is_high_ball_win(event)
    return out


def pulse(events: Iterable[MatchEvent], now_t: float, period: int) -> dict[str, Any]:
    """Both sides' counts: the last five minutes of this half, and the match so far."""
    seen = list(events)
    recent = [e for e in seen if e.period == period and e.t > now_t - WINDOW_S]

    def counts(of: list[MatchEvent]) -> dict[str, dict[str, float]]:
        return {side.value: {m: compute(m, side, of) for m in PULSE_METRICS} for side in Side}

    out = {"minute": minute_label(now_t, period), "window_s": WINDOW_S}
    out |= {"recent": counts(recent), "match": counts(seen)}
    # Who had the ball lately, by passes: each side's share of the stretch's passes.
    passes = {side: out["recent"][side.value]["passes"] for side in Side}
    total = sum(passes.values())
    out["share"] = {s.value: round(100 * passes[s] / total) if total else None for s in Side}
    return out


def zones(profile: Profile) -> dict[str, float]:
    """The referee's geometry, in each defending side's frame (its own goal at x = 0)."""
    return {
        "area_x": AREA_X,
        "area_y0": AREA_Y[0],
        "area_y1": AREA_Y[1],
        "goal_chance_m": GOAL_CHANCE_M[profile],
        "central_m": CENTRAL_M,
        "promising_x": PROMISING_X[profile],
    }


def names_of(meta: MatchMeta) -> dict[str, tuple[str, int]]:
    return {p.id: (p.name, p.number) for p in meta.players}
