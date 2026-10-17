from support import state_until

from court.contracts import AlertKind
from court.metrics import PENALTY_XG, is_box_entry, shot_xg
from court.scout import Scout
from court.state import MatchState
from match_events import Pass, PassOutcome, Shot, ShotOutcome, Side


def _shot(**over) -> Shot:
    base = dict(
        id="e00001",
        seq=1,
        t=60,
        period=1,
        team=Side.HOME,
        possession=1,
        player_id="h10",
        x=94,
        y=34,
        body_part="right_foot",
        situation="open_play",
        outcome=ShotOutcome.SAVED,
        shot_speed_kmh=90,
        under_pressure=False,
    )
    return Shot(**{**base, **over})


def test_xg_behaves_like_football():
    assert shot_xg(_shot(situation="penalty")) == PENALTY_XG
    assert shot_xg(_shot(x=100)) > shot_xg(_shot(x=94)) > shot_xg(_shot(x=80))
    assert shot_xg(_shot(body_part="head")) < shot_xg(_shot())
    assert shot_xg(_shot(y=34)) > shot_xg(_shot(y=12))  # central beats tight angle
    assert shot_xg(_shot(under_pressure=True)) < shot_xg(_shot())


def test_box_entry_needs_a_completed_pass_from_outside_into_the_box():
    p = dict(
        id="e00002",
        seq=2,
        t=61,
        period=1,
        team=Side.HOME,
        possession=1,
        player_id="h08",
        recipient_id="h09",
        x=80,
        y=34,
        end_x=95,
        end_y=34,
        outcome=PassOutcome.COMPLETE,
        height="ground",
        cross=False,
        distance_m=15,
        ball_speed_kmh=50,
        difficulty=0.2,
        accuracy=0.9,
        under_pressure=False,
    )
    assert is_box_entry(Pass(**p))
    assert not is_box_entry(Pass(**{**p, "outcome": PassOutcome.INTERCEPTED}))
    assert not is_box_entry(Pass(**{**p, "x": 90}))  # already inside


def _scout_run(match):
    state, scout, alerts = MatchState(match.meta), Scout(), []
    for event in match.events:
        state.apply(event)
        alerts.extend(scout.observe(event, state))
    return alerts


def test_every_goal_raises_exactly_one_goal_alert_citing_the_shot(match):
    goals = [e for e in match.events if isinstance(e, Shot) and e.outcome is ShotOutcome.GOAL]
    alerts = [a for a in _scout_run(match) if a.kind is AlertKind.GOAL]
    assert [a.evidence[-1] for a in alerts] == [g.id for g in goals]


def test_scout_never_cites_the_future_or_the_unknown(match):
    by_id = {e.id: e for e in match.events}
    for alert in _scout_run(match):
        assert alert.evidence, f"{alert.id} has no evidence"
        for event_id in alert.evidence:
            assert by_id[event_id].seq <= alert.as_of_seq


def test_momentum_alerts_are_windowed_and_well_evidenced(swing_match):
    swings = [a for a in _scout_run(swing_match) if a.kind is AlertKind.MOMENTUM_SWING]
    assert swings, "seed 21 should produce momentum swings"
    for alert in swings:
        assert len(alert.evidence) >= 3
        assert alert.window and alert.window.period == alert.period
        assert alert.window.end_t - alert.window.start_t >= 240


def test_scout_is_deterministic(match):
    assert _scout_run(match) == _scout_run(match)


def test_state_rejects_out_of_order_events(match):
    state = state_until(match, 10)
    try:
        state.apply(match.events[20])
    except ValueError as exc:
        assert "out-of-order" in str(exc)
    else:
        raise AssertionError("out-of-order event accepted")
