"""Ask the match: a question answered from the Scout's tools, every answer through the Critic."""

import asyncio
import json

import pytest
from support import state_until

from court.ask import (
    CANNOT,
    MAX_ATTEMPTS,
    REFUSED,
    Draft,
    MatchTools,
    RuleAnswerer,
    about_betting,
    ask,
    suggestions,
)
from court.contracts import AlertKind, Assertion, Claim, RejectionCode
from court.critic import Critic
from court.foundry import FoundryNarrator
from court.metrics import compute
from match_events import Shot, ShotOutcome, Side, minute_label


@pytest.fixture(scope="module")
def at_70(swing_match):
    """The 2-2 match at 70', when both sides have scored twice."""
    last = max(e.seq for e in swing_match.events if e.t < 70 * 60)
    return state_until(swing_match, last)


def answer(state, question, answerer=None, **kwargs):
    return asyncio.run(ask(question, MatchTools(state), answerer or RuleAnswerer(), **kwargs))


def codes(answer_):
    return [r.code for refused in answer_.refused for r in refused.reasons]


def test_the_score_is_counted_and_checked(at_70):
    home, away = (compute("goals", side, at_70.events) for side in Side)
    reply = answer(at_70, "What's the score?")
    assert reply.status == "verified" and reply.refused == ()
    assert reply.text == f"Saltmarsh Rovers {home:.0f}, Brackenfield {away:.0f}, as of 70'."
    # 2, 2 and 70: the Critic counts each distinct number once.
    assert reply.receipt.numbers_checked == 2 and reply.receipt.facts_recomputed == 2
    # A count of the match so far cites the moment it was counted to.
    assert reply.evidence[-1] == at_70.events[-1].id


def test_who_scored_lists_every_goal_with_its_minute(at_70):
    reply = answer(at_70, "Who scored?")
    goals = [e for e in at_70.events if isinstance(e, Shot) and e.outcome is ShotOutcome.GOAL]
    assert reply.status == "verified" and len(goals) == 4
    assert set(reply.evidence) == {g.id for g in goals}
    for goal in goals:
        assert minute_label(goal.t, goal.period) in reply.text
        assert at_70.player_name(goal.player_id) in reply.text


def test_a_sides_count_in_one_half_and_a_players_counts(at_70):
    reply = answer(at_70, "How many shots have Saltmarsh Rovers had in the second half?")
    assert reply.status == "verified" and "in the second half" in reply.text
    shots = sum(isinstance(e, Shot) and e.team is Side.HOME and e.period == 2 for e in at_70.events)
    assert f"{shots} shots" in reply.text
    player = next(p for p in at_70.meta.players if p.position == "FW")
    reply = answer(at_70, f"How many passes has {player.name} completed?")
    done = compute("passes_completed", player.team, at_70.events, player.id)
    assert reply.status == "verified"
    assert reply.text == f"{player.name}: {done:.0f} passes completed, as of 70'."


@pytest.mark.parametrize(
    ("question", "why"),
    [
        ("Who will win?", "not_yet"),
        ("Is the number 9 injured?", "beyond_data"),
        ("What colour are the boots?", "unsupported"),
    ],
)
def test_what_the_events_cant_answer_gets_the_fixed_words(at_70, question, why):
    reply = answer(at_70, question)
    assert reply.status == "cannot" and reply.text == CANNOT[why]
    assert reply.evidence == () and reply.facts == ()


def test_the_stress_test_inflates_a_number_and_the_critic_catches_it(at_70):
    reply = answer(at_70, "What's the score?", stress=True)
    assert reply.status == "verified" and reply.receipt.attempts == 2
    assert codes(reply) == [RejectionCode.UNGROUNDED_NUMBER]


class Scripted:
    """An answerer that calls the tools as told and writes the given text."""

    writer = "scripted"

    def __init__(self, text, calls, extra_facts=()):
        self.text, self.calls, self.extra = text, calls, list(extra_facts)
        self.feedback = []

    async def answer(self, question, tools, feedback):
        self.feedback.append(list(feedback))
        ids = []
        for name, kwargs in self.calls:
            ids += [f["id"] for f in json.loads(getattr(tools, name)(**kwargs))["facts"]]
        text = self.text(tools) if callable(self.text) else self.text
        return Draft(text=text, facts=ids + self.extra, cannot="")


def test_a_name_the_facts_arent_about_is_refused(at_70):
    other = next(p for p in at_70.meta.players if p.team is Side.AWAY)
    scripted = Scripted(
        lambda tools: f"{other.name} drove it: Saltmarsh Rovers have the shots.",
        [("team_numbers", {"metrics": ["shots"], "team": "home"})],
    )
    reply = answer(at_70, "Who is on top?", scripted)
    assert reply.status == "refused" and reply.text == REFUSED
    assert len(reply.refused) == MAX_ATTEMPTS
    assert set(codes(reply)) == {RejectionCode.UNGROUNDED_NAME}
    # Each rewrite is told why the last was refused.
    assert "ungrounded_name" in "\n".join(scripted.feedback[1])


def test_a_fact_the_tools_never_returned_is_refused(at_70):
    scripted = Scripted("Saltmarsh Rovers are on top.", [], extra_facts=["f9"])
    reply = answer(at_70, "Who is on top?", scripted)
    assert reply.status == "refused"
    assert RejectionCode.UNKNOWN_EVENT in codes(reply)


def test_a_number_the_facts_dont_hold_is_refused(at_70):
    scripted = Scripted(
        "Saltmarsh Rovers have 99 shots.",
        [("team_numbers", {"metrics": ["shots"], "team": "home"})],
    )
    reply = answer(at_70, "Shots?", scripted)
    assert reply.status == "refused"
    assert set(codes(reply)) == {RejectionCode.UNGROUNDED_NUMBER}


def test_the_tools_see_only_what_had_happened(swing_match, at_70):
    early = next(e.seq for e in swing_match.events if isinstance(e, Shot) and e.outcome == "goal")
    tools = MatchTools(at_70, as_of_seq=early - 1)
    result = json.loads(tools.score())["facts"][0]
    assert "0" in result["says"] and tools.facts[result["id"]].assertions[0].value == 0
    # And a claim that cites a later event is refused, whatever the tools said.
    later = at_70.events[-1].id
    claim = tools.claim(
        Draft(text="Nothing yet.", facts=[result["id"]], cannot=""), question="?", attempt=1
    )
    claim = claim.model_copy(update={"citations": (*claim.citations, later)})
    verdict = Critic(hindsight=True).review(claim, at_70)
    assert [r.code for r in verdict.reasons] == [RejectionCode.FUTURE_EVENT]


def test_a_count_so_far_must_cite_where_it_stops(at_70):
    goal = next(e for e in at_70.events if isinstance(e, Shot) and e.outcome is ShotOutcome.GOAL)
    claim = Claim(
        id="q.1",
        alert_id="q",
        attempt=1,
        kind=AlertKind.ANSWER,
        team=goal.team,
        period=2,
        t=at_70.events[-1].t,
        as_of_seq=at_70.last_seq,
        severity=0.5,
        headline="?",
        text="2 goals.",
        citations=(goal.id,),
        assertions=(Assertion(metric="goals", team=goal.team, value=2),),
        names=(),
    )
    verdict = Critic(hindsight=True).review(claim, at_70)
    assert [r.code for r in verdict.reasons] == [RejectionCode.INSUFFICIENT_EVIDENCE]
    assert "counted to" in verdict.reasons[0].detail


def test_a_players_count_is_recomputed_from_that_players_events(at_70):
    player = next(p for p in at_70.meta.players if p.position == "MF")
    tools = MatchTools(at_70)
    fact = tools.facts[json.loads(tools.player_numbers(player.name))["facts"][0]["id"]]
    passes = next(a for a in fact.assertions if a.metric == "passes")
    assert passes.player_id == player.id
    assert passes.value == compute("passes", player.team, at_70.events, player.id)
    wrong = passes.model_copy(update={"value": passes.value + 1})
    claim = tools.claim(
        Draft(text=f"{player.name} has made passes.", facts=[fact.id], cannot=""),
        question="?",
        attempt=1,
    ).model_copy(update={"assertions": (wrong,)})
    verdict = Critic(hindsight=True).review(claim, at_70)
    assert [r.code for r in verdict.reasons] == [RejectionCode.ASSERTION_MISMATCH]


def test_an_answer_is_translated_and_keeps_its_english(at_70):
    async def translate(answer_id, text):
        return f"[ur] {text}", "gpt-4.1-mini"

    reply = answer(at_70, "What's the score?", lang="ur", translate=translate)
    assert reply.lang == "ur" and reply.text.startswith("[ur] Saltmarsh Rovers")
    assert reply.original.startswith("Saltmarsh Rovers")
    assert reply.receipt.translated_by == "gpt-4.1-mini"


# --- the model, with the tools ---------------------------------------------------------


class FakeResponse:
    def __init__(self, value):
        self.value = value
        self.usage_details = {"input_token_count": 900, "output_token_count": 60}


class ToolCallingAgent:
    """Stands in for a Foundry model: calls the tools it is given, then answers from them."""

    def __init__(self):
        self.prompts = []

    async def run(self, prompt, tools=None, options=None):
        self.prompts.append(prompt)
        assert options["response_format"] is Draft
        by_name = {t.name: t for t in tools}
        assert set(by_name) == {"score", "team_numbers", "player_numbers", "leaders", "moments"}
        result = json.loads(by_name["team_numbers"].func(metrics=["xg"], team="Saltmarsh Rovers"))
        fact = result["facts"][0]
        value = fact["says"].split("xG ")[1].split(" ")[0]
        draft = Draft(text=f"Saltmarsh Rovers have xG {value}.", facts=[fact["id"]], cannot="")
        return FakeResponse(draft)


def test_the_model_answers_with_the_tools_and_its_spend_is_on_the_receipt(at_70):
    agent = ToolCallingAgent()
    narrator = FoundryNarrator(
        project_endpoint="https://example.invalid",
        models=("gpt-4.1-mini",),
        agent_factory=lambda model, purpose="line": agent,
    )
    reply = answer(at_70, "What's Saltmarsh's xG?", narrator, spend=narrator.spend)
    assert reply.status == "verified" and reply.text.startswith("Saltmarsh Rovers have xG")
    assert reply.receipt.writer == "gpt-4.1-mini" and reply.receipt.model_calls == 1
    assert reply.receipt.tokens_in == 900 and reply.receipt.cost_usd > 0
    assert "Question: What's Saltmarsh's xG?" in agent.prompts[0]
    assert "Saltmarsh Rovers (home)" in agent.prompts[0]


def test_one_call_counts_several_things_for_both_sides(at_70):
    tools = MatchTools(at_70)
    facts = json.loads(tools.team_numbers(["shots", "xg"]))["facts"]
    assert len(facts) == 4
    assert [tools.facts[f["id"]].team for f in facts] == [Side.HOME, Side.AWAY] * 2
    assert "error" in json.loads(tools.team_numbers(["shots"], team="Nowhere United"))


def test_what_event_data_cant_see_is_held_back_before_any_model_is_asked(at_70):
    class Never:
        async def answer(self, question, tools, feedback):
            raise AssertionError("no model should be asked")

    for question in ("Is Adem Rosmere injured?", "How does the crowd feel?", "Is it raining?"):
        reply = answer(at_70, question, Never())
        assert reply.status == "cannot" and reply.text == CANNOT["beyond_data"]
        assert reply.receipt.writer == "none"
    # "Training" is not rain, and a question about passes is a question about passes.
    assert answer(at_70, "Which side has completed more passes?").status == "verified"


def test_which_chance_was_biggest_is_a_fact_of_its_own(at_70):
    tools = MatchTools(at_70)
    facts = json.loads(tools.moments("big_chances"))["facts"]
    top = facts[-1]
    assert top["says"].startswith("Of these, the biggest by xG: ")
    shots = [tools.facts[f["id"]] for f in facts[:-1]]
    biggest = max(shots, key=lambda f: f.assertions[0].value)
    assert tools.facts[top["id"]].citations == biggest.citations


def test_betting_gets_fixed_words_that_steer_away_before_any_model_is_asked(at_70):
    class Never:
        async def answer(self, question, tools, feedback):
            raise AssertionError("no model should be asked")

    for question in (
        "What are the odds on Saltmarsh Rovers winning?",
        "Should I bet on the next goal?",
        "Is this a good game for an accumulator?",
        "اس میچ پر سٹہ لگاؤں؟",  # Urdu: should I bet on this match?
        "ما هي أفضل مراهنة الآن؟",  # Arabic: what is the best bet now?
    ):
        reply = answer(at_70, question, Never())
        assert reply.status == "cannot" and reply.text == CANNOT["betting"], question
        assert reply.receipt.writer == "none" and reply.facts == ()
    assert "not the odds" in CANNOT["betting"]
    # Whole words only: a counter-attack in Urdu ("jawabi hamla") is football, not "jua".
    assert answer(at_70, "Who has had more shots?").status == "verified"
    assert about_betting("کس ٹیم کے جوابی حملے زیادہ تھے؟") is False
    assert about_betting("Who has the better chances?") is False


def test_who_has_the_most_is_ranked_by_code_and_a_tie_names_everyone_level(at_70):
    reply = answer(at_70, "Who has completed the most passes?")
    assert reply.status == "verified" and "has the most passes completed" in reply.text
    passes = {
        p.name: compute("passes_completed", p.team, at_70.events, p.id) for p in at_70.meta.players
    }
    best = max(passes.values())
    assert reply.text.startswith(next(n for n, v in passes.items() if v == best))
    # Four players scored once each by 70': all four are level, none left out.
    reply = answer(at_70, "Who is the top scorer?")
    scorers = {
        at_70.player_name(e.player_id)
        for e in at_70.events
        if isinstance(e, Shot) and e.outcome is ShotOutcome.GOAL
    }
    assert reply.status == "verified" and reply.text.startswith("Level at the top with 1 goal each")
    assert all(name in reply.text for name in scorers)


def test_a_wrong_count_in_a_ranking_is_refused(at_70):
    scripted = Scripted(
        lambda tools: (
            next(f.says for f in tools.facts.values() if f.says.startswith("Of these"))
            .replace("Of these, the most passes completed: ", "")
            .replace(", as of", " (and 9 more), as of")
        ),
        [("leaders", {"metric": "passes_completed"})],
    )
    reply = answer(at_70, "Who passes most?", scripted)
    assert reply.status == "refused"
    assert RejectionCode.UNGROUNDED_NUMBER in codes(reply)


def test_a_follow_up_borrows_what_the_last_question_counted(at_70):
    first = answer(at_70, "How many shots have Saltmarsh Rovers had?")
    shots = compute("shots", Side.AWAY, at_70.events)
    reply = answer(at_70, "And Brackenfield?", history=[(first.question, first.text)])
    assert (
        reply.status == "verified"
        and reply.text == f"Brackenfield {shots:.0f} shots so far, as of 70'."
    )
    # With no question before it, a bare "And Brackenfield?" has nothing to borrow.
    assert answer(at_70, "And Brackenfield?").status == "cannot"


def test_the_model_is_told_the_conversation_but_counts_again(at_70):
    agent = ToolCallingAgent()
    narrator = FoundryNarrator(
        project_endpoint="https://example.invalid",
        models=("gpt-4.1-mini",),
        agent_factory=lambda model, purpose="line": agent,
    )
    history = [("How many shots have Saltmarsh Rovers had?", "Saltmarsh Rovers 9 shots so far.")]
    answer(at_70, "And their xG?", narrator, spend=narrator.spend, history=history)
    assert "Earlier in this conversation" in agent.prompts[0]
    assert "never reuse a number from here" in agent.prompts[0]


def test_suggestions_come_from_what_has_happened(at_70):
    asked = suggestions(MatchTools(at_70))
    assert asked[0] == "Who scored?" and asked[-1] == "Who will win?"
    assert any(q.startswith("How is ") for q in asked)
    assert "How many fouls has Saltmarsh Rovers committed in the second half?" in asked
