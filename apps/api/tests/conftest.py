import pytest

from court.state import MatchState
from match_events import SyntheticMatch, generate


@pytest.fixture(scope="session")
def match() -> SyntheticMatch:
    return generate(7)


@pytest.fixture(scope="session")
def swing_match() -> SyntheticMatch:
    """A 2-2 draw whose two momentum calls are both real. Seed 7 raises none at the Scout's
    sure-call defaults, which is the point of them."""
    return generate(21)


@pytest.fixture
def full_state(match: SyntheticMatch) -> MatchState:
    state = MatchState(match.meta)
    for event in match.events:
        state.apply(event)
    return state
