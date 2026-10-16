"""The Agent Framework narrative workflow: draft -> verify -> (rewrite | air | spike)."""

import pytest
from support import first_goal

from court.contracts import AlertKind, Claim, Cue, RejectionCode, RejectionNotice, Spiked, Verdict
from court.critic import Critic
from court.localizer import Localizer
from court.narrator import TemplateNarrator
from court.scout import Scout
from court.state import MatchState
from court.workflow import build_narrative_workflow


@pytest.fixture
def goal_case(match):
    shot = first_goal(match)
    state, scout = MatchState(match.meta), Scout()
    alert = None
    for event in match.events[: shot.seq + 1]:
        state.apply(event)
        alert = next((a for a in scout.observe(event, state) if a.kind is AlertKind.GOAL), alert)
    return state, alert


class OverreachOnce(TemplateNarrator):
    """First draft drops its citations; the rewrite is faithful."""

    def draft(self, alert, state) -> Claim:
        return super().draft(alert, state).model_copy(update={"citations": ()})


class Stubborn(TemplateNarrator):
    """Never learns: every draft and rewrite is uncited."""

    def draft(self, alert, state) -> Claim:
        return super().draft(alert, state).model_copy(update={"citations": ()})

    def rewrite(self, verdict: Verdict, state) -> Claim:
        return super().rewrite(verdict, state).model_copy(update={"citations": ()})


def _workflow(state, narrator, critic=None, max_attempts=3):
    return build_narrative_workflow(
        narrator=narrator,
        critic=critic or Critic(),
        localizer=Localizer(),
        state=state,
        max_attempts=max_attempts,
    )


async def test_faithful_claim_airs_first_time(goal_case):
    state, alert = goal_case
    outputs = (await _workflow(state, TemplateNarrator()).run(alert)).get_outputs()
    assert len(outputs) == 1 and isinstance(outputs[0], Cue)
    cue = outputs[0]
    assert cue.status == "verified" and cue.attempts == 1 and cue.evidence == alert.evidence


async def test_rejected_draft_is_rewritten_and_airs(goal_case):
    state, alert = goal_case
    outputs = (await _workflow(state, OverreachOnce()).run(alert)).get_outputs()
    assert [type(o) for o in outputs] == [RejectionNotice, Cue]
    assert outputs[0].reasons[0].code is RejectionCode.NO_EVIDENCE
    assert outputs[1].attempts == 2


async def test_stubborn_narrator_is_spiked_after_budget(goal_case):
    state, alert = goal_case
    outputs = (await _workflow(state, Stubborn(), max_attempts=3).run(alert)).get_outputs()
    assert [type(o) for o in outputs] == [RejectionNotice] * 3 + [Spiked]
    assert not any(isinstance(o, Cue) for o in outputs)


async def test_unfixable_rejection_spikes_without_rewrites(goal_case):
    state, alert = goal_case
    outputs = (
        await _workflow(state, TemplateNarrator(), Critic(rules={})).run(alert)
    ).get_outputs()
    assert [type(o) for o in outputs] == [RejectionNotice, Spiked]


async def test_workflow_is_reusable_across_alerts(goal_case):
    state, alert = goal_case
    wf = _workflow(state, TemplateNarrator())
    first = (await wf.run(alert)).get_outputs()
    second = (await wf.run(alert)).get_outputs()
    assert first == second
