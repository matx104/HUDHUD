from court.contracts import Alert, AlertKind, Window
from court.narrator import TemplateNarrator
from court.state import MatchState
from match_events import Side


def _swing(match, **metrics: float) -> tuple[Alert, MatchState]:
    alert = Alert(
        id="a0001",
        kind=AlertKind.MOMENTUM_SWING,
        team=Side.HOME,
        period=1,
        t=1200.0,
        as_of_seq=500,
        severity=0.7,
        evidence=("e00490", "e00495", "e00499"),
        window=Window(period=1, start_t=900.0, end_t=1200.0),
        metrics={
            "score": 2.1,
            "passes": 46,
            "passes_completed": 41,
            "base_passes": 120,
            "base_passes_completed": 91,
            "base_start_t": 0.0,
            "final_third": 14,
            "opp_final_third": 4,
            "shots": 2,
            "xg": 0.4,
            "window_s": 300,
            **metrics,
        },
    )
    return alert, MatchState(match.meta)


def test_momentum_line_says_the_numbers_the_critic_will_check(match):
    alert, state = _swing(match)
    claim = TemplateNarrator().draft(alert, state)
    home, away = match.meta.home.name, match.meta.away.name
    assert claim.text == (
        f"{home} have taken control, completing 41 of 46 passes in the last 5 minutes "
        f"(89%, up from 76% earlier in the half). 14 of them ended in the final third, "
        f"against 4 for {away}."
    )
    asserted = {(a.metric, a.team, a.window.start_t): a.value for a in claim.assertions}
    assert asserted[("passes_completed", Side.HOME, 900.0)] == 41
    assert asserted[("passes", Side.HOME, 0.0)] == 120  # the "earlier in the half" baseline
    assert asserted[("final_third_passes", Side.AWAY, 900.0)] == 4


def test_momentum_counts_read_as_english_in_the_singular(match):
    alert, state = _swing(
        match, passes=1, passes_completed=1, final_third=1, base_passes=0, window_s=60
    )
    text = TemplateNarrator().draft(alert, state).text
    assert "completing 1 of 1 pass in the last minute (100%)." in text
    assert "1 of them ended in the final third, against 4 for" in text


def test_a_fall_in_completion_is_said_plainly(match):
    alert, state = _swing(match, passes_completed=30)
    assert "(65%, down from 76% earlier in the half)" in TemplateNarrator().draft(alert, state).text
