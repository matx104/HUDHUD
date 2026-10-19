"""Ref's call: a foul that matters, the referee's likely decision, recomputed by the Critic."""

import pytest

from court.contracts import AlertKind, RefCall
from court.critic import Critic
from court.narrator import TemplateNarrator
from court.referee import PROFILES, call, matters
from court.scout import Scout
from court.state import MatchState
from match_events import Tackle, generate


def _foul(**fields) -> Tackle:
    base = {"id": "e00100", "seq": 100, "t": 600.0, "period": 1, "team": "home", "possession": 9}
    base |= {"player_id": "h05", "opponent_id": "a09", "outcome": "foul"}
    return Tackle(**(base | fields))


def test_the_restart_follows_where_the_foul_was():
    assert call(_foul(x=10.0, y=34.0)).restart == "penalty"
    assert call(_foul(x=10.0, y=5.0)).restart == "free_kick", "wide of the area"
    assert call(_foul(x=40.0, y=34.0)).restart == "free_kick"
    assert call(_foul(x=10.0, y=34.0, outcome="won")) is None, "a clean tackle is no foul"


def test_strictness_changes_the_card_not_the_restart():
    just_outside = _foul(x=19.5, y=34.0)  # central, 19.5 m out
    assert {p: call(just_outside, p).card for p in PROFILES} == {
        "lenient": "none",
        "standard": "red",
        "strict": "red",
    }, "a clear chance denied outside the area is a red, unless the game is called leniently"
    assert {call(just_outside, p).restart for p in PROFILES} == {"free_kick"}
    halfway = _foul(x=45.0, y=20.0)  # the opponent's half, not their attacking third
    assert [call(halfway, p).card for p in PROFILES] == ["none", "none", "yellow"]
    in_area = _foul(x=8.0, y=34.0)
    assert call(in_area, "standard") == RefCall(
        restart="penalty", card="yellow", profile="standard", reason="goal_chance"
    ), "a challenge for the ball in the area: a penalty and a yellow, not a red"


def test_the_critic_judges_by_the_competitions_profile_not_the_claims():
    from court.contracts import Claim
    from court.critic import ref_rule

    foul = _foul(x=19.5, y=34.0)
    red = call(foul, "standard")
    claim = Claim(
        id="a1.1", alert_id="a1", attempt=1, kind=AlertKind.REF_CALL, team=foul.team,
        period=1, t=600.0, as_of_seq=100, severity=0.9, headline="REF'S CALL",
        text="A foul 20 m out: likely a direct free kick, and a red card.",
        citations=(foul.id,), call=red,
    )  # fmt: skip
    assert ref_rule("standard")(claim, [foul]) is None
    assert "the Law gives a direct free kick and no card" in ref_rule("lenient")(claim, [foul])


@pytest.fixture(scope="module")
def penalty_call():
    match = generate(21)
    state, scout = MatchState(match.meta), Scout()
    for event in match.events:
        state.apply(event)
        for alert in scout.observe(event, state):
            if alert.kind is AlertKind.REF_CALL and alert.call.restart == "penalty":
                return state, alert
    raise AssertionError("seed 21 has a penalty")


def test_the_line_states_the_decision_and_passes(penalty_call):
    state, alert = penalty_call
    claim = TemplateNarrator().draft(alert, state)
    assert "likely a penalty, and a yellow card" in claim.text
    assert Critic().review(claim, state).approved


def test_a_harsher_card_than_the_law_gives_is_refused(penalty_call):
    state, alert = penalty_call
    claim = TemplateNarrator().draft(alert, state)
    red = claim.model_copy(update={"call": claim.call.model_copy(update={"card": "red"})})
    detail = Critic().review(red, state).reasons[0].detail
    assert "at standard strictness the Law gives a penalty and a yellow card" in detail


def test_the_decision_must_be_said_not_only_carried(penalty_call):
    state, alert = penalty_call
    claim = TemplateNarrator().draft(alert, state)
    vague = claim.model_copy(update={"text": "A foul, and the referee points somewhere."})
    assert "must say the decision" in Critic().review(vague, state).reasons[0].detail


def test_calls_come_at_a_believable_rate():
    calls = {p: 0 for p in PROFILES}
    for seed in range(20):
        events = generate(seed).events
        for p in PROFILES:
            calls[p] += sum(matters(call(e, p)) for e in events if isinstance(e, Tackle))
    assert calls["lenient"] < calls["standard"] <= calls["strict"]
    assert 1.0 <= calls["standard"] / 20 <= 3.5
