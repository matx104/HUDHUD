"""The narrator eval, offline: fake agents stand in for the models."""

from test_foundry import FakeAgent, _narrator

from court.narrator_eval import Summary, decide, run, summarize


def _summary(model, **fields):
    base = dict(
        alerts=10,
        first_pass=0.9,
        aired=1.0,
        invented=0.0,
        median_s=3.0,
        p95_s=5.0,
        cost_per_cue=0.0005,
        tokens_out_per_cue=200,
        words=20,
    )
    return Summary(model=model, **(base | fields))


def test_the_gate_comes_first():
    winner, why = decide({"a": _summary("a", aired=0.9, first_pass=1.0), "b": _summary("b")})
    assert winner == "b" and "only model" in why


def test_a_clear_first_pass_lead_wins_over_speed_and_price():
    fast_cheap = _summary("fast", first_pass=0.80, median_s=1.0, cost_per_cue=0.0001)
    assert (
        decide({"fast": fast_cheap, "steady": _summary("steady", first_pass=0.90)})[0] == "steady"
    )


def test_then_speed_then_price():
    a, b = _summary("a", median_s=3.0), _summary("b", median_s=2.0)
    assert decide({"a": a, "b": b})[0] == "b"
    a, b = _summary("a", cost_per_cue=0.0002), _summary("b", median_s=2.9)
    assert decide({"a": a, "b": b})[0] == "a"


async def test_every_model_narrates_the_same_alerts_and_invented_numbers_are_counted():
    def make(model):
        if model == "honest":
            return _narrator({model: FakeAgent(["It's in."] * 100)})
        # Invents a statistic on every first draft, then writes a clean line.
        return _narrator({model: FakeAgent(["A 30-yard strike.", "It's in."] * 100)})

    trials = await run(["honest", "boastful"], [21], make)
    honest = [t for t in trials if t.model == "honest"]
    boastful = [t for t in trials if t.model == "boastful"]
    assert [t.alert_id for t in honest] == [t.alert_id for t in boastful] != []
    assert all(t.first_pass and t.aired for t in honest)
    assert all(not t.first_pass and t.aired and t.invented_numbers == 1 for t in boastful)
    summary = summarize(trials)
    assert summary["honest"].first_pass == 1.0 and summary["boastful"].first_pass == 0.0
    assert decide(summary)[0] == "honest"
