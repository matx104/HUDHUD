"""Critic: the adversarial verifier. Fail-closed: a claim airs only if every check passes.

Checks, in order (all failures are collected so the UI can show every reason):
1. it cites evidence at all
2. every citation is a real event that had happened by the claim's moment
3. cited events are fresh: same period and recent
4. the claim kind's evidence rule is satisfied (unregistered kind -> refuse)
5. every numeric assertion survives independent recomputation from raw events
"""

from collections.abc import Callable, Mapping, Sequence

from match_events import MatchEvent, Shot, ShotOutcome

from .contracts import AlertKind, Claim, Reason, RejectionCode, Verdict
from .metrics import measure
from .state import MatchState

# An evidence rule inspects the (valid) cited events and returns a failure detail,
# or None when the evidence is sufficient for this kind of claim.
EvidenceRule = Callable[[Claim, Sequence[MatchEvent]], str | None]


def goal_rule(claim: Claim, cited: Sequence[MatchEvent]) -> str | None:
    if any(
        isinstance(e, Shot) and e.outcome is ShotOutcome.GOAL and e.team == claim.team
        for e in cited
    ):
        return None
    return "a goal claim must cite the scoring shot"


def big_chance_rule(claim: Claim, cited: Sequence[MatchEvent]) -> str | None:
    if any(isinstance(e, Shot) and e.team == claim.team for e in cited):
        return None
    return "a chance claim must cite the shot itself"


def momentum_rule(claim: Claim, cited: Sequence[MatchEvent]) -> str | None:
    """What evidence proves that one side has seized momentum?

    `cited` holds the citations that passed the earlier checks: real events, from before
    the claim, in the same period and recent. The Scout cites the claiming side's shots
    and completed passes into the final third from the claim's window, up to ten. The
    claim's numbers are recomputed separately, so this rule decides only whether the
    cited events are enough to stand on. Return None if they are, else a one-line reason.
    """
    # TODO(human): decide what a momentum claim must cite, then register this rule in
    # EVIDENCE_RULES below. Until then momentum claims fail closed with NO_RULE, and
    # tests/test_momentum_rule.py skips; it switches on once the rule is registered.
    raise NotImplementedError


EVIDENCE_RULES: Mapping[AlertKind, EvidenceRule] = {
    AlertKind.GOAL: goal_rule,
    AlertKind.BIG_CHANCE: big_chance_rule,
}

TOLERANCE = {"xg": 0.011, "shot_xg": 0.011}  # rounding slack; counts must match exactly


class Critic:
    def __init__(
        self,
        rules: Mapping[AlertKind, EvidenceRule] | None = None,
        *,
        max_evidence_age_s: float = 900.0,
    ) -> None:
        self.rules = EVIDENCE_RULES if rules is None else rules
        self.max_evidence_age_s = max_evidence_age_s

    def review(self, claim: Claim, state: MatchState) -> Verdict:
        reasons: list[Reason] = []

        def refuse(code: RejectionCode, detail: str) -> None:
            reasons.append(Reason(code=code, detail=detail))

        if not claim.citations:
            refuse(RejectionCode.NO_EVIDENCE, "claim cites no events")

        cited: list[MatchEvent] = []
        for event_id in claim.citations:
            event = state.get(event_id)
            if event is None or event.seq > claim.as_of_seq:
                if event is not None or _seq_of(event_id) > claim.as_of_seq:
                    refuse(
                        RejectionCode.FUTURE_EVENT,
                        f"{event_id} had not happened when the claim was made "
                        f"(as of e{claim.as_of_seq:05d})",
                    )
                else:
                    refuse(RejectionCode.UNKNOWN_EVENT, f"{event_id} is not in the match record")
                continue
            if event.period != claim.period or claim.t - event.t > self.max_evidence_age_s:
                refuse(RejectionCode.STALE_EVENT, f"{event_id} is too old to support this claim")
                continue
            cited.append(event)

        rule = self.rules.get(claim.kind)
        if rule is None:
            refuse(
                RejectionCode.NO_RULE,
                f"no evidence rule registered for {claim.kind} claims; failing closed",
            )
        elif cited and (problem := rule(claim, cited)):
            refuse(RejectionCode.INSUFFICIENT_EVIDENCE, problem)

        for assertion in claim.assertions:
            actual = measure(assertion, state, claim.as_of_seq)
            tolerance = TOLERANCE.get(assertion.metric, 0.0)
            if actual is None or abs(actual - assertion.value) > tolerance:
                shown = "nothing measurable" if actual is None else _fmt(actual)
                refuse(
                    RejectionCode.ASSERTION_MISMATCH,
                    f"claimed {assertion.metric}={_fmt(assertion.value)} for "
                    f"{assertion.team}, events show {shown}",
                )

        return Verdict(claim=claim, reasons=tuple(reasons))


def _seq_of(event_id: str) -> int:
    try:
        return int(event_id.removeprefix("e"))
    except ValueError:
        return -1


def _fmt(value: float) -> str:
    return f"{value:.0f}" if float(value).is_integer() else f"{value:.2f}"
