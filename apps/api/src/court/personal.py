"""Personal modes (§4.1 i e): the same verified broadcast, seen one viewer's way.

Nothing here writes a fact. A viewer's favourite club and player mark the cues that are theirs and
lift them up the overlay's queue; the other side's moments still air, marked as the rival's, since
a swing against your club is news too. Player focus keeps only one player's moments and counts the
rest, so nothing is lost without saying so. Single-metric mode follows one number for both sides.
The player card and the metric come from court.metrics, the functions the Critic recomputes claims
with, and each carries the events it counted.
"""

from collections.abc import Iterable, Sequence
from typing import Any

from match_events import (
    MatchEvent,
    MatchMeta,
    Pass,
    PassOutcome,
    Pressure,
    Shot,
    ShotOutcome,
    Side,
    Tackle,
)

from .contracts import Cue, Output, Preferences, TickerMetric
from .metrics import compute, is_final_third_pass, shot_xg

# How much a cue that is the viewer's own rises in the overlay's queue, per reason (club, player).
FOR_YOU_LIFT = 0.15

METRIC_LABELS: dict[TickerMetric, str] = {
    "xg": "Expected goals (xG)",
    "shots": "Shots",
    "box_entries": "Passes into the box",
    "final_third_passes": "Passes ending in the final third",
    "passes_completed": "Passes completed",
    "pass_completion": "Pass completion (%)",
}


class PreferenceError(ValueError):
    """The preferences don't fit this match: a player who isn't in it, or a focus with no player."""


def check(prefs: Preferences, meta: MatchMeta) -> Preferences:
    if prefs.player is not None and prefs.player not in {p.id for p in meta.players}:
        raise PreferenceError(f"no player {prefs.player!r} in this match")
    if prefs.focus == "player" and prefs.player is None:
        raise PreferenceError("player focus needs a favourite player")
    return prefs


class Personal:
    """Applies one viewer's preferences to the court's outputs, as they leave for the screen."""

    def __init__(self, prefs: Preferences, meta: MatchMeta) -> None:
        self.prefs = check(prefs, meta)
        self.hidden = 0  # cues player focus kept off this viewer's feed

    def view(self, output: Output) -> Output | None:
        """The output as this viewer sees it, or None when their focus leaves it out. Refusals,
        spiked claims and changes of service level always pass: the Critic's desk is everyone's.
        """
        if not isinstance(output, Cue):
            return output
        marks = self.marks(output)
        if self.prefs.focus == "player" and "player" not in marks:
            self.hidden += 1
            return None
        if not marks:
            return output
        lift = FOR_YOU_LIFT * sum(m != "rival" for m in marks)
        priority = round(min(1.0, output.priority + lift), 2)
        return output.model_copy(update={"for_you": marks, "priority": priority})

    def marks(self, cue: Cue) -> tuple[str, ...]:
        marks = []
        if self.prefs.club is not None:
            marks.append("club" if cue.team is self.prefs.club else "rival")
        if self.prefs.player is not None and any(p.id == self.prefs.player for p in cue.players):
            marks.append("player")
        return tuple(marks)


def player_card(player_id: str, meta: MatchMeta, events: Iterable[MatchEvent]) -> dict[str, Any]:
    """One player's match so far, counted from their own events, with the events it counted."""
    player = next(p for p in meta.players if p.id == player_id)
    events = list(events)
    shots_set_up = {e.assist_event_id for e in events if isinstance(e, Shot) and e.assist_event_id}
    passes, shots, tackles, pressures = [], [], [], []
    for e in events:
        if getattr(e, "player_id", None) != player_id:
            continue
        if isinstance(e, Pass):
            passes.append(e)
        elif isinstance(e, Shot):
            shots.append(e)
        elif isinstance(e, Tackle):
            tackles.append(e)
        elif isinstance(e, Pressure):
            pressures.append(e)
    completed = [p for p in passes if p.outcome is PassOutcome.COMPLETE]
    counted = passes + shots + tackles + pressures
    return {
        "player": {
            "id": player.id,
            "name": player.name,
            "number": player.number,
            "position": player.position,
            "team": player.team.value,
        },
        "passes": len(passes),
        "passes_completed": len(completed),
        "completion_pct": round(100 * len(completed) / len(passes)) if passes else None,
        "final_third_passes": sum(map(is_final_third_pass, passes)),
        "chances_created": sum(p.id in shots_set_up for p in completed),
        "shots": len(shots),
        "goals": sum(s.outcome is ShotOutcome.GOAL for s in shots),
        "xg": round(sum(shot_xg(s) for s in shots), 2),
        "tackles_won": sum(t.outcome == "won" for t in tackles),
        "pressures": len(pressures),
        "evidence": [e.id for e in sorted(counted, key=lambda e: e.seq)],
    }


def metric_value(metric: TickerMetric, side: Side, events: Sequence[MatchEvent]) -> float | None:
    """The single metric for one side, as court.metrics computes it."""
    if metric != "pass_completion":
        return compute(metric, side, events)
    attempted = compute("passes", side, events)
    return round(100 * compute("passes_completed", side, events) / attempted) if attempted else None


def metric_line(metric: TickerMetric, events: Sequence[MatchEvent]) -> dict[str, Any]:
    """The single metric for both sides so far, and how many events it was counted from."""
    kind = Shot if metric in ("xg", "shots") else Pass
    return {
        "metric": metric,
        "label": METRIC_LABELS[metric],
        "home": metric_value(metric, Side.HOME, events),
        "away": metric_value(metric, Side.AWAY, events),
        "counted": sum(isinstance(e, kind) for e in events),
    }
