"""End to end: one synthetic match through all five agents, plus warm-path failure."""

import pytest

from court.config import DEFAULT_PRODUCT_NAME, product_name
from court.contracts import OUTPUT_ADAPTER, Cue, Degradation, RejectionNotice
from court.narrator import TemplateNarrator
from court.orchestrator import run_match
from match_events import Shot, ShotOutcome


class Collector(list):
    def __call__(self, output) -> None:
        self.append(output)


class FlakyNarrator(TemplateNarrator):
    """Backend down for the first `failures` calls, then healthy."""

    def __init__(self, failures: int) -> None:
        super().__init__()
        self.failures = failures

    def draft(self, alert, state):
        if self.failures > 0:
            self.failures -= 1
            raise ConnectionError("narrator backend unreachable")
        return super().draft(alert, state)


async def test_one_match_flows_end_to_end(match):
    out = Collector()
    orch = await run_match(match.stream(), sink=out)

    assert orch.stats["events"] == len(match.events)
    goals = [e for e in match.events if isinstance(e, Shot) and e.outcome is ShotOutcome.GOAL]
    goal_cues = [o for o in out if isinstance(o, Cue) and o.kind == "goal"]
    assert len(goal_cues) == len(goals)
    assert all(c.status == "verified" for c in goal_cues)


async def test_nothing_airs_without_real_prior_evidence(match):
    out = Collector()
    orch = await run_match(
        match.stream(), sink=out, narrator=TemplateNarrator(overreach_rate=0.5, seed=3)
    )
    assert any(isinstance(o, RejectionNotice) for o in out), "overreach should be caught"
    for cue in (o for o in out if isinstance(o, Cue)):
        assert cue.evidence
        for event_id in cue.evidence:
            event = orch.state.get(event_id)
            assert event is not None and event.t <= cue.t and event.period == cue.period


async def test_warm_path_failure_degrades_and_recovers(match):
    out = Collector()
    orch = await run_match(match.stream(), sink=out, narrator=FlakyNarrator(failures=4), retries=1)

    # the stream never stopped
    assert orch.stats["events"] == len(match.events)
    levels = [o.level for o in out if isinstance(o, Degradation)]
    assert levels == ["detection_only", "full"]
    degraded = [o for o in out if isinstance(o, Cue) and o.status == "detection_only"]
    assert len(degraded) == 2  # 4 failures / (1 try + 1 retry) = two alerts degraded
    assert all(c.evidence for c in degraded)


async def test_outputs_serialise_as_machine_readable_cues(match):
    out = Collector()
    await run_match(match.stream(), sink=out)
    for output in out:
        assert OUTPUT_ADAPTER.validate_json(OUTPUT_ADAPTER.dump_json(output)) == output


async def test_stream_must_begin_with_meta(match):
    with pytest.raises(ValueError, match="match_meta"):
        await run_match(list(match.events), sink=Collector())


def test_product_name_is_configurable(monkeypatch):
    assert product_name() == DEFAULT_PRODUCT_NAME
    monkeypatch.setenv("PRODUCT_NAME", "Renamed")
    assert product_name() == "Renamed"
