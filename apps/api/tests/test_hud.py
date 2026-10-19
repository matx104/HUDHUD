"""HUD²: every action placed on the pitch as the camera sees it, and the numbers beside them
counted the way the Critic counts them."""

import pytest
from fastapi.testclient import TestClient
from test_server import _events

from court.hud import attacks_right, names_of, place, play, pulse, zones
from court.metrics import compute
from court.referee import GOAL_CHANCE_M, call
from court.server import create_app
from match_events import PeriodStart, Shot, ShotOutcome, Side, Tackle


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
    return TestClient(create_app())


def test_the_ends_change_at_half_time(swing_match):
    meta = swing_match.meta
    for side in Side:
        assert attacks_right(side, 1, meta) != attacks_right(side, 2, meta)
        assert attacks_right(side, 1, meta) != attacks_right(side.other(), 1, meta)
    left = next(s for s in Side if not attacks_right(s, 1, meta))
    # A side attacking left sees its frame turned half a circle: its own goal line is on the right.
    assert place(0, 0, left, 1, meta) == (105, 68)
    assert place(80.0, 10.0, left.other(), 1, meta) == (80.0, 10.0)


def test_every_goal_lands_at_the_end_its_side_was_attacking(swing_match):
    meta, names = swing_match.meta, names_of(swing_match.meta)
    goals = [e for e in swing_match.events if isinstance(e, Shot) and e.outcome is ShotOutcome.GOAL]
    assert len(goals) == 4
    for goal in goals:
        action = play(goal, meta, names)
        right = attacks_right(goal.team, goal.period, meta)
        assert (action["x"] > 52.5) == right, goal.id
        assert action["player"] == names[goal.player_id][0] and action["xg"] > 0


def test_each_action_carries_what_its_layer_draws(swing_match):
    meta, names = swing_match.meta, names_of(swing_match.meta)
    actions = [play(e, meta, names) for e in swing_match.events]
    marks = [
        a for a, e in zip(actions, swing_match.events, strict=True) if isinstance(e, PeriodStart)
    ]
    assert marks == [None, None]
    kinds = {a["kind"] for a in actions if a}
    assert kinds == {"pass", "shot", "tackle", "pressure", "possession_change"}
    passes = [a for a in actions if a and a["kind"] == "pass"]
    assert all({"ex", "ey", "to", "final_third", "box"} <= set(a) for a in passes)
    assert any(a["box"] for a in passes) and any(a["final_third"] for a in passes)
    # A foul carries the facts its likely call rests on, and they agree with the call.
    fouls = [e for e in swing_match.events if isinstance(e, Tackle) and e.outcome == "foul"]
    assert fouls
    for foul in fouls:
        action = play(foul, meta, names)
        assert action["in_area"] == (call(foul).restart == "penalty")
        assert action["to_goal_m"] >= 0 and action["opponent"]


def test_the_pulse_counts_what_the_critic_counts(swing_match):
    events = [e for e in swing_match.events if e.period == 1 or e.t < 70 * 60]
    now = events[-1]
    beat = pulse(events, now.t, now.period)
    for side in Side:
        for metric in ("shots", "xg", "passes_completed", "fouls", "goals"):
            assert beat["match"][side.value][metric] == compute(metric, side, events)
    recent = [e for e in events if e.period == now.period and e.t > now.t - 300]
    assert beat["recent"]["home"]["passes"] == compute("passes", Side.HOME, recent)
    assert sum(beat["share"].values()) in (99, 100, 101)  # two rounded shares
    assert beat["minute"] == "70'"


def test_the_referee_zones_follow_the_strictness():
    assert zones("strict")["goal_chance_m"] > zones("lenient")["goal_chance_m"]
    assert zones("standard")["goal_chance_m"] == GOAL_CHANCE_M["standard"]
    assert zones("lenient")["promising_x"] == 0  # the lenient reading lets a stopped attack go


def test_the_hud_stream_places_every_action_and_anchors_every_cue(client):
    events = _events(client, "seed=21&speed=0&stress=0.25&hud=1")
    hello = events[0][1]
    assert hello["hud"]["zones"] == zones("standard")
    plays = [d for k, d in events if k == "play"]
    assert len(plays) > 1500 and len({p["id"] for p in plays}) == len(plays)
    assert [p["seq"] for p in plays] == sorted(p["seq"] for p in plays)
    pulses = [d for k, d in events if k == "pulse"]
    assert len(pulses) >= 90 and pulses[-1]["match"]["home"]["shots"] > 0
    # Every verified line can be pinned where it happened: it cites at least one placed action.
    placed = {p["id"] for p in plays}
    cues = [d for k, d in events if k == "output" and d["type"] == "cue"]
    assert cues and all(placed & set(c["evidence"]) for c in cues)


def test_without_hud_the_studio_stream_is_unchanged(client):
    kinds = {k for k, _ in _events(client, "seed=7&speed=0&start=80")}
    assert "play" not in kinds and "pulse" not in kinds
    hello = _events(client, "seed=7&speed=0&start=89")[0][1]
    assert "hud" not in hello


def test_the_hud_page_is_served_with_the_product_mark(client):
    page = client.get("/hud")
    assert page.status_code == 200 and "/static/hud.js" in page.text
    assert client.get("/api/config").json()["mark"] == "HUD²"
