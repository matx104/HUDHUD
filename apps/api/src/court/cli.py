"""Console runner: `python -m court run --seed 7`. One synthetic match, end to end."""

import argparse
import asyncio
import sys
from pathlib import Path

from match_events import Side, generate, read_jsonl

from .config import ARCHITECTURE_NAME, product_name
from .contracts import OUTPUT_ADAPTER, Cue, Degradation, Output, RejectionNotice, Spiked
from .localizer import Localizer
from .narrator import TemplateNarrator
from .orchestrator import run_match


def _console(output: Output) -> None:
    match output:
        case Cue():
            mark = "✔" if output.status == "verified" else "◌"
            retry = f"  (attempt {output.attempts})" if output.attempts > 1 else ""
            cites = " ".join(output.evidence)
            print(f"{output.minute:>7} {mark} {output.headline}  {output.text}{retry}  [{cites}]")
        case RejectionNotice():
            why = "; ".join(f"{r.code}: {r.detail}" for r in output.reasons)
            print(f"{output.minute:>7} ✘ REJECTED {output.claim.id}  {why}")
        case Spiked():
            print(f"{output.minute:>7} ✖ SPIKED {output.claim.id}  never aired")
        case Degradation():
            print(f"{output.minute:>7} ⚠ SERVICE {output.level.upper()}  {output.detail}")


def _jsonl(output: Output) -> None:
    sys.stdout.write(OUTPUT_ADAPTER.dump_json(output).decode() + "\n")


async def _run(args: argparse.Namespace) -> int:
    messages = read_jsonl(args.input) if args.input else list(generate(args.seed).stream())
    meta = messages[0]
    if not args.json:
        print(f"{product_name()} · {ARCHITECTURE_NAME} · synthetic data only")
        print(f"{meta.match_id}  {meta.home.name} vs {meta.away.name}  (seed {meta.seed})\n")
    orch = await run_match(
        messages,
        sink=_jsonl if args.json else _console,
        speed=args.speed,
        narrator=TemplateNarrator(overreach_rate=args.overreach, seed=meta.seed),
        localizer=Localizer(mode=args.mode),
    )
    if not args.json:
        s, st = orch.state.score, orch.stats
        print(f"\n     FT  {meta.home.name} {s[Side.HOME]}-{s[Side.AWAY]} {meta.away.name}")
        print("         " + " · ".join(f"{k} {v}" for k, v in sorted(st.items())))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="court")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run one match through the agent pipeline")
    run.add_argument("--seed", type=int, default=7, help="synthetic match seed")
    run.add_argument("--input", type=Path, help="JSONL match stream instead of --seed")
    run.add_argument("--mode", choices=("casual", "analyst"), default="analyst")
    run.add_argument("--speed", type=float, default=0.0, help="match-seconds per second")
    run.add_argument(
        "--overreach",
        type=float,
        default=0.25,
        help="rate at which the offline narrator deliberately overreaches",
    )
    run.add_argument("--json", action="store_true", help="emit outputs as JSONL")
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))
