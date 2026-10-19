"""The studio: a synthetic match, live on a web page, with every agent's work in view.

Judges and viewers open it in a browser (rules §4.8). A match streams as Server-Sent Events: the
clock and score, every shot, and every output of the court (cues with their receipts, the Critic's
refusals, spiked claims, changes of service level). From the studio a viewer can take the narrator
off air and put it back, to watch the Orchestrator recover, and can stress-test the Critic: a share
of drafts is corrupted on purpose, as the offline narrator's demo mode does, and the Critic has to
catch every one.

An open demo must not run up the bill: model-narrated matches are capped per day (then the offline
narrator takes over, and the studio says so), and so are concurrent streams.

Personal modes (court.personal) ride in the address too: a favourite club and player mark the cues
that are the viewer's own, player focus follows one player with a live card, and single-metric mode
follows one number for both sides. The models tell the line from the favourite club's side; the
Critic checks it as it checks every line. At full time the page gets the recap (court.recap).
With SPEECH_RESOURCE_ID and SPEECH_REGION set, the page can ask for any line that aired to be
spoken aloud (court.speech): by its cue's id, never as free text.

A viewer can ask the match a question, during it or after full time (court.ask): the narrator
answers from the Scout's tools, and the Critic checks the answer before the page shows it. A
model-narrated match answers with the models; otherwise, or when they fail, the offline answerer
does. Questions are capped per match. With the voice connected, a question can be asked out loud:
the page records it and the studio turns it into words in the match's language, keeping no audio.

The Critic is also an A2A agent at /a2a/ (court.a2a_server): another agent can read its card and
put claims or questions to it.

On Azure the studio is private (docs/azure.md, "The wall"): Cloudflare Access signs the owner in at
studio.hudhud.com.pk, and a Worker (edge/) carries each request on to Azure. With `ACCESS_TEAM` and
`ACCESS_AUD` set, the studio refuses any request that doesn't carry a token Access signed for it, so
its own Azure address is no way around the wall.

    make studio        # http://localhost:8091
"""

import asyncio
import contextlib
import functools
import inspect
import json
import logging
import os
import random
import threading
import time
import urllib.request
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import jwt
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.transport_security import TransportSecuritySettings
from opentelemetry import trace
from opentelemetry.trace import SpanKind

from match_events import MatchMeta, Shot, ShotOutcome, Side, generate, minute_label

from . import telemetry
from .ask import MAX_QUESTION, MatchTools, RuleAnswerer, held_back
from .ask import ask as ask_match
from .audit import AuditTrail, CosmosStore, record_answer
from .config import product_name
from .contracts import OUTPUT_ADAPTER, Answer, Cue, Output, Preferences, TickerMetric
from .critic import Critic
from .localizer import Localizer
from .mcp_server import server as critic_mcp
from .metrics import shot_xg
from .narrator import TemplateNarrator
from .orchestrator import run_match
from .personal import Personal, PreferenceError, metric_line, player_card
from .personal import check as check_preferences
from .recap import build as build_recap
from .recap import render_html as recap_page
from .referee import Profile
from .scout import Scout
from .shield import Shield
from .speech import (
    MAX_LISTEN_S,
    WAV_RATE,
    NothingHeard,
    SpeechBudgetSpent,
    SpeechUnavailable,
    Voice,
)
from .state import MatchState

STUDIO = Path(__file__).parent / "studio"
# The demo matches: 21 has two goals each way and two momentum swings; 7 has six goals; 33 a
# second-half momentum call.
DEMO_SEEDS = (21, 7, 33)
MAX_STREAMS = int(os.environ.get("STUDIO_MAX_STREAMS", "8"))
MAX_SESSION_S = 15 * 60  # a backstop: no stream outlives this, whatever the client does
log = logging.getLogger("court.studio")
DAILY_MODEL_MATCHES = int(os.environ.get("STUDIO_DAILY_MODEL_MATCHES", "200"))
MAX_QUESTIONS = int(os.environ.get("STUDIO_MAX_QUESTIONS", "12"))  # per match
SHIELD = "Prompt Shields (Azure AI Content Safety)"
BOARDS = 16  # matches a viewer can still ask about, the latest, after their stream has ended


class AccessKeys:
    """The Access team's signing keys, by key id. A token naming a key not seen yet refreshes them,
    but at most once every `cooldown_s`, and never while a refresh is under way: made-up key ids
    can't turn requests into fetches.
    """

    def __init__(self, url: str, *, cooldown_s: float = 300.0) -> None:
        self.url, self.cooldown_s = url, cooldown_s
        self._keys: dict[str, Any] = {}
        self._fetched = float("-inf")
        self._lock = threading.Lock()

    def cached(self, kid: str) -> Any | None:
        return self._keys.get(kid)

    def get(self, kid: str) -> Any | None:
        """The key, refreshing first if it's unknown and the cooldown has passed. Blocks on the
        network when it refreshes: call it off the event loop."""
        if kid in self._keys or not self._lock.acquire(blocking=False):
            return self._keys.get(kid)
        try:
            if time.monotonic() - self._fetched >= self.cooldown_s:
                self._fetched = time.monotonic()
                self._keys = self._fetch() or self._keys
        finally:
            self._lock.release()
        return self._keys.get(kid)

    def _fetch(self) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(self.url, timeout=10) as response:
                keys = jwt.PyJWKSet.from_dict(json.load(response)).keys
        except (OSError, ValueError, jwt.PyJWTError):
            log.warning("couldn't fetch the Access signing keys from %s", self.url)
            return {}
        return {k.key_id: k.key for k in keys if k.key_id}


class AccessOnly:
    """Lets through only requests Cloudflare Access let in. Access signs a token for each one
    (Cf-Access-Jwt-Assertion), checked here against the team's published keys and this app's
    audience tag: nothing secret is stored. Container Apps' health probes call /healthz directly,
    so it stays open; it says only "ok".
    """

    HEADER = b"cf-access-jwt-assertion"

    def __init__(self, app: Any, *, team: str, audience: str, keys: Any = None) -> None:
        self.app, self.audience = app, audience
        self.issuer = f"https://{team}"
        self.keys = keys or AccessKeys(f"{self.issuer}/cdn-cgi/access/certs")

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http" and scope["path"] != "/healthz":
            token = dict(scope["headers"]).get(self.HEADER, b"").decode()
            if not await self._signed(token):
                refused = PlainTextResponse(f"This {product_name()} studio is private.", 403)
                return await refused(scope, receive, send)
        await self.app(scope, receive, send)

    async def _signed(self, token: str) -> bool:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            return False
        kid = header.get("kid")
        if header.get("alg") != "RS256" or not isinstance(kid, str):
            return False
        key = self.keys.cached(kid) or await asyncio.to_thread(self.keys.get, kid)
        if key is None:
            return False
        try:
            jwt.decode(token, key, algorithms=["RS256"], audience=self.audience, issuer=self.issuer)
        except jwt.PyJWTError:
            return False
        return True


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


class Spoken:
    """The lines a viewer saw air, by session and cue, for the voice: the last `size` of them, so
    a line can still be spoken just after full time, and nothing else can be."""

    def __init__(self, size: int = 2000) -> None:
        self.size, self._lines = size, OrderedDict()

    def keep(self, session: str, cue: str, text: str, lang: str) -> None:
        self._lines[(session, cue)] = (text, lang)
        while len(self._lines) > self.size:
            self._lines.popitem(last=False)

    def line(self, session: str, cue: str) -> tuple[str, str] | None:
        return self._lines.get((session, cue))


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
        prefs: Preferences | None = None,
        strictness: Profile = "standard",
        spoken: Spoken | None = None,
        shield: Shield | None = None,
    ) -> None:
        self.spoken = spoken
        self.shield = shield  # Prompt Shields, read before any model sees a question
        self.strictness = strictness  # how strictly the referee's likely calls are read
        self.stress = stress
        self.id = uuid.uuid4().hex[:12]
        self.match = generate(seed)
        self.speed, self.start_t, self.mode, self.lang = speed, start * 60.0, mode, lang
        self.prefs = prefs or Preferences()
        self.personal = Personal(self.prefs, self.match.meta)
        self.record: list[Output] = []  # everything the court put out, for the recap
        # The events so far, for the viewer's questions (court.ask): the page's own copy, so a
        # question reads the match as the viewer has seen it, live or after full time.
        self.state = MatchState(self.match.meta)
        self.asked = 0
        self._ask_rng = random.Random(seed + 1)
        self.run_id: str | None = None  # the audit trail's run, for the answers' records
        self._writes: set[asyncio.Task] = set()
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
            club = self.prefs.club and self.match.meta.team(self.prefs.club).name
            narrator = FoundryNarrator(project_endpoint=endpoint, models=models, viewer_club=club)
            return narrator, "foundry"
        if wanted == "foundry":
            why = "today's model budget is spent" if endpoint else "no models are connected here"
            self.notices.append(f"{why}: the offline narrator calls this match")
        if self.lang != "en":
            self.notices.append("Urdu and Arabic need the models: lines stay in English")
        return TemplateNarrator(overreach_rate=stress, seed=seed), "template"

    def send(self, kind: str, data: dict[str, Any]) -> None:
        self.queue.put_nowait((kind, data))

    async def ask(self, question: str) -> Answer:
        """A viewer's question, answered from the events so far (court.ask), and kept in the
        match's audit trail when it has one."""
        answer = await self._answer(question)
        endpoint = os.environ.get("COSMOS_ENDPOINT")
        if endpoint and self.run_id:
            write = record_answer(
                CosmosStore(endpoint),
                match_id=self.match.meta.match_id,
                run_id=self.run_id,
                answer=answer,
            )
            task = asyncio.create_task(write)
            self._writes.add(task)  # held until written: a bare task can be collected mid-write
            task.add_done_callback(self._writes.discard)
        return answer

    async def _answer(self, question: str) -> Answer:
        """The models answer a model-narrated match while the narrator is on air; otherwise, or
        if they fail, the offline answerer does, from the same moment. The stress test
        overreaches on a share of answers, as it does on lines."""
        tools = MatchTools(self.state)
        stress = self._ask_rng.random() < self.stress
        model = self.narrator.inner if self.narration == "foundry" else None
        attack = None
        if model is not None and self.narrator.on_air and self.shield is not None:
            # A model reads only a question the shield passed. Flagged: fixed words. No verdict
            # (the shield is down): the offline answerer takes it, and no model reads it.
            attack = await self.shield.attack(question)
            if attack:
                return held_back(question, tools, "instruction", screened_by=SHIELD)
            if attack is None:
                model = None
        if model is not None and self.narrator.on_air:
            translate = None
            if self.lang != "en":
                localizer = Localizer(lang=self.lang, translator=model.translate)
                localizer.bind(self.match.meta)
                translate = localizer.translate
            try:
                answer = await ask_match(
                    question,
                    tools,
                    model,
                    stress=stress,
                    lang=self.lang,
                    translate=translate,
                    spend=model.spend,
                )
                if attack is False:
                    receipt = answer.receipt.model_copy(update={"screened_by": SHIELD})
                    answer = answer.model_copy(update={"receipt": receipt})
                return answer
            except Exception:  # an outage costs the model's answer, never the answer
                log.exception("the models couldn't answer; the offline answerer does")
        tools = MatchTools(self.state, as_of_seq=tools.as_of_seq)
        return await ask_match(question, tools, RuleAnswerer(), stress=stress)

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
                    self.run_id = trail.run_id
                sink = self._output if trail is None else trail.tee(self._output)
                orch = await run_match(
                    self._paced(),
                    sink=sink,
                    narrator=self.narrator,
                    scout=Scout(strictness=self.strictness),
                    critic=Critic(strictness=self.strictness),
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
                if self.prefs.focus == "player":
                    summary["hidden_by_focus"] = self.personal.hidden
                if trail:
                    await trail.close(summary)
                    summary["audit"] = trail.report()
                span.set_attributes({f"hudhud.{k}": v for k, v in orch.stats.items()})
                span.set_attribute("hudhud.cost_usd", cost)
                recap = build_recap(orch.state, self.record)
                self.send("recap", {"html": recap_page(recap), "refused": len(recap.refused)})
                self.send("end", summary)
        except Exception as error:  # tell the page, never leave it waiting; details stay here
            ref = uuid.uuid4().hex[:8]
            log.exception("studio match %s failed (ref %s)", self.match.meta.match_id, ref)
            trace.get_current_span().record_exception(error)
            self.send("error", {"detail": "the match stopped on a server error", "ref": ref})
        finally:
            self.queue.put_nowait(None)

    def _output(self, output: Output) -> None:
        """What the court produced, as this viewer sees it (the audit trail keeps it unchanged)."""
        self.record.append(output)
        if (seen := self.personal.view(output)) is not None:
            if isinstance(seen, Cue) and self.spoken is not None:
                self.spoken.keep(self.id, seen.id, seen.text, seen.lang)
            self.send("output", OUTPUT_ADAPTER.dump_python(seen, mode="json"))

    def _personal(self, events: list[Any]) -> None:
        """The player card and the single metric, recounted from the events so far."""
        update: dict[str, Any] = {}
        if self.prefs.player:
            update["card"] = player_card(self.prefs.player, self.match.meta, events)
        if self.prefs.metric:
            update["metric"] = metric_line(self.prefs.metric, events)
        if update:
            self.send("personal", update)

    async def _paced(self) -> AsyncIterator[Any]:
        """The match stream, paced from the chosen minute, with the clock and shots for the page."""
        messages = list(self.match.stream())
        meta: MatchMeta = messages[0]
        yield meta
        names = {p.id: p.name for p in meta.players}
        score = {Side.HOME: 0, Side.AWAY: 0}
        minute, previous, seen = None, None, []
        for event in messages[1:]:
            live = self.speed > 0 and event.t >= self.start_t
            if live and previous is not None and previous.period == event.period:
                await asyncio.sleep(max(0.0, event.t - previous.t) / self.speed)
            previous = event
            seen.append(event)
            self.state.apply(event)
            label = minute_label(event.t, event.period)
            if isinstance(event, Shot):
                score[event.team] += event.outcome is ShotOutcome.GOAL
                self.send("shot", _shot(event, label, names))
            if label != minute or isinstance(event, Shot):
                if label != minute:
                    self._personal(seen)
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


@functools.cache
def _meta(seed: int) -> MatchMeta:
    return generate(seed).meta


def _players(meta: MatchMeta) -> list[dict[str, Any]]:
    """For the personal modes' pickers: every player, as the cues tag them."""
    fields = ("id", "name", "number", "position")
    return [{**{f: getattr(p, f) for f in fields}, "team": p.team.value} for p in meta.players]


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
    boards: OrderedDict[str, Session] = OrderedDict()  # live and ended, for questions
    budget = ModelBudget(DAILY_MODEL_MATCHES)
    spoken = Spoken()
    voice = None
    if (resource := os.environ.get("SPEECH_RESOURCE_ID")) and (
        region := os.environ.get("SPEECH_REGION")
    ):
        voice = Voice(resource_id=resource, region=region)
    app.state.voice = voice  # the tests swap in a fake
    endpoint = os.environ.get("CONTENT_SAFETY_ENDPOINT")
    app.state.shield = Shield(endpoint) if endpoint else None
    app.state.sessions = sessions  # read by the tests: every stream must leave none behind
    app.state.boards = boards

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
            meta = _meta(seed)
            matches.append(
                {
                    "seed": seed,
                    "home": _team(meta.home),
                    "away": _team(meta.away),
                    "players": _players(meta),
                }
            )
        return {
            "product": product_name(),
            "matches": matches,
            "models": bool(os.environ.get("FOUNDRY_PROJECT_ENDPOINT")),
            "voice": app.state.voice is not None,
            "model_matches_left": budget.left,
            "questions": MAX_QUESTIONS,
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
        club: Literal["", "home", "away"] = "",
        player: str = "",
        focus: Literal["match", "player"] = "match",
        metric: Literal["", TickerMetric] = "",
        strictness: Profile = "standard",
    ) -> StreamingResponse:
        if seed not in DEMO_SEEDS:
            raise HTTPException(404, f"no demo match with seed {seed}")
        prefs = Preferences(
            club=Side(club) if club else None,
            player=player or None,
            focus=focus,
            metric=metric or None,
        )
        try:
            check_preferences(prefs, _meta(seed))
        except PreferenceError as error:
            raise HTTPException(422, str(error)) from None
        if len(sessions) >= MAX_STREAMS:  # the quick answer; events() holds the line
            raise HTTPException(503, "the studio is full: try again in a minute")
        options = {
            "narration": narration,
            "speed": max(0.0, min(speed, 600.0)),
            "start": max(0, min(start, 90)),
            "mode": mode,
            "stress": max(0.0, min(stress, 0.5)),
            "lang": lang,
            "prefs": prefs,
            "strictness": strictness,
            "spoken": spoken,
            "shield": app.state.shield,
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
            boards[session.id] = session
            while len(boards) > BOARDS:
                boards.popitem(last=False)
            task = asyncio.create_task(session.run())
            task.add_done_callback(lambda _: sessions.pop(session.id, None))
            deadline = asyncio.get_running_loop().time() + MAX_SESSION_S
            meta = session.match.meta
            hello = {"session": session.id, "seed": seed, "narration": session.narration}
            hello |= {"home": _team(meta.home), "away": _team(meta.away)}
            hello |= {"notices": session.notices, "competition": meta.competition}
            hello["prefs"] = prefs.model_dump(mode="json")
            hello["strictness"] = strictness
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

    @app.post("/api/sessions/{session_id}/ask")
    async def ask(
        session_id: str, question: str = Body(embed=True, min_length=1, max_length=MAX_QUESTION)
    ) -> dict[str, Any]:
        """A viewer's question about a match, live or after full time (court.ask)."""
        session = boards.get(session_id)
        if session is None:
            raise HTTPException(404, "no such match in this studio: start one to ask about it")
        if session.state.last_seq < 0:
            raise HTTPException(409, "the match hasn't kicked off")
        if session.asked >= MAX_QUESTIONS:
            raise HTTPException(429, f"this match's {MAX_QUESTIONS} questions are used up")
        session.asked += 1
        with telemetry.tracer.start_as_current_span("ask") as span:
            answer = await session.ask(question)
            span.set_attributes(
                {
                    "hudhud.status": answer.status,
                    "hudhud.attempts": answer.receipt.attempts,
                    "hudhud.writer": answer.receipt.writer,
                    "hudhud.refused": len(answer.refused),
                }
            )
        # The voice may read it: a verified answer, or the product's own fixed words, never a
        # draft the Critic refused.
        spoken.keep(session.id, answer.id, answer.text, answer.lang)
        return answer.model_dump(mode="json") | {"left": MAX_QUESTIONS - session.asked}

    @app.post("/api/sessions/{session_id}/listen")
    async def listen(session_id: str, request: Request) -> dict[str, str]:
        """A question said aloud (court.speech): 16 kHz mono WAV in, its words out, in the match's
        language. The page then asks it as if it had been typed."""
        voice = app.state.voice
        if voice is None:
            raise HTTPException(404, "no voice is connected here")
        session = boards.get(session_id)
        if session is None:
            raise HTTPException(404, "no such match in this studio: start one to ask about it")
        most = 44 + int(WAV_RATE * 2 * (MAX_LISTEN_S + 0.5))
        too_long = HTTPException(413, f"a question can be at most {MAX_LISTEN_S} seconds long")
        if int(request.headers.get("content-length") or 0) > most:
            raise too_long
        # Read in pieces and stop at the limit: a chunked upload declares no length up front.
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > most:
                raise too_long
            chunks.append(chunk)
        wav = b"".join(chunks)
        with telemetry.tracer.start_as_current_span(
            "listen", attributes={"hudhud.lang": session.lang, "hudhud.bytes": len(wav)}
        ):
            try:
                text = await voice.listen(wav, session.lang)
            except NothingHeard as error:
                raise HTTPException(422, str(error)) from None
            except SpeechBudgetSpent as error:
                raise HTTPException(429, str(error)) from None
            except SpeechUnavailable as error:
                raise HTTPException(503, str(error)) from None
        return {"text": text[:MAX_QUESTION], "lang": session.lang}

    @app.get("/api/sessions/{session_id}/speak")
    async def speak(session_id: str, cue: str) -> Response:
        """A line that aired, spoken (court.speech). Only by its cue's id: never free text."""
        voice = app.state.voice
        if voice is None:
            raise HTTPException(404, "no voice is connected here")
        line = spoken.line(session_id, cue)
        if line is None:
            raise HTTPException(404, "no such line aired in this match")
        text, lang = line
        with telemetry.tracer.start_as_current_span(
            "speak", attributes={"hudhud.lang": lang, "hudhud.chars": len(text)}
        ):
            try:
                audio = await voice.speak(text, lang)
            except SpeechBudgetSpent as error:
                raise HTTPException(429, str(error)) from None
            except SpeechUnavailable as error:
                raise HTTPException(503, str(error)) from None
        return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})

    app.mount("/mcp", critic)
    # The Critic as an A2A agent (court.a2a_server), for other agents, behind the same wall.
    try:
        from .a2a_server import app as a2a_app

        public = os.environ.get("STUDIO_PUBLIC_URL", "http://127.0.0.1:8091/").rstrip("/")
        app.mount("/a2a", a2a_app(f"{public}/a2a/"))
    except ImportError:  # the a2a extra isn't installed: the studio runs without it
        log.info("agent-framework-a2a isn't installed: no A2A endpoint")
    app.mount("/static", StaticFiles(directory=STUDIO), name="static")
    if (team := os.environ.get("ACCESS_TEAM")) and (aud := os.environ.get("ACCESS_AUD")):
        app.add_middleware(AccessOnly, team=team, audience=aud)
    return app


telemetry.configure(service="studio")
app = create_app()
