"""Redact Azure screenshots for the showcase site: cover every identifier, then publish.

Save screenshots of the Azure portal to proof/raw/ (git-ignored: the originals never leave this
machine). For each one, OCR finds the words on screen, and anything that identifies the account is
covered with a solid box: IDs (GUIDs and long hex), email addresses, the directory's domain, IP
addresses, and any extra boxes listed in proof/raw/<name>.boxes.json as [[x, y, w, h], ...].
Solid boxes, never blur: blurred text can sometimes be read back. The results go to
site/assets/proof/ as WebP, and site/data/proof.js lists them with their captions
(proof/raw/captions.json maps a file name to its caption). Check every output by eye before
committing: OCR can miss text, and a miss is a leak.

    .venv/bin/python scripts/redact.py
"""

import json
import re
import subprocess
import sys

from _azure import ROOT
from PIL import Image, ImageDraw

RAW = ROOT / "proof" / "raw"
OUT = ROOT / "site" / "assets" / "proof"
INDEX = ROOT / "site" / "data" / "proof.js"
SENSITIVE = [
    re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}", re.I),  # a GUID, even cut short by the layout
    re.compile(r"\b[0-9a-f]{16,}\b", re.I),  # long hex: keys, object ids
    re.compile(r"@"),  # email addresses, user principal names
    re.compile(r"onmicrosoft|gmail|outlook\.com|hotmail", re.I),
    re.compile(r"\b\d{1,3}(\.\d{1,3}){3}\b"),  # IP addresses
    re.compile(r"REDACTED", re.I),  # the directory's name, built from the owner's email
]
PAD = 4
COVER = (24, 32, 40)


def words(image_path) -> list[tuple[str, tuple[int, int, int, int]]]:
    """Every word tesseract reads, with its box (left, top, width, height)."""
    tsv = subprocess.run(
        ["tesseract", str(image_path), "-", "--psm", "11", "tsv"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    found = []
    for line in tsv[1:]:
        cols = line.split("\t")
        if len(cols) == 12 and cols[11].strip():
            left, top, width, height = map(int, cols[6:10])
            found.append((cols[11].strip(), (left, top, width, height)))
    return found


def redact(path) -> tuple[Image.Image, list[str]]:
    image = Image.open(path).convert("RGB")
    # OCR reads small portal text better at twice the size.
    big = RAW / f".{path.stem}.2x.png"
    image.resize((image.width * 2, image.height * 2), Image.LANCZOS).save(big)
    covered, boxes = [], []
    for text, (left, top, width, height) in words(big):
        if any(p.search(text) for p in SENSITIVE):
            covered.append(text[:4] + "…")
            boxes.append((left // 2, top // 2, (left + width) // 2, (top + height) // 2))
    big.unlink()
    extra = path.with_suffix(".boxes.json")
    if extra.exists():
        for x, y, w, h in json.loads(extra.read_text()):
            boxes.append((x, y, x + w, y + h))
            covered.append("manual box")
    draw = ImageDraw.Draw(image)
    for x0, y0, x1, y1 in boxes:
        draw.rectangle((x0 - PAD, y0 - PAD, x1 + PAD, y1 + PAD), fill=COVER)
    return image, covered


def main() -> int:
    shots = sorted(p for p in RAW.glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
    if not shots:
        print(f"no screenshots in {RAW.relative_to(ROOT)}/: save the portal pages there first")
        return 1
    captions_file = RAW / "captions.json"
    captions = json.loads(captions_file.read_text()) if captions_file.exists() else {}
    OUT.mkdir(parents=True, exist_ok=True)
    listed = []
    for path in shots:
        image, covered = redact(path)
        target = OUT / f"{path.stem}.webp"
        image.save(target, "WEBP", quality=86)
        caption = captions.get(path.name) or path.stem.replace("-", " ").capitalize()
        listed.append(
            {
                "src": f"assets/proof/{target.name}",
                "caption": caption,
                "alt": f"Azure portal screenshot: {caption}, identifiers covered",
            }
        )
        print(f"{path.name}: covered {len(covered)} ({', '.join(covered) or 'nothing found'})")
    header = "// Written by scripts/redact.py: the redacted Azure screenshots (#/control).\n"
    INDEX.write_text(f"{header}window.PROOF = {json.dumps(listed, indent=2)};\n")
    print(f"\nwrote {len(listed)} to {OUT.relative_to(ROOT)}/ and {INDEX.relative_to(ROOT)}")
    print("Look at every one before you commit: OCR can miss text.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
