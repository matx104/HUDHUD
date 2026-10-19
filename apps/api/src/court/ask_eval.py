"""Ask the match, measured: do the answers state what the events say, on matches never seen?

A fixed set of questions is asked at three moments (30', 70' and full time) of unseen matches,
seeds 60 on. Each answerable question carries its truth, computed by code: the numbers, and for
some the names, a right answer must state. Each unanswerable one carries the reason it can't be
answered. The models answer through the Critic, as in the studio, and every answer is scored:

- right: verified by the Critic, and it states the truth
- off the question: verified, so every number in it is true, but not the one asked for. The
  Critic proves what an answer states, not that it answers; this measures that gap
- refused: no draft could be proven, and the viewer was told so
- declined: the model said it couldn't answer a question the events can answer
- for the unanswerable: declined for the right reason, for another, or answered anyway

Then Foundry's evaluators judge each verified answer, with a different model as the judge: does
it answer the question asked (relevance), and does it keep to the facts it stands on
(groundedness)?

    scripts/live ask-eval --seeds 2

Writes docs/ask-eval.md and site/data/ask_eval.js. Needs the `evaluation` extra.
"""

import asyncio
import json
import os
import statistics
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from match_events import Shot, ShotOutcome, Side, generate, minute_label

from .ask import CANNOT, MatchTools, ask
from .contracts import Answer, Window
from .critic import NUMBER
from .foundry import NarrationUnavailable
from .metrics import compute, shot_xg
from .state import MatchState

ROOT = Path(__file__).resolve().parents[4]
MOMENTS = (30, 70, None)  # minutes; None is full time
JUDGED = ("relevance", "groundedness")
RIGHT = ("right", "declined, right reason")
WHY = {text: why for why, text in CANNOT.items()}


@dataclass(frozen=True)
class Probe:
    """A question and what a right answer must do."""

    question: str
    numbers: tuple[str, ...] = ()  # each must be among the numbers the answer states
    names: tuple[str, ...] = ()  # each must be named in the answer
    cannot: str = ""  # for a question the events can't answer: the right reason


def probes(state: MatchState) -> list[Probe]:
    """The questions for this moment of this match, each with its truth counted by code."""
    meta, events = state.meta, state.events
    home, away = meta.home, meta.away
    goals = {side: compute("goals", side, events) for side in Side}
    xg = {side: compute("xg", side, events) for side in Side}
    passer = max(
        (p for p in meta.players if p.team is Side.HOME),
        key=lambda p: compute("passes", Side.HOME, events, p.id),
    )
    found = [
        Probe("What's the score?", numbers=(_n(goals[Side.HOME]), _n(goals[Side.AWAY]))),
        Probe(
            f"How many shots have {home.name} had?",
            numbers=(_n(compute("shots", Side.HOME, events)),),
        ),
        Probe(
            "What is each side's xG so far?",
            numbers=(f"{xg[Side.HOME]:.2f}", f"{xg[Side.AWAY]:.2f}"),
        ),
        Probe(
            f"How many passes has {passer.name} completed?",
            numbers=(_n(compute("passes_completed", Side.HOME, events, passer.id)),),
        ),
    ]
    scorers = [e for e in events if isinstance(e, Shot) and e.outcome is ShotOutcome.GOAL]
    if scorers:
        names = dict.fromkeys(state.player_name(e.player_id) for e in scorers)
        found.append(Probe("Who has scored so far?", names=tuple(names)))
    if events[-1].period == 2:
        second = state.in_window(Window(period=2, start_t=0.0, end_t=1e9))
        fouls = compute("fouls", Side.AWAY, second)
        found.append(
            Probe(
                f"How many fouls have {away.name} committed in the second half?",
                numbers=(_n(fouls),),
            )
        )
    shots = sorted((e for e in events if isinstance(e, Shot)), key=shot_xg, reverse=True)
    if shots and (len(shots) == 1 or round(shot_xg(shots[0]), 2) > round(shot_xg(shots[1]), 2)):
        top = shots[0]
        found.append(
            Probe(
                "What has been the biggest chance so far, and who had it?",
                numbers=(f"{shot_xg(top):.2f}",),
                names=(state.player_name(top.player_id),),
            )
        )
    found += [
        Probe("Who will win?", cannot="not_yet"),
        Probe(f"Is {passer.name} carrying an injury?", cannot="beyond_data"),
        Probe("What's the capital of France?", cannot="off_topic"),
    ]
    return found


def grade(probe: Probe, answer: Answer) -> str:
    if probe.cannot:
        if answer.status != "cannot":
            return "answered anyway"
        right = WHY.get(answer.text) == probe.cannot
        return "declined, right reason" if right else "declined, another reason"
    if answer.status in ("refused", "cannot"):
        return "refused" if answer.status == "refused" else "declined"
    text = answer.original or answer.text
    stated = [float(n) for n in NUMBER.findall(text)]
    numbers = all(any(abs(float(n) - s) < 0.006 for s in stated) for n in probe.numbers)
    names = all(name.lower() in text.lower() for name in probe.names)
    return "right" if numbers and names else "off the question"


async def run(
    seeds: range, answerer, *, spend=None, parallel: int = 1, backoff_s: float = 20.0
) -> list[dict[str, Any]]:
    """Every probe at every moment of every match, answered and graded. One at a time by default:
    the student subscription's deployments allow a few requests a second, and an answer that hits
    the limit waits and goes again rather than counting as a failure."""
    gate = asyncio.Semaphore(parallel)
    jobs = []
    for seed in seeds:
        match = generate(seed)
        for minute in MOMENTS:
            state = MatchState(match.meta)
            for event in match.events:
                if minute is not None and event.t >= minute * 60:
                    break
                state.apply(event)
            for probe in probes(state):
                jobs.append((seed, state, probe))

    async def one(seed: int, state: MatchState, probe: Probe) -> dict[str, Any]:
        minute = minute_label(state.events[-1].t, state.events[-1].period)
        failure, answer = "", None
        async with gate:
            # A rate limit waits and goes again; any other failure (a reply cut off mid-JSON) gets
            # one more try. One that still fails counts against the model, and the run goes on.
            for wait in (1, 2, 4, 0):
                try:
                    answer = await ask(probe.question, MatchTools(state), answerer, spend=spend)
                    break
                except NarrationUnavailable as error:
                    failure = str(error).splitlines()[0][:160]
                    limited = "429" in failure
                    if not wait or (not limited and wait > 1):
                        break
                    await asyncio.sleep(backoff_s * wait if limited else 1)
        if answer is None:
            return {
                "seed": seed,
                "minute": minute,
                "question": probe.question,
                "expects": probe.cannot or "answer",
                "grade": "unavailable",
                "status": "unavailable",
                "answer": failure,
                "facts": [],
                "drafts_refused": 0,
                "reasons": [],
                "latency_ms": 0.0,
                "cost_usd": 0.0,
            }
        return {
            "seed": seed,
            "minute": minute,
            "question": probe.question,
            "expects": probe.cannot or "answer",
            "grade": grade(probe, answer),
            "status": answer.status,
            "answer": answer.original or answer.text,
            "facts": [f.says for f in answer.facts],
            "drafts_refused": len(answer.refused),
            "reasons": [r.code for d in answer.refused for r in d.reasons],
            "latency_ms": answer.receipt.latency_ms,
            "cost_usd": answer.receipt.cost_usd,
        }

    return list(await asyncio.gather(*(one(*job) for job in jobs)))


def summarize(rows: list[dict[str, Any]], writer: str) -> dict[str, Any]:
    answerable = [r for r in rows if r["expects"] == "answer"]
    unanswerable = [r for r in rows if r["expects"] != "answer"]
    grades: dict[str, int] = {}
    for r in rows:
        grades[r["grade"]] = grades.get(r["grade"], 0) + 1
    right = sum(r["grade"] == "right" for r in answerable)
    held = sum(r["grade"] == "declined, right reason" for r in unanswerable)
    latencies = sorted(r["latency_ms"] for r in rows if r["status"] != "unavailable")
    return {
        "date": date.today().isoformat(),
        "writer": writer,
        "seeds": sorted({r["seed"] for r in rows}),
        "questions": len(rows),
        "answerable": len(answerable),
        "right": right,
        "right_pct": round(100 * right / len(answerable), 1) if answerable else None,
        "unanswerable": len(unanswerable),
        "declined_right": held,
        "grades": grades,
        "unavailable": sum(r["grade"] == "unavailable" for r in rows),
        "drafts_refused": sum(r["drafts_refused"] for r in rows),
        "refusal_reasons": sorted({c for r in rows for c in r["reasons"]}),
        "median_s": round(statistics.median(latencies) / 1000, 1) if latencies else None,
        "cost_usd": round(sum(r["cost_usd"] for r in rows), 4),
        "misses": [r for r in rows if r["grade"] not in RIGHT][:10],
    }


def write(summary: dict[str, Any]) -> None:
    judged = summary.get("judged") or {}
    judge_rows = "\n".join(
        f"| {m.capitalize()} | {s['mean']} | {s['pass_pct']}% | {s['scored']} |"
        for m, s in judged.items()
    )
    grades = "\n".join(f"| {g} | {n} |" for g, n in sorted(summary["grades"].items()))
    misses = "\n".join(
        f'- **{m["minute"]}, seed {m["seed"]}: {m["question"]}** ({m["grade"]}). "{m["answer"]}"'
        for m in summary["misses"]
    )
    judge_part = ""
    if judge_rows:
        judge_part = f"""
## Foundry's judges

Each verified answer, judged by {summary["judge"]} (a different model from the writer) with
Microsoft Foundry's evaluators: relevance against the question asked, groundedness against the facts
the answer stood on. 1 to 5, pass at 3.

| Judged for | Mean (1-5) | Passed | Answers judged |
|---|---|---|---|
{judge_rows}
"""
    (ROOT / "docs" / "ask-eval.md").write_text(f"""# Ask the match, measured

> Written by `scripts/live ask-eval` on {summary["date"]}. Unseen matches, seeds
> {", ".join(map(str, summary["seeds"]))}; questions asked at 30', 70' and full time.

{summary["writer"]} answered {summary["questions"]} questions through the Critic, as the studio
does. Each answerable question's truth was counted by code; each unanswerable one has the reason it
can't be answered.

- **Right:** {summary["right"]} of {summary["answerable"]} answerable questions
  ({summary["right_pct"]}%): verified by the Critic, and stating the true numbers and names.
- **Held back:** {summary["declined_right"]} of {summary["unanswerable"]} questions the events
  can't answer were declined for the right reason, in fixed words.
- **Caught on the way:** the Critic refused {summary["drafts_refused"]} drafts before an answer
  showed ({", ".join(summary["refusal_reasons"]) or "none"}).
- **Speed and cost:** median {summary["median_s"]} s an answer, ${summary["cost_usd"]} for the run.
- **Failed to reply:** {summary["unavailable"]} (the model's reply couldn't be read after a retry;
  in the studio the backup model or the offline answerer would have answered).

| Grade | Answers |
|---|---|
{grades}

"Off the question" is the gap the Critic leaves by design: it proves every number, name and
citation an answer states, not that the answer is the one asked for.
{judge_part}
## Every answer that wasn't right

{misses or "None."}
""")
    data = "// Generated by scripts/live ask-eval. Do not edit.\n"
    public = {k: v for k, v in summary.items() if k != "misses"}
    data += f"window.ASK_EVAL = {json.dumps(public, indent=2)};\n"
    (ROOT / "site" / "data" / "ask_eval.js").write_text(data)


def main(first: int, seeds: int, judge_model: str) -> int:
    from .foundry import FoundryNarrator
    from .foundry_eval import judge
    from .foundry_eval import summarize as summarize_judged

    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        raise SystemExit("set FOUNDRY_PROJECT_ENDPOINT (scripts/live does)")
    writer = os.environ.get("FOUNDRY_MODELS", "gpt-4.1-mini").split(",")[0]
    narrator = FoundryNarrator(project_endpoint=endpoint, models=(writer,))
    rows = asyncio.run(run(range(first, first + seeds), narrator, spend=narrator.spend))
    summary = summarize(rows, writer)
    out = ROOT / "dist" / "ask-eval"
    out.mkdir(parents=True, exist_ok=True)
    (out / "answers.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print(
        f"{summary['right']}/{summary['answerable']} right, "
        f"{summary['declined_right']}/{summary['unanswerable']} held back, "
        f"{summary['drafts_refused']} drafts refused, ${summary['cost_usd']}; judging"
    )
    verified = [
        {"query": r["question"], "response": r["answer"], "context": "\n".join(r["facts"])}
        for r in rows
        if r["status"] == "verified"
    ]
    result = judge(
        verified,
        endpoint=endpoint,
        judge_model=judge_model,
        out=out,
        metrics=JUDGED,
        name="HUDHUD answers to viewers' questions",
    )
    judged = summarize_judged(result, verified, judge_model, writer, metrics=JUDGED)
    summary |= {"judge": judge_model, "judged": {m: judged[m] for m in JUDGED}}
    summary["portal"] = judged.get("portal")
    write(summary)
    for m in JUDGED:
        print(f"  {m:<13} mean {judged[m]['mean']}  passed {judged[m]['pass_pct']}%")
    print("wrote docs/ask-eval.md and site/data/ask_eval.js")
    return 0


def _n(value: float) -> str:
    return f"{value:.0f}"
