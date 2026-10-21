"""Critic: the adversarial verifier. Fail-closed: a claim airs only if every check passes.

Checks, in order (all failures are collected so the UI can show every reason):
1. it cites evidence at all
2. every citation is a real event that had happened by the claim's moment
3. cited events are fresh: same period and recent (lifted for the recap, which has hindsight)
4. the claim kind's evidence rule is satisfied (unregistered kind -> refuse)
5. every numeric assertion survives independent recomputation from raw events; one about a
   single event must be about an event the claim cites, of the side it names
6. every number the text states is one the claim accounts for (its figures or assertions):
   a model that invents a statistic is caught here, whatever else it got right
7. when the claim says which players its evidence is about (an answer does), every player of
   the match the text names is one of them
"""

import re
from collections.abc import Callable, Mapping, Sequence

from match_events import (
    MatchEvent,
    Pass,
    PassOutcome,
    PeriodEnd,
    PossessionChange,
    Shot,
    ShotOutcome,
    Side,
    Tackle,
)

from .contracts import AlertKind, Claim, Reason, RejectionCode, Verdict
from .metrics import is_ball_win, is_final_third_pass, is_high_ball_win, measure
from .referee import Profile
from .referee import call as ref_call
from .referee import words as call_words
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
    the claim, in the same period and recent. The claim's numbers are recomputed
    separately, so this rule decides only whether the cited events are enough to stand on:

    - every one is the side's own attacking play (a shot, or a completed pass into the
      final third): the other side's events, or a square pass at the back, prove nothing
      about who is on top, and a viewer opening the evidence must see only support
    - every one falls inside the stretch of play the claim describes: an attack from
      before the spell began is not part of it
    - there are at least MOMENTUM_MIN_ACTIONS of them: one chance is a moment, not a spell

    It doesn't ask the evidence to be spread out. On seeds 0-99 the Scout's calls whose
    actions came in one tight burst were real swings as often as the rest (a side pinning
    its opponent in attacks in bursts), so a spread test would cost true calls for nothing.
    """
    windows = [a.window for a in claim.assertions if a.window is not None]
    if not windows:
        return "a momentum claim must say which stretch of play it covers"
    spell = max(windows, key=lambda w: w.end_t)
    for event in cited:
        if getattr(event, "team", None) != claim.team or not _attacking(event):
            return (
                f"{event.id} is not {claim.team}'s attacking play; momentum stands on the "
                "side's own shots and passes into the final third"
            )
        if not spell.start_t <= event.t <= spell.end_t:
            return f"{event.id} came before the spell the claim describes"
    if len(cited) < MOMENTUM_MIN_ACTIONS:
        return (
            f"momentum needs at least {MOMENTUM_MIN_ACTIONS} attacking actions from the spell; "
            f"the claim cites {len(cited)}"
        )
    return None


MOMENTUM_MIN_ACTIONS = 3  # the Scout's min_events: it never raises a swing it can't cite


def _attacking(event: MatchEvent) -> bool:
    return isinstance(event, Shot) or is_final_third_pass(event)


COUNTER_MAX_S = 15.0  # the Scout's: from winning the ball to the shot
HALFWAY_X = 52.5


def counter_rule(claim: Claim, cited: Sequence[MatchEvent]) -> str | None:
    """A break is the ball won in the side's own half and a shot away soon after, in the same
    possession: the claim cites both."""
    wins = [
        e
        for e in cited
        if isinstance(e, PossessionChange)
        and is_ball_win(e)
        and e.team == claim.team
        and e.x < HALFWAY_X
    ]
    shots = [e for e in cited if isinstance(e, Shot) and e.team == claim.team]
    for win in wins:
        for shot in shots:
            quick = 0 <= shot.t - win.t <= COUNTER_MAX_S and shot.period == win.period
            if quick and shot.possession == win.possession:
                return None
    return (
        "a counterattack claim must cite the ball won in the side's own half and the shot from "
        f"the same possession, within {COUNTER_MAX_S:.0f} seconds"
    )


PRESS_MIN_WINS = 4  # the Scout's PRESS_WINS


def press_rule(claim: Claim, cited: Sequence[MatchEvent]) -> str | None:
    """The press stands on the ball won back high: every cited event is one of the side's wins in
    the attacking third, inside the stretch the claim describes, and there are enough of them."""
    windows = [a.window for a in claim.assertions if a.window is not None]
    if not windows:
        return "a high-press claim must say which stretch of play it covers"
    spell = max(windows, key=lambda w: w.end_t)
    for event in cited:
        if not is_high_ball_win(event) or event.team != claim.team:
            return f"{event.id} is not {claim.team} winning the ball in the attacking third"
        if not spell.start_t <= event.t <= spell.end_t:
            return f"{event.id} came before the stretch the claim describes"
    if len(cited) < PRESS_MIN_WINS:
        return f"the press needs {PRESS_MIN_WINS} high ball wins; the claim cites {len(cited)}"
    return None


END_TO_END_MIN_WINS = 11  # the Scout's END_TO_END_WINS


def end_to_end_rule(claim: Claim, cited: Sequence[MatchEvent]) -> str | None:
    """A match broken open stands on the ball changing hands and the chances at both ends: every
    cited event is a ball win or a shot inside the stretch the claim describes, there are enough
    ball wins, and each side has a shot among them."""
    windows = [a.window for a in claim.assertions if a.window is not None]
    if not windows:
        return "an end-to-end claim must say which stretch of play it covers"
    spell = max(windows, key=lambda w: w.end_t)
    for event in cited:
        if not (is_ball_win(event) or isinstance(event, Shot)):
            return f"{event.id} is neither the ball won back nor a shot"
        if not spell.start_t <= event.t <= spell.end_t:
            return f"{event.id} came before the stretch the claim describes"
    wins = sum(map(is_ball_win, cited))
    if wins < END_TO_END_MIN_WINS:
        return f"end to end needs {END_TO_END_MIN_WINS} ball wins; the claim cites {wins}"
    if {e.team for e in cited if isinstance(e, Shot)} != set(Side):
        return "end to end needs a shot from each side"
    return None


def ref_rule(profile: Profile) -> EvidenceRule:
    """The referee's likely call, recomputed from the cited foul under the competition's profile
    (court.referee). The claim must cite the foul, carry the same decision, and say it in words."""

    def rule(claim: Claim, cited: Sequence[MatchEvent]) -> str | None:
        foul = next((e for e in cited if isinstance(e, Tackle) and e.team == claim.team), None)
        decision = ref_call(foul, profile) if foul is not None else None
        if decision is None:
            return "a ref's call must cite the foul, by the side it names"
        said = claim.call
        if said is None or (said.restart, said.card) != (decision.restart, decision.card):
            law = " and ".join(call_words(decision))
            stated = " and ".join(call_words(said)) if said else "no decision"
            return (
                f"at {profile} strictness the Law gives {law} for {foul.id}; the claim gives "
                f"{stated}"
            )
        text = claim.text.lower()
        missing = [w for w in call_words(decision) if w not in text]
        if missing:
            return f"the line must say the decision: {', '.join(missing)}"
        return None

    return rule


def recap_rule(claim: Claim, cited: Sequence[MatchEvent]) -> str | None:
    """A recap line states the match as it ended: a number about the whole match must be counted
    to the final whistle, so the line cites it, and a line about moments cites those moments."""
    whole_match = [a for a in claim.assertions if a.window is None and a.event_id is None]
    if whole_match and not any(isinstance(e, PeriodEnd) for e in cited):
        return "a recap line with whole-match numbers must cite the final whistle"
    return None


def answer_rule(claim: Claim, cited: Sequence[MatchEvent]) -> str | None:
    """An answer counts what had happened when it was asked (court.ask): a count over the match so
    far cites the moment it was counted to, so a viewer opening the evidence sees where it stops."""
    so_far = [a for a in claim.assertions if a.window is None and a.event_id is None]
    if so_far and not any(e.seq == claim.as_of_seq for e in cited):
        return (
            "a count of the match so far must cite the moment it was counted to "
            f"(e{claim.as_of_seq:05d})"
        )
    return None


def great_pass_rule(claim: Claim, cited: Sequence[MatchEvent]) -> str | None:
    """A pass is called great for what it made: the claim cites the completed pass and the
    shot it set up, both the side's own."""
    passes = {
        e.id
        for e in cited
        if isinstance(e, Pass) and e.team == claim.team and e.outcome is PassOutcome.COMPLETE
    }
    if any(
        isinstance(e, Shot) and e.team == claim.team and e.assist_event_id in passes for e in cited
    ):
        return None
    return "a great-pass claim must cite the completed pass and the shot it set up"


EVIDENCE_RULES: Mapping[AlertKind, EvidenceRule] = {
    AlertKind.GOAL: goal_rule,
    AlertKind.BIG_CHANCE: big_chance_rule,
    AlertKind.MOMENTUM_SWING: momentum_rule,
    AlertKind.GREAT_PASS: great_pass_rule,
    AlertKind.COUNTER: counter_rule,
    AlertKind.HIGH_PRESS: press_rule,
    AlertKind.END_TO_END: end_to_end_rule,
    AlertKind.REF_CALL: ref_rule("standard"),
    AlertKind.RECAP: recap_rule,
    AlertKind.ANSWER: answer_rule,
}

TOLERANCE = {"xg": 0.011, "shot_xg": 0.011}  # rounding slack; counts must match exactly
# A number standing on its own: not part of an event id (e00599) or a longer number.
NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")


class Critic:
    def __init__(
        self,
        rules: Mapping[AlertKind, EvidenceRule] | None = None,
        *,
        max_evidence_age_s: float = 900.0,
        hindsight: bool = False,
        strictness: Profile = "standard",
    ) -> None:
        # The competition's strictness decides what the referee's likely call is (court.referee).
        if rules is None:
            rules = {**EVIDENCE_RULES, AlertKind.REF_CALL: ref_rule(strictness)}
        self.rules = rules
        self.strictness = strictness
        self.max_evidence_age_s = max_evidence_age_s
        # After full time a claim may look back over the whole match (court.recap): evidence from
        # either half and any minute. Every other check stands.
        self.hindsight = hindsight

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
            stale = event.period != claim.period or claim.t - event.t > self.max_evidence_age_s
            if stale and not self.hindsight:
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
            # A number about one event must be about an event the claim cites, of the side the
            # assertion names: a true number about some other moment proves nothing about this one.
            if assertion.event_id is not None:
                event = state.get(assertion.event_id)
                if (
                    assertion.event_id not in claim.citations
                    or getattr(event, "team", None) != assertion.team
                ):
                    refuse(
                        RejectionCode.ASSERTION_MISMATCH,
                        f"{assertion.metric} on {assertion.event_id} must be about an event the "
                        f"claim cites, by {assertion.team}",
                    )
                    continue
            actual = measure(assertion, state, claim.as_of_seq)
            tolerance = TOLERANCE.get(assertion.metric, 0.0)
            if actual is None or abs(actual - assertion.value) > tolerance:
                shown = "nothing measurable" if actual is None else _fmt(actual)
                refuse(
                    RejectionCode.ASSERTION_MISMATCH,
                    f"claimed {assertion.metric}={_fmt(assertion.value)} for "
                    f"{assertion.team}, events show {shown}",
                )

        ungrounded = _ungrounded(claim)
        for number in ungrounded:
            refuse(
                RejectionCode.UNGROUNDED_NUMBER,
                f"the text says {number}, which none of the claim's figures or assertions support",
            )

        for name in _unbacked_names(claim, state):
            refuse(
                RejectionCode.UNGROUNDED_NAME,
                f"the text names {name}, whom none of the claim's evidence is about",
            )

        stated = len(dict.fromkeys(NUMBER.findall(claim.text)))
        return Verdict(
            claim=claim, reasons=tuple(reasons), numbers_checked=stated - len(ungrounded)
        )


def _ungrounded(claim: Claim) -> list[str]:
    """Numbers in the text that the claim's figures and assertions don't account for."""
    known = [*claim.figures.values(), *(a.value for a in claim.assertions)]
    stated = dict.fromkeys(NUMBER.findall(claim.text))
    return [n for n in stated if not any(abs(float(n) - k) < 0.005 for k in known)]


def _unbacked_names(claim: Claim, state: MatchState) -> list[str]:
    """Players of the match the text names (in full, or by a surname none of its own players
    share) whom the claim's evidence isn't about. Unchecked when the claim lists no names."""
    if claim.names is None:
        return []
    text = claim.text.lower()
    backed = {n.lower() for n in claim.names}
    surnames = {n.split()[-1] for n in backed}
    named = []
    for player in state.meta.players:
        full = player.name.lower()
        surname = full.split()[-1]
        if full in backed:
            continue
        if _says(text, full) or (surname not in surnames and _says(text, surname)):
            named.append(player.name)
    return named


def _says(text: str, words: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(words)}(?!\w)", text) is not None


# Eastern Arabic (U+0660) and Persian (U+06F0) digits, and the Arabic decimal separator, read as
# the ASCII they mean.
_DIGITS = {0x0660 + d: str(d) for d in range(10)} | {0x06F0 + d: str(d) for d in range(10)}
_DIGITS[0x066B] = "."


def invented_numbers(line: str, translation: str) -> list[str]:
    """Numbers a translation states that the verified line it translates doesn't.

    The Critic checked every number in the line; a translation must carry those numbers and no
    other, in any digits. A number it adds is unverified, so the translation can't air.
    """
    known = [float(n) for n in NUMBER.findall(line.translate(_DIGITS))]
    stated = dict.fromkeys(_numbers(translation.translate(_DIGITS)))
    return [n for n in stated if not any(abs(float(n) - k) < 0.005 for k in known)]


def _numbers(text: str) -> list[str]:
    # In Urdu and Arabic a digit can sit against a letter, so letters don't fence a number here.
    return re.findall(r"(?<![\d.])\d+(?:\.\d+)?", text)


def _seq_of(event_id: str) -> int:
    try:
        return int(event_id.removeprefix("e"))
    except ValueError:
        return -1


def _fmt(value: float) -> str:
    return f"{value:.0f}" if float(value).is_integer() else f"{value:.2f}"
