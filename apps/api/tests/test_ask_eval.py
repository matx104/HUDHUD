"""The answers' evaluation: each question's truth counted by code, each answer graded."""

import asyncio

from support import state_until

from court.ask import RuleAnswerer
from court.ask_eval import Probe, grade, probes, run, summarize
from court.contracts import Answer


def test_every_moment_gets_answerable_and_unanswerable_questions(swing_match):
    state = state_until(swing_match, len(swing_match.events) - 1)
    found = probes(state)
    assert found[0] == Probe("What's the score?", numbers=("2", "2"))
    assert any(p.names for p in found) and {p.cannot for p in found if p.cannot} == {
        "not_yet",
        "beyond_data",
        "off_topic",
    }


def _answer(status, text, original=None):
    return Answer(id="a", question="q", status=status, text=text, minute="70'", original=original)


def test_grades_say_what_went_right_and_what_didnt():
    probe = Probe("Shots?", numbers=("7",), names=("Adem Rosmere",))
    assert grade(probe, _answer("verified", "Adem Rosmere has 7 shots.")) == "right"
    assert grade(probe, _answer("verified", "Adem Rosmere has 5 passes.")) == "off the question"
    assert grade(probe, _answer("refused", "...")) == "refused"
    # A translated answer is graded on the English the Critic checked.
    urdu = _answer("verified", "...", original="Adem Rosmere has 7 shots.")
    assert grade(probe, urdu) == "right"
    future = Probe("Who will win?", cannot="not_yet")
    from court.ask import CANNOT

    assert grade(future, _answer("cannot", CANNOT["not_yet"])) == "declined, right reason"
    assert grade(future, _answer("cannot", CANNOT["off_topic"])) == "declined, another reason"
    assert grade(future, _answer("verified", "Saltmarsh lead.")) == "answered anyway"


def test_the_offline_answerer_runs_the_whole_set_through_the_critic():
    rows = asyncio.run(run(range(60, 61), RuleAnswerer()))
    summary = summarize(rows, "template")
    assert summary["questions"] == len(rows) >= 20
    # Offline, nothing the events can't answer gets an answer, and the Critic refuses nothing.
    assert "answered anyway" not in summary["grades"] and summary["drafts_refused"] == 0
    assert summary["right"] == summary["answerable"]
