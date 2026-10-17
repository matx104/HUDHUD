import pytest
from support import first_goal, state_until

from court.contracts import AlertKind, Claim, RejectionCode
from court.critic import Critic
from court.narrator import TemplateNarrator
from court.scout import Scout
from court.state import MatchState
from match_events import Pass


@pytest.fixture
def goal_case(match):
    """State and Scout alert at the moment of the first goal."""
    shot = first_goal(match)
    state, scout = MatchState(match.meta), Scout()
    alert = None
    for event in match.events[: shot.seq + 1]:
        state.apply(event)
        alert = next((a for a in scout.observe(event, state) if a.kind is AlertKind.GOAL), alert)
    assert alert is not None
    return state, alert


def codes(verdict) -> set[RejectionCode]:
    return {r.code for r in verdict.reasons}


def test_faithful_goal_claim_is_approved(goal_case):
    state, alert = goal_case
    claim = TemplateNarrator().draft(alert, state)
    verdict = Critic().review(claim, state)
    assert verdict.approved, verdict.reasons


def test_uncited_claim_is_rejected(goal_case):
    state, alert = goal_case
    claim = TemplateNarrator().draft(alert, state).model_copy(update={"citations": ()})
    assert RejectionCode.NO_EVIDENCE in codes(Critic().review(claim, state))


def test_claim_citing_the_future_is_rejected(goal_case):
    state, alert = goal_case
    claim = TemplateNarrator().draft(alert, state)
    future = claim.model_copy(
        update={"citations": (*claim.citations, f"e{alert.as_of_seq + 1:05d}")}
    )
    assert codes(Critic().review(future, state)) == {RejectionCode.FUTURE_EVENT}


def test_claim_citing_an_unknown_event_is_rejected(goal_case):
    state, alert = goal_case
    claim = TemplateNarrator().draft(alert, state)
    bogus = claim.model_copy(update={"citations": (*claim.citations, "not-an-event")})
    assert codes(Critic().review(bogus, state)) == {RejectionCode.UNKNOWN_EVENT}


def test_inflated_number_fails_independent_recomputation(goal_case):
    state, alert = goal_case
    inflated = alert.model_copy(
        update={"metrics": {**alert.metrics, "xg": alert.metrics["xg"] + 0.3}}
    )
    claim = TemplateNarrator().draft(inflated, state)
    verdict = Critic().review(claim, state)
    assert codes(verdict) == {RejectionCode.ASSERTION_MISMATCH}
    assert "events show" in verdict.reasons[0].detail


def test_goal_claim_must_cite_the_scoring_shot(goal_case):
    state, alert = goal_case
    claim = TemplateNarrator().draft(alert, state)
    a_pass = next(e for e in state.events if isinstance(e, Pass) and e.period == claim.period)
    swapped = claim.model_copy(update={"citations": (a_pass.id,)})
    assert RejectionCode.INSUFFICIENT_EVIDENCE in codes(
        Critic(max_evidence_age_s=1e9).review(swapped, state)
    )


def test_evidence_from_another_period_is_stale(match):
    second_half = next(e for e in match.events if e.period == 2 and e.type == "pass")
    first_half = next(e for e in match.events if e.type == "pass")
    state = state_until(match, second_half.seq)
    claim = Claim(
        id="a9999.1",
        alert_id="a9999",
        attempt=1,
        kind=AlertKind.BIG_CHANCE,
        team=first_half.team,
        period=2,
        t=second_half.t,
        as_of_seq=second_half.seq,
        severity=0.5,
        headline="h",
        text="t",
        citations=(first_half.id,),
    )
    assert RejectionCode.STALE_EVENT in codes(Critic().review(claim, state))


def test_unregistered_claim_kind_fails_closed(goal_case):
    state, alert = goal_case
    claim = TemplateNarrator().draft(alert, state)
    verdict = Critic(rules={}).review(claim, state)
    assert codes(verdict) == {RejectionCode.NO_RULE}
    assert not verdict.rewritable


def test_scouted_momentum_numbers_survive_recomputation(swing_match):
    """Whatever evidence rule the Critic adopts, the numbers a momentum line states must be
    the numbers the raw events give: the Scout and the Critic share one set of metrics."""
    match = swing_match
    state, scout, narrator = MatchState(match.meta), Scout(), TemplateNarrator()
    lenient = Critic(rules={AlertKind.MOMENTUM_SWING: lambda claim, cited: None})
    checked = 0
    for event in match.events:
        state.apply(event)
        for alert in scout.observe(event, state):
            if alert.kind is not AlertKind.MOMENTUM_SWING:
                continue
            verdict = lenient.review(narrator.draft(alert, state), state)
            assert verdict.approved, verdict.reasons
            checked += 1
    assert checked, "seed 21 should produce momentum swings"


def test_a_number_the_claim_cannot_account_for_is_refused(goal_case):
    state, alert = goal_case
    claim = TemplateNarrator().draft(alert, state)
    invented = claim.model_copy(update={"text": claim.text + " His 12th of the season."})
    verdict = Critic().review(invented, state)
    assert [r.code for r in verdict.reasons] == [RejectionCode.UNGROUNDED_NUMBER]
    assert "12" in verdict.reasons[0].detail
    assert Critic().review(claim, state).approved  # every number in the template line is grounded
