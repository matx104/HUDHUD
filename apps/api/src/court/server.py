"""The studio: a synthetic match, live on a web page, with every agent's work in view.

Judges and viewers open it in a browser (rules §4.8). A match streams as Server-Sent Events: the
clock and score, every shot, and every output of the court (cues with their receipts, the Critic's
refusals, spiked claims, changes of service level). From the studio a viewer can take the narrator
off air and put it back, to watch the Orchestrator recover, and can stress-test the Critic: a share
of drafts is corrupted on purpose, as the offline narrator's demo mode does, and the Critic has to
catch every one.

An open demo must not run up the bill: model-narrated matches are capped per day (then the offline
narrator takes over, and the studio says so), and so are concurrent streams.

    make studio        # http://localhost:8080
"""

import asyncio
import contextlib
import inspect
import json
import logging
import os
import random
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.transport_security import TransportSecuritySettings
from opentelemetry import trace
from opentelemetry.trace import SpanKind

from match_events import MatchMeta, Shot, ShotOutcome, Side, generate, minute_label

from . import telemetry
from .audit import AuditTrail, CosmosStore
from .config import product_name
from .contracts import OUTPUT_ADAPTER, Output
from .localizer import Localizer
from .mcp_server import server as critic_mcp
from .metrics import shot_xg
from .narrator import TemplateNarrator
from .orchestrator import run_match

STUDIO = Path(__file__).parent / "studio"
# The demo matches: 21 has two goals each way and two momentum swings; 7 has six goals; 33 a
# second-half momentum call.
DEMO_SEEDS = (21, 7, 33)
MAX_STREAMS = int(os.environ.get("STUDIO_MAX_STREAMS", "8"))
MAX_SESSION_S = 15 * 60  # a backstop: no stream outlives this, whatever the client does
log = logging.getLogger("court.studio")
DAILY_MODEL_MATCHES = int(os.environ.get("STUDIO_DAILY_MODEL_MATCHES", "200"))


class OffAir(RuntimeError):
    """The studio took the narrator off air."""


class Switchable:
    """The narrator with two studio controls: a switch that takes it off air (every call then
    fails, as an outage would), and a stress test that corrupts a share of its drafts."""

    def __init__(self, inner: Any, *, stress: float = 0.0, seed: int = 0) -> None:
        self.inner = inner
        self.on_air = True
        self.stress = stress
        self._rng = random.Random(seed)
        self._saboteur = TemplateNarrator(seed=seed)

    async def draft(self, alert, state):
        self._check()
        claim = self.inner.draft(alert, state)
        claim = await claim if inspect.isawaitable(claim) else claim
        if self._rng.random() < self.stress:
            return self._saboteur.overreach(claim, alert, state)
        return claim

    async def rewrite(self, verdict, state):
        self._check()
        claim = self.inner.rewrite(verdict, state)
        return await claim if inspect.isawaitable(claim) else claim

    def _check(self) -> None:
        if not self.on_air:
            raise OffAir("the narrator was taken off air in the studio")

    def __getattr__(self, name: str) -> Any:  # spend, meter, handovers
        return getattr(self.inner, name)


class ModelBudget:
    """Model-narrated matches per day (UTC). An open demo can't run up the bill."""

    def __init__(self, per_day: int) -> None:
        self.per_day, self.day, self.used = per_day, None, 0

    def take(self) -> bool:
        today = datetime.now(UTC).date()
        if today != self.day:
            self.day, self.used = today, 0
        if self.used >= self.per_day:
            return False
        self.used += 1
        return True

    @property
    def left(self) -> int:
        today = datetime.now(UTC).date()
        return self.per_day - (self.used if today == self.day else 0)


Narration = Literal["foundry", "template"]


class Session:
    def __init__(
        self,
        seed: int,
        *,
        narration: Narration,
        speed: float,
        start: int,
        mode: Literal["casual", "analyst"],
        stress: float,
        budget: ModelBudget,
        lang: Literal["en", "ur", "ar"] = "en",
    ) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.match = generate(seed)
        self.speed, self.start_t, self.mode, self.lang = speed, start * 60.0, mode, lang
        self.queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()
        self.notices: list[str] = []
        inner, self.narration = self._narrator(narration, seed, stress, budget)
        # The offline narrator overreaches by itself; a model's drafts are corrupted here.
        sabotage = 0.0 if self.narration == "template" else stress
        self.narrator = Switchable(inner, stress=sabotage, seed=seed)

    def _narrator(self, wanted: Narration, seed: int, stress: float, budget: ModelBudget):
        endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        if wanted == "foundry" and endpoint and budget.take():
            from .foundry import FoundryNarrator

            models = os.environ.get("FOUNDRY_MODELS", "gpt-4.1-mini,gpt-5-mini").split(",")
            return FoundryNarrator(project_endpoint=endpoint, models=models), "foundry"
        if wanted == "foundry":
            why = "today's model budget is spent" if endpoint else "no models are connected here"
            self.notices.append(f"{why}: the offline narrator calls this match")
        if self.lang != "en":
            self.notices.append("Urdu and Arabic need the models: lines stay in English")
        return TemplateNarrator(overreach_rate=stress, seed=seed), "template"

    def send(self, kind: str, data: dict[str, Any]) -> None:
        self.queue.put_nowait((kind, data))

    async def run(self) -> None:
        meta = self.match.meta
        attributes = {"hudhud.match_id": meta.match_id, "hudhud.seed": meta.seed}
        attributes |= {"hudhud.narrator": self.narration, "hudhud.surface": "studio"}
        try:
            with telemetry.tracer.start_as_current_span(
                "match", kind=SpanKind.CONSUMER, attributes=attributes
            ) as span:
                trail = None
                if endpoint := os.environ.get("COSMOS_ENDPOINT"):
                    trail = AuditTrail(CosmosStore(endpoint), meta, narrator=self.narration)
                    trail.start()
                sink = self._output if trail is None else trail.tee(self._output)
                orch = await run_match(
                    self._paced(),
                    sink=sink,
                    narrator=self.narrator,
                    localizer=Localizer(
                        mode=self.mode,
                        lang=self.lang,
                        translator=getattr(self.narrator.inner, "translate", None),
                    ),
                    quiet_until_t=self.start_t,
                )
                meter = getattr(self.narrator.inner, "meter", None)
                cost = round(meter.cost_usd(), 6) if meter else 0.0
                summary = {"stats": dict(orch.stats), "cost_usd": cost}
                if trail:
                    await trail.close(summary)
                    summary["audit"] = trail.report()
                span.set_attributes({f"hudhud.{k}": v for k, v in orch.stats.items()})
                span.set_attribute("hudhud.cost_usd", cost)
                self.send("end", summary)
        except Exception as error:  # tell the page, never leave it waiting; details stay here
            ref = uuid.uuid4().hex[:8]
            log.exception("studio match %s failed (ref %s)", self.match.meta.match_id, ref)
            trace.get_current_span().record_exception(error)
            self.send("error", {"detail": "the match stopped on a server error", "ref": ref})
        finally:
            self.queue.put_nowait(None)

    def _output(self, output: Output) -> None:
        self.send("output", OUTPUT_ADAPTER.dump_python(output, mode="json"))

    async def _paced(self) -> AsyncIterator[Any]:
        """The match stream, paced from the chosen minute, with the clock and shots for the page."""
        messages = list(self.match.stream())
        meta: MatchMeta = messages[0]
        yield meta
        names = {p.id: p.name for p in meta.players}
        score = {Side.HOME: 0, Side.AWAY: 0}
        minute, previous = None, None
        for event in messages[1:]:
            live = self.speed > 0 and event.t >= self.start_t
            if live and previous is not None and previous.period == event.period:
                await asyncio.sleep(max(0.0, event.t - previous.t) / self.speed)
            previous = event
            label = minute_label(event.t, event.period)
            if isinstance(event, Shot):
                score[event.team] += event.outcome is ShotOutcome.GOAL
                self.send("shot", _shot(event, label, names))
            if label != minute or isinstance(event, Shot):
                minute = label
                self.send(
                    "clock",
                    {
                        "minute": label,
                        "period": event.period,
                        "score": [score[Side.HOME], score[Side.AWAY]],
                    },
                )
            yield event


def _shot(shot: Shot, minute: str, names: dict[str, str]) -> dict[str, Any]:
    return {
        "id": shot.id,
        "minute": minute,
        "team": shot.team.value,
        "player": names.get(shot.player_id, ""),
        "x": round(shot.x, 1),
        "y": round(shot.y, 1),
        "xg": round(shot_xg(shot), 2),
        "outcome": shot.outcome.value,
    }


def _team(team) -> dict[str, str]:
    return {"name": team.name, "short": team.short_name, "color": team.color}


def _sse(kind: str, data: dict[str, Any]) -> str:
    return f"event: {kind}\ndata: {json.dumps(data)}\n\n"


def create_app() -> FastAPI:
    # The Critic as a remote MCP server at /mcp/ (ADR 0007). It is public, read-only and holds
    # nothing private, so DNS-rebinding protection (which guards local servers from web pages)
    # adds nothing: anyone may call it directly anyway.
    critic = critic_mcp.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI):
        async with critic_mcp.session_manager.run():
            yield

    app = FastAPI(
        title=f"{product_name()} studio", docs_url=None, redoc_url=None, lifespan=lifespan
    )
    sessions: dict[str, Session] = {}
    budget = ModelBudget(DAILY_MODEL_MATCHES)
    app.state.sessions = sessions  # read by the tests: every stream must leave none behind

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STUDIO / "index.html")

    @app.get("/api/config")
    def config() -> dict[str, Any]:
        matches = []
        for seed in DEMO_SEEDS:
            meta = generate(seed).meta
            matches.append({"seed": seed, "home": _team(meta.home), "away": _team(meta.away)})
        return {
            "product": product_name(),
            "matches": matches,
            "models": bool(os.environ.get("FOUNDRY_PROJECT_ENDPOINT")),
            "model_matches_left": budget.left,
        }

    @app.get("/api/stream")
    async def stream(
        request: Request,
        seed: int = 21,
        narration: Narration = "template",
        speed: float = 60.0,
        start: int = 0,
        mode: Literal["casual", "analyst"] = "analyst",
        stress: float = 0.25,
        lang: Literal["en", "ur", "ar"] = "en",
    ) -> StreamingResponse:
        if seed not in DEMO_SEEDS:
            raise HTTPException(404, f"no demo match with seed {seed}")
        if len(sessions) >= MAX_STREAMS:  # the quick answer; events() holds the line
            raise HTTPException(503, "the studio is full: try again in a minute")
        options = {
            "narration": narration,
            "speed": max(0.0, min(speed, 600.0)),
            "start": max(0, min(start, 90)),
            "mode": mode,
            "stress": max(0.0, min(stress, 0.5)),
            "lang": lang,
        }

        async def events() -> AsyncIterator[str]:
            # The session exists only once streaming starts, and leaves with its task: a client
            # that disconnects early can't strand one. The cap is checked again here, with no
            # await between the check and the registration, so a burst can't slip past it.
            if len(sessions) >= MAX_STREAMS:
                yield _sse("error", {"detail": "the studio is full: try again in a minute"})
                return
            session = Session(seed, budget=budget, **options)
            sessions[session.id] = session
            task = asyncio.create_task(session.run())
            task.add_done_callback(lambda _: sessions.pop(session.id, None))
            deadline = asyncio.get_running_loop().time() + MAX_SESSION_S
            meta = session.match.meta
            hello = {"session": session.id, "seed": seed, "narration": session.narration}
            hello |= {"home": _team(meta.home), "away": _team(meta.away)}
            hello |= {"notices": session.notices, "competition": meta.competition}
            try:
                yield _sse("hello", hello)
                while True:
                    left = deadline - asyncio.get_running_loop().time()
                    try:
                        item = await asyncio.wait_for(session.queue.get(), timeout=max(left, 0))
                    except TimeoutError:
                        yield _sse(
                            "error", {"detail": "this match ran past the studio's time limit"}
                        )
                        break
                    if item is None or await request.is_disconnected():
                        break
                    yield _sse(*item)
            finally:
                task.cancel()
                sessions.pop(session.id, None)

        headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        return StreamingResponse(events(), media_type="text/event-stream", headers=headers)

    @app.post("/api/sessions/{session_id}/air")
    def air(session_id: str, on: bool) -> dict[str, bool]:
        session = sessions.get(session_id)
        if session is None:
            raise HTTPException(404, "no such match is running")
        session.narrator.on_air = on
        return {"on_air": on}

    app.mount("/mcp", critic)
    app.mount("/static", StaticFiles(directory=STUDIO), name="static")
    return app


telemetry.configure(service="studio")
app = create_app()
