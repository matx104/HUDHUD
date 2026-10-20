"""Narration on models deployed in the Foundry project.

Code computes every number; the model writes the line. Each draft starts from the claim the
template narrator composes for the alert. The model gets its facts as a sheet (the cited
events, the figures, the headline already on screen) and returns JSON with one field: the
line. Citations, assertions and figures stay those of the alert, never the model's, so the
Critic checks this prose exactly as it checks the template's. A number the model invents
fails the grounding check, and the rewrite prompt carries the Critic's reasons back.

If a deployment fails (timeout, throttling, an outage), the next one takes over: the backup
is a different model, so one deployment's trouble doesn't silence the broadcast. If every
deployment fails, NarrationUnavailable reaches the Orchestrator, which falls back to
detection-only cues.

    pip install -e "apps/api[foundry]"    # agent-framework-foundry, azure-identity
"""

import asyncio
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from .config import product_name
from .contracts import Alert, AlertKind, Claim, Verdict
from .describe import describe
from .narrator import TemplateNarrator
from .referee import words as call_words
from .state import MatchState

# USD per million tokens (input, output), Global Standard deployments. gpt-4.1-mini is from the
# Azure retail price list (2026-10-18); the list publishes only the priority tier for gpt-5-mini,
# so its standard list price is used. Cost Management is the source of truth for the bill.
PRICES = {"gpt-5-mini": (0.25, 2.00), "gpt-4.1-mini": (0.40, 1.60)}

LANGUAGES = {"ur": "Urdu", "ar": "Modern Standard Arabic"}

KIND = {
    AlertKind.GOAL: "goal",
    AlertKind.BIG_CHANCE: "big chance",
    AlertKind.MOMENTUM_SWING: "momentum swing",
    AlertKind.GREAT_PASS: "great pass",
    AlertKind.COUNTER: "counterattack",
    AlertKind.HIGH_PRESS: "high press winning the ball back",
    AlertKind.REF_CALL: "foul, and the referee's likely call",
}


class Line(BaseModel):
    """What the model returns: the commentary line and nothing else."""

    text: str = Field(description="One or two sentences for air, at most 40 words")


class NarrationUnavailable(RuntimeError):
    """Every deployment failed for this request."""


@dataclass
class TokenMeter:
    """Tokens and estimated cost per model, from the first call."""

    prices: dict[str, tuple[float, float]] = field(default_factory=lambda: dict(PRICES))
    calls: Counter[str] = field(default_factory=Counter)
    tokens_in: Counter[str] = field(default_factory=Counter)
    tokens_out: Counter[str] = field(default_factory=Counter)

    def record(self, model: str, usage: Any) -> tuple[int, int]:
        """Counts one call; returns its tokens (in, out)."""
        tokens = (0, 0)
        if usage is not None:
            tokens = (usage.get("input_token_count") or 0, usage.get("output_token_count") or 0)
        self.calls[model] += 1
        self.tokens_in[model] += tokens[0]
        self.tokens_out[model] += tokens[1]
        return tokens

    def price(self, model: str, tokens_in: int, tokens_out: int) -> float:
        price_in, price_out = self.prices.get(model, (0.0, 0.0))
        return (tokens_in * price_in + tokens_out * price_out) / 1_000_000

    def cost_usd(self, model: str | None = None) -> float:
        models = [model] if model else list(self.calls)
        return sum(self.price(m, self.tokens_in[m], self.tokens_out[m]) for m in models)

    def summary(self) -> str:
        parts = [
            f"{m}: {self.calls[m]} calls, {self.tokens_in[m]:,} in / {self.tokens_out[m]:,} out, "
            f"${self.cost_usd(m):.4f}"
            for m in self.calls
        ]
        return (
            "; ".join(parts) + f"  ·  total ${self.cost_usd():.4f}" if parts else "no model calls"
        )


def instructions() -> str:
    return (
        f"You are the Narrator for {product_name()}, live commentary for a football broadcast. "
        "Write the line a commentator would say, from the facts given and nothing else. "
        "One or two sentences, at most 40 words, plain and vivid, no hashtags or emoji. "
        "State numbers exactly as the fact sheet gives them, in digits, and state no other "
        "number: no invented minutes, scores, distances or statistics, and state each number "
        "as what the facts say it counts. Don't invent players or "
        "events, and add no detail the facts don't give: not how the keeper moved, not where "
        "the ball went, not whose save or whose chance it was beyond what the facts say. The "
        "headline, the minute and the score are already on screen: don't restate them; lead "
        "with the action."
    )


def ask_instructions() -> str:
    """For answering a viewer's question (court.ask): the facts come only from the tools."""
    return (
        f"You answer a viewer's questions about one football match for {product_name()}, from "
        "the match's events and nothing else. You learn a fact only by calling the tools: they "
        "count the events up to the moment of the question, and each result is a fact with an "
        "id. Call the tools you need, then answer in at most 60 words, plainly, as a broadcast "
        "analyst would, and list in facts the id of every fact your answer uses. State numbers "
        "only as the facts give them, in digits, each as what the fact says it counts. Name only "
        "players the facts you list are about. For who has the most of something, call leaders: "
        "code ranks the players, so rank only as its facts do. Add no detail the facts don't "
        "give, and never "
        "infer from the counts what they can't show (an injury, fitness, a mood, intent). If the "
        "events "
        "can't answer it (feelings, injuries, the weather, what anyone said, a player's fitness), "
        "leave the text empty and set cannot to beyond_data; for what hasn't happened yet (who "
        "will win, the next goal), not_yet; for a question not about this match, off_topic. "
        "Never predict a result or a score, never give or discuss odds, and never help anyone "
        "bet: for a question about bets, odds or gambling, set cannot to betting."
    )


class FoundryNarrator:
    def __init__(
        self,
        *,
        project_endpoint: str,
        models: Sequence[str] = ("gpt-4.1-mini", "gpt-5-mini"),  # primary first: ADR 0005
        timeout_s: float = 30.0,
        meter: TokenMeter | None = None,
        agent_factory: Callable[[str], Any] | None = None,
        viewer_club: str | None = None,
    ) -> None:
        self.project_endpoint = project_endpoint
        # Personal modes: the viewer's club, whose side the line is told from. Tone only: the
        # facts and the numbers come from the same sheet, and the Critic checks them the same way.
        self.viewer_club = viewer_club
        self.models = tuple(models)
        self.timeout_s = timeout_s
        self.meter = meter or TokenMeter()
        self.handovers = 0
        self._template = TemplateNarrator()
        self._make_agent = agent_factory or self._foundry_agent
        self._agents: dict[tuple[str, str], Any] = {}
        self._drafts: dict[str, tuple[Alert, Claim]] = {}
        self._spend: dict[str, dict[str, Any]] = {}  # per alert, for the cue's receipt

    async def draft(self, alert: Alert, state: MatchState) -> Claim:
        facts = self._template.compose(alert, state, attempt=1)
        self._drafts[alert.id] = (alert, facts)
        text = await self._write(self._sheet(alert, facts, state), alert.id)
        return facts.model_copy(update={"text": text})

    async def rewrite(self, verdict: Verdict, state: MatchState) -> Claim:
        alert, facts = self._drafts[verdict.claim.alert_id]
        attempt = verdict.claim.attempt + 1
        reasons = "\n".join(f"- {r.code}: {r.detail}" for r in verdict.reasons)
        prompt = (
            f'The Critic rejected your last line:\n"{verdict.claim.text}"\n'
            f"Its reasons:\n{reasons}\n"
            "Write the line again from the same facts, fixing exactly that.\n\n"
            + self._sheet(alert, facts, state)
        )
        text = await self._write(prompt, alert.id)
        return facts.model_copy(
            update={"id": f"{alert.id}.{attempt}", "attempt": attempt, "text": text}
        )

    # --- the fact sheet -----------------------------------------------------------------

    def _sheet(self, alert: Alert, facts: Claim, state: MatchState) -> str:
        meta = state.meta
        side, other = meta.team(alert.team), meta.team(alert.team.other())
        events = [
            f"- {e.id}: {describe(e, state)}"
            for e in (state.get(i) for i in facts.citations)
            if e is not None
        ]
        numbers = [f"{k}={_number(v)}" for k, v in facts.figures.items()]
        window_start = alert.window.start_t if alert.window else 0.0
        for a in facts.assertions:
            earlier = a.window is not None and a.window.start_t < window_start
            when = " earlier in the half" if earlier else ""
            numbers.append(f"{a.metric} for {meta.team(a.team).name}{when}={_number(a.value)}")
        viewer = ""
        if self.viewer_club:
            viewer = (
                f"The viewer supports {self.viewer_club}: tell it from their side, with hope at "
                "their moments and worry at the other side's. Change no fact for it.\n"
            )
        if facts.call is not None:
            restart, card = call_words(facts.call)
            viewer += (
                f'State the decision exactly in these words: "{restart}" and "{card}", and call '
                f"it likely: it is a {facts.call.profile} reading of the Law from event data, not "
                "the referee's.\n"
            )
        return (
            viewer + f"Moment: {KIND[alert.kind]} for {side.name} against {other.name}.\n"
            f"Headline on screen: {facts.headline}\n"
            "Cited events:\n" + "\n".join(events) + "\n"
            f"Numbers you may state: {', '.join(numbers)}\n"
            f"A plain version of the line, for the facts only: {facts.text}"
        )

    # --- calling the models -------------------------------------------------------------

    async def translate(
        self, alert_id: str, line: str, lang: str, reasons: list[str]
    ) -> tuple[str, str]:
        """The Localizer's translator: the verified line in Urdu or Arabic. Its tokens and cost go
        on the same cue's receipt; the Localizer checks its numbers."""
        prompt = (
            f"Translate this verified football commentary line into {LANGUAGES[lang]}, in the "
            "natural register of a live broadcast. Translate faithfully: say what the line says, "
            "and add nothing to it, no praise, no judgment, no fact it doesn't state. Keep every "
            "number exactly as written, and add no number. Keep every player and team name "
            "exactly as written, in Latin letters. Keep xG, km/h and m as they are. Return only "
            "the translated line.\n"
        )
        if reasons:
            prompt += (
                f"Your last translation was refused: {'; '.join(reasons)}. Fix exactly that.\n"
            )
        text = await self._write(prompt + f'Line: "{line}"', alert_id)
        return text, self._spend[alert_id]["writer"]

    async def answer(self, question: str, tools: Any, feedback: Sequence[str]) -> Any:
        """A viewer's question (court.ask). The model calls the Scout's tools for its facts and
        returns the answer with the ids of the facts it used; code builds the claim from those,
        and the Critic reviews it. A rewrite is shown the facts already counted."""
        prompt = f"{tools.brief()}\n\nQuestion: {question}"
        if getattr(tools, "history", ()):
            # A follow-up ("and them?") is read with the last exchanges: for what it refers to,
            # never for a number. Every number is counted again by the tools for this question.
            earlier = "\n".join(f"Q: {q}\nA: {a}" for q, a in tools.history)
            prompt = (
                f"{tools.brief()}\n\nEarlier in this conversation (for what the question refers "
                f"to; never reuse a number from here, count again):\n{earlier}\n\nQuestion: "
                f"{question}"
            )
        if feedback:
            prompt = (
                "\n".join(feedback)
                + "\nAnswer again, fixing exactly that. The facts the tools returned so far:\n"
                + tools.known()
                + "\n\n"
                + prompt
            )
        return await self._call(prompt, tools.id, purpose="ask", tools=tools.functions())

    def spend(self, alert_id: str) -> dict[str, Any]:
        """The receipt's writer line for one alert: the model, its calls, tokens and cost."""
        ledger = dict(self._spend.get(alert_id, {}))
        if "cost_usd" in ledger:
            ledger["cost_usd"] = round(ledger["cost_usd"], 6)
        return ledger

    async def _write(self, prompt: str, alert_id: str) -> str:
        line = await self._call(prompt, alert_id)
        return line.text.strip()

    async def _call(
        self, prompt: str, alert_id: str, *, purpose: str = "line", tools: Any = None
    ) -> Any:
        """One request, on the first deployment that answers; its spend goes on the receipt."""
        ledger = self._spend.setdefault(
            alert_id,
            {"model_calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "handovers": 0},
        )
        failure: Exception | None = None
        for i, model in enumerate(self.models):
            try:
                agent = self._agents.get((model, purpose)) or self._agents.setdefault(
                    (model, purpose),
                    self._make_agent(model)
                    if purpose == "line"
                    else self._make_agent(model, purpose),
                )
                # Answering calls tools in rounds, so it gets longer than a line.
                timeout = self.timeout_s * (2 if tools else 1)
                options = _options(model, purpose)
                run = (
                    agent.run(prompt, tools=tools, options=options)
                    if tools
                    else agent.run(prompt, options=options)
                )
                response = await asyncio.wait_for(run, timeout=timeout)
                tokens = self.meter.record(model, getattr(response, "usage_details", None))
                ledger["writer"] = model
                ledger["model_calls"] += 1
                ledger["tokens_in"] += tokens[0]
                ledger["tokens_out"] += tokens[1]
                ledger["cost_usd"] += self.meter.price(model, *tokens)
                if response.value is None:
                    raise ValueError("the model's reply didn't parse")
                return response.value
            except Exception as error:  # timeouts, throttling, outages: hand over to the next
                failure = error
                if i + 1 < len(self.models):
                    self.handovers += 1
                    ledger["handovers"] += 1
        raise NarrationUnavailable(f"no deployment answered: {failure!r}") from failure

    def _foundry_agent(self, model: str, purpose: str = "line") -> Any:
        from agent_framework import Agent
        from agent_framework.foundry import FoundryChatClient

        from .identity import credential

        client = FoundryChatClient(
            project_endpoint=self.project_endpoint, model=model, credential=credential()
        )
        guide = instructions() if purpose == "line" else ask_instructions()
        return Agent(client=client, name="Narrator", instructions=guide)


def _options(model: str, purpose: str = "line") -> dict[str, Any]:
    """Structured output always. Reasoning models think briefly; live cues can't wait. An answer
    is written cooler than a line: it reports, it doesn't commentate."""
    if purpose == "ask":
        from .ask import Draft

        if model.startswith(("gpt-5", "o")):
            return {"response_format": Draft, "reasoning": {"effort": "low"}, "max_tokens": 2500}
        return {"response_format": Draft, "temperature": 0.2, "max_tokens": 400}
    if model.startswith(("gpt-5", "o")):
        return {"response_format": Line, "reasoning": {"effort": "low"}, "max_tokens": 1200}
    return {"response_format": Line, "temperature": 0.6, "max_tokens": 200}


def _number(value: float) -> str:
    return f"{value:.0f}" if float(value).is_integer() else f"{value:.2f}"
