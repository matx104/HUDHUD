"""Narrator: turns alerts into claims (prose plus a checkable evidence chain).

`TemplateNarrator` is the offline backend: deterministic, free, used in tests and CI.
The Foundry-hosted LLM narrator plugs in behind the same two methods. The template
backend can also *overreach on purpose* (seeded, so reproducible), which is how the
Critic's on-camera rejection is guaranteed rather than left to LLM luck.
"""

import random
from typing import Protocol

from match_events import Shot, Side

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


class Narrator(Protocol):
    def draft(self, alert: Alert, state: MatchState) -> Claim: ...
    def rewrite(self, verdict: Verdict, state: MatchState) -> Claim: ...


class TemplateNarrator:
    OVERREACH_STYLES = ("uncited", "inflated", "phantom")

    def __init__(self, *, overreach_rate: float = 0.0, seed: int = 0) -> None:
        self.overreach_rate = overreach_rate
        self._rng = random.Random(seed)
        self._alerts: dict[str, Alert] = {}

    def draft(self, alert: Alert, state: MatchState) -> Claim:
        self._alerts[alert.id] = alert
        claim = self._compose(alert, state, attempt=1, metrics=dict(alert.metrics))
        if self._rng.random() < self.overreach_rate:
            return self._overreach(claim, alert, state)
        return claim

    def rewrite(self, verdict: Verdict, state: MatchState) -> Claim:
        alert = self._alerts[verdict.claim.alert_id]
        return self._compose(
            alert, state, attempt=verdict.claim.attempt + 1, metrics=dict(alert.metrics)
        )

    # --- composition ---------------------------------------------------------------

    def _compose(
        self, alert: Alert, state: MatchState, *, attempt: int, metrics: dict[str, float]
    ) -> Claim:
        compose = {
            AlertKind.GOAL: self._goal,
            AlertKind.BIG_CHANCE: self._chance,
            AlertKind.MOMENTUM_SWING: self._momentum,
        }[alert.kind]
        headline, text, assertions = compose(alert, state, metrics)
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
        )

    def _goal(self, alert: Alert, state: MatchState, m: dict[str, float]):
        shot = state.get(alert.evidence[-1])
        assert isinstance(shot, Shot)
        meta, team = state.meta, state.meta.team(alert.team)
        xg = m["xg"]
        score = f"{meta.home.short_name} {m['home_goals']:.0f}-{m['away_goals']:.0f} "
        score += meta.away.short_name
        scorer = state.player_name(shot.player_id)
        if shot.situation == "penalty":
            how = "from the penalty spot"
        else:
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
        return f"GOAL · {score}", text, assertions

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
        return f"BIG CHANCE · {team.short_name}", text, assertions

    def _momentum(self, alert: Alert, state: MatchState, m: dict[str, float]):
        team, opp = state.meta.team(alert.team), state.meta.team(alert.team.other())
        minutes = max(1, round(m["window_s"] / 60))
        span = "minute" if minutes == 1 else f"{minutes} minutes"
        now = _pct(m["passes_completed"], m["passes"])
        trend = ""
        if m["base_passes"]:
            base = _pct(m["base_passes_completed"], m["base_passes"])
            word = "up from" if now > base else "down from" if now < base else "level with"
            trend = f", {word} {base}% earlier in the half"
        text = (
            f"{team.name} have taken control, completing {m['passes_completed']:.0f} of "
            f"{_count(m['passes'], 'pass', 'passes')} in the last {span} ({now}%{trend}). "
            f"They've found the final third {_count(m['final_third'], 'time')} "
            f"to {opp.name}'s {m['opp_final_third']:.0f}."
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
        return f"MOMENTUM · {team.short_name} on top", text, tuple(assertions)

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
        return self._compose(alert, state, attempt=claim.attempt, metrics=metrics)
