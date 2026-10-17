"""What the Critic's momentum evidence rule must do: the Scout's calls air, and evidence
that doesn't show this side on top in this spell is refused."""

from court.contracts import AlertKind, Claim, RejectionCode, Window
from court.critic import Critic
from court.metrics import is_final_third_pass
from court.narrator import TemplateNarrator
from court.scout import Scout
from court.state import MatchState
from match_events import Pass, Shot


def _reviewed(match, edit=lambda claim, state: claim):
    """Every scouted momentum claim, optionally edited, reviewed at the moment it was made."""
    state, scout, narrator, critic = MatchState(match.meta), Scout(), TemplateNarrator(), Critic()
    verdicts = []
    for event in match.events:
        state.apply(event)
        for alert in scout.observe(event, state):
            if alert.kind is AlertKind.MOMENTUM_SWING:
                claim = edit(narrator.draft(alert, state), state)
                verdicts.append(critic.review(claim, state))
    assert verdicts, "seed 21 should produce momentum swings"
    return verdicts


def _codes(verdict) -> set[RejectionCode]:
    return {r.code for r in verdict.reasons}


def test_the_scouts_momentum_claims_air(swing_match):
    for verdict in _reviewed(swing_match):
        assert verdict.approved, verdict.reasons


def test_one_event_is_not_momentum(swing_match):
    def single(claim: Claim, state) -> Claim:
        return claim.model_copy(update={"citations": claim.citations[-1:]})

    for verdict in _reviewed(swing_match, single):
        assert RejectionCode.INSUFFICIENT_EVIDENCE in _codes(verdict)


def test_the_other_sides_events_do_not_prove_this_side_is_on_top(swing_match):
    def theirs(claim: Claim, state) -> Claim:
        window = next(a.window for a in claim.assertions if a.window is not None)
        other = [
            e.id
            for e in state.in_window(window)
            if isinstance(e, Pass) and e.team == claim.team.other()
        ]
        return claim.model_copy(update={"citations": tuple(other[-10:])})

    for verdict in _reviewed(swing_match, theirs):
        assert RejectionCode.INSUFFICIENT_EVIDENCE in _codes(verdict)


def test_attacks_from_before_the_spell_are_not_part_of_it(swing_match):
    def earlier(claim: Claim, state) -> Claim:
        spell = max((a.window for a in claim.assertions if a.window), key=lambda w: w.end_t)
        before = Window(period=claim.period, start_t=claim.t - 900, end_t=spell.start_t - 1)
        old = [
            e.id
            for e in state.in_window(before)
            if getattr(e, "team", None) == claim.team
            and (isinstance(e, Shot) or is_final_third_pass(e))
        ]
        return claim.model_copy(update={"citations": (*old[-3:], *claim.citations)})

    for verdict in _reviewed(swing_match, earlier):
        assert RejectionCode.INSUFFICIENT_EVIDENCE in _codes(verdict)
