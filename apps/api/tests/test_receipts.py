"""Every cue carries a receipt, and each line of it comes from the agent that knows it."""

from support import first_goal
from test_foundry import FakeAgent, _narrator

from court.contracts import AlertKind, Cue
from court.critic import NUMBER, Critic
from court.foundry import TokenMeter
from court.narrator import TemplateNarrator
from court.orchestrator import run_match
from court.scout import Scout
from court.state import MatchState


class Unreachable(TemplateNarrator):
    def draft(self, alert, state):
        raise ConnectionError("no model answers")


async def _cues(match, narrator):
    outputs = []
    await run_match(list(match.stream()), sink=outputs.append, narrator=narrator)
    return [o for o in outputs if isinstance(o, Cue)]


async def test_a_verified_cue_shows_what_was_checked_and_who_wrote_it(swing_match):
    narrator = TemplateNarrator(overreach_rate=0.25, seed=21)
    cues = await _cues(swing_match, narrator)
    assert cues and all(c.status == "verified" for c in cues)
    for cue in cues:
        r = cue.receipt
        assert r.writer == "template" and r.model_calls == 0 and r.cost_usd == 0
        assert r.attempts == cue.attempts and r.evidence == len(cue.evidence)
        # The line may be cut to its first sentence; the Critic checked every number in the claim.
        assert r.numbers_checked >= len(set(NUMBER.findall(cue.text)))
        assert r.facts_recomputed >= 1 and r.latency_ms > 0
    assert sum(c.receipt.numbers_checked for c in cues) > 0


async def test_a_detection_only_cue_has_no_writer_and_nothing_checked(swing_match):
    cues = await _cues(swing_match, Unreachable())
    assert cues and all(c.status == "detection_only" for c in cues)
    for cue in cues:
        assert cue.receipt.writer == "none" and cue.receipt.numbers_checked == 0
        assert cue.receipt.evidence == len(cue.evidence)


async def test_the_critic_counts_only_numbers_it_could_match(swing_match):
    state, critic, scout, narrator = (
        MatchState(swing_match.meta),
        Critic(),
        Scout(),
        TemplateNarrator(),
    )
    for event in swing_match.events:
        state.apply(event)
        for alert in scout.observe(event, state):
            verdict = critic.review(narrator.draft(alert, state), state)
            assert verdict.approved
            assert verdict.numbers_checked == len(set(NUMBER.findall(verdict.claim.text)))


async def test_the_foundry_ledger_names_the_model_that_answered_and_what_it_cost(match):
    shot = first_goal(match)
    state, scout, alert = MatchState(match.meta), Scout(), None
    for event in match.events[: shot.seq + 1]:
        state.apply(event)
        alert = next((a for a in scout.observe(event, state) if a.kind is AlertKind.GOAL), alert)
    primary, backup = FakeAgent([TimeoutError("primary stalled")]), FakeAgent(["It's in."])
    meter = TokenMeter(prices={"backup": (1.0, 10.0)})
    narrator = _narrator({"primary": primary, "backup": backup}, meter=meter)
    await narrator.draft(alert, state)
    ledger = narrator.spend(alert.id)
    assert ledger["writer"] == "backup" and ledger["handovers"] == 1
    assert (ledger["model_calls"], ledger["tokens_in"], ledger["tokens_out"]) == (1, 400, 60)
    assert ledger["cost_usd"] == round((400 * 1.0 + 60 * 10.0) / 1_000_000, 6)
