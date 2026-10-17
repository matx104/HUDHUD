"""What the Critic's momentum evidence rule must do, whatever its details.

These switch on once `momentum_rule` is registered in EVIDENCE_RULES. Until then momentum
claims fail closed with NO_RULE and the tests skip, so CI stays green.
"""

import pytest

from court.contracts import AlertKind, Claim, RejectionCode
from court.critic import EVIDENCE_RULES, Critic
from court.narrator import TemplateNarrator
from court.scout import Scout
from court.state import MatchState
from match_events import Pass

pytestmark = pytest.mark.skipif(
    AlertKind.MOMENTUM_SWING not in EVIDENCE_RULES, reason="critic.momentum_rule is TODO(human)"
)


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
