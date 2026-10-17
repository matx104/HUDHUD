"""Narrator: turns alerts into claims (prose plus a checkable evidence chain).

`TemplateNarrator` is the offline backend: deterministic, free, used in tests and CI.
`court.foundry.FoundryNarrator` writes the line with a model deployed in Foundry, behind
the same two methods, starting from the facts the template composes here. The template
backend can also *overreach on purpose* (seeded, so reproducible), which is how the
Critic's on-camera rejection is guaranteed rather than left to LLM luck.

Every claim carries its figures: the numbers code computed that the text may state. The
Critic rejects any number in the text that isn't among them or its assertions.
"""

import random
import re
from collections.abc import Awaitable
from typing import Protocol

from match_events import Pass, Shot, Side, minute_label

from .contracts import Alert, AlertKind, Assertion, Claim, Verdict, Window
from .metrics import shot_distance
from .state import MatchState

OUTCOME_PHRASE = {
    "saved": "kept out by the keeper",
    "off_target": "dragged wide",
    "blocked": "blocked at the last moment",
    "woodwork": "off the woodwork",
}


def _count(n: float, one: str, many: str | None = None) -> str:
    """'1 shot', '3 shots', '0 shots': counts read as English, never '1 shots'."""
    return f"{n:.0f} {one if round(n) == 1 else many or one + 's'}"


def _pct(done: float, total: float) -> int:
    return round(100 * done / total) if total else 0


def minute_figures(alert: Alert) -> dict[str, float]:
    """The minute as figures: 35' gives minute=35; 45+2' gives minute=45, added_time=2."""
    numbers = [int(n) for n in re.findall(r"\d+", minute_label(alert.t, alert.period))]
    return dict(zip(("minute", "added_time"), numbers, strict=False))


def _event_figures(alert: Alert, state: MatchState) -> dict[str, float]:
    """Numbers the cited events carry (a pass's length), named by event: true facts to state."""
    figures = {}
    for event_id in alert.evidence:
        event = state.get(event_id)
        if isinstance(event, Pass):
            figures[f"{event_id}_pass_m"] = round(event.distance_m)
    return figures


class Narrator(Protocol):
    """Synchronous (template) or asynchronous (a model call): the workflow awaits either."""

    def draft(self, alert: Alert, state: MatchState) -> Claim | Awaitable[Claim]: ...
    def rewrite(self, verdict: Verdict, state: MatchState) -> Claim | Awaitable[Claim]: ...


class TemplateNarrator:
    OVERREACH_STYLES = ("uncited", "inflated", "phantom")

    def __init__(self, *, overreach_rate: float = 0.0, seed: int = 0) -> None:
        self.overreach_rate = overreach_rate
        self._rng = random.Random(seed)
        self._alerts: dict[str, Alert] = {}

    def draft(self, alert: Alert, state: MatchState) -> Claim:
        self._alerts[alert.id] = alert
        claim = self.compose(alert, state, attempt=1)
        if self._rng.random() < self.overreach_rate:
            return self._overreach(claim, alert, state)
        return claim

    def rewrite(self, verdict: Verdict, state: MatchState) -> Claim:
        alert = self._alerts[verdict.claim.alert_id]
        return self.compose(alert, state, attempt=verdict.claim.attempt + 1)

    # --- composition ---------------------------------------------------------------

    def compose(
        self,
        alert: Alert,
        state: MatchState,
        *,
        attempt: int,
        metrics: dict[str, float] | None = None,
    ) -> Claim:
        """The faithful claim for an alert: headline, line, evidence, assertions, figures."""
        metrics = dict(alert.metrics) if metrics is None else metrics
        compose = {
            AlertKind.GOAL: self._goal,
            AlertKind.BIG_CHANCE: self._chance,
            AlertKind.MOMENTUM_SWING: self._momentum,
        }[alert.kind]
        headline, text, assertions, figures = compose(alert, state, metrics)
        return Claim(
            id=f"{alert.id}.{attempt}",
            alert_id=alert.id,
            attempt=attempt,
            kind=alert.kind,
            team=alert.team,
            period=alert.period,
            t=alert.t,
            as_of_seq=alert.as_of_seq,
            severity=alert.severity,
            headline=headline,
            text=text,
            citations=alert.evidence,
            assertions=assertions,
            figures={**minute_figures(alert), **_event_figures(alert, state), **figures},
        )

    def _goal(self, alert: Alert, state: MatchState, m: dict[str, float]):
        shot = state.get(alert.evidence[-1])
        assert isinstance(shot, Shot)
        meta, team = state.meta, state.meta.team(alert.team)
        xg = m["xg"]
        score = f"{meta.home.short_name} {m['home_goals']:.0f}-{m['away_goals']:.0f} "
        score += meta.away.short_name
        scorer = state.player_name(shot.player_id)
        figures = {"xg": xg, "home_goals": m["home_goals"], "away_goals": m["away_goals"]}
        if shot.situation == "penalty":
            how = "from the penalty spot"
        else:
            figures["distance_m"] = round(shot_distance(shot))
            quality = "gilt-edged" if xg >= 0.4 else "good" if xg >= 0.15 else "speculative"
            how = f"from {shot_distance(shot):.0f} m, a {quality} chance (xG {xg:.2f})"
        text = f"{scorer} scores for {team.name} {how}."
        if shot.assist_event_id and (assist := state.get(shot.assist_event_id)):
            text += f" Set up by {state.player_name(assist.player_id)}."
        goals = m["home_goals"] if alert.team is Side.HOME else m["away_goals"]
        assertions = (
            Assertion(metric="shot_xg", team=alert.team, value=xg, event_id=shot.id),
            Assertion(metric="goals", team=alert.team, value=goals),
        )
        return f"GOAL · {score}", text, assertions, figures

    def _chance(self, alert: Alert, state: MatchState, m: dict[str, float]):
        shot = state.get(alert.evidence[-1])
        assert isinstance(shot, Shot)
        team = state.meta.team(alert.team)
        text = (
            f"{state.player_name(shot.player_id)} goes close for {team.name}: "
            f"xG {m['xg']:.2f}, {OUTCOME_PHRASE[shot.outcome.value]}."
        )
        assertions = (
            Assertion(metric="shot_xg", team=alert.team, value=m["xg"], event_id=shot.id),
        )
        figures = {"xg": m["xg"], "distance_m": round(shot_distance(shot))}
        return f"BIG CHANCE · {team.short_name}", text, assertions, figures

    def _momentum(self, alert: Alert, state: MatchState, m: dict[str, float]):
        team, opp = state.meta.team(alert.team), state.meta.team(alert.team.other())
        minutes = max(1, round(m["window_s"] / 60))
        span = "minute" if minutes == 1 else f"{minutes} minutes"
        now = _pct(m["passes_completed"], m["passes"])
        figures: dict[str, float] = {"minutes": minutes, "completion_pct": now}
        trend = ""
        if m["base_passes"]:
            base = _pct(m["base_passes_completed"], m["base_passes"])
            figures["earlier_completion_pct"] = base
            word = "up from" if now > base else "down from" if now < base else "level with"
            trend = f", {word} {base}% earlier in the half"
        text = (
            f"{team.name} have taken control, completing {m['passes_completed']:.0f} of "
            f"{_count(m['passes'], 'pass', 'passes')} in the last {span} ({now}%{trend}). "
            f"{m['final_third']:.0f} of them ended in the final third, against "
            f"{m['opp_final_third']:.0f} for {opp.name}."
        )
        w, mine = alert.window, alert.team
        assertions = [
            Assertion(metric="passes_completed", team=mine, value=m["passes_completed"], window=w),
            Assertion(metric="passes", team=mine, value=m["passes"], window=w),
            Assertion(metric="final_third_passes", team=mine, value=m["final_third"], window=w),
            Assertion(
                metric="final_third_passes", team=mine.other(), value=m["opp_final_third"], window=w
            ),
        ]
        if m["base_passes"] and w is not None:
            earlier = Window(period=alert.period, start_t=m["base_start_t"], end_t=w.start_t)
            assertions += [
                Assertion(metric="passes", team=mine, value=m["base_passes"], window=earlier),
                Assertion(
                    metric="passes_completed",
                    team=mine,
                    value=m["base_passes_completed"],
                    window=earlier,
                ),
            ]
        return f"MOMENTUM · {team.short_name} on top", text, tuple(assertions), figures

    # --- deliberate overreach (demo + tests) ----------------------------------------

    def _overreach(self, claim: Claim, alert: Alert, state: MatchState) -> Claim:
        style = self._rng.choice(self.OVERREACH_STYLES)
        if style == "uncited":
            return claim.model_copy(update={"citations": ()})
        if style == "phantom":
            phantom = f"e{alert.as_of_seq + 3:05d}"  # an event that hasn't happened yet
            return claim.model_copy(update={"citations": (*claim.citations, phantom)})
        metrics = dict(alert.metrics)
        if alert.kind is AlertKind.MOMENTUM_SWING:
            metrics["final_third"] += 3
        else:
            metrics["xg"] += 0.25
        return self.compose(alert, state, attempt=claim.attempt, metrics=metrics)
