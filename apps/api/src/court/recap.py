"""The recap: the match's story after full time, every line checked as a cue is.

Each line the recap writes is a claim: the events it stands on and the numbers it states, which
the Critic recomputes from the raw events before the line goes in. It is the broadcast's own
Critic with one rule lifted: a recap looks back over the whole match, so its evidence may come
from either half and any minute (hindsight). A line the Critic refuses stays out, and the recap
lists it with the reasons. The moments that aired live are quoted as they aired: they were
checked then, and their receipts say so.

Sections: the result and the goals; the numbers; the moments that aired, momentum swings first;
the standout players, counted from their own events like the studio's player card (counted, not
claimed: the Critic has no per-player rule yet, and the recap says so); and the receipts.

One export ships: a standalone HTML page in the studio's colours, printable to PDF.

    python -m court recap --seed 21 --out recap.html
"""

import html
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from match_events import MatchEvent, MatchMeta, PeriodEnd, Shot, ShotOutcome, Side, minute_label

from .config import product_name
from .contracts import (
    AlertKind,
    Assertion,
    Claim,
    Cue,
    Output,
    RejectionNotice,
    Spiked,
)
from .critic import Critic
from .metrics import compute, shot_distance, shot_xg
from .personal import player_card
from .state import MatchState


class Line(BaseModel):
    """One line of the recap: what it says, the events behind it, and how it was checked."""

    text: str
    evidence: tuple[str, ...]
    minute: str | None = None
    check: str  # "checked": the Critic passed it now; "aired": it passed live; "counted"


class Refused(BaseModel):
    text: str
    reasons: tuple[str, ...]


class Recap(BaseModel):
    product: str
    match_id: str
    seed: int
    competition: str
    home: dict[str, str]
    away: dict[str, str]
    score: tuple[int, int]
    result: Line
    goals: list[Line]
    numbers: list[Line]
    moments: list[Line]
    standouts: list[Line]
    receipts: dict[str, Any]
    refused: list[Refused]
    generated: str


def build(state: MatchState, outputs: Sequence[Output], *, generated: str | None = None) -> Recap:
    """The recap of a finished match, from its events and what the broadcast put out.

    `generated` stamps the page (default: now); "" leaves it unstamped, so the same match always
    makes the same page.
    """
    meta, events = state.meta, state.events
    whistle = next(e for e in reversed(events) if isinstance(e, PeriodEnd))
    critic = Critic(hindsight=True)
    refused: list[Refused] = []
    n = 0

    def checked(text: str, evidence, assertions=(), figures=None, minute=None) -> Line | None:
        nonlocal n
        n += 1
        claim = Claim(
            id=f"recap.{n}",
            alert_id=f"recap.{n}",
            attempt=1,
            kind=AlertKind.RECAP,
            team=Side.HOME,
            period=whistle.period,
            t=whistle.t,
            as_of_seq=whistle.seq,
            severity=0.0,
            headline="RECAP",
            text=text,
            citations=tuple(evidence),
            assertions=tuple(assertions),
            figures=figures or {},
        )
        verdict = critic.review(claim, state)
        if not verdict.approved:
            refused.append(Refused(text=text, reasons=tuple(r.detail for r in verdict.reasons)))
            return None
        return Line(text=text, evidence=claim.citations, minute=minute, check="checked")

    home, away = meta.home, meta.away
    score = (state.score[Side.HOME], state.score[Side.AWAY])
    goal_shots = [e for e in events if isinstance(e, Shot) and e.outcome is ShotOutcome.GOAL]
    result = checked(
        f"{home.name} {score[0]}-{score[1]} {away.name}.",
        [*(s.id for s in goal_shots), whistle.id],
        [_total("goals", Side.HOME, score[0]), _total("goals", Side.AWAY, score[1])],
    )
    goals = [line for s in goal_shots if (line := _goal(s, state, checked))]
    numbers = [line for line in _numbers(meta, events, whistle, checked) if line]
    return Recap(
        product=product_name(),
        match_id=meta.match_id,
        seed=meta.seed,
        competition=meta.competition,
        home={"name": home.name, "short": home.short_name, "color": home.color},
        away={"name": away.name, "short": away.short_name, "color": away.color},
        score=score,
        result=result or Line(text=f"{home.name} v {away.name}", evidence=(), check="counted"),
        goals=goals,
        numbers=numbers,
        moments=_moments(outputs),
        standouts=_standouts(meta, events),
        receipts=_receipts(outputs),
        refused=refused,
        generated=datetime.now(UTC).isoformat(timespec="seconds")
        if generated is None
        else generated,
    )


def _total(metric: str, side: Side, value: float) -> Assertion:
    return Assertion(metric=metric, team=side, value=value)


def _goal(shot: Shot, state: MatchState, checked) -> Line | None:
    """One goal: the minute, the scorer, where from and how good a chance, and who set it up."""
    team = state.meta.team(shot.team)
    minute = minute_label(shot.t, shot.period)
    xg = round(shot_xg(shot), 2)
    figures = {"xg": xg}
    evidence = [shot.id]
    if shot.situation == "penalty":
        how = "from the penalty spot"
    else:
        distance = round(shot_distance(shot))
        figures["distance_m"] = distance
        how = f"from {distance} m (xG {xg:.2f})"
    # The minute shows beside the line, read from the cited shot itself.
    text = f"{state.player_name(shot.player_id)} for {team.name}, {how}"
    assist = state.get(shot.assist_event_id or "")
    if assist is not None:
        evidence.insert(0, assist.id)
        text += f", set up by {state.player_name(assist.player_id)}"
    facts = [Assertion(metric="shot_xg", team=shot.team, value=xg, event_id=shot.id)]
    return checked(text + ".", evidence, facts, figures, minute)


def _numbers(meta: MatchMeta, events: Sequence[MatchEvent], whistle: PeriodEnd, checked):
    """The match in numbers, both sides, counted to the final whistle."""
    h, a = Side.HOME, Side.AWAY
    hs, as_ = meta.home.short_name, meta.away.short_name

    def total(metric: str) -> tuple[float, float]:
        return compute(metric, h, events), compute(metric, a, events)

    shots, xg = total("shots"), total("xg")
    shot_ids = [e.id for e in events if isinstance(e, Shot)]
    yield checked(
        f"Shots: {hs} {shots[0]:.0f}, {as_} {shots[1]:.0f}. "
        f"Expected goals: {hs} {xg[0]:.2f}, {as_} {xg[1]:.2f}.",
        [*shot_ids, whistle.id],
        [
            _total(m, side, v)
            for m, pair in (("shots", shots), ("xg", xg))
            for side, v in zip((h, a), pair, strict=True)
        ],
    )
    passes, done = total("passes"), total("passes_completed")
    pct = tuple(round(100 * d / p) if p else 0 for d, p in zip(done, passes, strict=True))
    yield checked(
        f"Passing: {hs} completed {done[0]:.0f} of {passes[0]:.0f} ({pct[0]}%), "
        f"{as_} {done[1]:.0f} of {passes[1]:.0f} ({pct[1]}%).",
        [whistle.id],
        [
            _total(m, side, v)
            for m, pair in (("passes", passes), ("passes_completed", done))
            for side, v in zip((h, a), pair, strict=True)
        ],
        {"home_pct": pct[0], "away_pct": pct[1]},
    )
    final, box = total("final_third_passes"), total("box_entries")
    yield checked(
        f"Territory: passes ending in the final third, {hs} {final[0]:.0f}, {as_} {final[1]:.0f}; "
        f"into the box, {hs} {box[0]:.0f}, {as_} {box[1]:.0f}.",
        [whistle.id],
        [
            _total(m, side, v)
            for m, pair in (("final_third_passes", final), ("box_entries", box))
            for side, v in zip((h, a), pair, strict=True)
        ],
    )


# The moments the recap retells, as they aired: how the match turned first, then the chances.
MOMENT_ORDER = {
    AlertKind.MOMENTUM_SWING: 0,
    AlertKind.HIGH_PRESS: 1,
    AlertKind.COUNTER: 2,
    AlertKind.GREAT_PASS: 3,
    AlertKind.BIG_CHANCE: 4,
}
MOST_MOMENTS = 8


def _moments(outputs: Sequence[Output]) -> list[Line]:
    """The verified cues that weren't goals (the goals have their own lines), in match order."""
    cues = [
        o
        for o in outputs
        if isinstance(o, Cue) and o.status == "verified" and o.kind in MOMENT_ORDER
    ]
    picked = sorted(cues, key=lambda c: (MOMENT_ORDER[c.kind], -c.priority))[:MOST_MOMENTS]
    picked.sort(key=lambda c: (c.period, c.t))
    return [
        Line(
            text=f"{c.headline}. {c.original or c.text}",
            evidence=c.evidence,
            minute=c.minute,
            check="aired",
        )
        for c in picked
    ]


MOST_STANDOUTS = 3


def _standouts(meta: MatchMeta, events: Sequence[MatchEvent]) -> list[Line]:
    """The players who made the most happen: goals, then chances created, then shots' xG."""
    cards = [player_card(p.id, meta, events) for p in meta.players]
    cards.sort(key=lambda c: (c["goals"], c["chances_created"], c["xg"]), reverse=True)
    lines = []
    for c in cards[:MOST_STANDOUTS]:
        p = c["player"]
        team = meta.team(Side(p["team"])).short_name
        parts = []
        if c["goals"]:
            parts.append(_plural(c["goals"], "goal"))
        parts.append(f"{_plural(c['chances_created'], 'chance')} created")
        if c["shots"]:
            parts.append(f"{_plural(c['shots'], 'shot')} (xG {c['xg']:.2f})")
        if c["passes"]:
            parts.append(
                f"{c['passes_completed']} of {_plural(c['passes'], 'pass', 'passes')} completed"
            )
        text = f"{p['number']} {p['name']} ({team}, {p['position']}): {', '.join(parts)}."
        lines.append(Line(text=text, evidence=tuple(c["evidence"]), check="counted"))
    return lines


def _plural(n: float, one: str, many: str | None = None) -> str:
    return f"{n:.0f} {one if round(n) == 1 else many or one + 's'}"


def _receipts(outputs: Sequence[Output]) -> dict[str, Any]:
    cues = [o for o in outputs if isinstance(o, Cue)]
    refusals = [o for o in outputs if isinstance(o, RejectionNotice)]
    receipts = [c.receipt for c in cues if c.receipt]
    return {
        "aired": sum(c.status == "verified" for c in cues),
        "detection_only": sum(c.status != "verified" for c in cues),
        "refused": len(refusals),
        "spiked": sum(isinstance(o, Spiked) for o in outputs),
        "numbers_checked": sum(r.numbers_checked for r in receipts),
        "facts_recomputed": sum(r.facts_recomputed for r in receipts),
        "cost_usd": round(sum(r.cost_usd for r in receipts), 6),
        "writers": sorted({r.writer for r in receipts if r.writer not in ("none", "unknown")}),
        "reasons": dict(Counter(r.code.value for o in refusals for r in o.reasons).most_common()),
    }


# --- the export: one standalone HTML page --------------------------------------------------

REASON_WORDS = {
    "no_evidence": "cited no events",
    "unknown_event": "cited an event that doesn't exist",
    "future_event": "cited an event that hadn't happened yet",
    "stale_event": "cited events too old to support it",
    "assertion_mismatch": "stated a number the events contradict",
    "insufficient_evidence": "had too little evidence",
    "ungrounded_number": "stated a number nothing supports",
    "no_rule": "was a kind of claim with no rule to check it",
}


def render_html(recap: Recap) -> str:
    """The recap as a page: every line with its evidence and how it was checked."""
    e = html.escape
    home, away = recap.home, recap.away

    def lines(items: list[Line]) -> str:
        if not items:
            return '<p class="none">None.</p>'
        rows = []
        for line in items:
            chips = "".join(f"<code>{e(i)}</code>" for i in line.evidence[:14])
            more = len(line.evidence) - 14
            if more > 0:
                chips += f'<span class="more">and {more} more</span>'
            minute = f'<span class="minute">{e(line.minute)}</span>' if line.minute else ""
            rows.append(
                f'<li class="{line.check}">{minute}<p>{e(line.text)}</p><div class="ev">'
                f'<span class="check">{CHECK_WORDS[line.check]}</span>{chips}</div></li>'
            )
        return f"<ol>{''.join(rows)}</ol>"

    r = recap.receipts
    receipt_rows = [
        ("Cues aired, verified", r["aired"]),
        ("Detection-only cues", r["detection_only"]),
        ("Claims the Critic refused", r["refused"]),
        ("Claims spiked, never aired", r["spiked"]),
        ("Numbers checked on air", r["numbers_checked"]),
        ("Facts recomputed from events", r["facts_recomputed"]),
        ("Written by", ", ".join(r["writers"]) or "nobody: detection only"),
        ("Model cost", f"${r['cost_usd']:.4f}"),
    ]
    receipts = "".join(f"<dt>{e(k)}</dt><dd>{e(str(v))}</dd>" for k, v in receipt_rows)
    reasons = "".join(f"<li>{v} {e(REASON_WORDS.get(k, k))}</li>" for k, v in r["reasons"].items())
    refused = "".join(
        f"<li><s>{e(x.text)}</s><small>{e('; '.join(x.reasons))}</small></li>"
        for x in recap.refused
    )
    when = recap.generated.replace("T", " ").replace("+00:00", " UTC")
    stamp = f" Generated {e(when)}." if when else ""
    return RECAP_PAGE.format(
        product=e(recap.product),
        home=e(home["name"]),
        away=e(away["name"]),
        home_short=e(home["short"]),
        away_short=e(away["short"]),
        home_color=e(home["color"]),
        away_color=e(away["color"]),
        h=recap.score[0],
        a=recap.score[1],
        competition=e(recap.competition),
        seed=recap.seed,
        match_id=e(recap.match_id),
        result=lines([recap.result]),
        goals=lines(recap.goals),
        numbers=lines(recap.numbers),
        moments=lines(recap.moments),
        standouts=lines(recap.standouts),
        receipts=receipts,
        reasons=f"<p>Why claims were refused:</p><ul>{reasons}</ul>" if reasons else "",
        refused=(
            "<section><h2>Lines the Critic kept out of this recap</h2>"
            f"<ul class='refused'>{refused}</ul></section>"
            if refused
            else ""
        ),
        generated=stamp,
    )


CHECK_WORDS = {
    "checked": "Checked by the Critic",
    "aired": "Aired live, checked then",
    "counted": "Counted from events",
}

# The page, filled in by render_html with str.format (so its CSS braces are doubled).
RECAP_PAGE = (Path(__file__).parent / "recap.html").read_text()
