"""Drives the demo video on one clock: the browser, OBS, and the narrator's lines (docs/video.md).

Separate tool calls are too slow to hit a 110-second shot list, so the shots are a script. Each take
opens in its own tab a few seconds before its cut, so its match is already running, and comes to
the front on its second; clicks land on their beats; OBS starts and stops with the video; and the
terminal shows the line to say now and the one coming next.

The browser is Chromium in kiosk mode (no tabs, no address bar), opened by Playwright from WSL, so
it shows on the Windows desktop for OBS to capture. Its profile is kept between runs, so the Azure
portal stays signed in after --signin. The studio is reached with the Access service token, added
only to requests for the studio's own host; nothing else sees it.

    .venv/bin/python scripts/director.py --signin   # once: sign in to the Azure portal yourself
    .venv/bin/python scripts/director.py            # a rehearsal: every shot, nothing recorded
    .venv/bin/python scripts/director.py --record   # OBS records the video

OBS (on Windows): Tools > WebSocket Server Settings, enable it (port 4455). The password goes in
~/.config/obs-studio-mcp/credentials.json as {"password": "..."}, the file the OBS MCP server reads.
From WSL's NAT networking OBS is at the Windows host's address, so Windows Firewall must let TCP
4455 in from WSL.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import subprocess
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from _azure import ROOT, SITE_URL, STUDIO_URL, through_the_wall

PROFILE = Path.home() / ".config" / "hudhud" / "recording-browser"
OBS_SECRET = Path.home() / ".config" / "obs-studio-mcp" / "credentials.json"
OPS = ROOT / "site" / "data" / "ops.js"
STUDIO = STUDIO_URL.rstrip("/")
SITE = SITE_URL.rstrip("/")
LENGTH = 110.0  # seconds: under two minutes, hard (task.md)

Action = Callable[["Page"], Awaitable[None]]  # noqa: F821 (playwright's Page)


@dataclass
class Shot:
    at: float  # seconds into the video when it is on screen
    name: str
    say: str  # the voiceover from here to the next shot
    url: str | None = None  # opened in a tab of its own; None: the tab of an earlier shot
    tab: str | None = None  # which earlier shot's tab, when url is None
    preroll: float = 4.0  # seconds before `at` the tab opens, so it's live on its cut
    actions: list[tuple[float, Action]] = field(default_factory=list)  # seconds after `at`
    close_after: float | None = None  # seconds after `at` its tab closes, ending its match


def studio(path: str = "", **query: str | int) -> str:
    return f"{STUDIO}/{path}?" + "&".join(f"{k}={quote(str(v))}" for k, v in query.items())


async def scroll_to(page, selector: str) -> None:
    await page.locator(selector).first.evaluate(
        "n => n.scrollIntoView({behavior: 'smooth', block: 'center'})"
    )


async def scroll_top(page) -> None:
    await page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")


async def click(page, selector: str) -> None:
    await page.locator(selector).first.click()


async def key(page, name: str) -> None:
    await page.keyboard.press(name)


async def ask(page, question: str) -> None:
    await page.locator("[data-ask] input[name=question]").fill(question)
    await page.locator("[data-ask] input[name=question]").press("Enter")


async def back_on_air(page) -> None:
    """Back on air once a line has aired on the Scout's facts alone (or after eight seconds): the
    model narrates at its own pace, so the moment can't be fixed to the clock."""
    try:
        await page.locator(".cue.detection").first.wait_for(timeout=8000)
        await asyncio.sleep(1.5)
    except Exception:  # no moment came in time: come back anyway
        pass
    await click(page, "[data-pull]")


def portal(label: str) -> str:
    """A control-room link by its label (site/data/ops.js, written by scripts/control_room.py)."""
    text = OPS.read_text()
    ops = json.loads(text[text.index("{") : text.rindex("}") + 1])
    return next(
        link["href"] for g in ops["groups"] for link in g["links"] if link["label"] == label
    )


def shots() -> list[Shot]:
    match = {"seed": 21, "narration": "foundry", "stress": 1, "autostart": 1}
    return [
        Shot(
            0,
            "the site",
            "AI can commentate a football match. The trouble is, it sounds just as sure when "
            "it's wrong. HUDHUD checks every line against the match before it airs.",
            url=f"{SITE}/",
            preroll=5,
            actions=[(4.5, lambda p: scroll_to(p, ".front-three"))],
        ),
        Shot(
            9,
            "the studio",
            "This is my studio, live on Azure Container Apps. A model on Microsoft Foundry writes "
            "each line from facts my code computed. Every line carries its evidence and a "
            "receipt, and the Critic's desk shows what it refused, and why.",
            url=studio(
                **match, start=40, speed=60, lang="en", club="home", player="h09", metric="xg"
            ),
            preroll=8,  # running behind the site's shot, so lines are on air at the cut
            actions=[(12, lambda p: scroll_to(p, ".desk")), (19, scroll_top)],
        ),
        Shot(
            31,
            "HUD², the referee",
            "HUD², the referee's lens. A foul in the box: likely a penalty and a yellow, read "
            "from the Law and recomputed by the Critic, pinned where it happened. Commentators "
            "and fans get lenses of their own.",
            url=studio("hud", **match, lens="referee", start=50, speed=30, view="stand"),
            preroll=10,  # the penalty's call (54') lands as the shot cuts in
            actions=[(10, lambda p: key(p, "2")), (13, lambda p: key(p, "3"))],
            close_after=16,
        ),
        Shot(
            47,
            "off air",
            "Now I take the narrator off air. The broadcast keeps going on the Scout's own "
            "facts, says so, and brings the commentary back.",
            tab="the studio",
            actions=[(2, lambda p: click(p, "[data-pull]")), (3, back_on_air)],
            close_after=13,
        ),
        Shot(
            60,
            "Urdu",
            "The same law holds in Urdu and Arabic, on screen and spoken: a translation may not "
            "add a number or change a name.",
            url=studio(**match, start=54, speed=30, lang="ur"),
            preroll=6,
            actions=[(-5, lambda p: click(p, "[data-hear]"))],
            close_after=6,
        ),
        Shot(
            66,
            "Arabic",
            "",
            url=studio(**match, start=54, speed=30, lang="ar"),
            preroll=6,
            actions=[(-5, lambda p: click(p, "[data-hear]"))],
            close_after=6,
        ),
        Shot(
            72,
            "ask the match",
            "Ask the match anything, typed or out loud. Code counts every number, the Critic "
            "checks the answer, and it's sealed in the match's ledger, so your browser can "
            "verify it. And it never helps anyone bet.",
            url=studio(
                "ask",
                seed=21,
                when="full",
                narration="foundry",
                autostart=1,
                q="Who has completed the most passes?",
            ),
            preroll=14,
            actions=[
                (2, lambda p: click(p, ".reply.verified .proof .quiet")),
                (6, lambda p: ask(p, "What are the odds on Brackenfield?")),
            ],
        ),
        Shot(
            86,
            "Azure",
            "Five agents on Microsoft Agent Framework. Models chosen by evaluation and judged by "
            "Foundry's own evaluators. Every call traced, every claim kept on Cosmos DB, and the "
            "Critic open to any assistant over MCP and any agent over A2A.",
            url=portal("HUDHUD control room"),
            preroll=12,  # the portal is slow to draw a workbook
        ),
        Shot(93, "every model call", "", url=portal("Every model call"), preroll=12),
        Shot(
            100,
            "the ledger",
            "",
            url=f"{SITE}/#/ledger",
            preroll=4,
            actions=[(1, lambda p: click(p, "[data-ledger-verify]"))],
        ),
        Shot(
            104,
            "the team sheet",
            "HUDHUD. Built by one engineer. Every call comes with its evidence.",
            url=f"{SITE}/#/",
            preroll=3,
            actions=[(1, lambda p: click(p, ".menu-button"))],
        ),
    ]


# --- OBS, over obs-websocket 5 -------------------------------------------------------------


class Obs:
    """Just enough of obs-websocket 5 to start and stop a recording: sign in, ask, read replies."""

    def __init__(self, host: str, port: int, password: str) -> None:
        self.url, self.password = f"ws://{host}:{port}", password

    async def __aenter__(self):
        import websockets

        self.ws = await websockets.connect(self.url, open_timeout=5)
        hello = json.loads(await self.ws.recv())["d"]
        identify = {"rpcVersion": 1}
        if auth := hello.get("authentication"):
            secret = base64.b64encode(
                hashlib.sha256((self.password + auth["salt"]).encode()).digest()
            )
            response = hashlib.sha256(secret + auth["challenge"].encode()).digest()
            identify["authentication"] = base64.b64encode(response).decode()
        await self.ws.send(json.dumps({"op": 1, "d": identify}))
        json.loads(await self.ws.recv())  # Identified
        return self

    async def __aexit__(self, *_) -> None:
        await self.ws.close()

    async def call(self, kind: str, data: dict | None = None) -> dict:
        rid = uuid.uuid4().hex
        request = {"requestType": kind, "requestId": rid, "requestData": data or {}}
        await self.ws.send(json.dumps({"op": 6, "d": request}))
        while True:
            message = json.loads(await self.ws.recv())
            if message["op"] == 7 and message["d"]["requestId"] == rid:
                status = message["d"]["requestStatus"]
                if not status["result"]:
                    raise RuntimeError(f"OBS {kind}: {status.get('comment', status['code'])}")
                return message["d"].get("responseData") or {}


def windows_host() -> str:
    route = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True)
    return route.stdout.split()[2]


# --- the run -------------------------------------------------------------------------------


def prompter(lines: list[tuple[float, str, str]], started: float) -> Callable[[], None]:
    """The terminal: the line to say now, a countdown, and the next one."""

    def draw() -> None:
        now = time.monotonic() - started
        current = max((x for x in lines if x[0] <= now), default=None, key=lambda x: x[0])
        upcoming = min((x for x in lines if x[0] > now), default=None, key=lambda x: x[0])
        out = [f"\033[2J\033[H  {now:5.1f} s of {LENGTH:.0f}"]
        if current:
            out.append(f"\n  NOW  {current[1]}\n\n  \033[1m{current[2] or '(keep going)'}\033[0m")
        if upcoming:
            out.append(f"\n\n  in {upcoming[0] - now:4.1f} s: {upcoming[1]}: {upcoming[2][:70]}")
        print("".join(out), flush=True)

    return draw


async def run(args: argparse.Namespace) -> int:
    from playwright.async_api import async_playwright

    plan = shots()
    wall = {k: v for k, v in through_the_wall().items() if k.startswith("CF-Access")}
    PROFILE.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            PROFILE,
            headless=args.headless,
            no_viewport=not args.headless,
            viewport={"width": 1920, "height": 1080} if args.headless else None,
            args=[
                "--kiosk" if not args.signin else "--start-maximized",
                "--autoplay-policy=no-user-gesture-required",
            ],
            ignore_default_args=["--enable-automation"],
        )

        async def through(route) -> None:
            await route.continue_(headers={**route.request.headers, **wall})

        await context.route(f"{STUDIO}/**", through)
        if args.signin:
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(portal("HUDHUD control room"))
            print("Sign in to the Azure portal in the window that opened, then close it.")
            await page.wait_for_event("close", timeout=0)
            await context.close()
            return 0

        obs = None
        if args.record:
            password = json.loads(OBS_SECRET.read_text())["password"]
            obs = await Obs(args.obs_host or windows_host(), 4455, password).__aenter__()
            print(f"OBS {(await obs.call('GetVersion'))['obsVersion']}: connected")

        tabs: dict[str, object] = {}
        snaps: set[asyncio.Task] = set()
        started = time.monotonic() + max(s.preroll for s in plan if s.at == 0) + 1
        lines = [(s.at, s.name, s.say) for s in plan]
        draw = prompter(lines, started)

        async def at(t: float) -> None:
            await asyncio.sleep(max(0.0, started + t - time.monotonic()))

        async def shot(s: Shot) -> None:
            if s.url:
                await at(s.at - s.preroll)
                page = await context.new_page()
                tabs[s.name] = page
                await page.goto(s.url, wait_until="domcontentloaded")
            else:  # an earlier shot's tab: it is open by the time this one is due
                await at(s.at - 0.5)
            page = tabs[s.name if s.url else s.tab]
            for offset, action in sorted(s.actions, key=lambda a: a[0]):
                if offset < 0:
                    await at(s.at + offset)
                    await action(page)
            await at(s.at)
            await page.bring_to_front()
            if args.frames:  # what each shot looks like two seconds in, to check a rehearsal
                snaps.add(asyncio.create_task(frame(page, s)))
            for offset, action in sorted(s.actions, key=lambda a: a[0]):
                if offset >= 0:
                    await at(s.at + offset)
                    try:
                        await action(page)
                    except Exception as error:  # a missed click is noted, the take goes on
                        print(f"\n  ! {s.name} +{offset}s: {type(error).__name__}", flush=True)
            if s.close_after is not None:
                await at(s.at + s.close_after)
                await page.close()

        async def frame(page, s: Shot) -> None:
            await at(s.at + 2)
            name = f"{int(s.at):03d}-{s.name.replace(' ', '-').replace('²', '2')}.png"
            await page.screenshot(path=str(Path(args.frames) / name))

        async def tick() -> None:
            while time.monotonic() < started + LENGTH:
                draw()
                await asyncio.sleep(0.25)

        async def record() -> None:
            await at(-0.5)
            await obs.call("StartRecord")
            await at(LENGTH)
            saved = await obs.call("StopRecord")
            print(f"\n  recorded: {saved.get('outputPath', '(see OBS)')}", flush=True)

        jobs = [shot(s) for s in plan] + [tick()]
        if obs:
            jobs.append(record())
        try:
            await asyncio.gather(*jobs)
            await at(LENGTH + 1)
        finally:
            if obs:
                await obs.__aexit__()
            await context.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--record", action="store_true", help="OBS records the video")
    parser.add_argument("--signin", action="store_true", help="open the browser to sign in once")
    parser.add_argument("--obs-host", help="OBS's address (default: the Windows host)")
    parser.add_argument("--headless", action="store_true", help="no window: for testing the shots")
    parser.add_argument(
        "--frames", help="save each shot as it looks two seconds in, to this folder"
    )
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
