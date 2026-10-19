"""Ask the match: a viewer's question, answered from the events so far and checked by the Critic.

The Narrator answers, but it can learn a number only by calling the Scout's tools: code that
counts the events up to the moment of the question with court.metrics, the functions the Critic
recomputes with. Each tool result is a fact with an id: what was counted, in plain words, the
numbers code computed and the events behind them. The answer names the facts it stands on, and
code builds the claim from those facts, never from the model's words. The Critic then reviews it
as it reviews a line: every cited event real and already happened, every count recomputed from
raw events, every number in the text one the facts hold, and every player it names one the facts
are about. A refused draft goes back with the reasons; after MAX_ATTEMPTS the viewer is told no
answer could be proven, and shown why.

A question the events can't answer (how a player feels, an injury, what happens next) gets a
fixed reply, never a model's prose: the data's limits are stated, not improvised.

The offline answerer (no model) knows the common questions (the score, who scored, a side's or a
player's counts, the chances, the fouls) and goes through the same tools and the same Critic.
"""

import difflib
import json
import re
import time
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, Protocol

from pydantic import BaseModel, Field

from match_events import (
    MatchEvent,
    PeriodStart,
    Player,
    Shot,
    ShotOutcome,
    Side,
    Tackle,
    minute_label,
)

from .contracts import (
    AlertKind,
    Answer,
    AnswerFact,
    Assertion,
    Claim,
    Receipt,
    RefusedDraft,
    Window,
)
from .critic import NUMBER, Critic
from .describe import describe
from .metrics import compute, shot_distance, shot_xg
from .state import MatchState

MAX_ATTEMPTS = 3
MAX_QUESTION = 200  # characters
CITE_MAX = 12  # events cited for a count, the latest; the count itself is recomputed in full
MOMENTS_MAX = 8
BIG_CHANCE_XG = 0.25  # the Scout's

# What each count is, in the words a fact says it in.
TEAM_METRICS = {
    "goals": ("goal", "goals"),
    "shots": ("shot", "shots"),
    "xg": ("xG", "xG"),
    "box_entries": ("pass completed into the box", "passes completed into the box"),
    "passes": ("pass", "passes"),
    "passes_completed": ("pass completed", "passes completed"),
    "final_third_passes": (
        "pass completed into the final third",
        "passes completed into the final third",
    ),
    "high_ball_wins": ("ball won in the attacking third", "balls won in the attacking third"),
    "high_pressures": ("press in the attacking third", "presses in the attacking third"),
    "tackles_won": ("tackle won", "tackles won"),
    "fouls": ("foul committed", "fouls committed"),
}
PLAYER_METRICS = (
    "goals",
    "shots",
    "xg",
    "passes",
    "passes_completed",
    "final_third_passes",
    "high_pressures",
    "tackles_won",
    "fouls",
)
TeamMetric = Literal[
    "goals",
    "shots",
    "xg",
    "box_entries",
    "passes",
    "passes_completed",
    "pass_completion",
    "final_third_passes",
    "high_ball_wins",
    "high_pressures",
    "tackles_won",
    "fouls",
]
MomentKind = Literal["goals", "shots", "big_chances", "saves", "penalties", "fouls"]
MOMENTS: dict[str, Callable[[MatchEvent], bool]] = {
    "goals": lambda e: isinstance(e, Shot) and e.outcome is ShotOutcome.GOAL,
    "shots": lambda e: isinstance(e, Shot),
    "big_chances": lambda e: isinstance(e, Shot) and shot_xg(e) >= BIG_CHANCE_XG,
    "saves": lambda e: isinstance(e, Shot) and e.outcome is ShotOutcome.SAVED,
    "penalties": lambda e: isinstance(e, Shot) and e.situation == "penalty",
    "fouls": lambda e: isinstance(e, Tackle) and e.outcome == "foul",
}

Cannot = Literal["", "beyond_data", "not_yet", "off_topic", "unsupported"]
# The fixed replies: the data's limits in the product's words, never a model's.
CANNOT = {
    "beyond_data": "The match events can't tell that. They record the ball: passes, shots, "
    "tackles, presses and fouls. Not feelings, injuries, the weather or what anyone said.",
    "not_yet": "That hasn't happened yet. I answer only from what has happened so far.",
    "off_topic": "I answer questions about this match, from its events.",
    "unsupported": "I can't answer that one from the events. Try the score, who scored, a side's "
    "or a player's shots, xG, passes or fouls, or the biggest chance.",
}
REFUSED = (
    "I couldn't prove an answer to that: the Critic refused every draft. The refusals show why."
)


class Draft(BaseModel):
    """What an answerer returns: the answer and the facts it stands on, or why it can't."""

    text: str = Field(description="The answer, at most 60 words; empty if it can't be answered")
    facts: list[str] = Field(description="The id of every fact the answer uses, such as f1")
    cannot: Cannot = Field(
        description="Why the events can't answer: beyond_data (what event data can't see), "
        "not_yet (it hasn't happened), off_topic (not about this match); empty when answered",
    )

    @classmethod
    def unanswerable(cls, why: Cannot) -> "Draft":
        return cls(text="", facts=[], cannot=why)


@dataclass(frozen=True)
class Fact:
    """One tool result: what was counted, the numbers code computed and the events behind them."""

    id: str
    says: str
    team: Side
    citations: tuple[str, ...]
    assertions: tuple[Assertion, ...] = ()
    figures: dict[str, float] = field(default_factory=dict)
    names: tuple[str, ...] = ()


class MatchTools:
    """The Scout's tools for one question: they count the events up to the moment it was asked,
    and keep every result as a fact the answer can stand on."""

    def __init__(self, state: MatchState, as_of_seq: int | None = None) -> None:
        if state.last_seq < 0:
            raise ValueError("the match hasn't kicked off")
        self.id = f"ask-{uuid.uuid4().hex[:8]}"
        self.state, self.meta = state, state.meta
        self.as_of_seq = state.last_seq if as_of_seq is None else as_of_seq
        self.events = state.until(self.as_of_seq)
        self.now = self.events[-1]
        self.minute = minute_label(self.now.t, self.now.period)
        self.facts: dict[str, Fact] = {}

    # --- what the answerer is told first ------------------------------------------------

    def brief(self) -> str:
        home, away = self.meta.home, self.meta.away
        squads = "\n".join(
            f"- {team.name} ({team.side.value}): "
            + ", ".join(p.name for p in self.meta.players if p.team is team.side)
            for team in (home, away)
        )
        return (
            f"The match: {home.name} (home) v {away.name} (away). The question is asked at "
            f"{self.minute}, in the {'first' if self.now.period == 1 else 'second'} half; the "
            f"tools count every event up to then.\nThe players:\n{squads}"
        )

    def known(self) -> str:
        """The facts the tools have returned for this question, for a rewrite to reuse."""
        return "\n".join(f"- {f.id}: {f.says}" for f in self.facts.values())

    # --- the tools ----------------------------------------------------------------------

    def score(self) -> str:
        """The score so far, and the minute it is counted to."""
        goals = {side: compute("goals", side, self.events) for side in Side}
        home, away = self.meta.home, self.meta.away
        scorers = [e.id for e in self.events if MOMENTS["goals"](e)]
        fact = self._add(
            f"The score as of {self.minute}: {home.name} {goals[Side.HOME]:.0f}, "
            f"{away.name} {goals[Side.AWAY]:.0f}",
            team=Side.HOME,
            citations=(*scorers, self.now.id),
            assertions=tuple(
                Assertion(metric="goals", team=side, value=goals[side]) for side in Side
            ),
            figures=self._minute_figures(self.now),
        )
        return self._result(fact)

    def team_numbers(
        self,
        team: Annotated[str, "The team's name, or home or away"],
        metric: Annotated[TeamMetric, "What to count"],
        half: Annotated[int | None, "1 or 2 for one half only; empty for the match so far"] = None,
        last_minutes: Annotated[
            int | None, "Only the last this many minutes of the current half"
        ] = None,
    ) -> str:
        """One side's count of something, over the match so far, one half or the last minutes."""
        side = self.find_team(team)
        if side is None:
            return self._error(f"no team called {team!r}: {self._teams()}")
        window, words, figures = self._window(half, last_minutes)
        if isinstance(window, str):
            return self._error(window)
        name = self.meta.team(side).name
        counted = self._in(window)
        if metric == "pass_completion":
            passes = compute("passes", side, counted)
            done = compute("passes_completed", side, counted)
            pct = round(100 * done / passes) if passes else 0
            fact = self._add(
                f"{name}, pass completion{words}, as of {self.minute}: {pct}% "
                f"({done:.0f} of {passes:.0f} passes completed)",
                team=side,
                citations=self._cite("passes_completed", side, counted),
                assertions=(
                    Assertion(metric="passes", team=side, value=passes, window=window),
                    Assertion(metric="passes_completed", team=side, value=done, window=window),
                ),
                figures=figures | {"pct": pct},
            )
            return self._result(fact)
        value = compute(metric, side, counted)
        fact = self._add(
            f"{name}, {_count(metric, value)}{words}, as of {self.minute}",
            team=side,
            citations=self._cite(metric, side, counted),
            assertions=(Assertion(metric=metric, team=side, value=value, window=window),),
            figures=figures,
        )
        return self._result(fact)

    def player_numbers(self, player: Annotated[str, "The player's name"]) -> str:
        """One player's counts so far: goals, shots, xG, passes, presses, tackles and fouls."""
        found = self.find_player(player)
        if found is None:
            close = difflib.get_close_matches(player, [p.name for p in self.meta.players], n=3)
            hint = f": did you mean {', '.join(close)}?" if close else ""
            return self._error(f"no player called {player!r} in this match{hint}")
        side, team = found.team, self.meta.team(found.team).name
        values = {m: compute(m, side, self.events, found.id) for m in PLAYER_METRICS}
        mine = [e for e in self.events if getattr(e, "player_id", None) == found.id]
        shots = [e.id for e in mine if isinstance(e, Shot)]
        counts = ", ".join(_count(m, v) for m, v in values.items())
        fact = self._add(
            f"{found.name} (number {found.number}, {team}), as of {self.minute}: {counts}",
            team=side,
            citations=(*shots[-CITE_MAX:], self.now.id),
            assertions=tuple(
                Assertion(metric=m, team=side, value=v, player_id=found.id)
                for m, v in values.items()
            ),
            figures=self._minute_figures(self.now) | {"number": found.number},
            names=(found.name,),
        )
        return self._result(fact)

    def moments(
        self,
        kind: Annotated[MomentKind, "Which moments"],
        team: Annotated[str | None, "Only this team's (its name, or home or away)"] = None,
        player: Annotated[str | None, "Only this player's"] = None,
        half: Annotated[int | None, "1 or 2 for one half only"] = None,
    ) -> str:
        """The moments of one kind so far, each with its minute and what happened: the goals, the
        shots, the big chances (the biggest first kept), the saves, the penalties or the fouls."""
        side = self.find_team(team) if team else None
        if team and side is None:
            return self._error(f"no team called {team!r}: {self._teams()}")
        who = self.find_player(player) if player else None
        if player and who is None:
            return self._error(f"no player called {player!r} in this match")
        window, _, _ = self._window(half, None)
        if isinstance(window, str):
            return self._error(window)
        found = [
            e
            for e in self._in(window)
            if MOMENTS[kind](e)
            and (side is None or e.team == side)
            and (who is None or e.player_id == who.id)
        ]
        if kind in ("shots", "big_chances") and len(found) > MOMENTS_MAX:
            biggest = sorted(found, key=shot_xg, reverse=True)[:MOMENTS_MAX]
            found = sorted(biggest, key=lambda e: e.seq)
        found = found[-MOMENTS_MAX:]
        if not found:
            fact = self._add(
                f"No {kind.replace('_', ' ')} so far, as of {self.minute}",
                team=side or Side.HOME,
                citations=(self.now.id,),
                figures=self._minute_figures(self.now),
            )
            return self._result(fact)
        return json.dumps({"facts": [self._moment(e) for e in found]})

    def functions(self, max_calls: int = 6) -> list[Any]:
        """The tools as Agent Framework function tools, for a model to call."""
        from agent_framework import tool

        return [
            tool(fn, name=fn.__name__, max_invocations=max_calls)
            for fn in (self.score, self.team_numbers, self.player_numbers, self.moments)
        ]

    # --- names ---------------------------------------------------------------------------

    def find_team(self, words: str | None) -> Side | None:
        """A side from what a model passes: its name, its short name, a word only it has, or
        home or away."""
        if not words:
            return None
        text = words.lower().strip()
        if text in ("home", "away"):
            return Side(text)
        for side in Side:
            team = self.meta.team(side)
            if text in (team.name.lower(), team.short_name.lower()) or self.find_team_in(
                text, side
            ):
                return side
        return None

    def find_player(self, words: str | None) -> Player | None:
        if not words:
            return None
        text = words.lower()
        for player in self.meta.players:
            if player.name.lower() in text:
                return player
        surnames = [p for p in self.meta.players if _word(text, p.name.lower().split()[-1])]
        return surnames[0] if len(surnames) == 1 else None

    def teams_named(self, text: str) -> list[Side]:
        return [s for s in Side if self.find_team_in(text, s)]

    def find_team_in(self, text: str, side: Side) -> bool:
        """Whether the text names the side: in full, or by a word of its name the other side's
        doesn't share ("Rovers" names no one when both are Rovers)."""
        name = self.meta.team(side).name.lower()
        other = set(self.meta.team(side.other()).name.lower().split())
        lowered = text.lower()
        return _word(lowered, name) or any(
            _word(lowered, w) for w in name.split() if len(w) > 3 and w not in other
        )

    # --- the claim the Critic reviews ------------------------------------------------------

    def claim(self, draft: Draft, *, question: str, attempt: int) -> Claim:
        """The claim an answer makes: its text, and the facts it names, as code recorded them. A
        fact id the tools never returned is cited as given, and the Critic refuses it."""
        wanted = list(dict.fromkeys(draft.facts))
        used = [self.facts[f] for f in wanted if f in self.facts]
        unknown = [f for f in wanted if f not in self.facts]
        assertions = list(dict.fromkeys(a for f in used for a in f.assertions))
        return Claim(
            id=f"{self.id}.{attempt}",
            alert_id=self.id,
            attempt=attempt,
            kind=AlertKind.ANSWER,
            team=used[0].team if used else Side.HOME,
            period=self.now.period,
            t=self.now.t,
            as_of_seq=self.as_of_seq,
            severity=0.5,
            headline=question,
            text=draft.text,
            citations=tuple(dict.fromkeys([c for f in used for c in f.citations] + unknown)),
            assertions=tuple(assertions),
            figures={f"{f.id}.{k}": v for f in used for k, v in f.figures.items()},
            names=tuple(dict.fromkeys(n for f in used for n in f.names)),
        )

    # --- inside --------------------------------------------------------------------------

    def _add(self, says: str, *, team: Side, citations, assertions=(), figures=None, names=()):
        fact = Fact(
            id=f"f{len(self.facts) + 1}",
            says=says,
            team=team,
            citations=tuple(dict.fromkeys(citations)),
            assertions=tuple(assertions),
            figures=dict(figures or {}),
            names=tuple(names),
        )
        self.facts[fact.id] = fact
        return fact

    def _moment(self, event: MatchEvent) -> dict[str, str]:
        minute = minute_label(event.t, event.period)
        team = self.meta.team(event.team)
        figures = self._minute_figures(event)
        assertions: tuple[Assertion, ...] = ()
        names = [self.state.player_name(event.player_id)]
        if isinstance(event, Shot):
            figures["distance_m"] = float(f"{shot_distance(event):.0f}")
            xg = round(shot_xg(event), 2)
            assertions = (
                Assertion(metric="shot_xg", team=event.team, value=xg, event_id=event.id),
            )
        if isinstance(event, Tackle):
            names.append(self.state.player_name(event.opponent_id))
        fact = self._add(
            f"{minute} {describe(event, self.state)} ({team.name})",
            team=event.team,
            citations=(event.id,),
            assertions=assertions,
            figures=figures,
            names=tuple(names),
        )
        return {"id": fact.id, "says": fact.says}

    def _window(self, half: int | None, last_minutes: int | None):
        """(the window, its words, its numbers), or (a reason it can't be counted, ...)."""
        figures = self._minute_figures(self.now)
        if last_minutes:
            minutes = max(1, min(int(last_minutes), 45))
            start = self._period_start(self.now.period)
            window = Window(
                period=self.now.period,
                start_t=max(start, self.now.t - 60 * minutes),
                end_t=self.now.t,
            )
            return window, f" in the last {minutes} minutes", figures | {"minutes": minutes}
        if half:
            if half not in (1, 2):
                return "a match has two halves: 1 or 2", "", figures
            if half > self.now.period:
                return "the second half hasn't started", "", figures
            words = " in the first half" if half == 1 else " in the second half"
            return Window(period=half, start_t=0.0, end_t=1e9), words, figures
        return None, " so far", figures

    def _period_start(self, period: int) -> float:
        starts = [e.t for e in self.events if isinstance(e, PeriodStart) and e.period == period]
        return starts[-1] if starts else 0.0

    def _in(self, window: Window | None) -> list[MatchEvent]:
        if window is None:
            return self.events
        return list(self.state.in_window(window, as_of_seq=self.as_of_seq))

    def _cite(self, metric: str, side: Side, events: Sequence[MatchEvent]) -> tuple[str, ...]:
        """The latest events that count towards a number, and the moment it is counted to."""
        counting = [e.id for e in events if compute(metric, side, [e]) > 0]
        return (*counting[-CITE_MAX:], self.now.id)

    @staticmethod
    def _minute_figures(event: MatchEvent) -> dict[str, float]:
        parts = [float(n) for n in NUMBER.findall(minute_label(event.t, event.period))]
        return {"minute": parts[0], **({"added": parts[1]} if len(parts) > 1 else {})}

    def _teams(self) -> str:
        return f"{self.meta.home.name} (home) or {self.meta.away.name} (away)"

    @staticmethod
    def _result(fact: Fact) -> str:
        return json.dumps({"facts": [{"id": fact.id, "says": fact.says}]})

    @staticmethod
    def _error(detail: str) -> str:
        return json.dumps({"error": detail})


class Answerer(Protocol):
    async def answer(self, question: str, tools: MatchTools, feedback: Sequence[str]) -> Draft: ...


# --- the offline answerer ----------------------------------------------------------------

NOT_YET = ("will ", "going to", "predict", "next goal", "who wins", "who will", "final score")
BEYOND = (
    "feel",
    "injur",
    "weather",
    "crowd",
    "angry",
    "happy",
    "tired",
    "said",
    "say to",
    "manager",
    "coach",
    "salary",
    "transfer",
    "contract",
    "referee think",
    "why did",
    "fans",
)
METRIC_WORDS = (
    ("pass completion", "pass_completion"),
    ("completion", "pass_completion"),
    ("expected goals", "xg"),
    ("xg", "xg"),
    ("into the box", "box_entries"),
    ("box", "box_entries"),
    ("final third", "final_third_passes"),
    ("completed", "passes_completed"),
    ("pass", "passes"),
    ("won the ball", "high_ball_wins"),
    ("ball wins", "high_ball_wins"),
    ("press", "high_pressures"),
    ("tackle", "tackles_won"),
    ("foul", "fouls"),
    ("shot", "shots"),
    ("goal", "goals"),
)


class RuleAnswerer:
    """The offline answerer: the common questions, by their words. It calls the same tools as a
    model would, and its answers go through the same Critic."""

    writer = "template"

    async def answer(self, question: str, tools: MatchTools, feedback: Sequence[str]) -> Draft:
        q = f" {question.lower()} "
        if any(w in q for w in NOT_YET):
            return Draft.unanswerable("not_yet")
        if any(w in q for w in BEYOND):
            return Draft.unanswerable("beyond_data")
        player = tools.find_player(q)
        sides = tools.teams_named(q) or list(Side)
        half = 1 if "first half" in q else 2 if "second half" in q else None
        metric = next((m for words, m in METRIC_WORDS if words in q), None)
        scorers = "who scored" in q or "scorer" in q
        if scorers or ("goals" in q and not player and "how many" not in q):
            return self._moments(tools, "goals", sides, half)
        if any(w in q for w in ("score", "winning", "result", "leading", "who's ahead")):
            return self._score(tools)
        if "chance" in q:
            return self._moments(tools, "big_chances", sides, half, biggest=True)
        if player and metric and metric != "pass_completion":
            return self._player(tools, player, metric)
        if player:
            return self._player(tools, player, None)
        if "who fouled" in q or "which fouls" in q:
            return self._moments(tools, "fouls", sides, half)
        if metric:
            return self._teams(tools, metric, sides, half)
        return Draft.unanswerable("unsupported")

    def _score(self, tools: MatchTools) -> Draft:
        fact = _only(tools.score())
        home, away = (a.value for a in tools.facts[fact].assertions)
        names = tools.meta.home.name, tools.meta.away.name
        return Draft(
            text=f"{names[0]} {home:.0f}, {names[1]} {away:.0f}, as of {tools.minute}.",
            facts=[fact],
            cannot="",
        )

    def _moments(self, tools, kind, sides, half, *, biggest=False) -> Draft:
        side = sides[0] if len(sides) == 1 else None
        team = tools.meta.team(side).name if side else None
        found = json.loads(tools.moments(kind, team=team, half=half))["facts"]
        facts = [tools.facts[f["id"]] for f in found]
        if not facts[0].assertions and not facts[0].names:  # "No goals so far"
            return Draft(text=f"{facts[0].says}.", facts=[facts[0].id], cannot="")
        if biggest:
            top = max(facts, key=lambda f: f.assertions[0].value)
            return Draft(text=f"The biggest chance: {top.says}.", facts=[top.id], cannot="")
        label = "Goals" if kind == "goals" else kind.replace("_", " ").capitalize()
        lines = "; ".join(f.says for f in facts)
        return Draft(text=f"{label} so far: {lines}.", facts=[f.id for f in facts], cannot="")

    def _player(self, tools: MatchTools, player: Player, metric: str | None) -> Draft:
        fact = tools.facts[_only(tools.player_numbers(player.name))]
        values = {a.metric: a.value for a in fact.assertions}
        if metric is None:
            shown = ("goals", "shots", "xg", "passes_completed")
        else:
            shown = (metric,) if metric in values else ("shots",)
        counts = ", ".join(_count(m, values[m]) for m in shown)
        return Draft(
            text=f"{player.name}: {counts}, as of {tools.minute}.", facts=[fact.id], cannot=""
        )

    def _teams(self, tools: MatchTools, metric: str, sides, half) -> Draft:
        ids, parts = [], []
        for side in sides:
            name = tools.meta.team(side).name
            fact = tools.facts[_only(tools.team_numbers(name, metric, half=half))]
            ids.append(fact.id)
            if metric == "pass_completion":
                parts.append(f"{name} {fact.figures['pct']:.0f}% of passes completed")
            else:
                parts.append(f"{name} {_count(metric, fact.assertions[0].value)}")
        words = {1: " in the first half", 2: " in the second half"}.get(half, " so far")
        return Draft(text=f"{', '.join(parts)}{words}, as of {tools.minute}.", facts=ids, cannot="")


# --- asking ------------------------------------------------------------------------------

# Translates a verified answer: (the answer's id, its text) -> (the translation, the model), or
# None when it can't be checked. The Localizer's, in the studio.
Translate = Callable[[str, str], Awaitable[tuple[str, str] | None]]


async def ask(
    question: str,
    tools: MatchTools,
    answerer: Answerer,
    *,
    critic: Critic | None = None,
    stress: bool = False,
    lang: str = "en",
    translate: Translate | None = None,
    spend: Callable[[str], dict[str, Any]] | None = None,
) -> Answer:
    """The question, answered from the tools' facts and passed by the Critic, or told it can't be.

    The Critic has hindsight here (an answer may look back over the whole match), and every other
    check stands. The stress test overreaches on the first draft, as it does for the lines."""
    question = " ".join(question.split())[:MAX_QUESTION]
    critic = critic or Critic(hindsight=True)
    started = time.perf_counter()
    writer = getattr(answerer, "writer", "template")
    refused: list[RefusedDraft] = []
    feedback: list[str] = []
    attempt, verdict, used = 0, None, []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        draft = await answerer.answer(question, tools, feedback)
        if draft.cannot or not draft.text.strip():
            text = CANNOT[draft.cannot or "unsupported"]
            return _answer(tools, question, "cannot", text, attempt, writer, started, spend)
        claim = tools.claim(draft, question=question, attempt=attempt)
        used = draft.facts
        if stress and attempt == 1:
            claim = overreach(claim)
        verdict = critic.review(claim, tools.state)
        if verdict.approved:
            break
        refused.append(RefusedDraft(text=claim.text, reasons=verdict.reasons))
        feedback = [f'Your answer was refused: "{claim.text}"', "The Critic's reasons:"]
        feedback += [f"- {r.code}: {r.detail}" for r in verdict.reasons]
    else:
        return _answer(
            tools, question, "refused", REFUSED, attempt, writer, started, spend, refused=refused
        )
    claim = verdict.claim
    answer = _answer(
        tools,
        question,
        "verified",
        claim.text,
        attempt,
        writer,
        started,
        spend,
        refused=refused,
        claim=claim,
        used=used,
        numbers=verdict.numbers_checked,
    )
    if lang != "en" and translate is not None:
        translated = await translate(tools.id, claim.text)
        if translated is not None:
            text, model = translated
            receipt = answer.receipt.model_copy(update={"translated_by": model})
            answer = answer.model_copy(
                update={"text": text, "lang": lang, "original": claim.text, "receipt": receipt}
            )
        else:
            receipt = answer.receipt.model_copy(update={"translation_refused": True})
            answer = answer.model_copy(update={"receipt": receipt})
    return answer


def overreach(claim: Claim) -> Claim:
    """The stress test for an answer: its first number made bigger, as an overreaching model
    would. The Critic must catch it."""
    match = NUMBER.search(claim.text)
    if match is None:
        return claim
    number = match.group()
    bigger = f"{float(number) + 0.3:.2f}" if "." in number else str(int(number) + 2)
    text = claim.text[: match.start()] + bigger + claim.text[match.end() :]
    return claim.model_copy(update={"text": text})


def _answer(
    tools: MatchTools,
    question: str,
    status: Literal["verified", "cannot", "refused"],
    text: str,
    attempts: int,
    writer: str,
    started: float,
    spend: Callable[[str], dict[str, Any]] | None,
    *,
    refused: Sequence[RefusedDraft] = (),
    claim: Claim | None = None,
    used: Sequence[str] = (),
    numbers: int = 0,
) -> Answer:
    ledger = spend(tools.id) if spend else {}
    evidence = tuple(c for c in claim.citations if tools.state.get(c)) if claim else ()
    facts = [tools.facts[f] for f in dict.fromkeys(used) if f in tools.facts]
    receipt = Receipt(
        writer=ledger.get("writer", writer),
        attempts=attempts,
        numbers_checked=numbers,
        facts_recomputed=len(claim.assertions) if claim else 0,
        evidence=len(evidence),
        model_calls=ledger.get("model_calls", 0),
        tokens_in=ledger.get("tokens_in", 0),
        tokens_out=ledger.get("tokens_out", 0),
        cost_usd=ledger.get("cost_usd", 0.0),
        handovers=ledger.get("handovers", 0),
        latency_ms=round(1000 * (time.perf_counter() - started), 1),
    )
    return Answer(
        id=tools.id,
        question=question,
        status=status,
        text=text,
        minute=tools.minute,
        evidence=evidence,
        facts=tuple(AnswerFact(id=f.id, says=f.says, evidence=f.citations) for f in facts),
        refused=tuple(refused),
        receipt=receipt,
    )


def _count(metric: str, value: float) -> str:
    one, many = TEAM_METRICS[metric]
    if metric == "xg":
        return f"xG {value:.2f}"
    return f"{value:.0f} {one if value == 1 else many}"


def _only(result: str) -> str:
    return json.loads(result)["facts"][0]["id"]


def _word(text: str, words: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(words)}(?!\w)", text) is not None
