"""The showcase site's live demos: one real match recorded from the studio, replayed by the
studio's own pages (site/demo/).

The studio is private, so the public site can't stream a match. This records one instead, from the
deployed studio through the wall, exactly as a viewer's browser received it, with the Foundry models
narrating and answering:

- recording.json: the studio's config and every server-sent event of one match with when it
  arrived (seed 21 from 50', 30 times live, HUD²'s stream, the stress test on), then the questions
  asked after full time with their answers, the suggestions offered, and each answer's proof.
- ledger.json: that match's ledger, as the studio's Download gives it.

It also copies the studio's pages (the studio, HUD² and Ask the match) and their scripts, with
replay.js loaded first: it stands in for the studio, playing the recording to the page's own code.
The copies change only where a page names the studio's paths; tests/site/demo.test.cjs fails if
they drift from the studio's.

    .venv/bin/python scripts/site_demo.py                               # the deployed studio
    .venv/bin/python scripts/site_demo.py --url http://localhost:8091/  # a local one
    .venv/bin/python scripts/site_demo.py --copy-only                   # the pages only
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request

from _azure import ROOT, STUDIO_URL, through_the_wall

STUDIO = ROOT / "apps" / "api" / "src" / "court" / "studio"
DEMO = ROOT / "site" / "demo"
PAGES = {"index.html": "studio.html", "hud.html": "hud.html", "ask.html": "ask.html"}
ASSETS = (
    "studio.css",
    "studio.js",
    "hud.css",
    "hud.js",
    "hud-core.js",
    "ask.css",
    "ask.js",
    "ledger-core.js",
    "voice.js",
)
STREAM = "seed=21&narration=foundry&speed=30&start=50&stress=0.25&hud=1&mode=analyst&lang=en"
QUESTIONS = (
    "Who scored?",
    "Who has completed the most passes?",
    "How many shots have Saltmarsh Rovers had?",
    "And Brackenfield?",
    "What was the biggest chance?",
    "How is Luka Dunvik doing?",
    "Which side had more of the ball in the second half?",
    "Is Adem Rosmere injured?",
    "What are the odds on Brackenfield?",
    "Who will win?",
)


def page(html: str) -> str:
    """A studio page as the demo serves it: its own folder's files, replay.js first, and links
    between the three pages kept inside the demo. Mirrored in tests/site/demo.test.cjs."""
    html = html.replace('src="/static/', 'src="').replace('href="/static/', 'href="')
    for path, name in (
        ('href="/"', "studio.html"),
        ('href="/hud"', "hud.html"),
        ('href="/ask"', "ask.html"),
    ):
        html = html.replace(path, f'href="{name}"')
    first = html.index("  <script src=")
    return html[:first] + '  <script src="replay.js"></script>\n' + html[first:]


def copy_pages() -> None:
    DEMO.mkdir(exist_ok=True)
    for source, target in PAGES.items():
        (DEMO / target).write_text(page((STUDIO / source).read_text()))
    for name in ASSETS:
        (DEMO / name).write_text((STUDIO / name).read_text())


def record(base: str, headers: dict[str, str]) -> None:
    def get(path: str) -> dict:
        request = urllib.request.Request(base + path, headers=headers)
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)

    def post(path: str, body: dict) -> dict:
        request = urllib.request.Request(
            base + path,
            data=json.dumps(body).encode(),
            headers=headers | {"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)

    config = get("api/config")
    events, kind, started = [], None, time.perf_counter()
    request = urllib.request.Request(f"{base}api/stream?{STREAM}", headers=headers)
    with urllib.request.urlopen(request, timeout=300) as response:
        for raw in response:
            line = raw.decode().rstrip("\n")
            if line.startswith("event: "):
                kind = line.removeprefix("event: ")
            elif line.startswith("data: "):
                at = round((time.perf_counter() - started) * 1000)
                events.append([at, kind, json.loads(line.removeprefix("data: "))])
    session = events[0][2]["session"]
    print(f"recorded {len(events)} events in {events[-1][0] / 1000:.0f} s, session {session}")
    asked = []
    for question in QUESTIONS:
        answer = post(f"api/sessions/{session}/ask", {"question": question})
        print(f"  {question} -> [{answer['status']}] {answer['text'][:90]}")
        asked.append(answer)
    suggest = get(f"api/sessions/{session}/suggest")["questions"]
    for answer in asked:  # after the last answer, so every proof ends at the same seal
        item = urllib.parse.quote(f"answer:{answer['id']}")
        answer["proof"] = get(f"api/sessions/{session}/ledger/proof?item={item}")
    ledger = get(f"api/sessions/{session}/ledger")
    recording = {
        "recorded": time.strftime("%Y-%m-%d", time.gmtime()),
        "stream": STREAM,
        "config": config | {"voice": False},  # the site has no voice: no audio to fetch
        "events": events,
        "answers": asked,
        "suggest": suggest,
    }
    (DEMO / "recording.json").write_text(json.dumps(recording, ensure_ascii=False) + "\n")
    (DEMO / "ledger.json").write_text(json.dumps(ledger, ensure_ascii=False) + "\n")
    print(f"wrote {DEMO / 'recording.json'} and the ledger: seal {ledger['head'][:16]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", help="the studio's address (default: the deployed one)")
    parser.add_argument("--copy-only", action="store_true", help="copy the pages, record nothing")
    args = parser.parse_args()
    copy_pages()
    print(f"copied {len(PAGES)} pages and {len(ASSETS)} files to {DEMO}")
    if not args.copy_only:
        base = (args.url or STUDIO_URL).rstrip("/") + "/"
        record(base, {} if args.url else through_the_wall())
    return 0


if __name__ == "__main__":
    sys.exit(main())
