"""Scores the Scout's momentum calls against what really happened.

The generator hides momentum spells in its ground truth and never streams them. A swing
alert says "this side has been on top over this window", so it is a hit when a spell for
that side covers at least `min_overlap` of the window. A spell is caught when at least one
hit lands on it; the lag is how long after the spell began the first hit came.

    python -m court eval --seeds 100
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from statistics import median

from match_events import MomentumSpell, SyntheticMatch, generate

from .contracts import Alert, AlertKind
from .scout import Scout
from .state import MatchState


@dataclass(frozen=True)
class SwingScore:
    alerts: int = 0
    hits: int = 0
    spells: int = 0
    caught: int = 0
    lags_s: tuple[float, ...] = field(default=())

    @property
    def precision(self) -> float:
        return self.hits / self.alerts if self.alerts else 0.0

    @property
    def recall(self) -> float:
        return self.caught / self.spells if self.spells else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    @property
    def median_lag_s(self) -> float | None:
        return median(self.lags_s) if self.lags_s else None

    def __add__(self, other: "SwingScore") -> "SwingScore":
        return SwingScore(
            self.alerts + other.alerts,
            self.hits + other.hits,
            self.spells + other.spells,
            self.caught + other.caught,
            self.lags_s + other.lags_s,
        )


def swings(match: SyntheticMatch, scout: Scout) -> list[Alert]:
    """The momentum alerts one Scout raises over one match."""
    state, found = MatchState(match.meta), []
    for event in match.events:
        state.apply(event)
        found.extend(a for a in scout.observe(event, state) if a.kind is AlertKind.MOMENTUM_SWING)
    return found


def _covered(alert: Alert, spell: MomentumSpell) -> float:
    """Share of the alert's window during which the spell was running for the alert's side."""
    w = alert.window
    if w is None or spell.team != alert.team or spell.period != alert.period:
        return 0.0
    overlap = min(w.end_t, spell.end_t) - max(w.start_t, spell.start_t)
    return max(0.0, overlap) / max(1.0, w.end_t - w.start_t)


def score(
    match: SyntheticMatch, alerts: Iterable[Alert], *, min_overlap: float = 0.5
) -> SwingScore:
    alerts = list(alerts)
    spells = match.truth.spells
    hits = [a for a in alerts if any(_covered(a, s) >= min_overlap for s in spells)]
    lags = []
    for spell in spells:
        landed = [a.t for a in alerts if _covered(a, spell) >= min_overlap]
        if landed:
            lags.append(min(landed) - spell.start_t)
    return SwingScore(len(alerts), len(hits), len(spells), len(lags), tuple(lags))


def evaluate(
    seeds: Iterable[int], make_scout: Callable[[], Scout] = Scout, *, min_overlap: float = 0.5
) -> SwingScore:
    total = SwingScore()
    for seed in seeds:
        match = generate(seed)
        total += score(match, swings(match, make_scout()), min_overlap=min_overlap)
    return total


def report(result: SwingScore) -> str:
    lag = result.median_lag_s
    return (
        f"precision {result.precision:.0%} ({result.hits}/{result.alerts} swing calls were real)"
        f"  ·  recall {result.recall:.0%} ({result.caught}/{result.spells} spells caught)"
        f"  ·  F1 {result.f1:.2f}"
        f"  ·  median lag {'n/a' if lag is None else f'{lag / 60:.1f} min'}"
    )
