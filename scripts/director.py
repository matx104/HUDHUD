"""Drives the demo video on one clock: the owner's own Chrome, OBS, and the narrator's lines
(docs/video.md).

Separate tool calls are too slow to hit a 110-second shot list, so the shots are a script. Each take
opens in its own tab a few seconds before its cut, so its match is already running, and comes to
the front on its second; clicks land on their beats; OBS starts and stops with the video; and the
terminal shows the line to say now and the one coming next.

The browser is the owner's Chrome on Windows, already signed in to the Azure portal, driven over
the Chrome DevTools Protocol. The owner turns remote debugging on at
chrome://inspect/#remote-debugging, and Chrome asks them to allow each connection, so one
connection runs every take (--control). The director touches only the window it opens, full screen
so no tabs, bookmarks or profile show, and the tabs in it. Chrome listens on Windows' loopback,
which WSL can't reach, so the connection goes through PowerShell on the Windows side: no port is
opened. The studio is reached with the Access service token, added only to requests for the
studio's own host; nothing else sees it.

    .venv/bin/python scripts/director.py                       # a rehearsal: nothing recorded
    .venv/bin/python scripts/director.py --record              # OBS records the video
    .venv/bin/python scripts/director.py --control FILE        # one connection, many takes
    .venv/bin/python scripts/director.py --headless --frames DIR  # a local Chromium: test the shots

With --control, after each take the director waits for FILE to say rehearse, record or quit.

OBS (on Windows): Tools > WebSocket Server Settings, enable it (port 4455). The password goes in
~/.config/obs-studio-mcp/credentials.json as {"password": "..."}, the file the OBS MCP server reads.
From WSL's NAT networking OBS is at the Windows host's address, so Windows Firewall must let TCP
4455 in from WSL.
"""

import argparse
import asyncio
import base64
import contextlib
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from _azure import ROOT, SITE_URL, STUDIO_URL, through_the_wall

OBS_SECRET = Path.home() / ".config" / "obs-studio-mcp" / "credentials.json"
OPS = ROOT / "site" / "data" / "ops.js"
STUDIO = STUDIO_URL.rstrip("/")
SITE = SITE_URL.rstrip("/")
LENGTH = 110.0  # seconds: under two minutes, hard (task.md)
BLANK = "data:text/html,<body style='background:%2306141F'>"  # the site's navy, between shots

Action = Callable[["Tab"], Awaitable[None]]


@dataclass
class Shot:
    at: float  # seconds into the video when it is on screen
    name: str
    say: str  # the voiceover from here to the next shot
    url: str | None = None  # opened in a tab of its own; None: the tab of an earlier shot
    tab: str | None = None  # which earlier shot's tab, when url is None
    preroll: float = 4.0  # seconds before `at` the tab opens, so it's live on its cut
    warm: float | None = None  # instead: opened before the take, this long on screen to draw
    data: str | None = None  # a selector with real content on it before the tab is brought front
    ready: list[Action] = field(default_factory=list)  # then these, before the take begins
    actions: list[tuple[float, Action]] = field(default_factory=list)  # seconds after `at`
    close_after: float | None = None  # seconds after `at` its tab closes, ending its match
    hide: str | None = None  # CSS selectors kept off screen (the portal's account)


def studio(path: str = "", **query: str | int) -> str:
    return f"{STUDIO}/{path}?" + "&".join(f"{k}={quote(str(v))}" for k, v in query.items())


async def scroll_to(tab: "Tab", selector: str) -> None:
    await tab.evaluate(
        f"document.querySelector({json.dumps(selector)})"
        ".scrollIntoView({behavior: 'smooth', block: 'center'})"
    )


async def scroll_top(tab: "Tab") -> None:
    await tab.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")


async def ask(tab: "Tab", question: str) -> None:
    await tab.click("[data-ask] input[name=question]:not([disabled])")
    await tab.type(question)
    await tab.press("Enter")


async def back_on_air(tab: "Tab") -> None:
    """Back on air once a line has aired on the Scout's facts alone (or after eight seconds): the
    model narrates at its own pace, so the moment can't be fixed to the clock."""
    with contextlib.suppress(TimeoutError):
        await tab.wait_for(".cue.detection", timeout=8)
        await asyncio.sleep(1.5)
    await tab.click("[data-pull]")


def portal(label: str) -> str:
    """A control-room link by its label (site/data/ops.js, written by scripts/control_room.py)."""
    text = OPS.read_text()
    ops = json.loads(text[text.index("{") : text.rindex("}") + 1])
    return next(
        link["href"] for g in ops["groups"] for link in g["links"] if link["label"] == label
    )


ACCOUNT = '[class*="avatarmenu"], [class*="fxs-avatar"]'  # the portal's top bar: who's signed in


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
            actions=[(4.5, lambda t: scroll_to(t, ".front-three"))],
        ),
        Shot(
            9,
            "the studio",
            "This is my studio, live on Azure Container Apps. A model on Microsoft Foundry writes "
            "each line from facts my code computed. Every line carries its evidence and a "
            "receipt, and the Critic's desk shows what it refused, and why.",
            url=studio(
                **match, start=44, speed=60, lang="en", club="home", player="h09", metric="xg"
            ),
            preroll=20,  # behind the site's shot: lines on air, the desk already refusing, at the cut
            data="[data-cues] .cue",  # a line on air before the cut, not a quiet feed
            actions=[(12, lambda t: scroll_to(t, ".desk")), (19, scroll_top)],
        ),
        Shot(
            31,
            "HUD², the referee",
            "HUD², the referee's lens. A foul in the box: likely a penalty and a yellow, read "
            "from the Law and recomputed by the Critic, pinned where it happened. Commentators "
            "and fans get lenses of their own.",
            url=studio("hud", **match, lens="referee", start=50, speed=30, view="stand"),
            preroll=15,  # the penalty's call (54') is on screen while the line describes it
            data="[data-pins] > *",  # the call pinned where it happened
            actions=[(10, lambda t: t.press("2")), (13, lambda t: t.press("3"))],
            close_after=16.5,  # just after the next shot is in front, so no other tab flashes
        ),
        Shot(
            47,
            "off air",
            "Now I take the narrator off air. The broadcast keeps going on the Scout's own "
            "facts, says so, and brings the commentary back.",
            tab="the studio",
            actions=[(2, lambda t: t.click("[data-pull]")), (3, back_on_air)],
            close_after=13.5,
        ),
        Shot(
            60,
            "Urdu",
            "The same law holds in Urdu and Arabic, on screen and spoken: a translation may not "
            "add a number or change a name.",
            url=studio(**match, start=54, speed=30, lang="ur"),
            preroll=14,  # lines already on air at the cut
            data="[data-cues] .cue",
            # Hear, just after the cut: Chrome holds a click for a hidden tab until it's shown, and
            # ticking it reads the line on air
            actions=[(0.3, lambda t: t.click("[data-hear]"))],
            close_after=6.5,
        ),
        Shot(
            66,
            "Arabic",
            "",
            url=studio(**match, start=54, speed=30, lang="ar"),
            preroll=14,
            data="[data-cues] .cue",
            actions=[(0.3, lambda t: t.click("[data-hear]"))],
            close_after=6.5,
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
            data=".reply",  # the first answer is on screen before the cut
            actions=[
                (2, lambda t: t.click(".reply.verified .proof .quiet")),
                (5, lambda t: ask(t, "What are the odds on Brackenfield?")),
            ],
        ),
        Shot(
            86,
            "Azure",
            "Five agents on Microsoft Agent Framework. Models chosen by evaluation and judged by "
            "Foundry's own evaluators. Every call traced, every claim kept on Cosmos DB, and the "
            "Critic open to any assistant over MCP and any agent over A2A.",
            url=portal("HUDHUD control room"),
            warm=25,  # a background tab doesn't draw the portal's workbook
            hide=ACCOUNT,
        ),
        Shot(
            93,
            "every model call",
            "",
            url=portal("Every model call"),
            warm=25,
            ready=[lambda t: t.press("Escape")],  # Logs opens its queries hub over the query
            hide=ACCOUNT,
        ),
        Shot(
            98,
            "the ledger",
            "",
            url=f"{SITE}/#/ledger",
            preroll=10,
            data="[data-ledger-squares] li",  # the ledger's blocks drawn, not a bare page
            actions=[(1, lambda t: t.click("[data-ledger-verify]"))],
        ),
        Shot(
            105,
            "the team sheet",
            "HUDHUD. Built by one engineer. Every call comes with its evidence.",
            url=f"{SITE}/#/",
            preroll=4,
            data=".menu-button",
            actions=[(1, lambda t: t.click(".menu-button"))],
        ),
    ]


# --- Chrome, over the DevTools Protocol ----------------------------------------------------

# Every tab the director opens is heard only while it's on screen: the studio speaks from a tab in
# the background too, and the Urdu voice would run over the shot before its own.
ON_SCREEN_ONLY = """(() => {
  const Heard = window.Audio;
  window.Audio = function (...args) {
    const audio = new Heard(...args);
    const follow = () => { audio.muted = document.hidden; };
    follow();
    document.addEventListener("visibilitychange", follow);
    return audio;
  };
})();"""

HIDE = """document.addEventListener("DOMContentLoaded", () => {{
  const style = document.createElement("style");
  style.textContent = {css} + " {{ visibility: hidden !important; }}";
  document.head.append(style);
}});"""

# Where a selector's element is, scrolled into view first when asked: null until it's there.
FIND = """((selector, scroll) => {{
  const node = document.querySelector(selector);
  if (!node) return null;
  let r = node.getBoundingClientRect();
  if (!r.width || !r.height) return null;
  if (scroll && (r.top < 0 || r.bottom > innerHeight)) {{
    node.scrollIntoView({{block: "center"}});
    r = node.getBoundingClientRect();
  }}
  return [r.x + r.width / 2, r.y + r.height / 2];
}})({selector}, {scroll})"""

KEYS = {
    "2": ("Digit2", 50, "2"),
    "3": ("Digit3", 51, "3"),
    "Enter": ("Enter", 13, "\r"),
    "Escape": ("Escape", 27, ""),
}


class Chrome:
    """Just enough of the DevTools Protocol: commands and their replies, and the studio's requests
    let through the wall."""

    def __init__(self, ws, wall: dict[str, str]) -> None:
        self.ws, self.wall, self.last, self.waiting = ws, wall, 0, {}
        self.passing: set[asyncio.Task] = set()
        self.reader = asyncio.create_task(self.read())

    async def read(self) -> None:
        async for raw in self.ws:
            message = json.loads(raw)
            if "id" in message:
                if future := self.waiting.pop(message["id"], None):
                    future.set_result(message)
            elif message.get("method") == "Fetch.requestPaused":
                task = asyncio.create_task(self.through(message))
                self.passing.add(task)
                task.add_done_callback(self.passing.discard)

    async def through(self, message: dict) -> None:
        paused = message["params"]
        headers = {**paused["request"]["headers"], **self.wall}
        await self.send(
            "Fetch.continueRequest",
            {
                "requestId": paused["requestId"],
                "headers": [{"name": k, "value": v} for k, v in headers.items()],
            },
            message["sessionId"],
        )

    async def send(self, method: str, params: dict | None = None, session: str | None = None):
        self.last += 1
        reply = self.waiting[self.last] = asyncio.get_running_loop().create_future()
        message = {"id": self.last, "method": method, "params": params or {}}
        if session:
            message["sessionId"] = session
        await self.ws.send(json.dumps(message))
        result = await asyncio.wait_for(reply, 30)
        if "error" in result:
            raise RuntimeError(f"{method}: {result['error'].get('message')}")
        return result.get("result", {})


class Tab:
    """One tab of the director's window: opened, driven like a viewer would, brought forward."""

    def __init__(self, chrome: Chrome, target: str, session: str) -> None:
        self.chrome, self.target, self.session = chrome, target, session

    @classmethod
    async def open(
        cls, chrome: Chrome, url: str, *, background: bool = True, hide: str | None = None
    ):
        params = {"url": "about:blank", "background": background}
        target = (await chrome.send("Target.createTarget", params))["targetId"]
        attached = {"targetId": target, "flatten": True}
        session = (await chrome.send("Target.attachToTarget", attached))["sessionId"]
        tab = cls(chrome, target, session)
        await tab.send("Page.enable")
        await tab.send("Network.enable")  # the studio's own files fresh, never a cached old copy
        await tab.send("Network.setCacheDisabled", {"cacheDisabled": True})
        await tab.send("Page.addScriptToEvaluateOnNewDocument", {"source": ON_SCREEN_ONLY})
        if hide:
            source = HIDE.format(css=json.dumps(hide))
            await tab.send("Page.addScriptToEvaluateOnNewDocument", {"source": source})
        await tab.send("Fetch.enable", {"patterns": [{"urlPattern": f"{STUDIO}/*"}]})
        await tab.send("Page.navigate", {"url": url})
        return tab

    async def send(self, method: str, params: dict | None = None):
        return await self.chrome.send(method, params, self.session)

    async def window(self) -> int:
        params = {"targetId": self.target}
        return (await self.chrome.send("Browser.getWindowForTarget", params))["windowId"]

    async def evaluate(self, expression: str):
        params = {"expression": expression, "returnByValue": True, "awaitPromise": True}
        result = await self.send("Runtime.evaluate", params)
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"].get("text", "the page threw"))
        return result["result"].get("value")

    async def wait_for(self, selector: str, *, timeout: float = 10, scroll: bool = False):
        end = time.monotonic() + timeout
        find = FIND.format(selector=json.dumps(selector), scroll=json.dumps(scroll))
        while (point := await self.evaluate(find)) is None:
            if time.monotonic() > end:
                raise TimeoutError(selector)
            await asyncio.sleep(0.1)
        return point

    async def click(self, selector: str) -> None:
        """A real click, as Chrome's own input: it counts as the viewer's, so audio may play."""
        x, y = await self.wait_for(selector, scroll=True)
        await self.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        for kind in ("mousePressed", "mouseReleased"):
            click = {"type": kind, "x": x, "y": y, "button": "left", "clickCount": 1}
            await self.send("Input.dispatchMouseEvent", click)
        await self.park()

    async def park(self) -> None:
        """The pointer to the right edge, off every link: Chrome shows a hovered link's address."""
        x, y = await self.evaluate("[innerWidth - 2, innerHeight / 2]")
        await self.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})

    async def press(self, key: str) -> None:
        code, number, text = KEYS[key]
        down = {"key": key, "code": code, "windowsVirtualKeyCode": number}
        typed = {"text": text} if text else {}
        await self.send("Input.dispatchKeyEvent", {"type": "keyDown", **typed, **down})
        await self.send("Input.dispatchKeyEvent", {"type": "keyUp", **down})

    async def type(self, text: str, pause: float = 0.04) -> None:
        for letter in text:  # one at a time, so it reads as typed
            await self.send("Input.insertText", {"text": letter})
            await asyncio.sleep(pause)

    async def front(self) -> None:
        await self.send("Page.bringToFront")
        with contextlib.suppress(Exception):  # a page still loading may not answer yet
            await self.park()

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            await self.chrome.send("Target.closeTarget", {"targetId": self.target})

    async def screenshot(self, path: Path) -> None:
        shot = await self.send("Page.captureScreenshot", {"format": "png"})
        path.write_bytes(base64.b64decode(shot["data"]))


# Chrome on Windows listens on Windows' own loopback. Each connection to the local port this opens
# is piped through a PowerShell on the Windows side, which connects there: nothing is exposed.
BRIDGE = """$c = [Net.Sockets.TcpClient]::new('127.0.0.1', {port}); $c.NoDelay = $true
$s = $c.GetStream(); $i = [Console]::OpenStandardInput(); $o = [Console]::OpenStandardOutput()
[Threading.Tasks.Task]::WaitAny($i.CopyToAsync($s), $s.CopyToAsync($o)) | Out-Null"""


async def bridge(port: int) -> asyncio.Server:
    script = base64.b64encode(BRIDGE.format(port=port).encode("utf-16-le")).decode()

    async def pipe(source, sink) -> None:
        while data := await source.read(1 << 16):
            sink.write(data)
            await sink.drain()
        sink.close()

    async def serve(reader, writer) -> None:
        shell = await asyncio.create_subprocess_exec(
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-EncodedCommand",
            script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )
        await asyncio.gather(
            pipe(reader, shell.stdin), pipe(shell.stdout, writer), return_exceptions=True
        )
        with contextlib.suppress(ProcessLookupError):
            shell.kill()

    return await asyncio.start_server(serve, "127.0.0.1", 0)


def windows_chrome() -> tuple[int, str]:
    """Where the owner's Chrome takes a debugging connection: the file it writes when remote
    debugging is on."""
    local = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", "$env:LOCALAPPDATA"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    folder = subprocess.run(["wslpath", local], capture_output=True, text=True).stdout.strip()
    active = Path(folder) / "Google" / "Chrome" / "User Data" / "DevToolsActivePort"
    if not active.exists():
        sys.exit("Chrome: turn remote debugging on at chrome://inspect/#remote-debugging")
    port, path = active.read_text().split()[:2]
    return int(port), path


async def local_chromium(folder: Path) -> tuple[subprocess.Popen, str]:
    """A headless Chromium the size of the owner's screen (1536 by 864 at 125%), to test shots."""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        binary = pw.chromium.executable_path
    process = subprocess.Popen(
        [
            binary,
            "--headless=new",
            "--remote-debugging-port=0",
            f"--user-data-dir={folder}",
            "--window-size=1536,864",
            "--force-device-scale-factor=1.25",
            "--mute-audio",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    active = folder / "DevToolsActivePort"
    while not active.exists() or len(active.read_text().split()) < 2:
        await asyncio.sleep(0.2)
    port, path = active.read_text().split()[:2]
    return process, f"ws://127.0.0.1:{port}{path}"


# --- OBS, over obs-websocket 5 -------------------------------------------------------------


class Obs:
    """Just enough of obs-websocket 5 to record: sign in, ask, read replies."""

    def __init__(self, host: str, port: int, password: str) -> None:
        self.url, self.password = f"ws://{host}:{port}", password
        self.lock = asyncio.Lock()  # one request at a time: replies come back on one socket

    async def __aenter__(self):
        import websockets

        self.ws = await websockets.connect(self.url, open_timeout=5, max_size=None)
        hello = json.loads(await self.ws.recv())["d"]
        identify = {"rpcVersion": 1, "eventSubscriptions": 0}
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
        async with self.lock:
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

    async def screenshot(self, path: Path) -> None:
        scene = (await self.call("GetCurrentProgramScene"))["currentProgramSceneName"]
        image = {"sourceName": scene, "imageFormat": "png", "imageWidth": 1920}
        data = (await self.call("GetSourceScreenshot", image))["imageData"]
        path.write_bytes(base64.b64decode(data.split(",", 1)[1]))


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


async def stage(chrome: Chrome, *, headless: bool) -> tuple["Tab", int]:
    """The director's window, kept for every take: full screen, its first tab the site's navy.
    Chrome's "controlled by automated test software" bar shows even in full screen; the owner
    closes it once, and the page growing by its height says they have."""
    first = await chrome.send("Target.createTarget", {"url": BLANK, "newWindow": True})
    attached = {"targetId": first["targetId"], "flatten": True}
    blank = Tab(chrome, first["targetId"], "")
    blank.session = (await chrome.send("Target.attachToTarget", attached))["sessionId"]
    window = await blank.window()
    # full screen; headless has none, so there the owner's screen's size (1536 by 864 at 125%)
    bounds = {"width": 1536, "height": 864} if headless else {"windowState": "fullscreen"}
    await chrome.send("Browser.setWindowBounds", {"windowId": window, "bounds": bounds})
    await blank.front()
    if not headless:
        await asyncio.sleep(1)
        if await blank.evaluate("innerHeight < screen.height - 1"):
            print("Chrome: close the automated-test bar with its x, then hands off", flush=True)
            while await blank.evaluate("innerHeight < screen.height - 1"):
                await asyncio.sleep(0.5)
        print("Chrome: the director's window is ready", flush=True)
        await asyncio.sleep(3)
    return blank, window


async def take(
    chrome: Chrome,
    obs: Obs | None,
    blank: "Tab",
    window: int,
    *,
    record: bool,
    frames: Path | None,
) -> None:
    """One run of the shot list in the director's window; its tabs closed at the end."""
    plan = shots()
    await blank.front()
    tabs: dict[str, Tab] = {}
    opened: list[Tab] = []

    async def open_tab(s: Shot, *, background: bool = True) -> Tab:
        tab = await Tab.open(chrome, s.url, background=background, hide=s.hide)
        tabs[s.name] = tab
        opened.append(tab)
        if await tab.window() != window:
            print(f"\n  ! {s.name}: its tab opened in another Chrome window", flush=True)
        return tab

    async def act(s: Shot, offset: float, action: Action, tab: Tab) -> None:
        began = time.monotonic()
        try:
            await action(tab)
        except Exception as error:  # a missed click is noted, the take goes on
            print(f"\n  ! {s.name} {offset:+}s: {type(error).__name__} {error}", flush=True)
        if (took := time.monotonic() - began) > 2:
            print(f"\n  ! {s.name} {offset:+}s: took {took:.1f} s", flush=True)

    for s in plan:  # pages that only draw on screen: drawn before the clock starts
        if s.warm:
            tab = await open_tab(s, background=False)
            await tab.front()
            await asyncio.sleep(s.warm)
            for action in s.ready:
                await act(s, 0, action, tab)
    await blank.front()
    await asyncio.sleep(1)

    snaps: set[asyncio.Task] = set()
    started = time.monotonic() + max(s.preroll for s in plan if s.at == 0) + 1
    draw = prompter([(s.at, s.name, s.say) for s in plan], started)

    async def at(t: float) -> None:
        await asyncio.sleep(max(0.0, started + t - time.monotonic()))

    async def shot(s: Shot) -> None:
        if s.url and not s.warm:
            await at(s.at - s.preroll)
            await open_tab(s)
        else:  # warmed, or an earlier shot's tab: it is open by the time this one is due
            await at(s.at - 0.5)
        tab = tabs[s.tab or s.name]
        # real data before the cut: a page that hasn't drawn its content yet isn't brought front.
        # The wait can't hold the cut up (it lives inside the preroll), but it is logged if missed.
        if s.data:
            try:
                await tab.wait_for(s.data, timeout=max(0.5, started + s.at - time.monotonic() - 0.3))
            except TimeoutError:
                print(f"\n  ! {s.name}: no data for {s.data} at its cut", flush=True)
        # what happens before the cut runs on its own: a page slow to answer can't hold the cut up
        early = [asyncio.create_task(soon(s, o, a, tab)) for o, a in s.actions if o < 0]
        await at(s.at)
        await tab.front()
        if (late := time.monotonic() - started - s.at) > 0.3:
            print(f"\n  ! {s.name}: on screen {late:.1f} s late", flush=True)
        if frames:  # what each shot looks like two and six seconds in, to check a rehearsal
            snaps.update(asyncio.create_task(frame(tab, s, after)) for after in (2, 6))
        for offset, action in sorted(s.actions, key=lambda a: a[0]):
            if offset >= 0:
                await at(s.at + offset)
                await act(s, offset, action, tab)
        await asyncio.gather(*early)
        if s.close_after is not None:
            await at(s.at + s.close_after)
            await tab.close()

    async def soon(s: Shot, offset: float, action: Action, tab: Tab) -> None:
        await at(s.at + offset)
        await act(s, offset, action, tab)

    async def frame(tab: Tab, s: Shot, after: float) -> None:
        await at(s.at + after)
        name = f"{int(s.at + after):03d}-{s.name.replace(' ', '-').replace('²', '2')}.png"
        await (obs.screenshot(frames / name) if obs else tab.screenshot(frames / name))

    async def tick() -> None:
        while time.monotonic() < started + LENGTH:
            draw()
            await asyncio.sleep(0.25)

    async def recording() -> None:
        await at(-0.5)
        await obs.call("StartRecord")
        await at(LENGTH)
        saved = await obs.call("StopRecord")
        print(f"\n  recorded: {saved.get('outputPath', '(see OBS)')}", flush=True)

    jobs = [shot(s) for s in plan] + [tick()]
    if record:
        jobs.append(recording())
    try:
        await asyncio.gather(*jobs)
        await at(LENGTH + 1)
        await asyncio.gather(*snaps)
    finally:
        await blank.front()
        for tab in opened:
            await tab.close()


async def run(args: argparse.Namespace) -> int:
    import websockets

    wall = {k: v for k, v in through_the_wall().items() if k.startswith("CF-Access")}
    frames = Path(args.frames) if args.frames else None
    if frames:
        frames.mkdir(parents=True, exist_ok=True)
    obs = None
    if args.record or args.control or (frames and not args.headless):
        password = json.loads(OBS_SECRET.read_text())["password"]
        obs = await Obs(args.obs_host or windows_host(), 4455, password).__aenter__()
        print(f"OBS {(await obs.call('GetVersion'))['obsVersion']}: connected", flush=True)

    with tempfile.TemporaryDirectory() as folder:
        local = None
        if args.headless:
            local, url = await local_chromium(Path(folder))
        else:
            port, path = windows_chrome()
            server = await bridge(port)
            url = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}{path}"
            print("Chrome: click Allow on its remote debugging dialog", flush=True)
        try:
            async with websockets.connect(url, open_timeout=300, max_size=None) as ws:
                chrome = Chrome(ws, wall)
                version = (await chrome.send("Browser.getVersion"))["product"]
                print(f"{version}: connected", flush=True)
                blank, window = await stage(chrome, headless=args.headless)
                record = args.record
                while True:
                    await take(chrome, obs, blank, window, record=record, frames=frames)
                    if not args.control:
                        break
                    command = await next_take(Path(args.control))
                    if command == "quit":
                        break
                    record = command == "record"
                await blank.close()  # the last tab: the window goes with it
        finally:
            if obs:
                await obs.__aexit__()
            if local:
                local.terminate()
    return 0


async def next_take(control: Path) -> str:
    """Waits for the control file to say what's next (rehearse, record or quit), then clears it:
    a command written while a take runs waits for its end."""
    print(f"\n  waiting: write rehearse, record or quit to {control}", flush=True)
    while (command := control.read_text().strip()) not in ("rehearse", "record", "quit"):
        await asyncio.sleep(0.5)
    control.write_text("")
    print(f"\n  next: {command}", flush=True)
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--record", action="store_true", help="OBS records the video")
    parser.add_argument("--control", help="one connection, many takes: wait on this file")
    parser.add_argument("--obs-host", help="OBS's address (default: the Windows host)")
    parser.add_argument("--headless", action="store_true", help="a local Chromium: test shots")
    parser.add_argument(
        "--frames", help="save each shot as it looks two and six seconds in, to this folder"
    )
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
