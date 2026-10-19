"""Player tags: who a cue is about, with speed and distance badges when a threshold is reached.

The rules ask for player identification "with speed and distance tags when thresholds are
reached" (§4.1). Tags come from the cue's own cited events, computed here from raw fields: no
model writes them, so there is nothing for the Critic to doubt.
"""

from collections import Counter

from match_events import Pass, PassOutcome, PossessionChange, Shot, ShotOutcome, Tackle

from .contracts import AlertKind, Cue, PlayerTag
from .metrics import event_metric
from .state import MatchState

FAST_SHOT_KMH = 110  # about the fastest quarter of shots (seeds 0-39)
LONG_PASS_M = 30  # about the longest tenth of completed passes into the final third
HARD_PASS = 40  # pass difficulty out of 100, as for the Scout's great pass


def player_tags(cue: Cue, state: MatchState) -> tuple[PlayerTag, ...]:
    cited = [e for e in (state.get(i) for i in cue.evidence) if e is not None]
    if cue.kind in (AlertKind.MOMENTUM_SWING, AlertKind.HIGH_PRESS):
        # A spell has many hands: tag the two players behind most of the cited actions.
        counts = Counter(_actor(e, state) for e in cited)
        return tuple(_tag(state, pid, "involved", ()) for pid, _ in counts.most_common(2) if pid)
    if cue.kind is AlertKind.REF_CALL:
        foul = next((e for e in cited if isinstance(e, Tackle)), None)
        if foul is None:
            return ()
        tags = (
            _tag(state, foul.player_id, "offender", ()),
            _tag(state, foul.opponent_id, "fouled", ()),
        )
        return tuple(t for t in tags if t is not None)
    shots = [e for e in cited if isinstance(e, Shot)]
    assists = {s.assist_event_id for s in shots}
    tags = []
    for event in cited:
        if isinstance(event, Shot):
            role = "scorer" if event.outcome is ShotOutcome.GOAL else "shooter"
            tags.append(_tag(state, event.player_id, role, _shot_badges(event)))
        elif isinstance(event, Pass) and event.outcome is PassOutcome.COMPLETE:
            role = "assister" if event.id in assists else "passer"
            tags.append(_tag(state, event.player_id, role, _pass_badges(event)))
    return tuple(t for t in tags if t is not None)


def _actor(event, state: MatchState) -> str | None:
    """Who did it. A ball won by a tackle is the tackler's; an interception names no one."""
    if isinstance(event, PossessionChange):
        cause = state.get(event.cause_event_id or "")
        return cause.player_id if isinstance(cause, Tackle) and cause.team == event.team else None
    return getattr(event, "player_id", None)


def _shot_badges(shot: Shot) -> tuple[str, ...]:
    speed = event_metric("shot_speed", shot)
    return (f"{speed:.0f} km/h shot",) if speed >= FAST_SHOT_KMH else ()


def _pass_badges(pass_: Pass) -> tuple[str, ...]:
    badges = []
    if (distance := event_metric("pass_distance", pass_)) >= LONG_PASS_M:
        badges.append(f"{distance:.0f} m pass")
    if (difficulty := event_metric("pass_difficulty", pass_)) >= HARD_PASS:
        badges.append(f"difficulty {difficulty:.0f}")
    return tuple(badges)


def _tag(state: MatchState, player_id: str, role: str, badges) -> PlayerTag | None:
    player = state.player(player_id)
    if player is None:
        return None
    return PlayerTag(
        id=player.id,
        name=player.name,
        number=player.number,
        position=player.position,
        team=player.team,
        role=role,
        badges=tuple(badges),
    )
