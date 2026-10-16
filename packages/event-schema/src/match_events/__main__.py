"""CLI: `python -m match_events {generate,schema,stats}`."""

import argparse
import sys
from collections import Counter
from pathlib import Path

from . import schema
from .io import to_jsonl
from .models import Pass, PassOutcome, Shot, ShotOutcome
from .synth import generate


def _stats(seed: int) -> str:
    match = generate(seed)
    types = Counter(e.type for e in match.events)
    passes = [e for e in match.events if isinstance(e, Pass)]
    shots = [e for e in match.events if isinstance(e, Shot)]
    done = sum(p.outcome is PassOutcome.COMPLETE for p in passes)
    goals = sum(s.outcome is ShotOutcome.GOAL for s in shots)
    m = match.meta
    score = match.truth.final_score
    return "\n".join(
        [
            f"{m.match_id}  {m.home.name} {score['home']}-{score['away']} {m.away.name}",
            f"events {len(match.events)}  "
            + "  ".join(f"{k} {v}" for k, v in sorted(types.items())),
            f"pass completion {done / max(len(passes), 1):.1%}  shots {len(shots)}  goals {goals}",
            f"momentum spells {len(match.truth.spells)}",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="match_events")
    sub = parser.add_subparsers(dest="cmd", required=True)
    gen = sub.add_parser("generate", help="write one match as JSONL")
    gen.add_argument("--seed", type=int, default=7)
    gen.add_argument("--out", type=Path, help="file to write (default: stdout)")
    sub.add_parser("schema", help="regenerate the committed JSON Schema")
    st = sub.add_parser("stats", help="summarise one generated match")
    st.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)

    if args.cmd == "generate":
        text = to_jsonl(generate(args.seed).stream())
        if args.out:
            args.out.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
    elif args.cmd == "schema":
        print(schema.write())
    else:
        print(_stats(args.seed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
