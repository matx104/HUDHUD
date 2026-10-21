"""Control or chaos: a match broken open, called, checked and shown on the HUD's pulse."""

import asyncio
from collections import Counter

import pytest

from court.contracts import AlertKind, Cue, RejectionCode
from court.critic import Critic
from court.hud import pulse
from court.localizer import AWAITING_REVIEW, Localizer
from court.metrics import is_ball_win
from court.narrator import TemplateNarrator
from court.orchestrator import run_match
from court.scout import END_TO_END_WINS, Scout
from court.state import MatchState
from match_events import Shot, Side, generate


def _alerts(seed: int):
    match = generate(seed)
    state, scout, found = MatchState(match.meta), Scout(), []
    for event in match.events:
        state.apply(event)
        found.extend(scout.observe(event, state))
    return state, found


@pytest.fixture(scope="module")
def seed5():
    state, alerts = _alerts(5)
    return state, next(a for a in alerts if a.kind is AlertKind.END_TO_END)


def test_it_comes_at_the_rate_it_was_designed_for():
    kinds = Counter(a.kind for seed in range(30) for a in _alerts(seed)[1])
    assert 0.2 <= kinds[AlertKind.END_TO_END] / 30 <= 1.0


def test_it_stands_on_ball_wins_and_a_shot_at_each_end(seed5):
    state, alert = seed5
    cited = [state.get(i) for i in alert.evidence]
    assert sum(map(is_ball_win, cited)) >= END_TO_END_WINS
    assert {e.team for e in cited if isinstance(e, Shot)} == set(Side)
    shot = state.get(alert.evidence[-1])
    assert isinstance(shot, Shot) and shot.outcome.value != "goal"


def test_the_line_says_what_the_events_show_and_passes(seed5):
    state, alert = seed5
    claim = TemplateNarrator().draft(alert, state)
    assert Critic().review(claim, state).approved, claim.text
    changes = alert.metrics["wins"] + alert.metrics["opp_wins"]
    assert claim.text.startswith(
        f"The match has broken open: the ball has changed hands {changes:.0f} "
    )
    assert claim.headline == "END TO END · " + " v ".join(
        (state.meta.home.short_name, state.meta.away.short_name)
    )


def test_it_needs_enough_ball_wins_and_both_ends(seed5):
    state, alert = seed5
    claim = TemplateNarrator().draft(alert, state)
    critic = Critic()
    wins = [i for i in claim.citations if is_ball_win(state.get(i))]
    short = claim.model_copy(update={"citations": tuple(wins[:5])})
    assert "needs 11 ball wins" in critic.review(short, state).reasons[0].detail
    no_shots = claim.model_copy(update={"citations": tuple(wins)})
    reasons = critic.review(no_shots, state).reasons
    assert [r.code for r in reasons] == [RejectionCode.INSUFFICIENT_EVIDENCE]
    assert "a shot from each side" in reasons[0].detail


def test_an_inflated_count_is_refused(seed5):
    state, alert = seed5
    claim = TemplateNarrator().draft(alert, state)
    for seed in range(10):  # the overreach style is random: find the inflated number
        inflated = TemplateNarrator(seed=seed).overreach(claim, alert, state)
        if inflated.citations == claim.citations and inflated.text != claim.text:
            break
    codes = {r.code for r in Critic().review(inflated, state).reasons}
    assert codes & {RejectionCode.ASSERTION_MISMATCH, RejectionCode.NO_EVIDENCE}


def test_its_headline_stays_english_until_the_owner_signs_it_off(seed5):
    state, alert = seed5
    assert "END TO END" in AWAITING_REVIEW
    cue = Localizer(lang="ur").detection_cue(alert, state)
    assert cue.headline.startswith("END TO END · ")


def test_the_pulse_carries_the_control_or_chaos_index(seed5):
    state, alert = seed5
    events = list(state.until(alert.as_of_seq))
    p = pulse(events, alert.t, alert.period)
    assert p["tempo"]["broken"] == END_TO_END_WINS
    assert p["tempo"]["changes"] >= END_TO_END_WINS
    assert p["tempo"]["changes"] == sum(p["recent"][s.value]["ball_wins"] for s in Side)


def test_it_airs_live():
    outputs = []
    asyncio.run(run_match(generate(5).stream(), sink=outputs.append))
    cues = [o for o in outputs if isinstance(o, Cue) and o.kind is AlertKind.END_TO_END]
    assert cues and all(c.status == "verified" for c in cues)
    assert any(p.role == "involved" for p in cues[0].players)
