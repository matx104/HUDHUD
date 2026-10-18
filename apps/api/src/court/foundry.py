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
        "number: no invented minutes, scores, distances or statistics. Don't invent players or "
        "events. The headline, the minute and the score are already on screen: don't restate "
        "them; lead with the action."
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
    ) -> None:
        self.project_endpoint = project_endpoint
        self.models = tuple(models)
        self.timeout_s = timeout_s
        self.meter = meter or TokenMeter()
        self.handovers = 0
        self._template = TemplateNarrator()
        self._make_agent = agent_factory or self._foundry_agent
        self._agents: dict[str, Any] = {}
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
        return (
            f"Moment: {KIND[alert.kind]} for {side.name} against {other.name}.\n"
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

    def spend(self, alert_id: str) -> dict[str, Any]:
        """The receipt's writer line for one alert: the model, its calls, tokens and cost."""
        ledger = dict(self._spend.get(alert_id, {}))
        if "cost_usd" in ledger:
            ledger["cost_usd"] = round(ledger["cost_usd"], 6)
        return ledger

    async def _write(self, prompt: str, alert_id: str) -> str:
        ledger = self._spend.setdefault(
            alert_id,
            {"model_calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "handovers": 0},
        )
        failure: Exception | None = None
        for i, model in enumerate(self.models):
            try:
                agent = self._agents.get(model) or self._agents.setdefault(
                    model, self._make_agent(model)
                )
                response = await asyncio.wait_for(
                    agent.run(prompt, options=_options(model)), timeout=self.timeout_s
                )
                tokens = self.meter.record(model, getattr(response, "usage_details", None))
                ledger["writer"] = model
                ledger["model_calls"] += 1
                ledger["tokens_in"] += tokens[0]
                ledger["tokens_out"] += tokens[1]
                ledger["cost_usd"] += self.meter.price(model, *tokens)
                return response.value.text.strip()
            except Exception as error:  # timeouts, throttling, outages: hand over to the next
                failure = error
                if i + 1 < len(self.models):
                    self.handovers += 1
                    ledger["handovers"] += 1
        raise NarrationUnavailable(f"no deployment answered: {failure!r}") from failure

    def _foundry_agent(self, model: str) -> Any:
        from agent_framework import Agent
        from agent_framework.foundry import FoundryChatClient

        from .identity import credential

        client = FoundryChatClient(
            project_endpoint=self.project_endpoint, model=model, credential=credential()
        )
        return Agent(client=client, name="Narrator", instructions=instructions())


def _options(model: str) -> dict[str, Any]:
    """Structured output always. Reasoning models think briefly; live cues can't wait."""
    if model.startswith(("gpt-5", "o")):
        return {"response_format": Line, "reasoning": {"effort": "low"}, "max_tokens": 1200}
    return {"response_format": Line, "temperature": 0.6, "max_tokens": 200}


def _number(value: float) -> str:
    return f"{value:.0f}" if float(value).is_integer() else f"{value:.2f}"
