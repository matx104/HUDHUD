"""The audit trail keeps every output of a match, and a failing store never costs a cue."""

import asyncio

from court.audit import AuditTrail, MemoryStore
from court.contracts import Cue
from court.narrator import TemplateNarrator
from court.orchestrator import run_match


class BrokenStore(MemoryStore):
    async def write(self, record):
        raise ConnectionError("store unreachable")


class SlowStore(MemoryStore):
    async def write(self, record):
        await asyncio.sleep(60)


async def _run(match, store, **close):
    """One match, the template overreaching as in the demo, so the Critic refuses some claims."""
    aired, messages = [], list(match.stream())
    trail = AuditTrail(store, messages[0], narrator="template")
    trail.start()
    narrator = TemplateNarrator(overreach_rate=0.25, seed=match.meta.seed)
    orch = await run_match(messages, sink=trail.tee(aired.append), narrator=narrator)
    await trail.close(dict(orch.stats), **close)
    return trail, aired


async def test_every_output_is_kept_in_order_between_run_and_summary(swing_match):
    store = MemoryStore()
    trail, aired = await _run(swing_match, store)
    kinds = [r["type"] for r in store.records]
    assert kinds[0] == "run" and kinds[-1] == "summary"
    assert kinds[1:-1] == [o.type for o in aired]
    assert {r["matchId"] for r in store.records} == {swing_match.meta.match_id}
    assert len({r["id"] for r in store.records}) == len(store.records)
    assert trail.written == len(store.records) and trail.failure is None


async def test_a_rejection_is_kept_with_the_critics_reasons(swing_match):
    store = MemoryStore()
    await _run(swing_match, store)
    rejected = [r for r in store.records if r["type"] in ("rejection", "spiked")]
    assert rejected, "seed 21's run includes refused claims"
    assert all(r["reasons"] and r["claim"]["citations"] is not None for r in rejected)


def _untimed(outputs):
    """The same match airs the same outputs; only the receipts' timings differ run to run."""
    return [
        o.model_copy(update={"receipt": o.receipt.model_copy(update={"latency_ms": 0.0})})
        if isinstance(o, Cue) and o.receipt
        else o
        for o in outputs
    ]


async def test_a_broken_store_costs_the_trail_not_the_broadcast(swing_match):
    _, expected = await _run(swing_match, MemoryStore())
    trail, aired = await _run(swing_match, BrokenStore())
    assert _untimed(aired) == _untimed(expected)
    assert trail.written == 0 and trail.failure.startswith("ConnectionError")
    assert trail.dropped == len(expected) + 2


async def test_a_hanging_store_is_abandoned_at_close(swing_match):
    trail, aired = await _run(swing_match, SlowStore(), timeout_s=0.2)
    assert aired and trail.failure


async def test_an_answer_joins_its_matchs_run_and_a_failing_store_costs_only_the_record():
    from court.ask import MatchTools, RuleAnswerer, ask
    from court.audit import record_answer
    from court.state import MatchState
    from match_events import generate

    match = generate(21)
    state = MatchState(match.meta)
    for event in match.events:
        state.apply(event)
    answer = await ask("What's the score?", MatchTools(state), RuleAnswerer(), stress=True)
    store = MemoryStore()
    kept = await record_answer(store, match_id=match.meta.match_id, run_id="r1", answer=answer)
    [record] = store.records
    assert kept and record["type"] == "answer" and record["runId"] == "r1"
    assert record["matchId"] == match.meta.match_id and record["id"] == f"r1-{answer.id}"
    assert record["question"] == "What's the score?" and record["status"] == "verified"
    assert record["refused"], "the drafts the Critic refused are kept too"

    class Broken(MemoryStore):
        async def write(self, record):
            raise ConnectionError("down")

    assert not await record_answer(Broken(), match_id="m", run_id="r", answer=answer)
