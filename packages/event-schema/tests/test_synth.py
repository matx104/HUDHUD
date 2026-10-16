import statistics

import pytest

from match_events import (
    STREAM_ADAPTER,
    MatchMeta,
    Pass,
    PassOutcome,
    PeriodEnd,
    PeriodStart,
    PossessionChange,
    Shot,
    ShotOutcome,
    generate,
    minute_label,
    to_jsonl,
)

SEEDS = range(12)

# Distinctive tokens of real top-flight clubs. Synthetic data must never borrow them.
REAL_CLUB_TOKENS = (
    "arsenal", "chelsea", "liverpool", "everton", "tottenham", "villa", "newcastle",
    "brighton", "fulham", "brentford", "wolves", "wanderers", "bournemouth", "forest",
    "palace", "west ham", "manchester", "leicester", "southampton", "ipswich", "leeds",
    "burnley", "sunderland", "hotspur",
)  # fmt: skip


@pytest.fixture(scope="module")
def matches():
    return {seed: generate(seed) for seed in SEEDS}


def test_same_seed_is_byte_identical():
    assert to_jsonl(generate(7).stream()) == to_jsonl(generate(7).stream())


def test_different_seeds_differ(matches):
    assert to_jsonl(matches[1].stream()) != to_jsonl(matches[2].stream())


def test_seq_and_ids_are_contiguous_and_unique(matches):
    for m in matches.values():
        assert [e.seq for e in m.events] == list(range(len(m.events)))
        assert len({e.id for e in m.events}) == len(m.events)


def test_two_periods_bracketed_by_markers(matches):
    for m in matches.values():
        markers = [e for e in m.events if isinstance(e, PeriodStart | PeriodEnd)]
        assert [(type(e).__name__, e.period) for e in markers] == [
            ("PeriodStart", 1),
            ("PeriodEnd", 1),
            ("PeriodStart", 2),
            ("PeriodEnd", 2),
        ]
        assert m.events[0] == markers[0] and m.events[-1] == markers[-1]


def test_clock_is_monotonic_within_each_period(matches):
    for m in matches.values():
        for period in (1, 2):
            clock = [e.t for e in m.events if e.period == period]
            assert clock == sorted(clock)
        assert m.events[-1].t >= 5400  # full 90 minutes plus stoppage


def test_every_possession_begins_with_a_possession_change(matches):
    for m in matches.values():
        seen = set()
        for e in m.events:
            if isinstance(e, PossessionChange):
                assert e.possession not in seen
                seen.add(e.possession)
            elif hasattr(e, "possession"):
                assert e.possession in seen, f"{e.id} in unannounced possession {e.possession}"


def test_score_matches_goal_events(matches):
    for m in matches.values():
        goals = {"home": 0, "away": 0}
        for e in m.events:
            if isinstance(e, Shot) and e.outcome is ShotOutcome.GOAL:
                goals[e.team.value] += 1
        assert goals == {k.value: v for k, v in m.truth.final_score.items()}


def test_assists_reference_earlier_completed_passes_by_same_team(matches):
    for m in matches.values():
        by_id = {e.id: e for e in m.events}
        for shot in (e for e in m.events if isinstance(e, Shot) and e.assist_event_id):
            assist = by_id[shot.assist_event_id]
            assert isinstance(assist, Pass) and assist.outcome is PassOutcome.COMPLETE
            assert assist.team == shot.team and assist.seq < shot.seq
            assert assist.recipient_id == shot.player_id


def test_football_realistic_volumes(matches):
    """Calibrated against typical top-flight averages; generous bounds, tight means."""
    passes = [[e for e in m.events if isinstance(e, Pass)] for m in matches.values()]
    shots = [[e for e in m.events if isinstance(e, Shot)] for m in matches.values()]
    completion = [sum(p.outcome is PassOutcome.COMPLETE for p in ps) / len(ps) for ps in passes]
    goals = [sum(s.outcome is ShotOutcome.GOAL for s in ss) for ss in shots]

    assert 900 <= statistics.mean(map(len, passes)) <= 1250
    assert 0.74 <= statistics.mean(completion) <= 0.86
    assert 18 <= statistics.mean(map(len, shots)) <= 36
    assert 1.5 <= statistics.mean(goals) <= 4.5


def test_meta_declares_synthetic_and_uses_invented_clubs(matches):
    for m in matches.values():
        assert m.meta.synthetic is True
        assert m.meta.home.name != m.meta.away.name
        for team in (m.meta.home, m.meta.away):
            assert not any(tok in team.name.lower() for tok in REAL_CLUB_TOKENS)
        assert len(m.meta.players) == 22


def test_stream_round_trips_through_json(matches):
    m = matches[3]
    for message in m.stream():
        assert STREAM_ADAPTER.validate_json(STREAM_ADAPTER.dump_json(message)) == message
    assert isinstance(next(m.stream()), MatchMeta)


@pytest.mark.parametrize(
    ("t", "period", "label"),
    [
        (0, 1, "1'"),
        (59.9, 1, "1'"),
        (60, 1, "2'"),
        (2699, 1, "45'"),
        (2700, 1, "45+1'"),
        (2830, 1, "45+3'"),
        (2700, 2, "46'"),
        (5399, 2, "90'"),
        (5460, 2, "90+2'"),
    ],
)
def test_minute_label(t, period, label):
    assert minute_label(t, period) == label
