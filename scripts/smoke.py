"""Does the live studio work, end to end, right now? Streams one short match and checks every part.

Health, config, then a match from the 80th minute: the hello, the clock, the cues with their
receipts, the end. The offline narrator by default, so it costs nothing; --models has the Foundry
models narrate it instead (well under a cent). Exits 1 on any failure: run it before a recording.

    make smoke                         # the deployed studio
    .venv/bin/python scripts/smoke.py --url http://localhost:8080/ --models
"""

import argparse
import json
import sys
import time
import urllib.request

from _azure import studio_url


def stream(url: str) -> list[tuple[str, dict]]:
    events, kind = [], None
    with urllib.request.urlopen(url, timeout=180) as response:
        for raw in response:
            line = raw.decode().rstrip("\n")
            if line.startswith("event: "):
                kind = line.removeprefix("event: ")
            elif line.startswith("data: "):
                events.append((kind, json.loads(line.removeprefix("data: "))))
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", help="the studio's address (default: the deployed one)")
    parser.add_argument("--models", action="store_true", help="narrate with the Foundry models")
    args = parser.parse_args()
    base = (args.url or studio_url()).rstrip("/") + "/"
    failures = []

    def check(ok: bool, what: str) -> None:
        print(f" {'✔' if ok else '✘'} {what}")
        if not ok:
            failures.append(what)

    with urllib.request.urlopen(base + "healthz", timeout=30) as response:
        check(json.load(response) == {"status": "ok"}, f"healthy: {base}")
    with urllib.request.urlopen(base + "api/config", timeout=30) as response:
        config = json.load(response)
    check(len(config["matches"]) >= 1, f"{len(config['matches'])} demo matches")
    if args.models:
        check(config["models"], f"models connected, {config['model_matches_left']} left today")

    narration = "foundry" if args.models else "template"
    started = time.perf_counter()
    events = stream(f"{base}api/stream?seed=21&narration={narration}&speed=0&start=70&stress=0.25")
    seconds = time.perf_counter() - started
    kinds = [kind for kind, _ in events]
    check(
        kinds[:1] == ["hello"] and events[0][1]["narration"] == narration,
        f"hello: narrated by {events[0][1].get('narration') if events else '?'}",
    )
    check("clock" in kinds, f"{kinds.count('clock')} clock updates")
    cues = [d for k, d in events if k == "output" and d["type"] == "cue"]
    check(
        bool(cues) and all(c.get("receipt") for c in cues), f"{len(cues)} cues, each with a receipt"
    )
    writers = sorted({c["receipt"]["writer"] for c in cues})
    check(not args.models or writers == ["gpt-4.1-mini"], f"written by {', '.join(writers)}")
    check(kinds[-1:] == ["end"], f"full time in {seconds:.1f} s")
    if kinds[-1:] == ["end"]:
        end = events[-1][1]
        print(f"   {end['stats']}  cost ${end['cost_usd']:.4f}  {end.get('audit', '')}")
    print(f"\n{'all good' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
