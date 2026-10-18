"""Scout: hot-path pattern detection. Deterministic, sub-millisecond, no LLM.

It sees every event and must never block the stream, which is why it lives on the
Orchestrator's hot path and not inside the (slower, fallible) narrative workflow.

Momentum is judged against each side's own baseline, not in absolute terms: a stronger
side keeps more of the ball all match, and that is not news. Two figures a commentator
can say out loud carry the call, both relative to the opponent:

- pass completion over the window, against the same side's completion earlier in the half
- completed passes into the final third per minute, against the side's earlier rate

The two go on one scale by dividing by their typical spread, and a swing is called only
once the combined score has held for `hold_checks` checks in a row: real spells last
minutes, noise flickers. `python -m court eval` scores the calls against the generator's
hidden ground truth.
"""

from match_events import MatchEvent, Pass, PassOutcome, PeriodStart, Shot, ShotOutcome, Side

from .contracts import Alert, AlertKind, Window
from .metrics import compute, event_metric, in_box, is_final_third_pass, shot_xg
from .state import MatchState

# Typical spread of each side-versus-side figure over seeds 0-59 (the eval reports on the
# unseen seeds 60-99). Dividing by them puts completion and territory on one scale.
# A great pass: completed into the box, not a cross, of a difficulty (40 of 100: completed less than
# six times in ten) that only the hardest twentieth of passes behind a shot reach, and it made the
# chance. 0.8 a match on seeds 0-59; a goal or a big chance carries its pass in its own cue instead.
GREAT_PASS_DIFFICULTY = 40
COMPLETION_SPREAD = 0.088
FINAL_THIRD_SPREAD = 2.2  # final-third passes per minute
# What a side's completion is assumed to be before it has much of a baseline.
LEAGUE_COMPLETION = 0.78
NEUTRAL_FINAL_THIRD_RATE = 2.0


class Scout:
    def __init__(
        self,
        *,
        big_chance_xg: float = 0.25,
        window_s: float = 300.0,
        swing_z: float = 2.5,
        hold_checks: int = 6,
        min_events: int = 3,
        cooldown_s: float = 240.0,
        check_every_s: float = 30.0,
    ) -> None:
        self.big_chance_xg = big_chance_xg
        self.window_s = window_s
        self.swing_z = swing_z
        self.hold_checks = hold_checks
        self.min_events = min_events
        self.cooldown_s = cooldown_s
        self.check_every_s = check_every_s
        self._n = 0
        self._next_check_t = 0.0
        self._last_swing: tuple[Side, float] | None = None
        self._held = dict.fromkeys(Side, 0)

    def observe(self, event: MatchEvent, state: MatchState) -> list[Alert]:
        if isinstance(event, PeriodStart):
            self._last_swing = None
            self._held = dict.fromkeys(Side, 0)
            self._next_check_t = event.t + self.window_s / 2
            return []
        alerts = []
        if isinstance(event, Shot):
            alerts.extend(self._shot(event, state))
        if isinstance(event, Pass | Shot) and event.t >= self._next_check_t:
            self._next_check_t = event.t + self.check_every_s
            if swing := self._momentum(event, state):
                alerts.append(swing)
        return alerts

    def _alert(self, **fields: object) -> Alert:
        self._n += 1
        return Alert(id=f"a{self._n:04d}", **fields)

    def _shot(self, shot: Shot, state: MatchState) -> list[Alert]:
        xg = round(shot_xg(shot), 2)
        goal = shot.outcome is ShotOutcome.GOAL
        if not goal and xg < self.big_chance_xg:
            return self._great_pass(shot, state, xg)
        evidence = (shot.assist_event_id, shot.id) if shot.assist_event_id else (shot.id,)
        metrics = {"xg": xg}
        if goal:
            metrics |= {"home_goals": state.score[Side.HOME], "away_goals": state.score[Side.AWAY]}
        return [
            self._alert(
                kind=AlertKind.GOAL if goal else AlertKind.BIG_CHANCE,
                team=shot.team,
                period=shot.period,
                t=shot.t,
                as_of_seq=shot.seq,
                severity=1.0 if goal else min(1.0, round(0.4 + xg, 2)),
                evidence=evidence,
                metrics=metrics,
            )
        ]

    def _great_pass(self, shot: Shot, state: MatchState, xg: float) -> list[Alert]:
        """A pass that opened the defence, judged once the shot shows it made a chance."""
        pass_ = state.get(shot.assist_event_id or "")
        if not (
            isinstance(pass_, Pass)
            and pass_.outcome is PassOutcome.COMPLETE
            and not pass_.cross
            and in_box(pass_.end_x, pass_.end_y)
            and event_metric("pass_difficulty", pass_) >= GREAT_PASS_DIFFICULTY
        ):
            return []
        metrics = {m: event_metric(m, pass_) for m in ("pass_distance", "pass_difficulty")}
        metrics |= {"pass_accuracy": event_metric("pass_accuracy", pass_), "xg": xg}
        return [
            self._alert(
                kind=AlertKind.GREAT_PASS,
                team=shot.team,
                period=shot.period,
                t=shot.t,
                as_of_seq=shot.seq,
                severity=0.5,
                evidence=(pass_.id, shot.id),
                metrics=metrics,
            )
        ]

    def _momentum(self, event: MatchEvent, state: MatchState) -> Alert | None:
        start = max(state.period_start_t, event.t - self.window_s)
        if event.t - start < 0.8 * self.window_s:
            return None  # too little play yet to call a swing
        window = Window(period=event.period, start_t=start, end_t=event.t)
        earlier = Window(period=event.period, start_t=state.period_start_t, end_t=start)
        now, before = list(state.in_window(window)), list(state.in_window(earlier))
        minutes = (window.end_t - window.start_t) / 60, (earlier.end_t - earlier.start_t) / 60
        form = {side: _form(side, now, before, *minutes) for side in Side}
        score = {}
        for side in Side:
            (comp, terr), (opp_comp, opp_terr) = form[side], form[side.other()]
            score[side] = (comp - opp_comp) / COMPLETION_SPREAD
            score[side] += (terr - opp_terr) / FINAL_THIRD_SPREAD
            self._held[side] = self._held[side] + 1 if score[side] >= self.swing_z else 0

        team = max(Side, key=lambda s: score[s])
        if self._held[team] < self.hold_checks:
            return None
        if self._last_swing is not None:
            last_team, last_t = self._last_swing
            if event.t - last_t < self.cooldown_s:
                return None
            if last_team == team and event.t - last_t < 2 * self.window_s:
                return None  # same side still on top: not news yet
        mine = [e for e in now if getattr(e, "team", None) == team]
        cited = [e.id for e in mine if isinstance(e, Shot) or is_final_third_pass(e)][-10:]
        if len(cited) < self.min_events:
            return None  # every alert must be citable
        self._last_swing = (team, event.t)
        opp = team.other()
        return self._alert(
            kind=AlertKind.MOMENTUM_SWING,
            team=team,
            period=event.period,
            t=event.t,
            as_of_seq=event.seq,
            severity=round(min(1.0, 0.3 + 0.15 * score[team]), 2),
            evidence=tuple(cited),
            window=window,
            metrics={
                "score": round(score[team], 2),
                "passes": compute("passes", team, now),
                "passes_completed": compute("passes_completed", team, now),
                "base_passes": compute("passes", team, before),
                "base_passes_completed": compute("passes_completed", team, before),
                "base_start_t": earlier.start_t,
                "final_third": compute("final_third_passes", team, now),
                "opp_final_third": compute("final_third_passes", opp, now),
                "shots": compute("shots", team, now),
                "xg": compute("xg", team, now),
                "window_s": round(window.end_t - window.start_t),
            },
        )


def _completion(passes: list[Pass], prior: int) -> float:
    """Share of passes completed, pulled towards the league norm when there are few."""
    done = sum(p.outcome is PassOutcome.COMPLETE for p in passes)
    return (done + LEAGUE_COMPLETION * prior) / (len(passes) + prior)


def _form(
    side: Side, now: list[MatchEvent], before: list[MatchEvent], now_min: float, before_min: float
) -> tuple[float, float]:
    """How far a side is above its own earlier level: completion, and final-third rate.

    Completion leaves crosses out: they come off about a quarter of the time whoever is on
    top, so a few of them would swamp five minutes of passing. A cross that arrives still
    counts as a pass into the final third.
    """
    passes_now = [e for e in now if isinstance(e, Pass) and e.team == side]
    passes_before = [e for e in before if isinstance(e, Pass) and e.team == side]
    completion = _completion([p for p in passes_now if not p.cross], prior=10)
    completion -= _completion([p for p in passes_before if not p.cross], prior=40)
    rate_now = sum(map(is_final_third_pass, passes_now)) / max(1.0, now_min)
    rate_before = (
        sum(map(is_final_third_pass, passes_before)) / max(1.0, before_min)
        if passes_before
        else NEUTRAL_FINAL_THIRD_RATE
    )
    return completion, rate_now - rate_before
