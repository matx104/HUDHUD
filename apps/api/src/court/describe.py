"""Plain-English descriptions of match events, one wording everywhere.

The site's evidence chain and the fact sheet a model narrates from use the same lines, so
what the viewer reads is what the model read.
"""

from match_events import MatchEvent, Pass, PossessionChange, Shot

from .metrics import shot_distance, shot_xg
from .state import MatchState


def describe(event: MatchEvent, state: MatchState) -> str:
    name = state.player_name
    match event:
        case Shot():
            where = "penalty" if event.situation == "penalty" else f"{shot_distance(event):.0f} m"
            outcome = event.outcome.replace("_", " ")
            return f"Shot by {name(event.player_id)}, {where}, {outcome}, xG {shot_xg(event):.2f}"
        case Pass():
            to = name(event.recipient_id)
            return f"Pass from {name(event.player_id)} to {to}, {event.distance_m:.0f} m"
        case PossessionChange(reason="interception" | "tackle"):
            team = state.meta.team(event.team).name
            return f"Ball won by {team} ({event.reason}), {event.x:.0f} m from their own goal"
        case _:
            reason = getattr(event, "reason", None)
            label = event.type.replace("_", " ").capitalize()
            return f"{label} ({reason.replace('_', ' ')})" if reason else label
