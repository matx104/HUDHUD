from court.contracts import Alert, AlertKind, Window
from court.evals import SwingScore, evaluate, score


def _call(spell, team, start_t, end_t) -> Alert:
    return Alert(
        id="a1",
        kind=AlertKind.MOMENTUM_SWING,
        team=team,
        period=spell.period,
        t=end_t,
        as_of_seq=0,
        severity=0.5,
        evidence=("e00001",),
        metrics={},
        window=Window(period=spell.period, start_t=start_t, end_t=end_t),
    )


def test_a_call_inside_a_real_spell_is_a_hit_and_catches_it(match):
    spell = match.truth.spells[0]
    call = _call(spell, spell.team, spell.start_t + 60, spell.start_t + 300)
    result = score(match, [call])
    assert (result.alerts, result.hits, result.caught) == (1, 1, 1)
    assert [round(lag) for lag in result.lags_s] == [300]


def test_the_wrong_side_or_a_window_mostly_outside_the_spell_is_a_miss(match):
    spell = match.truth.spells[0]
    wrong_side = _call(spell, spell.team.other(), spell.start_t + 60, spell.start_t + 300)
    mostly_before = _call(spell, spell.team, spell.start_t - 240, spell.start_t + 60)
    result = score(match, [wrong_side, mostly_before])
    assert (result.alerts, result.hits, result.caught) == (2, 0, 0)


def test_scores_add_up_across_matches():
    a, b = SwingScore(4, 2, 5, 2, (60.0, 120.0)), SwingScore(1, 1, 2, 1, (30.0,))
    total = a + b
    assert (total.alerts, total.hits, total.spells, total.caught) == (5, 3, 7, 3)
    assert total.precision == 0.6 and round(total.recall, 2) == 0.43
    assert total.median_lag_s == 60.0


def test_most_momentum_calls_are_real_on_matches_never_tuned_on():
    """A floor under the Scout's precision, on seeds 60-79 (`python -m court eval` for all
    of 60-99). It moves only if detection gets worse, or the floor is changed on purpose."""
    result = evaluate(range(60, 80))
    assert result.precision >= 0.55, result
    assert result.caught >= 10, result
