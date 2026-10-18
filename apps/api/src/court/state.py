"""Shared match state. The Orchestrator owns it: ingest writes, every agent reads."""

from bisect import bisect_left, bisect_right
from collections.abc import Iterator

from match_events import (
    MatchEvent,
    MatchMeta,
    PeriodStart,
    Player,
    PossessionChange,
    Shot,
    ShotOutcome,
    Side,
)

from .contracts import Window


class MatchState:
    def __init__(self, meta: MatchMeta) -> None:
        self.meta = meta
        self.events: list[MatchEvent] = []
        self.score = {Side.HOME: 0, Side.AWAY: 0}
        self.period = 1
        self.period_start_t = 0.0
        self.possession_team: Side | None = None
        self._by_id: dict[str, MatchEvent] = {}
        # (period, t) is non-decreasing in seq order, so windows can bisect.
        self._keys: list[tuple[int, float]] = []
        self._players = {p.id: p for p in meta.players}

    def apply(self, event: MatchEvent) -> None:
        if event.seq != len(self.events):
            raise ValueError(f"out-of-order event {event.id}: expected seq {len(self.events)}")
        self.events.append(event)
        self._by_id[event.id] = event
        self._keys.append((event.period, event.t))
        if isinstance(event, PeriodStart):
            self.period, self.period_start_t = event.period, event.t
        elif isinstance(event, PossessionChange):
            self.possession_team = event.team
        elif isinstance(event, Shot) and event.outcome is ShotOutcome.GOAL:
            self.score[event.team] += 1

    @property
    def last_seq(self) -> int:
        return len(self.events) - 1

    def get(self, event_id: str) -> MatchEvent | None:
        return self._by_id.get(event_id)

    def until(self, as_of_seq: int) -> list[MatchEvent]:
        return self.events[: as_of_seq + 1]

    def in_window(self, window: Window, *, as_of_seq: int | None = None) -> Iterator[MatchEvent]:
        lo = bisect_left(self._keys, (window.period, window.start_t))
        hi = bisect_right(self._keys, (window.period, window.end_t))
        limit = self.last_seq if as_of_seq is None else as_of_seq
        return (e for e in self.events[lo:hi] if e.seq <= limit)

    def player(self, player_id: str) -> Player | None:
        return self._players.get(player_id)

    def player_name(self, player_id: str) -> str:
        player = self._players.get(player_id)
        return player.name if player else player_id
