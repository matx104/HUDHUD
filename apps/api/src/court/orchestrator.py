"""Orchestrator: owns shared match state and the hot path, supervises the warm path.

Hot path (every event, deterministic, never blocks): ingest -> MatchState -> Scout.
Warm path (per alert, fallible): the Agent Framework narrative workflow.

If the warm path fails, the Orchestrator retries; if it still fails, the broadcast
degrades to detection-only cues (the Scout's computed, evidence-linked facts) and
announces the change. It never goes dark. When the warm path recovers, full service
resumes and that is announced too.
"""

import asyncio
from collections import Counter
from collections.abc import AsyncIterable, Callable, Iterable

from match_events import MatchEvent, MatchMeta, StreamMessage, minute_label

from .contracts import Alert, Cue, Degradation, Output, RejectionNotice, Spiked
from .critic import Critic
from .localizer import Localizer
from .narrator import Narrator, TemplateNarrator
from .scout import Scout
from .state import MatchState
from .telemetry import tracer
from .workflow import build_narrative_workflow

Sink = Callable[[Output], None]


class Orchestrator:
    def __init__(
        self,
        meta: MatchMeta,
        *,
        sink: Sink,
        scout: Scout | None = None,
        narrator: Narrator | None = None,
        critic: Critic | None = None,
        localizer: Localizer | None = None,
        max_attempts: int = 3,
        retries: int = 1,
    ) -> None:
        self.state = MatchState(meta)
        self.scout = scout or Scout()
        self.localizer = localizer or Localizer()
        self.workflow = build_narrative_workflow(
            narrator=narrator or TemplateNarrator(),
            critic=critic or Critic(),
            localizer=self.localizer,
            state=self.state,
            max_attempts=max_attempts,
        )
        self.retries = retries
        self.level: str = "full"
        self.stats: Counter[str] = Counter()
        self._sink = sink
        self._outputs: list[Output] = []  # what the alert being narrated has produced so far

    async def ingest(self, event: MatchEvent) -> None:
        self.state.apply(event)
        self.stats["events"] += 1
        for alert in self.scout.observe(event, self.state):
            self.stats["alerts"] += 1
            await self._narrate(alert)

    async def _narrate(self, alert: Alert) -> None:
        with tracer.start_as_current_span(f"alert {alert.kind}") as span:
            self._outputs = []
            await self._warm_path(alert)
            span.set_attributes(_outcome(alert, self._outputs, self.level))

    async def _warm_path(self, alert: Alert) -> None:
        failure: Exception | None = None
        for _ in range(self.retries + 1):
            try:
                result = await self.workflow.run(alert)
            except Exception as exc:  # the warm path may fail; the broadcast may not
                failure = exc
                self.stats["warm_path_failures"] += 1
                continue
            if self.level != "full":
                self._set_level("full", alert, "narrative path recovered; full service resumed")
            for output in result.get_outputs():
                self._emit(output)
            return
        if self.level != "detection_only":
            detail = f"narrative path failed ({type(failure).__name__}): detection-only cues"
            self._set_level("detection_only", alert, detail)
        self._emit(self.localizer.detection_cue(alert, self.state))

    def _set_level(self, level: str, alert: Alert, detail: str) -> None:
        self.level = level
        self._emit(
            Degradation(
                level=level,
                period=alert.period,
                t=alert.t,
                minute=minute_label(alert.t, alert.period),
                detail=detail,
            )
        )

    def _emit(self, output: Output) -> None:
        match output:
            case Cue(status="verified"):
                self.stats["aired"] += 1
            case Cue():
                self.stats["aired_detection_only"] += 1
            case RejectionNotice():
                self.stats["rejected"] += 1
            case Spiked():
                self.stats["spiked"] += 1
            case Degradation():
                self.stats["level_changes"] += 1
        self._outputs.append(output)
        self._sink(output)


def _outcome(alert: Alert, outputs: list[Output], level: str) -> dict[str, str | int]:
    """Span attributes for one alert: what aired, after how many tries, and what was refused."""
    cue = next((o for o in outputs if isinstance(o, Cue)), None)
    refused = [o for o in outputs if isinstance(o, RejectionNotice | Spiked)]
    spiked = any(isinstance(o, Spiked) for o in outputs)
    return {
        "hudhud.alert.id": alert.id,
        "hudhud.alert.kind": alert.kind.value,
        "hudhud.team": alert.team.value,
        "hudhud.minute": minute_label(alert.t, alert.period),
        "hudhud.outcome": "spiked" if spiked else cue.status if cue else "none",
        "hudhud.attempts": cue.attempts if cue else len(refused),
        "hudhud.rejections": len(refused),
        "hudhud.rejection_codes": ",".join(sorted({r.code for o in refused for r in o.reasons})),
        "hudhud.service_level": level,
    }


async def _iterate(messages: Iterable[StreamMessage] | AsyncIterable[StreamMessage]):
    if isinstance(messages, AsyncIterable):
        async for message in messages:
            yield message
    else:
        for message in messages:
            yield message


async def run_match(
    messages: Iterable[StreamMessage] | AsyncIterable[StreamMessage],
    *,
    sink: Sink,
    speed: float = 0.0,
    **orchestrator_kwargs: object,
) -> Orchestrator:
    """Consume one match stream (match_meta first). `speed` > 0 paces the replay at
    that many match-seconds per wall-second; 0 runs as fast as possible."""
    orchestrator: Orchestrator | None = None
    previous: MatchEvent | None = None
    async for message in _iterate(messages):
        if isinstance(message, MatchMeta):
            orchestrator = Orchestrator(message, sink=sink, **orchestrator_kwargs)
            continue
        if orchestrator is None:
            raise ValueError("stream must start with match_meta")
        if speed > 0 and previous is not None and previous.period == message.period:
            await asyncio.sleep(max(0.0, message.t - previous.t) / speed)
        previous = message
        await orchestrator.ingest(message)
    if orchestrator is None:
        raise ValueError("empty stream")
    return orchestrator
