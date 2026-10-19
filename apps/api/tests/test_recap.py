"""The recap: after full time, every line the recap writes is checked as a cue is."""

import asyncio

import pytest

from court.contracts import AlertKind, Assertion, Claim, RejectionCode
from court.critic import Critic
from court.orchestrator import run_match
from court.recap import build, render_html
from match_events import PeriodEnd, Side


@pytest.fixture(scope="module")
def finished(swing_match):
    outputs = []
    orchestrator = asyncio.run(run_match(swing_match.stream(), sink=outputs.append))
    return orchestrator.state, outputs


def test_the_recap_tells_the_whole_match_and_every_written_line_passed(finished):
    state, outputs = finished
    recap = build(state, outputs)
    assert recap.refused == []
    assert (
        recap.result.check == "checked"
        and recap.result.text == "Saltmarsh Rovers 2-2 Brackenfield."
    )
    assert recap.score == (2, 2) and len(recap.goals) == 4
    assert all(line.check == "checked" for line in [*recap.goals, *recap.numbers])
    assert recap.moments and all(line.check == "aired" for line in recap.moments)
    assert all(line.check == "counted" and line.evidence for line in recap.standouts)
    assert recap.receipts["aired"] == sum(
        1 for o in outputs if getattr(o, "status", "") == "verified"
    )


def _recap_claim(state, text, assertions, citations):
    whistle = next(e for e in reversed(state.events) if isinstance(e, PeriodEnd))
    return Claim(
        id="r.1", alert_id="r.1", attempt=1, kind=AlertKind.RECAP, team=Side.HOME,
        period=whistle.period, t=whistle.t, as_of_seq=whistle.seq, severity=0.0,
        headline="RECAP", text=text, citations=tuple(citations), assertions=tuple(assertions),
    )  # fmt: skip


def test_hindsight_lifts_only_the_freshness_rule(finished):
    state, _ = finished
    whistle = next(e for e in reversed(state.events) if isinstance(e, PeriodEnd))
    early = next(e for e in state.events if e.period == 1 and getattr(e, "team", None))
    goals = Assertion(metric="goals", team=Side.HOME, value=2)
    claim = _recap_claim(state, "Saltmarsh Rovers scored 2.", [goals], [early.id, whistle.id])
    live = Critic().review(claim, state)
    assert RejectionCode.STALE_EVENT in {r.code for r in live.reasons}
    assert Critic(hindsight=True).review(claim, state).approved
    wrong = _recap_claim(
        state, "Saltmarsh Rovers scored 3.", [goals.model_copy(update={"value": 3})], [whistle.id]
    )
    codes = {r.code for r in Critic(hindsight=True).review(wrong, state).reasons}
    assert RejectionCode.ASSERTION_MISMATCH in codes, "a number the events contradict"


def test_whole_match_numbers_must_be_counted_to_the_final_whistle(finished):
    state, _ = finished
    shot = next(e for e in state.events if e.type == "shot")
    goals = Assertion(metric="goals", team=Side.HOME, value=2)
    claim = _recap_claim(state, "Saltmarsh Rovers scored 2.", [goals], [shot.id])
    verdict = Critic(hindsight=True).review(claim, state)
    assert [r.code for r in verdict.reasons] == [RejectionCode.INSUFFICIENT_EVIDENCE]
    assert "final whistle" in verdict.reasons[0].detail


def test_the_page_shows_each_line_with_its_evidence_and_how_it_was_checked(finished):
    state, outputs = finished
    recap = build(state, outputs)
    page = render_html(recap)
    assert page.startswith("<!doctype html>")
    assert "SAL" in page and "2-2" in page
    for words in ("Checked by the Critic", "Aired live, checked then", "Counted from events"):
        assert words in page
    assert all(f"<code>{i}</code>" in page for i in recap.goals[0].evidence)
    assert "<script" not in page, "a static page: nothing runs"
