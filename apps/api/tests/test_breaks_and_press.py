"""Counterattacks and the high press: how the ball is won back, called and checked."""

import asyncio
from collections import Counter

import pytest

from court.contracts import AlertKind, Cue, RejectionCode
from court.critic import Critic
from court.describe import describe
from court.narrator import TemplateNarrator
from court.orchestrator import run_match
from court.scout import Scout
from court.state import MatchState
from match_events import PossessionChange, generate


def _alerts(seed: int):
    match = generate(seed)
    state, scout, found = MatchState(match.meta), Scout(), []
    for event in match.events:
        state.apply(event)
        found.extend(scout.observe(event, state))
    return state, found


def test_both_come_at_the_rate_they_were_designed_for():
    kinds = Counter(a.kind for seed in range(30) for a in _alerts(seed)[1])
    assert 0.3 <= kinds[AlertKind.COUNTER] / 30 <= 1.0
    assert 1.0 <= kinds[AlertKind.HIGH_PRESS] / 30 <= 3.0


@pytest.fixture(scope="module")
def seed21():
    state, alerts = _alerts(21)
    counter = next(a for a in alerts if a.kind is AlertKind.COUNTER)
    press = next(a for a in alerts if a.kind is AlertKind.HIGH_PRESS)
    return state, counter, press


def test_the_lines_say_what_the_events_show_and_pass(seed21):
    state, counter, press = seed21
    critic, narrator = Critic(), TemplateNarrator()
    for alert in (counter, press):
        claim = narrator.draft(alert, state)
        assert critic.review(claim, state).approved, claim.text
    line = narrator.draft(counter, state).text
    assert "the ball won in their own half" in line and "seconds later" in line
    assert "keep winning the ball high" in narrator.draft(press, state).text


def test_a_break_must_start_in_the_sides_own_half(seed21):
    state, counter, _ = seed21
    claim = TemplateNarrator().draft(counter, state)
    win = state.get(claim.citations[0])
    assert isinstance(win, PossessionChange) and win.x < 52.5
    without = claim.model_copy(update={"citations": claim.citations[1:]})
    reasons = Critic().review(without, state).reasons
    assert [r.code for r in reasons] == [RejectionCode.INSUFFICIENT_EVIDENCE]


def test_the_press_needs_enough_wins_and_true_numbers(seed21):
    state, _, press = seed21
    claim = TemplateNarrator().draft(press, state)
    short = claim.model_copy(update={"citations": claim.citations[:3]})
    assert "needs 4 high ball wins" in Critic().review(short, state).reasons[0].detail
    inflated = TemplateNarrator().overreach(claim, press, state)
    for _ in range(10):  # the overreach style is random: find the inflated number
        if inflated.citations == claim.citations and inflated.text != claim.text:
            break
        inflated = TemplateNarrator(seed=_ + 1).overreach(claim, press, state)
    codes = {r.code for r in Critic().review(inflated, state).reasons}
    assert codes & {
        RejectionCode.ASSERTION_MISMATCH,
        RejectionCode.NO_EVIDENCE,
        RejectionCode.FUTURE_EVENT,
    }


def test_a_ball_win_reads_plainly_in_the_evidence(seed21):
    state, counter, _ = seed21
    win = state.get(counter.evidence[0])
    assert describe(win, state).startswith("Ball won by Brackenfield (")
    assert "m from their own goal" in describe(win, state)


def test_they_air_live_with_their_players(swing_match):
    outputs = []
    asyncio.run(run_match(swing_match.stream(), sink=outputs.append))
    cues = [o for o in outputs if isinstance(o, Cue)]
    counter = next(c for c in cues if c.kind is AlertKind.COUNTER)
    assert counter.status == "verified" and any(p.role == "shooter" for p in counter.players)
    assert any(c.kind is AlertKind.HIGH_PRESS and c.status == "verified" for c in cues)
