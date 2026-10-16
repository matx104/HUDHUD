import pytest

from court.state import MatchState
from match_events import SyntheticMatch, generate


@pytest.fixture(scope="session")
def match() -> SyntheticMatch:
    return generate(7)


@pytest.fixture
def full_state(match: SyntheticMatch) -> MatchState:
    state = MatchState(match.meta)
    for event in match.events:
        state.apply(event)
    return state
