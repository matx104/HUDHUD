"""Foundry's own judges on the lines that aired: groundedness, relevance, coherence, fluency.

The Critic checks every number and citation by code before a line airs. This is a second,
independent opinion, from Microsoft Foundry's evaluators (azure-ai-evaluation): a model reads each
line that aired against the fact sheet it was written from and scores it from 1 to 5. The writer
and the judge are different models (gpt-4.1-mini writes, gpt-5-mini judges), so no model grades its
own work. The run is logged to the Foundry project, where it shows next to the models it judged.

    scripts/live foundry-eval --seeds 2       # unseen matches 60-61, narrated, then judged

Writes docs/foundry-eval.md and site/data/foundry_eval.js. Needs the `evaluation` extra.
"""

import asyncio
import json
import os
import statistics
from datetime import date
from pathlib import Path
from typing import Any

from match_events import generate

from .contracts import Cue, Output
from .localizer import Localizer
from .orchestrator import run_match

ROOT = Path(__file__).resolve().parents[4]
QUERY = "Write one line of live football commentary for this moment, from the facts given."
METRICS = ("groundedness", "relevance", "coherence", "fluency")


class Recording:
    """The Foundry narrator, keeping the fact sheet each line was written from."""

    def __init__(self, inner: Any) -> None:
        self.inner, self.sheets = inner, {}

    async def draft(self, alert, state):
        claim = await self.inner.draft(alert, state)
        _, facts = self.inner._drafts[alert.id]
        self.sheets[alert.id] = self.inner._sheet(alert, facts, state)
        return claim

    async def rewrite(self, verdict, state):
        return await self.inner.rewrite(verdict, state)

    def __getattr__(self, name: str) -> Any:  # spend, meter
        return getattr(self.inner, name)


async def lines(seeds: range, make_narrator) -> list[dict[str, Any]]:
    """Every verified line from the matches, with the sheet it was written from."""
    rows = []
    for seed in seeds:
        outputs: list[Output] = []
        narrator = Recording(make_narrator())
        await run_match(
            generate(seed).stream(),
            sink=outputs.append,
            narrator=narrator,
            localizer=Localizer(mode="analyst"),
        )
        for cue in outputs:
            if (
                isinstance(cue, Cue)
                and cue.status == "verified"
                and cue.alert_id in narrator.sheets
            ):
                rows.append(
                    {
                        "query": QUERY,
                        "context": narrator.sheets[cue.alert_id],
                        "response": cue.original or cue.text,
                        "kind": cue.kind.value,
                        "seed": seed,
                        "attempts": cue.attempts,
                    }
                )
    return rows


def judge(
    rows: list[dict[str, Any]],
    *,
    endpoint: str,
    judge_model: str,
    out: Path,
    metrics: tuple[str, ...] = METRICS,
    name: str = "HUDHUD narrator lines",
) -> dict:
    """Foundry's evaluators over the rows; the run is logged to the project."""
    from azure.ai.evaluation import (
        CoherenceEvaluator,
        FluencyEvaluator,
        GroundednessEvaluator,
        RelevanceEvaluator,
        evaluate,
    )

    from .identity import credential

    out.mkdir(parents=True, exist_ok=True)
    data = out / "lines.jsonl"
    data.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    account = endpoint.split("//")[1].split(".")[0]
    model = {
        "azure_endpoint": f"https://{account}.openai.azure.com/",
        "azure_deployment": judge_model,
        "api_version": "2025-01-01-preview",
    }
    cred = credential()
    reasoning = judge_model.startswith(("gpt-5", "o1", "o3", "o4"))
    classes = {
        "groundedness": GroundednessEvaluator,
        "relevance": RelevanceEvaluator,
        "coherence": CoherenceEvaluator,
        "fluency": FluencyEvaluator,
    }
    evaluators = {
        metric: classes[metric](model, credential=cred, is_reasoning_model=reasoning)
        for metric in metrics
    }
    result = evaluate(
        data=str(data),
        evaluators=evaluators,
        evaluation_name=f"{name}, judged by {judge_model}",
        azure_ai_project=endpoint,
        output_path=str(out / "result.json"),
    )
    return result


def summarize(
    result: dict,
    rows: list[dict[str, Any]],
    judge_model: str,
    writer: str,
    metrics: tuple[str, ...] = METRICS,
) -> dict:
    scored = result.get("rows", [])
    summary: dict[str, Any] = {
        "lines": len(rows),
        "writer": writer,
        "judge": judge_model,
        "date": date.today().isoformat(),
        "portal": result.get("studio_url"),
    }
    for metric in metrics:
        # Only lines the judge answered: a call that failed (a dropped connection) is no verdict,
        # so it counts neither for nor against, and the summary says how many were judged.
        judged = [
            r
            for r in scored
            if r.get(f"outputs.{metric}.{metric}_result") in ("pass", "fail")
            and isinstance(r.get(f"outputs.{metric}.{metric}"), int | float)
            and r[f"outputs.{metric}.{metric}"] == r[f"outputs.{metric}.{metric}"]  # not NaN
        ]
        values = [float(r[f"outputs.{metric}.{metric}"]) for r in judged]
        passed = [r[f"outputs.{metric}.{metric}_result"] == "pass" for r in judged]
        summary[metric] = {
            "mean": round(statistics.mean(values), 2) if values else None,
            "pass_pct": round(100 * sum(passed) / len(passed), 1) if passed else None,
            "scored": len(values),
        }
    return summary


def write(summary: dict) -> None:
    rows = "\n".join(
        f"| {m.capitalize()} | {s['mean']} | {s['pass_pct']}% | {s['scored']} |"
        for m, s in ((m, summary[m]) for m in METRICS)
    )
    portal = f"\nThe run in the Foundry portal: {summary['portal']}\n" if summary["portal"] else ""
    (ROOT / "docs" / "foundry-eval.md").write_text(f"""# Foundry's judges on the lines that aired

> Written by `scripts/live foundry-eval` on {summary["date"]}.

Microsoft Foundry's evaluators (azure-ai-evaluation) read {summary["lines"]} lines that aired,
each against the fact sheet it was written from, and scored them from 1 to 5 (pass at 3). The
lines were written by {summary["writer"]} and passed the Critic first; the judge was
{summary["judge"]}, a different model, so none graded its own work. Unseen matches, seeds 60 on.

| Judged for | Mean (1-5) | Passed | Lines judged |
|---|---|---|---|
{rows}
{portal}
The Critic's checks are code: every number recomputed, every citation real. These judges are a
second opinion from a model, on what code can't measure: whether the line keeps to its facts in
spirit, answers the moment, and reads well.
""")
    data = "// Generated by scripts/live foundry-eval. Do not edit.\n"
    data += f"window.FOUNDRY_EVAL = {json.dumps(summary, indent=2)};\n"
    (ROOT / "site" / "data" / "foundry_eval.js").write_text(data)


def main(first: int, seeds: int, judge_model: str) -> int:
    from .foundry import FoundryNarrator

    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        raise SystemExit("set FOUNDRY_PROJECT_ENDPOINT (scripts/live does)")
    writer = os.environ.get("FOUNDRY_MODELS", "gpt-4.1-mini").split(",")[0]

    def make():
        return FoundryNarrator(project_endpoint=endpoint, models=(writer,))

    rows = asyncio.run(lines(range(first, first + seeds), make))
    print(f"{len(rows)} verified lines from seeds {first}-{first + seeds - 1}; judging")
    result = judge(rows, endpoint=endpoint, judge_model=judge_model, out=ROOT / "dist" / "eval")
    summary = summarize(result, rows, judge_model, writer)
    write(summary)
    for metric in METRICS:
        print(
            f"  {metric:<13} mean {summary[metric]['mean']}  passed {summary[metric]['pass_pct']}%"
        )
    print(f"portal: {summary['portal']}\nwrote docs/foundry-eval.md and site/data/foundry_eval.js")
    return 0
