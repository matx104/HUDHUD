"""Scout: hot-path pattern detection. Deterministic, sub-millisecond, no LLM.

It sees every event and must never block the stream, which is why it lives on the
Orchestrator's hot path and not inside the (slower, fallible) narrative workflow.
"""

from match_events import (
    MatchEvent,
    Pass,
    PassOutcome,
    PeriodStart,
    Shot,
    ShotOutcome,
    Side,
)

from .contracts import Alert, AlertKind, Window
from .metrics import compute, is_box_entry, shot_xg
from .state import MatchState

FINAL_THIRD_X = 70.0


class Scout:
    def __init__(
        self,
        *,
        big_chance_xg: float = 0.25,
        window_s: float = 300.0,
        swing_index: float = 0.55,
        min_threat: float = 0.6,
        min_events: int = 3,
        cooldown_s: float = 240.0,
        check_every_s: float = 30.0,
    ) -> None:
        self.big_chance_xg = big_chance_xg
        self.window_s = window_s
        self.swing_index = swing_index
        self.min_threat = min_threat
        self.min_events = min_events
        self.cooldown_s = cooldown_s
        self.check_every_s = check_every_s
        self._n = 0
        self._next_check_t = 0.0
        self._last_swing: tuple[Side, float] | None = None

    def observe(self, event: MatchEvent, state: MatchState) -> list[Alert]:
        if isinstance(event, PeriodStart):
            self._last_swing = None
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
            return []
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

    def _momentum(self, event: MatchEvent, state: MatchState) -> Alert | None:
        start = max(state.period_start_t, event.t - self.window_s)
        if event.t - start < 0.8 * self.window_s:
            return None  # too little play yet to call a swing
        window = Window(period=event.period, start_t=start, end_t=event.t)
        events = list(state.in_window(window))
        threat = {side: self._threat(side, events) for side in Side}
        total = sum(threat.values())
        if total < self.min_threat:
            return None
        team = max(Side, key=lambda s: threat[s])
        index = (threat[team] - threat[team.other()]) / total
        if index < self.swing_index:
            return None
        if self._last_swing is not None:
            last_team, last_t = self._last_swing
            if event.t - last_t < self.cooldown_s:
                return None
            if last_team == team and event.t - last_t < 2 * self.window_s:
                return None  # same side still on top: not news yet
        mine = [e for e in events if getattr(e, "team", None) == team]
        cited = [e.id for e in mine if isinstance(e, Shot) or is_box_entry(e)][-10:]
        if len(cited) < self.min_events:
            return None  # one shot is not momentum, and every alert must be citable
        self._last_swing = (team, event.t)
        opp = team.other()
        return self._alert(
            kind=AlertKind.MOMENTUM_SWING,
            team=team,
            period=event.period,
            t=event.t,
            as_of_seq=event.seq,
            severity=round(min(1.0, 0.3 + 0.6 * index), 2),
            evidence=tuple(cited),
            window=window,
            metrics={
                "index": round(index, 2),
                "shots": compute("shots", team, events),
                "xg": compute("xg", team, events),
                "box_entries": compute("box_entries", team, events),
                "opp_shots": compute("shots", opp, events),
                "opp_xg": compute("xg", opp, events),
                "window_s": round(window.end_t - window.start_t),
            },
        )

    @staticmethod
    def _threat(side: Side, events: list[MatchEvent]) -> float:
        threat = 0.0
        for e in events:
            if getattr(e, "team", None) != side:
                continue
            if isinstance(e, Shot):
                threat += shot_xg(e)
            elif is_box_entry(e):
                threat += 0.08
            elif (
                isinstance(e, Pass)
                and e.outcome is PassOutcome.COMPLETE
                and e.end_x >= FINAL_THIRD_X
            ):
                threat += 0.015
        return threat
