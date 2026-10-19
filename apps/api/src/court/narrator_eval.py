"""Which model writes the commentary? Evaluation decides (ADR 0005).

Each model narrates the same alerts, from the same unseen matches, under the same Critic and the
same rewrite budget as on air, with no backup to lean on. Per model it measures how often the
first draft passes, how often a cue airs within the budget, how often the model invents a number,
how long a cue takes (every call it needed) and what it costs.

The decision rule is fixed here, before any run, so the results can't shape it:

1. Gate: a model must air at least 95% of the alerts within the rewrite budget.
2. Of the models through the gate, a first-pass rate 5 points or more ahead wins: every rewrite
   is a whole extra model call while the moment goes stale.
3. Otherwise a median time per cue 20% or more lower wins.
4. Otherwise the cheaper cue wins.

    scripts/live narrator-eval --first 60 --seeds 5      # about 90 model calls, a few cents
"""

import asyncio
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from statistics import median
from typing import Any

from match_events import generate

from .contracts import AlertKind, RejectionCode
from .critic import Critic
from .scout import Scout
from .state import MatchState

AIR_GATE = 0.95
FIRST_PASS_LEAD = 0.05
SPEED_LEAD = 0.20


@dataclass(frozen=True)
class Trial:
    """One alert, narrated by one model."""

    model: str
    seed: int
    alert_id: str
    kind: AlertKind
    first_pass: bool
    aired: bool
    attempts: int
    invented_numbers: int  # drafts the Critic refused for a number nothing computed
    codes: tuple[str, ...]
    seconds: float
    tokens_in: int
    tokens_out: int
    cost_usd: float
    words: int


@dataclass(frozen=True)
class Summary:
    model: str
    alerts: int
    first_pass: float
    aired: float
    invented: float  # share of drafts with an invented number
    median_s: float
    p95_s: float
    cost_per_cue: float
    tokens_out_per_cue: float
    words: float


async def narrate(
    narrator: Any,
    alert: Any,
    state: MatchState,
    *,
    critic: Critic,
    model: str,
    seed: int,
    max_attempts: int = 3,
) -> Trial:
    """The on-air loop for one alert: draft, review, rewrite with the Critic's reasons."""
    started, codes, invented = time.perf_counter(), [], 0
    claim, verdict, attempts = None, None, 0
    try:
        claim = await narrator.draft(alert, state)
        while True:
            attempts += 1
            verdict = critic.review(claim, state)
            refused = {r.code for r in verdict.reasons}
            invented += RejectionCode.UNGROUNDED_NUMBER in refused
            codes += sorted(refused)
            if verdict.approved or not verdict.rewritable or attempts >= max_attempts:
                break
            claim = await narrator.rewrite(verdict, state)
    except Exception as error:  # the model never answered: that counts against it
        codes.append(f"unavailable:{type(error).__name__}")
    spend = narrator.spend(alert.id)
    approved = verdict is not None and verdict.approved
    return Trial(
        model=model,
        seed=seed,
        alert_id=alert.id,
        kind=alert.kind,
        first_pass=approved and attempts == 1,
        aired=approved,
        attempts=attempts,
        invented_numbers=invented,
        codes=tuple(codes),
        seconds=time.perf_counter() - started,
        tokens_in=spend.get("tokens_in", 0),
        tokens_out=spend.get("tokens_out", 0),
        cost_usd=spend.get("cost_usd", 0.0),
        words=len(claim.text.split()) if claim else 0,
    )


# The kinds of moment the rule was fixed on (ADR 0005, 2026-10-18). Kinds added since (counter,
# high press, ref's call) join at the next run, under a rule written before that run.
EVAL_KINDS = frozenset(
    {AlertKind.GOAL, AlertKind.BIG_CHANCE, AlertKind.MOMENTUM_SWING, AlertKind.GREAT_PASS}
)


async def _match(
    seed: int, models: Sequence[str], make_narrator: Callable[[str], Any], critic: Critic
) -> list[Trial]:
    match = generate(seed)
    state, scout = MatchState(match.meta), Scout()
    narrators = {m: make_narrator(m) for m in models}
    trials: list[Trial] = []
    for event in match.events:
        state.apply(event)
        for alert in scout.observe(event, state):
            if alert.kind not in EVAL_KINDS:
                continue
            # Every model narrates this alert at this moment, from the same state.
            trials += await asyncio.gather(
                *(
                    narrate(narrators[m], alert, state, critic=critic, model=m, seed=seed)
                    for m in models
                )
            )
    return trials


async def run(
    models: Sequence[str],
    seeds: Iterable[int],
    make_narrator: Callable[[str], Any],
    *,
    critic: Critic | None = None,
) -> list[Trial]:
    critic = critic or Critic()
    batches = await asyncio.gather(*(_match(s, models, make_narrator, critic) for s in seeds))
    return [t for batch in batches for t in batch]


def summarize(trials: Sequence[Trial]) -> dict[str, Summary]:
    out = {}
    for model in dict.fromkeys(t.model for t in trials):
        mine = [t for t in trials if t.model == model]
        aired = [t for t in mine if t.aired]
        drafts = sum(t.attempts for t in mine) or 1
        seconds = sorted(t.seconds for t in mine)
        out[model] = Summary(
            model=model,
            alerts=len(mine),
            first_pass=sum(t.first_pass for t in mine) / len(mine),
            aired=len(aired) / len(mine),
            invented=sum(t.invented_numbers for t in mine) / drafts,
            median_s=median(seconds),
            p95_s=seconds[min(len(seconds) - 1, round(0.95 * (len(seconds) - 1)))],
            cost_per_cue=sum(t.cost_usd for t in mine) / max(1, len(aired)),
            tokens_out_per_cue=sum(t.tokens_out for t in mine) / max(1, len(aired)),
            words=sum(t.words for t in aired) / max(1, len(aired)),
        )
    return out


def decide(summaries: dict[str, Summary]) -> tuple[str | None, str]:
    """The rule in the module docstring. Returns the winner (None if nobody passes the gate)."""
    passed = [s for s in summaries.values() if s.aired >= AIR_GATE]
    if not passed:
        return None, f"no model aired {AIR_GATE:.0%} of the alerts"
    if len(passed) == 1:
        return passed[0].model, "the only model through the gate"
    best, other = sorted(passed, key=lambda s: s.first_pass, reverse=True)[:2]
    if best.first_pass - other.first_pass >= FIRST_PASS_LEAD:
        lead = best.first_pass - other.first_pass
        return best.model, f"first-pass rate {lead:.0%} points ahead"
    fast, slow = sorted(passed, key=lambda s: s.median_s)[:2]
    if fast.median_s <= (1 - SPEED_LEAD) * slow.median_s:
        return fast.model, f"median cue in {fast.median_s:.1f} s against {slow.median_s:.1f} s"
    cheap = min(passed, key=lambda s: s.cost_per_cue)
    return cheap.model, f"cheaper per cue (${cheap.cost_per_cue:.5f})"


def report(summaries: dict[str, Summary]) -> str:
    rows = [
        f"{'model':<14}{'alerts':>7}{'1st pass':>10}{'aired':>8}{'invented':>10}"
        f"{'median s':>10}{'p95 s':>8}{'$/cue':>10}{'out tok':>9}{'words':>7}"
    ]
    for s in summaries.values():
        rows.append(
            f"{s.model:<14}{s.alerts:>7}{s.first_pass:>10.0%}{s.aired:>8.0%}{s.invented:>10.0%}"
            f"{s.median_s:>10.1f}{s.p95_s:>8.1f}{s.cost_per_cue:>10.5f}"
            f"{s.tokens_out_per_cue:>9.0f}{s.words:>7.0f}"
        )
    winner, why = decide(summaries)
    rows.append(f"\nwinner: {winner or 'none'} ({why})")
    return "\n".join(rows)
