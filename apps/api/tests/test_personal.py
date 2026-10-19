"""Personal modes (§4.1 i e): one viewer's way into the same verified broadcast."""

import asyncio

import pytest

from court.contracts import Cue, Degradation, Preferences, RejectionNotice
from court.metrics import compute
from court.orchestrator import run_match
from court.personal import Personal, PreferenceError, check, metric_line, player_card
from match_events import Pass, PassOutcome, Shot, Side


@pytest.fixture(scope="module")
def broadcast(swing_match):
    outputs = []
    asyncio.run(run_match(swing_match.stream(), sink=outputs.append))
    return outputs


def _cues(outputs):
    return [o for o in outputs if isinstance(o, Cue)]


def _busiest(cues) -> str:
    """The player tagged on most cues: someone a fan could follow."""
    counts: dict[str, int] = {}
    for cue in cues:
        for tag in cue.players:
            counts[tag.id] = counts.get(tag.id, 0) + 1
    return max(counts, key=counts.__getitem__)


def test_a_favourite_club_marks_its_moments_and_still_airs_the_rivals(swing_match, broadcast):
    personal = Personal(Preferences(club=Side.HOME), swing_match.meta)
    cues = _cues(broadcast)
    seen = [personal.view(c) for c in cues]
    assert all(s is not None for s in seen), "nothing is hidden for a favourite club"
    for cue, mine in zip(cues, seen, strict=True):
        assert mine.for_you == (("club",) if cue.team is Side.HOME else ("rival",))
        assert (mine.text, mine.evidence, mine.receipt) == (cue.text, cue.evidence, cue.receipt)
        lifted = cue.team is Side.HOME and cue.priority < 1
        assert (mine.priority > cue.priority) == lifted


def test_player_focus_keeps_one_players_moments_and_counts_the_rest(swing_match, broadcast):
    cues = _cues(broadcast)
    player = _busiest(cues)
    personal = Personal(Preferences(player=player, focus="player"), swing_match.meta)
    seen = [s for s in (personal.view(o) for o in broadcast) if s is not None]
    kept = _cues(seen)
    assert kept and all("player" in c.for_you for c in kept)
    assert all(any(t.id == player for t in c.players) for c in kept)
    assert personal.hidden == len(cues) - len(kept) > 0
    others = [o for o in broadcast if isinstance(o, RejectionNotice | Degradation)]
    assert all(o in seen for o in others), "the Critic's desk is everyone's"


def test_preferences_must_fit_the_match(swing_match):
    with pytest.raises(PreferenceError, match="no player"):
        check(Preferences(player="nobody"), swing_match.meta)
    with pytest.raises(PreferenceError, match="needs a favourite player"):
        check(Preferences(focus="player"), swing_match.meta)


def test_the_player_card_counts_only_that_players_own_events(swing_match):
    events = swing_match.events
    player = next(p for p in swing_match.meta.players if p.position == "MF")
    card = player_card(player.id, swing_match.meta, events)
    passes = [e for e in events if isinstance(e, Pass) and e.player_id == player.id]
    assert card["passes"] == len(passes)
    assert card["passes_completed"] == sum(p.outcome is PassOutcome.COMPLETE for p in passes)
    assert card["shots"] == sum(isinstance(e, Shot) and e.player_id == player.id for e in events)
    by_id = {e.id: e for e in events}
    assert card["evidence"] and all(by_id[i].player_id == player.id for i in card["evidence"])


def test_single_metric_mode_counts_as_the_critic_does(swing_match):
    events = swing_match.events
    for metric in ("xg", "shots", "final_third_passes"):
        line = metric_line(metric, events)
        assert line["home"] == compute(metric, Side.HOME, events)
        assert line["away"] == compute(metric, Side.AWAY, events)
    pct = metric_line("pass_completion", events)["home"]
    done, tried = (compute(m, Side.HOME, events) for m in ("passes_completed", "passes"))
    assert pct == round(100 * done / tried)
