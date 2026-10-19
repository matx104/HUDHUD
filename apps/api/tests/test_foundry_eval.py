"""Foundry's judges: each aired line goes with the sheet it was written from, and the scores
summarize honestly (no score, no mean)."""

import asyncio

from test_foundry import FakeAgent, _narrator

from court.foundry_eval import METRICS, lines, summarize


def test_every_aired_line_goes_with_the_sheet_it_was_written_from():
    def make():
        return _narrator({"writer": FakeAgent(["What a moment."] * 400)})

    rows = asyncio.run(lines(range(21, 22), make))
    assert rows and all(r["response"] == "What a moment." for r in rows)
    assert all(
        r["context"].startswith(("Moment:", "The viewer", "State the decision")) for r in rows
    )
    assert all("Numbers you may state" in r["context"] for r in rows)
    assert {r["seed"] for r in rows} == {21}


def test_the_summary_counts_what_was_scored_and_no_more():
    scored = [
        {
            "outputs.groundedness.groundedness": 5,
            "outputs.groundedness.groundedness_result": "pass",
        },
        {
            "outputs.groundedness.groundedness": 2,
            "outputs.groundedness.groundedness_result": "fail",
        },
        {"outputs.groundedness.groundedness": "error"},
    ]
    summary = summarize(
        {"rows": scored, "studio_url": "https://ai.azure.com/x"}, [{}] * 3, "j", "w"
    )
    assert summary["groundedness"] == {"mean": 3.5, "pass_pct": 33.3, "scored": 2}
    assert summary["relevance"]["mean"] is None and summary["portal"] == "https://ai.azure.com/x"
    assert set(METRICS) <= set(summary)
