"""Finishes the demo video from the director's take (docs/video.md): the voiceover, read by Azure AI
Speech; the voiceover burned in as captions, for anyone watching with the sound off, each under a
title naming its shot; and the frames where Chrome hadn't yet drawn a tab just brought forward held
on the shot before, so no cut flashes empty.

The lines and their times come from the director's shot list, so the two can't drift. Each sentence
is spoken on its own, so its caption is on screen exactly while it's said. A shot's first sentence
starts just after its cut, or as soon as the sentence before ends; a shot that runs over is named.

The take's own sound is kept (the studio's Urdu and Arabic voices), turned down under the narration.
The narrator is a different voice from the studio's commentary, so the two never blur.
Speech signs in with the owner's Entra ID, as the studio does: no keys.

    .venv/bin/python scripts/video_post.py TAKE.mp4                     # dist/video/hudhud-demo.mp4
    .venv/bin/python scripts/video_post.py TAKE.mp4 --swap 86=AZURE.mp4  # a shot re-recorded alone
    .venv/bin/python scripts/video_post.py TAKE.mp4 --plan               # the timings, nothing made

OBS starts recording a moment after the director asks it to, and stops when asked: the take's
length says when it started (--start overrides it).
"""

import argparse
import hashlib
import re
import subprocess
import sys
import urllib.request
import wave
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from _azure import ROOT, az
from director import LENGTH, shots

WORK = ROOT / "dist" / "video"
VOICE = ("en-US", "en-US-AndrewMultilingualNeural")  # the narrator; the studio's own is en-GB-Ryan
REGION = "uaenorth"
LEAD = 0.4  # seconds after its cut a shot's first sentence starts
GAP = 0.3  # between sentences
FPS = 60
# Said differently from how it's written: the name is a word, not six letters.
SPOKEN = {"HUDHUD": "Hudhud", "HUD²": "HUD squared"}
# Each shot's title over its captions; where the captions sit, clear of what the shot shows.
TITLES = {
    "the site": "HUDHUD: AI commentary that proves every call",
    "the studio": "The studio, live on Azure Container Apps",
    "HUD², the referee": "HUD²: the referee's lens",
    "off air": "The narrator, taken off air",
    "Urdu": "Urdu, on screen and spoken",
    "Arabic": "Arabic, on screen and spoken",
    "ask the match": "Ask the match: checked, sealed, verified in your browser",
    "Azure": "The control room on Azure",
    "every model call": "Every model call, traced",
    "the ledger": "The match ledger, checked in your browser",
    "the team sheet": "hudhud.com.pk",
}
TOP: set[str] = set()  # shots whose captions sit at the top, clear of what's at the bottom


@dataclass
class Line:
    shot: str
    text: str
    audio: Path
    seconds: float
    start: float = 0.0  # on the director's clock


# --- the voice ------------------------------------------------------------------------------


def speech_token() -> str:
    resource = az(
        "containerapp",
        "show",
        "-n",
        "hudhud-studio",
        "-g",
        "rg-hudhud",
        "--query",
        "properties.template.containers[0].env[?name=='SPEECH_RESOURCE_ID'].value | [0]",
        "-o",
        "tsv",
    )
    token = az(
        "account",
        "get-access-token",
        "--resource",
        "https://cognitiveservices.azure.com",
        "--query",
        "accessToken",
        "-o",
        "tsv",
    )
    return f"aad#{resource}#{token}"


def speak(text: str, token: str | None) -> Path:
    """One sentence as WAV, kept by its text: a re-run doesn't pay for it twice."""
    for written, said in SPOKEN.items():
        text = text.replace(written, said)
    locale, voice = VOICE
    ssml = (
        f"<speak version='1.0' xml:lang='{locale}'><voice name='{voice}'>"
        f"<prosody rate='+4%'>{escape(text)}</prosody></voice></speak>"
    )
    path = WORK / "voice" / f"{hashlib.sha256(ssml.encode()).hexdigest()[:16]}.wav"
    if path.exists():
        return path
    if token is None:
        raise SystemExit("the voice isn't made yet: run without --plan once")
    request = urllib.request.Request(
        f"https://{REGION}.tts.speech.microsoft.com/cognitiveservices/v1",
        data=ssml.encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "riff-48khz-16bit-mono-pcm",
            "User-Agent": "hudhud-video",
        },
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(request, timeout=60) as response:
        path.write_bytes(response.read())
    return path


def seconds(path: Path) -> float:
    with wave.open(str(path)) as audio:
        return audio.getnframes() / audio.getframerate()


def narration(token: str | None, start: float) -> list[Line]:
    """Every sentence, spoken and placed: on its shot's cut, or after the sentence before; none
    before the recording began."""
    lines, free = [], start
    for shot in shots():
        for i, text in enumerate(re.split(r"(?<=[.!?])\s+", shot.say) if shot.say else []):
            audio = speak(text, token)
            line = Line(shot.name, text, audio, seconds(audio))
            line.start = max(shot.at + LEAD if i == 0 else 0.0, free + GAP)
            free = line.start + line.seconds
            lines.append(line)
    return lines


def report(lines: list[Line]) -> None:
    # where each shot's narration should end: the next shot with a line of its own
    plan = shots()
    after = {
        s.name: next((n.at for n in plan[i + 1 :] if n.say), LENGTH) for i, s in enumerate(plan)
    }
    for line in lines:
        end = line.start + line.seconds
        over = end - after.get(line.shot, LENGTH)
        flag = f"  runs {over:.1f} s into the next shot" if over > 0 else ""
        print(f"  {line.start:6.1f}-{end:6.1f}  [{line.shot}] {line.text[:64]}{flag}")
        if end > LENGTH:
            print(f"  ! ends at {end:.1f} s, after the video's {LENGTH:.0f}")


# --- the picture ----------------------------------------------------------------------------

CARD = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@800&family=Hanken+Grotesk:wght@500&display=block">
<style>
  html, body {{ margin: 0; width: 1920px; height: 1080px; background: transparent; }}
  .card {{ position: absolute; left: 50%; transform: translateX(-50%); {place}
    max-width: 1380px; box-sizing: border-box; padding: 18px 34px 22px;
    background: rgba(6, 20, 31, 0.88); border: 1px solid rgba(184, 245, 61, 0.35);
    border-left: 6px solid #B8F53D; border-radius: 14px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.45); }}
  .title {{ font: 800 30px/1.1 "Big Shoulders Display", sans-serif; color: #B8F53D;
    letter-spacing: 0.01em; margin: 0 0 8px; }}
  .say {{ font: 500 38px/1.3 "Hanken Grotesk", sans-serif; color: #F4F1E8; margin: 0;
    text-wrap: balance; }}
</style></head><body><div class="card"><p class="title">{title}</p><p class="say">{say}</p></div>
</body></html>"""


async def cards(lines: list[Line]) -> list[Path]:
    """Each caption as a transparent frame-sized image, the shot's title above it."""
    from playwright.async_api import async_playwright

    out = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        for i, line in enumerate(lines):
            place = "top: 132px;" if line.shot in TOP else "bottom: 112px;"
            html = CARD.format(place=place, title=escape(TITLES[line.shot]), say=escape(line.text))
            await page.set_content(html, wait_until="networkidle")
            await page.evaluate("document.fonts.ready")
            path = WORK / "cards" / f"{i:02d}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(path), omit_background=True)
            out.append(path)
        await browser.close()
    return out


def blanks(take: Path) -> list[tuple[int, int]]:
    """The frames where a tab just brought forward hadn't drawn yet: one flat colour, edge to
    edge. Each run is held on the frame before it."""
    probe = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(take),
            "-vf",
            "scale=192:108,signalstats,metadata=print:file=-",
            "-an",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    frames: dict[int, dict[str, float]] = {}
    frame = 0
    for row in probe.splitlines():
        if row.startswith("frame:"):
            frame = int(row.split()[0].split(":")[1])
        elif "=" in row:
            key, value = row.rsplit("=", 1)
            frames.setdefault(frame, {})[key.rsplit(".", 1)[1]] = float(value)
    flat = sorted(n for n, s in frames.items() if s.get("YMAX", 255) - s.get("YMIN", 0) < 6)
    runs: list[tuple[int, int]] = []
    for n in flat:
        if runs and n == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], n)
        else:
            runs.append((n, n))
    return [(a, b) for a, b in runs if a > 0]


# --- the cut --------------------------------------------------------------------------------


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout)


def render(
    take: Path, start: float, lines: list[Line], images: list[Path], out: Path, swaps: dict
) -> None:
    inputs = ["-i", str(take)]
    video = "[0:v]"
    chain = []
    held = blanks(take)
    if held:  # the undrawn frames dropped; fps fills each gap with the frame before it
        dropped = "+".join(f"between(n,{a},{b})" for a, b in held)
        chain.append(f"{video}select='not({dropped})',fps={FPS}[held]")
        video = "[held]"
    print(
        f"  held {len(held)} undrawn moments: {[(round(a / FPS, 2), b - a + 1) for a, b in held]}"
    )
    count = 1
    plan = shots()
    for at, segment in swaps.items():  # a shot re-recorded alone, laid over the take
        nxt = next(s.at for s in plan if s.at > at)
        inputs += ["-i", str(segment)]
        chain.append(f"[{count}:v]trim=0:{nxt - at},setpts=PTS-STARTPTS+{at - start}/TB[s{count}]")
        chain.append(f"{video}[s{count}]overlay=0:0:eof_action=pass[w{count}]")
        video = f"[w{count}]"
        count += 1
    for line, image in zip(lines, images, strict=True):
        shown = line.seconds + 0.25
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{shown:.3f}", "-i", str(image)]
        chain.append(
            f"[{count}:v]format=rgba,fade=t=in:st=0:d=0.2:alpha=1,"
            f"fade=t=out:st={shown - 0.2:.3f}:d=0.2:alpha=1,"
            f"setpts=PTS-STARTPTS+{line.start - start:.3f}/TB[c{count}]"
        )
        chain.append(f"{video}[c{count}]overlay=0:0:eof_action=pass[v{count}]")
        video = f"[v{count}]"
        count += 1
    voices = []
    for line in lines:
        inputs += ["-i", str(line.audio)]
        delay = round((line.start - start) * 1000)
        chain.append(f"[{count}:a]volume=2.2,aformat=channel_layouts=stereo,adelay={delay}|{delay}[a{count}]")
        voices.append(f"[a{count}]")
        count += 1
    chain.append(f"{''.join(voices)}amix=inputs={len(voices)}:normalize=0,asplit[vo][key]")
    # the take's own sound, gentler and turned down while the narrator speaks: the studio's
    # Urdu and Arabic lines must duck, not vanish mid-sentence
    chain.append(
        "[0:a]volume=0.6[desk];"
        "[desk][key]sidechaincompress=threshold=0.03:ratio=6:attack=25:release=650[room]"
    )
    chain.append("[room][vo]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[mix]")
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(chain),
            "-map",
            video,
            "-map",
            "[mix]",
            "-t",
            f"{duration(take):.3f}",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "medium",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            str(out),
        ],
        check=True,
    )


def main() -> int:
    import asyncio

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("take", type=Path, help="the director's recording")
    parser.add_argument("-o", "--out", type=Path, default=WORK / "hudhud-demo.mp4")
    parser.add_argument("--start", type=float, help="the director's clock when OBS began")
    parser.add_argument("--swap", action="append", default=[], help="AT=FILE: a shot re-shot")
    parser.add_argument("--plan", action="store_true", help="print the timings only")
    args = parser.parse_args()
    start = args.start if args.start is not None else LENGTH - duration(args.take)
    print(f"the take began at {start:.2f} s on the director's clock")
    lines = narration(None if args.plan else speech_token(), start)
    report(lines)
    if args.plan:
        return 0
    swaps = {float(a): Path(f) for a, f in (s.split("=", 1) for s in args.swap)}
    images = asyncio.run(cards(lines))
    render(args.take, start, lines, images, args.out, swaps)
    print(f"made {args.out} ({duration(args.out):.1f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
