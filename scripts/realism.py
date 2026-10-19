"""How real is the synthetic football? The generator's scorelines against real international ones.

    .venv/bin/python scripts/realism.py          # writes docs/realism.md and site/data/realism.js

The benchmark is Mart Jürisoo's "International football results from 1872", released into the
public domain (CC0 1.0): github.com/martj42/international_results. It is downloaded to
benchmarks/ (git-ignored) and never committed or used as product data (rules §4.7): only the
comparison computed here is. Real matches: competitive men's internationals since 2010 at a
home venue (no friendlies, no neutral grounds). Synthetic: the generator's matches, seeds 0-199.

It compares what a result can show: goals a match, home wins, draws and away wins, and the
commonest scorelines. It can't check event volumes (passes, shots, pressures): the benchmark has
results only. Aggregates only, and no team is named.

    mkdir -p benchmarks && curl -fsSL -o benchmarks/international-results.csv \\
      https://raw.githubusercontent.com/martj42/international_results/master/results.csv
"""

import csv
import json
import statistics
import sys
from collections import Counter
from datetime import date

from _azure import ROOT

from match_events import Side, generate

BENCHMARK = ROOT / "benchmarks" / "international-results.csv"
SOURCE = "https://github.com/martj42/international_results"
SINCE = "2010-01-01"
SEEDS = range(200)
REPORT = ROOT / "docs" / "realism.md"
SITE = ROOT / "site" / "data" / "realism.js"


def real_results() -> list[tuple[int, int]]:
    with BENCHMARK.open(newline="") as f:
        rows = list(csv.DictReader(f))
    return [
        (int(r["home_score"]), int(r["away_score"]))
        for r in rows
        if r["date"] >= SINCE
        and r["neutral"] == "FALSE"
        and r["tournament"] != "Friendly"
        and r["home_score"] not in ("", "NA")
    ]


def synthetic_results() -> list[tuple[int, int]]:
    finals = (generate(seed).truth.final_score for seed in SEEDS)
    return [(score[Side.HOME], score[Side.AWAY]) for score in finals]


def summary(results: list[tuple[int, int]]) -> dict:
    n = len(results)
    goals = [h + a for h, a in results]
    spread = Counter(min(g, 7) for g in goals)
    scores = Counter(f"{h}-{a}" for h, a in results)
    return {
        "matches": n,
        "goals_per_match": round(statistics.mean(goals), 2),
        "goals_sd": round(statistics.stdev(goals), 2),
        "home_win_pct": round(100 * sum(h > a for h, a in results) / n, 1),
        "draw_pct": round(100 * sum(h == a for h, a in results) / n, 1),
        "away_win_pct": round(100 * sum(h < a for h, a in results) / n, 1),
        "both_score_pct": round(100 * sum(h > 0 and a > 0 for h, a in results) / n, 1),
        "goals_spread_pct": {
            f"{g}{'+' if g == 7 else ''}": round(100 * spread[g] / n, 1) for g in range(8)
        },
        "top_scores": [[s, round(100 * c / n, 1)] for s, c in scores.most_common(8)],
        "goalless_pct": round(100 * scores["0-0"] / n, 1),
    }


def verdict(real: dict, syn: dict) -> list[str]:
    """Plain sentences on where the generator sits close and where it doesn't."""
    lines = []
    gap = syn["goals_per_match"] - real["goals_per_match"]
    near = "close to" if abs(gap) <= 0.3 else "above" if gap > 0 else "below"
    lines.append(
        f"Goals: {syn['goals_per_match']} a match, {near} the real {real['goals_per_match']}."
    )
    home_gap = syn["home_win_pct"] - real["home_win_pct"]
    lines.append(
        f"Home wins: {syn['home_win_pct']}% against {real['home_win_pct']}% real"
        + (
            ": the generator gives the home side less of an edge than real football does."
            if home_gap < -5
            else ": in line."
            if abs(home_gap) <= 5
            else ": more than real football."
        )
    )
    draw_gap = syn["draw_pct"] - real["draw_pct"]
    lines.append(
        f"Draws: {syn['draw_pct']}% against {real['draw_pct']}% real"
        + (": in line." if abs(draw_gap) <= 5 else ": fewer." if draw_gap < 0 else ": more.")
    )
    goalless = syn["goalless_pct"] - real["goalless_pct"]
    lines.append(
        f"Goalless draws: {syn['goalless_pct']}% against {real['goalless_pct']}% real"
        + (
            ": too few, and the goals spread less widely than real football's."
            if goalless < -2
            else ": in line."
        )
    )
    return lines


def write(real: dict, syn: dict) -> None:
    today = date.today().isoformat()
    said = verdict(real, syn)
    rows = [
        ("Matches compared", f"{real['matches']:,}", syn["matches"]),
        ("Goals a match", real["goals_per_match"], syn["goals_per_match"]),
        ("Spread of goals (sd)", real["goals_sd"], syn["goals_sd"]),
        ("Home wins", f"{real['home_win_pct']}%", f"{syn['home_win_pct']}%"),
        ("Draws", f"{real['draw_pct']}%", f"{syn['draw_pct']}%"),
        ("Away wins", f"{real['away_win_pct']}%", f"{syn['away_win_pct']}%"),
        ("Both sides score", f"{real['both_score_pct']}%", f"{syn['both_score_pct']}%"),
    ]
    table = "\n".join(f"| {a} | {b} | {c} |" for a, b, c in rows)
    spread = "\n".join(
        f"| {g} | {real['goals_spread_pct'][g]}% | {syn['goals_spread_pct'][g]}% |"
        for g in real["goals_spread_pct"]
    )
    tops = "\n".join(
        f"| {i + 1} | {r[0]} ({r[1]}%) | {s[0]} ({s[1]}%) |"
        for i, (r, s) in enumerate(zip(real["top_scores"], syn["top_scores"], strict=False))
    )
    REPORT.write_text(f"""# How real is the synthetic football?

> Written by `scripts/realism.py` on {today}. Benchmark only: the real results are never product
> data (rules §4.7), and no team is named here.

**Real:** {real["matches"]:,} competitive men's internationals since 2010 at a home venue, from
Mart Jürisoo's *International football results from 1872* (public domain, CC0 1.0,
{SOURCE}). **Synthetic:** the generator's matches, seeds 0-199.

{chr(10).join(f"- {line}" for line in said)}

| | Real | Synthetic |
|---|---|---|
{table}

## Goals in a match

| Goals | Real | Synthetic |
|---|---|---|
{spread}

## The commonest scorelines (home-away)

| | Real | Synthetic |
|---|---|---|
{tops}

## What this can't tell you

A result can't check what happens inside a match: passes, shots, pressures and possession are
calibrated separately (over 100 seeds: about 1,000 passes, 29 shots and 320 pressures a match, 78.5%
of passes completed). Internationals aren't club football: they mix strong and weak sides more
than a league does, which widens the scores. It is the closest public-domain benchmark of real
results; read it as a check on shape, not a target.
""")
    data = {"source": SOURCE, "since": SINCE, "real": real, "synthetic": syn, "verdict": said}
    header = "// Generated by scripts/realism.py. Do not edit.\n"
    SITE.write_text(f"{header}window.REALISM = {json.dumps(data, indent=2)};\n")


def main() -> int:
    if not BENCHMARK.exists():
        print(__doc__)
        return 1
    real, syn = summary(real_results()), summary(synthetic_results())
    write(real, syn)
    print("\n".join(verdict(real, syn)))
    print(f"wrote {REPORT.relative_to(ROOT)} and {SITE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
