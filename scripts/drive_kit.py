"""The public media kit on Google Drive: the demo video, the Azure proof and the brand.

    .venv/bin/python scripts/drive_kit.py                   # build, sync, print the folder's link
    .venv/bin/python scripts/drive_kit.py --build           # build dist/kit/ only, to look first
    .venv/bin/python scripts/drive_kit.py --video demo.mp4  # put the recording in "1 Demo video"

It carries nothing the public site doesn't already show: the crest, icons and social card from
site/assets/, the screenshots approved for the site (scripts/redact.py --approve), the sample recap
(site/recap/, as a page and a PDF), the video's thumbnail and two PDFs, all printed from kit/.
The folder is shared as "anyone with the link can view". rclone does the Drive work through the
remote in DRIVE_REMOTE (default personal-drive:). It only ever copies, never deletes, so a file
added to the folder by hand stays put. The PDFs need Playwright and Chromium.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from _azure import ROOT
from PIL import Image

REMOTE = os.environ.get("DRIVE_REMOTE", "personal-drive:")
CONFIG = ROOT / "site" / "config.js"
ASSETS = ROOT / "site" / "assets"
PROOF_INDEX = ROOT / "site" / "data" / "proof.js"
KIT = ROOT / "kit"
OUT = ROOT / "dist" / "kit"
# Drive's folder palette has no navy: these are its nearest to the brand's lime and gold.
LIME, GOLD = "#b3dc6c", "#fad165"
VIDEO, SHOTS, BRAND, SAMPLE = "1 Demo video", "2 Azure screenshots", "3 Brand kit", "4 Sample match"
RECAP = ROOT / "site" / "recap" / "seed-21.html"  # scripts/site_sample.py


def site() -> dict:
    """The site's identity, from the one config it comes from."""
    text = CONFIG.read_text()
    found = dict(re.findall(r'^\s*(\w+): "([^"]*)"', text, re.M))
    found["repoPublic"] = re.search(r"^\s*repoPublic: true", text, re.M) is not None
    return found


def folders(name: str) -> dict[str, tuple[str, str]]:
    about = (
        f"{name}: AI football commentary that shows its working. Five AI agents commentate a "
        "synthetic match, and a Critic checks every claim against the match events before it "
        "airs. Built for Inside the Game: Developer Hackathon, October 2026: an independent "
        "entry. Every club, player and match is invented."
    )
    return {
        "": (LIME, about),
        VIDEO: (
            LIME,
            "The 110-second demo: the live studio on Azure, the Critic refusing a claim it can't "
            "prove, the broadcast recovering, and the same match in Urdu and Arabic.",
        ),
        SHOTS: (
            GOLD,
            "The Azure side as it looks in the portal. Account names, email addresses and "
            "identifiers are covered with solid boxes.",
        ),
        BRAND: (
            LIME,
            f"{name}'s crest, icons, social card, the video's thumbnail and the brand sheet. The "
            "type is under the SIL Open Font License.",
        ),
        SAMPLE: (
            GOLD,
            "One match's recap as the studio writes it at full time: synthetic match seed 21, as a "
            "page and a PDF. Every line it wrote was checked by the Critic before it went in.",
        ),
    }


def rclone(*args: str) -> str:
    done = subprocess.run(["rclone", *args], capture_output=True, text=True)
    if done.returncode:
        sys.exit(f"rclone {args[0]} failed: {done.stderr.strip()}")
    return done.stdout.strip()


def dress(top: str, path: str, color: str, description: str) -> None:
    """Create a folder, or update it, with its colour and description.

    rclone writes a folder's metadata only when the folder is part of the copy, not when it's
    the destination itself, so each one is copied in as an empty folder under its parent.
    """
    parent, _, leaf = f"{top}/{path}".rstrip("/").rpartition("/")
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / leaf).mkdir()
        meta = [f"folder-color-rgb={color}", f"description={description}"]
        sets = [arg for m in meta for arg in ("--metadata-set", m)]
        rclone("copy", tmp, REMOTE + parent, "--create-empty-src-dirs", "-M", *sets)


def share(path: str, *, folder: bool) -> str:
    """Anyone with the link can view: the link Drive gives, in the form its pages use."""
    link = rclone("link", REMOTE + path)
    item = re.search(r"id=([\w-]+)", link)
    if not item:
        return link
    if folder:
        return f"https://drive.google.com/drive/folders/{item[1]}"
    return f"https://drive.google.com/file/d/{item[1]}/view"


def approved_shots() -> list[tuple[str, str]]:
    """(image, caption) for each screenshot redact.py has published to the site."""
    if not PROOF_INDEX.exists():
        return []
    text = PROOF_INDEX.read_text()
    return re.findall(r'"src": "([^"]+)",\s*"caption": "([^"]+)"', text)


def render(fields: dict[str, str], jobs: list[tuple[str | Path, Path]]) -> None:
    """Prints each job: a kit/ template (its {{fields}} filled) or a finished page, to a PDF, or
    for a .png target, a picture of the template's .card at the card's own size."""
    from playwright.sync_api import sync_playwright

    chromium = os.environ.get("CHROMIUM") or shutil.which("chromium") or shutil.which("chrome")
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
        shutil.copy(KIT / "kit.css", tmp)
        browser = p.chromium.launch(executable_path=chromium)
        for source, target in jobs:
            if isinstance(source, Path):
                page_path = source
            else:
                page_path = Path(tmp) / source
                html = (KIT / source).read_text()
                page_path.write_text(re.sub(r"\{\{(\w+)\}\}", lambda m: fields[m[1]], html))
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(page_path.as_uri(), wait_until="networkidle")
            page.evaluate("document.fonts.ready")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.suffix == ".png":
                page.locator(".card").screenshot(path=str(target))
            else:
                page.pdf(path=str(target), prefer_css_page_size=True, print_background=True)
            page.close()
        browser.close()


def build(info: dict, folder_url: str) -> None:
    name, mark = info["productName"], info.get("productMark", info["productName"])
    shutil.rmtree(OUT, ignore_errors=True)
    for sub in (VIDEO, SHOTS, BRAND, SAMPLE):
        (OUT / sub).mkdir(parents=True)
    shutil.copy(ASSETS / "og.png", OUT / f"{name} cover.png")
    for source, target in [
        ("crest.svg", "crest.svg"),
        ("icon-512.png", "crest-512.png"),
        ("icon-192.png", "crest-192.png"),
        ("apple-touch-icon.png", "crest-180.png"),
        ("og.png", "social-card-1200x630.png"),
    ]:
        shutil.copy(ASSETS / source, OUT / BRAND / target)
    for i, (src, _caption) in enumerate(approved_shots(), 1):
        # Named from the image ("2-control-room-workbook" -> "2 Control room workbook.png"); the
        # captions stay on the site. The site serves WebP; PNG pastes into a post or a slide.
        label = Path(src).stem.split("-", 1)[-1].replace("-", " ").capitalize()
        Image.open(ROOT / "site" / src).save(OUT / SHOTS / f"{i} {label}.png")
    shutil.copy(RECAP, OUT / SAMPLE / "Recap, seed 21.html")
    repo = info["repoUrl"] if info["repoPublic"] else f"{info['repoUrl']} (public from October 27)"
    fields = {
        "name": name,
        "mark": mark,
        "site": info["siteUrl"],
        "studio": info.get("studioUrl", ""),
        "folder": folder_url,
        "repo": repo,
        "repo_url": info["repoUrl"],
        "date": date.today().strftime("%-d %B %Y"),
    }
    render(
        fields,
        [
            ("read-me.html", OUT / "Read me.pdf"),
            ("brand-sheet.html", OUT / BRAND / "Brand sheet.pdf"),
            ("thumbnail.html", OUT / BRAND / "video-thumbnail-1280x720.png"),
            (RECAP, OUT / SAMPLE / "Recap, seed 21.pdf"),
        ],
    )
    files = sorted(p.relative_to(OUT) for p in OUT.rglob("*") if p.is_file())
    print(f"built {OUT.relative_to(ROOT)}/: {len(files)} files")
    for f in files:
        print(f"  {f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--build", action="store_true", help="build dist/kit/ only; Drive untouched"
    )
    parser.add_argument(
        "--video", type=Path, help="upload the demo recording into the video folder"
    )
    args = parser.parse_args()
    info = site()
    top = info["productName"]

    if args.video:
        target = f"{top}/{VIDEO}/{top} demo{args.video.suffix.lower()}"
        rclone("copyto", str(args.video), REMOTE + target, "--progress")
        print(f"the video, viewable by anyone with the link: {share(target, folder=False)}")
        return 0

    if args.build:
        # A folder's own listing doesn't carry its ID; its parent's does. Nothing is shared here.
        listing = ["lsjson", "--dirs-only", "--max-depth", "1", REMOTE, "--include", f"/{top}/"]
        found = re.search(
            rb'"ID": ?"([\w-]+)"', subprocess.run(["rclone", *listing], capture_output=True).stdout
        )
        url = (
            f"https://drive.google.com/drive/folders/{found[1].decode()}" if found else "(none yet)"
        )
        build(info, url)
        return 0

    for path, (color, description) in folders(top).items():
        dress(top, path, color, description)
    link = share(top, folder=True)
    build(info, link)
    rclone("copy", str(OUT), REMOTE + top, "--checksum")
    print(f"\nsynced to Drive. The folder, viewable by anyone with the link:\n{link}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
