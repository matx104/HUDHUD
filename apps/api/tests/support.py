"""Test helpers (importable via the `pythonpath` setting in the root pyproject)."""

from court.state import MatchState
from match_events import Shot, ShotOutcome, SyntheticMatch


def state_until(match: SyntheticMatch, seq: int) -> MatchState:
    """Shared state as it stood the moment event `seq` was ingested."""
    state = MatchState(match.meta)
    for event in match.events[: seq + 1]:
        state.apply(event)
    return state


def first_goal(match: SyntheticMatch) -> Shot:
    return next(e for e in match.events if isinstance(e, Shot) and e.outcome is ShotOutcome.GOAL)
