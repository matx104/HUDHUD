"""The rules' §4.1 cues: pass quality, speed, and player tags, every number checked."""

from statistics import mean

from court.contracts import AlertKind, Assertion, Cue, RejectionCode
from court.critic import Critic
from court.metrics import event_metric, measure
from court.narrator import TemplateNarrator
from court.orchestrator import run_match
from court.scout import GREAT_PASS_DIFFICULTY, Scout
from court.state import MatchState
from court.tags import FAST_SHOT_KMH
from match_events import Pass, generate


def _alerts(seed: int, kind: AlertKind):
    match = generate(seed)
    state, scout = MatchState(match.meta), Scout()
    for event in match.events:
        state.apply(event)
        for alert in scout.observe(event, state):
            if alert.kind is kind:
                yield alert, state


def test_great_passes_come_about_once_a_match():
    per_match = [sum(1 for _ in _alerts(seed, AlertKind.GREAT_PASS)) for seed in range(60)]
    assert 0.4 <= mean(per_match) <= 1.5


def test_a_great_pass_airs_with_its_quality_checked():
    critic, narrator = Critic(), TemplateNarrator()
    for alert, state in _alerts(7, AlertKind.GREAT_PASS):
        claim = narrator.draft(alert, state)
        verdict = critic.review(claim, state)
        assert verdict.approved, verdict.reasons
        assert {a.metric for a in claim.assertions} == {
            "pass_distance",
            "pass_difficulty",
            "pass_accuracy",
        }
        assert alert.metrics["pass_difficulty"] >= GREAT_PASS_DIFFICULTY
        assert f"difficulty {alert.metrics['pass_difficulty']:.0f} of 100" in claim.text


def test_a_great_pass_must_cite_the_shot_it_made_and_its_numbers_must_hold():
    critic, narrator = Critic(), TemplateNarrator(overreach_rate=0.0)
    alert, state = next(_alerts(7, AlertKind.GREAT_PASS))
    claim = narrator.draft(alert, state)
    pass_only = claim.model_copy(update={"citations": claim.citations[:1]})
    assert RejectionCode.INSUFFICIENT_EVIDENCE in {
        r.code for r in critic.review(pass_only, state).reasons
    }
    inflated = TemplateNarrator().compose(
        alert, state, attempt=1, metrics=alert.metrics | {"pass_difficulty": 95}
    )
    assert RejectionCode.ASSERTION_MISMATCH in {
        r.code for r in critic.review(inflated, state).reasons
    }


def test_event_metrics_are_recomputed_from_the_event_itself(match):
    state = MatchState(match.meta)
    for event in match.events:
        state.apply(event)
    pass_ = next(e for e in match.events if isinstance(e, Pass))
    claim_of = lambda metric, value: Assertion(  # noqa: E731
        metric=metric, team=pass_.team, value=value, event_id=pass_.id
    )
    assert measure(claim_of("pass_difficulty", 0), state, state.last_seq) == round(
        100 * pass_.difficulty
    )
    assert measure(claim_of("shot_speed", 0), state, state.last_seq) is None  # not a shot
    assert event_metric("pass_accuracy", pass_) == round(100 * pass_.accuracy)


async def test_cues_tag_their_players_with_threshold_badges():
    outputs = []
    match = generate(7)
    await run_match(list(match.stream()), sink=outputs.append, narrator=TemplateNarrator())
    cues = [o for o in outputs if isinstance(o, Cue)]
    goals = [c for c in cues if c.kind is AlertKind.GOAL]
    assert all(any(p.role == "scorer" for p in c.players) for c in goals)
    assisted = [c for c in goals if len(c.evidence) == 2]
    assert all({p.role for p in c.players} == {"scorer", "assister"} for c in assisted)
    fast = [c for c in cues if "struck at" in c.text]
    assert fast and all(
        any(b.endswith("km/h shot") for p in c.players for b in p.badges) for c in fast
    )
    for c in cues:
        for p in c.players:
            for badge in p.badges:
                if badge.endswith("km/h shot"):
                    assert int(badge.split()[0]) >= FAST_SHOT_KMH
