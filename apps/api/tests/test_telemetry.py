"""Each alert's span says what became of it, so a workbook can chart the Critic's work."""

from contextlib import contextmanager

from court import orchestrator
from court.contracts import Cue, RejectionNotice, Spiked
from court.narrator import TemplateNarrator
from court.orchestrator import run_match


class RecordingTracer:
    """Stands in for OpenTelemetry's tracer: records each span's name and attributes."""

    def __init__(self) -> None:
        self.spans: list[tuple[str, dict]] = []

    @contextmanager
    def start_as_current_span(self, name, **_):
        attributes: dict = {}
        span = type("Span", (), {"set_attributes": lambda _, a: attributes.update(a)})()
        yield span
        self.spans.append((name, attributes))


async def test_every_alert_span_records_its_outcome(swing_match, monkeypatch):
    tracer = RecordingTracer()
    monkeypatch.setattr(orchestrator, "tracer", tracer)
    outputs = []
    narrator = TemplateNarrator(overreach_rate=0.25, seed=21)
    orch = await run_match(list(swing_match.stream()), sink=outputs.append, narrator=narrator)

    assert len(tracer.spans) == orch.stats["alerts"]
    attrs = [a for _, a in tracer.spans]
    aired = sum(a["hudhud.outcome"] == "verified" for a in attrs)
    assert aired == sum(isinstance(o, Cue) and o.status == "verified" for o in outputs)
    refused = sum(isinstance(o, RejectionNotice | Spiked) for o in outputs)
    assert sum(a["hudhud.rejections"] for a in attrs) == refused > 0
    retried = [a for a in attrs if a["hudhud.rejections"]]
    assert all(a["hudhud.rejection_codes"] for a in retried)
    assert all(
        a["hudhud.attempts"] == a["hudhud.rejections"] + 1
        for a in retried
        if a["hudhud.outcome"] == "verified"
    )
