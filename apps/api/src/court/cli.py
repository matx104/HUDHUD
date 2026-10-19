"""Console runner.

    python -m court run --seed 7                        # one synthetic match, end to end
    python -m court run --seed 21 --narrator foundry    # the same, narrated by Foundry models
    python -m court run --seed 21 --audit cosmos        # and keep every output in Cosmos DB
    python -m court recap --seed 21 --out recap.html    # the match, then its recap as a page
    python -m court eval                                # momentum calls vs hidden ground truth
    python -m court narrator-eval --seeds 5             # which model writes the commentary
    python -m court foundry-eval --seeds 2              # Foundry's evaluators judge the lines
    python -m court ask-eval --seeds 2                  # questions answered, graded and judged
    python -m court schema                              # the output stream's JSON Schema

The Foundry narrator reads FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODELS (comma-separated,
primary first); the Cosmos DB audit trail reads COSMOS_ENDPOINT. scripts/live sets them and
puts the project's Azure CLI first on PATH.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from opentelemetry.trace import SpanKind

from match_events import Side, generate, read_jsonl

from . import telemetry
from .audit import AuditTrail, CosmosStore
from .config import ARCHITECTURE_NAME, product_name
from .contracts import (
    OUTPUT_ADAPTER,
    Cue,
    Degradation,
    Output,
    Receipt,
    RejectionNotice,
    Spiked,
)
from .critic import Critic
from .evals import evaluate, report
from .localizer import Localizer
from .narrator import TemplateNarrator
from .orchestrator import run_match
from .scout import Scout


def _console(output: Output) -> None:
    match output:
        case Cue():
            mark = "✔" if output.status == "verified" else "◌"
            retry = f"  (attempt {output.attempts})" if output.attempts > 1 else ""
            cites = " ".join(output.evidence)
            print(f"{output.minute:>7} {mark} {output.headline}  {output.text}{retry}  [{cites}]")
            if output.receipt:
                print(f"{'':>9}receipt  {_receipt(output.receipt)}")
        case RejectionNotice():
            why = "; ".join(f"{r.code}: {r.detail}" for r in output.reasons)
            line = f'"{output.claim.text}"'
            print(f"{output.minute:>7} ✘ REJECTED {output.claim.id}  {line}  {why}")
        case Spiked():
            print(f"{output.minute:>7} ✖ SPIKED {output.claim.id}  never aired")
        case Degradation():
            print(f"{output.minute:>7} ⚠ SERVICE {output.level.upper()}  {output.detail}")


def _receipt(r: Receipt) -> str:
    def n(count: int, noun: str) -> str:
        return f"{count} {noun}" + ("" if count == 1 else "s")

    if r.writer == "none":
        parts = ["detection only: the Scout's facts, no writer", n(r.evidence, "event") + " cited"]
    else:
        parts = [r.writer, n(r.attempts, "attempt"), n(r.numbers_checked, "number") + " checked"]
        parts += [n(r.facts_recomputed, "fact") + " recomputed", n(r.evidence, "event") + " cited"]
    parts.append(f"{r.latency_ms / 1000:.1f} s")
    if r.model_calls:
        parts.append(f"{r.tokens_in:,} in / {r.tokens_out:,} out, ${r.cost_usd:.4f}")
    if r.handovers:
        parts.append(n(r.handovers, "handover"))
    return " · ".join(parts)


def _jsonl(output: Output) -> None:
    sys.stdout.write(OUTPUT_ADAPTER.dump_json(output).decode() + "\n")


async def _run(args: argparse.Namespace) -> int:
    messages = read_jsonl(args.input) if args.input else list(generate(args.seed).stream())
    meta = messages[0]
    if not args.json:
        print(f"{product_name()} · {ARCHITECTURE_NAME} · synthetic data only")
        print(f"{meta.match_id}  {meta.home.name} vs {meta.away.name}  (seed {meta.seed})\n")
    narrator = _narrator(args, meta.seed)
    sink = _jsonl if args.json else _console
    trail = _audit(args, meta)
    attributes = {"hudhud.match_id": meta.match_id, "hudhud.seed": meta.seed}
    attributes["hudhud.narrator"] = args.narrator
    with telemetry.tracer.start_as_current_span(
        "match", kind=SpanKind.CONSUMER, attributes=attributes
    ) as span:
        if trail:
            trail.start()
            sink = trail.tee(sink)
        orch = await run_match(
            messages,
            sink=sink,
            speed=args.speed,
            narrator=narrator,
            scout=Scout(strictness=args.strictness),
            critic=Critic(strictness=args.strictness),
            localizer=Localizer(
                mode=args.mode, lang=args.lang, translator=getattr(narrator, "translate", None)
            ),
        )
        meter, handovers = getattr(narrator, "meter", None), getattr(narrator, "handovers", 0)
        summary = {"stats": dict(orch.stats), "handovers": handovers}
        if meter:
            summary |= {"cost_usd": round(meter.cost_usd(), 6), "models": meter.summary()}
        if trail:
            await trail.close(summary)
        span.set_attributes({f"hudhud.{k}": v for k, v in orch.stats.items()})
        span.set_attributes({"hudhud.handovers": handovers, "hudhud.level": orch.level})
        if meter:
            span.set_attribute("hudhud.cost_usd", summary["cost_usd"])
    telemetry.flush()
    if not args.json:
        s, st = orch.state.score, orch.stats
        print(f"\n     FT  {meta.home.name} {s[Side.HOME]}-{s[Side.AWAY]} {meta.away.name}")
        print("         " + " · ".join(f"{k} {v}" for k, v in sorted(st.items())))
        if meter:
            print(f"   cost  {meter.summary()}  ·  handovers {handovers}")
        if trail:
            print(f"  audit  {trail.report()}")
    return 0


async def _recap(args: argparse.Namespace) -> int:
    """Runs the match quietly, then writes its recap: every line checked by the Critic."""
    from .recap import build, render_html

    outputs: list[Output] = []
    narrator = _narrator(args, args.seed)
    orch = await run_match(
        generate(args.seed).stream(),
        sink=outputs.append,
        narrator=narrator,
        localizer=Localizer(mode="analyst"),
    )
    recap = build(orch.state, outputs)
    args.out.write_text(render_html(recap))
    kept = len(recap.goals) + len(recap.numbers) + 1
    print(f"wrote {args.out}: {kept} lines checked, {len(recap.refused)} refused")
    return 1 if recap.refused else 0


def _audit(args: argparse.Namespace, meta) -> AuditTrail | None:
    if args.audit == "none":
        return None
    endpoint = os.environ.get("COSMOS_ENDPOINT")
    if not endpoint:
        raise SystemExit("set COSMOS_ENDPOINT (scripts/live does), or run with --audit none")
    return AuditTrail(CosmosStore(endpoint), meta, narrator=args.narrator)


def _narrator(args: argparse.Namespace, seed: int):
    if args.narrator == "template":
        return TemplateNarrator(overreach_rate=args.overreach, seed=seed)
    from .foundry import FoundryNarrator

    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        raise SystemExit("set FOUNDRY_PROJECT_ENDPOINT (scripts/live does), or use the template")
    models = [
        m.strip() for m in os.environ.get("FOUNDRY_MODELS", "gpt-4.1-mini,gpt-5-mini").split(",")
    ]
    return FoundryNarrator(project_endpoint=endpoint, models=[m for m in models if m])


def _eval(args: argparse.Namespace) -> int:
    seeds = range(args.first, args.first + args.seeds)
    print(f"Scout momentum calls against hidden ground truth, seeds {seeds[0]}-{seeds[-1]}")
    print(report(evaluate(seeds)))
    return 0


def _narrator_eval(args: argparse.Namespace) -> int:
    from dataclasses import asdict
    from datetime import UTC, datetime

    from .foundry import FoundryNarrator
    from .narrator_eval import report, run, summarize

    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        raise SystemExit("set FOUNDRY_PROJECT_ENDPOINT (scripts/live does)")
    models = [m.strip() for m in os.environ.get("FOUNDRY_MODELS", "").split(",") if m.strip()]
    seeds = range(args.first, args.first + args.seeds)
    print(f"Narrator eval: {', '.join(models)} on the alerts of seeds {seeds[0]}-{seeds[-1]}")

    def make(model: str) -> FoundryNarrator:
        return FoundryNarrator(project_endpoint=endpoint, models=(model,))

    trials = asyncio.run(run(models, seeds, make))
    summaries = summarize(trials)
    print(report(summaries))
    if args.out:
        record = {
            "ran": datetime.now(UTC).isoformat(timespec="seconds"),
            "seeds": list(seeds),
            "summaries": {m: asdict(s) for m, s in summaries.items()},
            "trials": [asdict(t) for t in trials],
        }
        args.out.write_text(json.dumps(record, indent=2, default=str) + "\n")
        print(f"wrote {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="court")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run one match through the agent pipeline")
    run.add_argument("--seed", type=int, default=7, help="synthetic match seed")
    run.add_argument("--input", type=Path, help="JSONL match stream instead of --seed")
    run.add_argument("--mode", choices=("casual", "analyst"), default="analyst")
    run.add_argument(
        "--lang",
        choices=Localizer.SUPPORTED_LANGS,
        default="en",
        help="the cues' language; Urdu and Arabic are translated by the Foundry models",
    )
    run.add_argument("--speed", type=float, default=0.0, help="match-seconds per second")
    run.add_argument(
        "--overreach",
        type=float,
        default=0.25,
        help="rate at which the offline narrator deliberately overreaches",
    )
    run.add_argument("--json", action="store_true", help="emit outputs as JSONL")
    run.add_argument(
        "--strictness",
        choices=("lenient", "standard", "strict"),
        default="standard",
        help="how strictly the referee's likely calls are read (court.referee)",
    )
    run.add_argument(
        "--narrator",
        choices=("template", "foundry"),
        default="template",
        help="offline template (default) or models deployed in the Foundry project",
    )
    run.add_argument(
        "--audit",
        choices=("none", "cosmos"),
        default="none",
        help="keep every output in the Cosmos DB audit trail (default: none)",
    )
    rc = sub.add_parser("recap", help="run one match, then write its recap as an HTML page")
    rc.add_argument("--seed", type=int, default=21, help="synthetic match seed")
    rc.add_argument("--out", type=Path, default=Path("recap.html"), help="where to write it")
    rc.add_argument("--narrator", choices=("template", "foundry"), default="template")
    rc.add_argument(
        "--overreach", type=float, default=0.25, help="the offline narrator's deliberate overreach"
    )
    ev = sub.add_parser("eval", help="score the Scout's momentum calls against ground truth")
    ev.add_argument("--first", type=int, default=60, help="first seed (60-99 were never tuned on)")
    ev.add_argument("--seeds", type=int, default=40, help="how many seeds to score")
    ne = sub.add_parser("narrator-eval", help="the Foundry models narrate the same alerts")
    ne.add_argument("--first", type=int, default=60, help="first seed (60-99 were never tuned on)")
    ne.add_argument("--seeds", type=int, default=5, help="how many matches")
    ne.add_argument("--out", type=Path, help="write the summaries and every trial as JSON")
    sub.add_parser("schema", help="write the output stream's JSON Schema (apps/api/schema/)")
    fe = sub.add_parser("foundry-eval", help="Foundry's evaluators judge the lines that aired")
    fe.add_argument("--first", type=int, default=60, help="first seed (60-99 were never tuned on)")
    fe.add_argument("--seeds", type=int, default=2, help="how many matches")
    fe.add_argument("--judge", default="gpt-5-mini", help="the judging model (not the writer)")
    ae = sub.add_parser("ask-eval", help="questions asked of unseen matches, graded and judged")
    ae.add_argument("--first", type=int, default=60, help="first seed (60-99 were never tuned on)")
    ae.add_argument("--seeds", type=int, default=2, help="how many matches")
    ae.add_argument("--judge", default="gpt-5-mini", help="the judging model (not the writer)")
    ae.add_argument(
        "--rejudge", action="store_true", help="only judge again the answers the last run saved"
    )
    args = parser.parse_args(argv)
    if args.cmd == "schema":
        from .schema import write

        print(f"wrote {write()}")
        return 0
    if args.cmd == "foundry-eval":
        from .foundry_eval import main as foundry_eval

        telemetry.configure()
        try:
            return foundry_eval(args.first, args.seeds, args.judge)
        finally:
            telemetry.flush()
    if args.cmd == "ask-eval":
        from .ask_eval import main as ask_eval

        telemetry.configure()
        try:
            return ask_eval(args.first, args.seeds, args.judge, rejudge=args.rejudge)
        finally:
            telemetry.flush()
    if args.cmd == "eval":
        return _eval(args)
    if args.cmd == "narrator-eval":
        telemetry.configure()
        try:
            return _narrator_eval(args)
        finally:
            telemetry.flush()
    telemetry.configure()
    if args.cmd == "recap":
        return asyncio.run(_recap(args))
    return asyncio.run(_run(args))
