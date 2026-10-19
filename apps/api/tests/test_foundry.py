"""The Foundry narrator, offline: a fake agent stands in for the deployed models."""

import pytest
from support import first_goal

from court.contracts import AlertKind, RejectionCode
from court.critic import Critic
from court.foundry import FoundryNarrator, Line, NarrationUnavailable, TokenMeter
from court.scout import Scout
from court.state import MatchState


class FakeResponse:
    def __init__(self, text: str, usage: dict | None = None) -> None:
        self.value = Line(text=text)
        self.usage_details = usage or {"input_token_count": 400, "output_token_count": 60}


class FakeAgent:
    """Answers with the next line it was given, or raises it if it's an exception."""

    def __init__(self, answers: list) -> None:
        self.answers, self.prompts = list(answers), []

    async def run(self, prompt: str, options: dict) -> FakeResponse:
        self.prompts.append(prompt)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return FakeResponse(answer)


def _narrator(agents: dict[str, FakeAgent], **kwargs) -> FoundryNarrator:
    return FoundryNarrator(
        project_endpoint="https://example.services.ai.azure.com/api/projects/test",
        models=tuple(agents),
        agent_factory=agents.__getitem__,
        **kwargs,
    )


@pytest.fixture
def goal(match):
    shot = first_goal(match)
    state, scout, alert = MatchState(match.meta), Scout(), None
    for event in match.events[: shot.seq + 1]:
        state.apply(event)
        alert = next((a for a in scout.observe(event, state) if a.kind is AlertKind.GOAL), alert)
    return state, alert


async def test_the_model_writes_the_line_and_the_facts_stay_the_alerts(goal):
    state, alert = goal
    agent = FakeAgent(["What a finish, and it counts."])
    claim = await _narrator({"primary": agent}).draft(alert, state)
    assert claim.text == "What a finish, and it counts."
    assert claim.citations == alert.evidence  # the model never chooses its evidence
    assert claim.assertions and claim.figures["xg"] == alert.metrics["xg"]
    sheet = agent.prompts[0]
    assert all(event_id in sheet for event_id in alert.evidence)
    assert f"xg={alert.metrics['xg']:.2f}" in sheet


async def test_an_invented_number_is_caught_and_the_reasons_go_back_to_the_model(goal):
    state, alert = goal
    agent = FakeAgent(["A 30-yard thunderbolt!", "A clinical finish, and it counts."])
    narrator = _narrator({"primary": agent})
    verdict = Critic().review(await narrator.draft(alert, state), state)
    assert RejectionCode.UNGROUNDED_NUMBER in {r.code for r in verdict.reasons}
    rewritten = await narrator.rewrite(verdict, state)
    assert "the text says 30" in agent.prompts[1]  # the Critic's own words reach the model
    assert rewritten.attempt == 2 and Critic().review(rewritten, state).approved


async def test_a_failing_deployment_hands_over_to_the_backup(goal):
    state, alert = goal
    primary, backup = FakeAgent([TimeoutError("primary stalled")]), FakeAgent(["It's in."])
    meter = TokenMeter(prices={"backup": (1.0, 10.0)})
    narrator = _narrator({"primary": primary, "backup": backup}, meter=meter)
    claim = await narrator.draft(alert, state)
    assert claim.text == "It's in." and narrator.handovers == 1
    assert meter.calls == {"backup": 1}
    assert meter.cost_usd() == pytest.approx((400 * 1.0 + 60 * 10.0) / 1_000_000)


async def test_when_every_deployment_fails_the_orchestrator_is_told(goal):
    state, alert = goal
    narrator = _narrator({"only": FakeAgent([ConnectionError("down")])})
    with pytest.raises(NarrationUnavailable):
        await narrator.draft(alert, state)


async def test_a_favourite_club_changes_the_telling_not_the_facts(goal):
    state, alert = goal
    agent = FakeAgent(["Heartbreak: they score."])
    narrator = _narrator({"primary": agent}, viewer_club="Brackenfield")
    claim = await narrator.draft(alert, state)
    assert agent.prompts[0].startswith("The viewer supports Brackenfield: tell it from their side")
    plain = await _narrator({"primary": FakeAgent(["x"])}).draft(alert, state)
    assert (claim.citations, claim.assertions, claim.figures) == (
        plain.citations,
        plain.assertions,
        plain.figures,
    ), "the sheet's facts, and so the Critic's checks, don't move"
