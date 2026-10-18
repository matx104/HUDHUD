"""Redact Azure screenshots for the showcase site: cover every identifier, review, then publish.

Save screenshots of the Azure portal to proof/raw/ (git-ignored: originals stay on this machine).

    .venv/bin/python scripts/redact.py                  # redact everything into proof/review/
    .venv/bin/python scripts/redact.py --approve NAME   # after looking at proof/review/NAME.webp

Redaction: OCR reads every word, and each screen line is matched as a whole, with its spaces both
kept and squeezed out, so an ID split across words is still caught. Covered with solid boxes (never
blur: blurred text can be read back): GUIDs and their fragments, hex runs, email addresses and
anything with "@", guest-account markers, directory domains, IP addresses, the signed-in account's
own names (read from the project's Azure CLI at run time, never written in this file), any extra
terms in proof/raw/sensitive.txt, and any boxes in proof/raw/<name>.boxes.json as [[x, y, w, h]].

It fails closed. Redacted images wait in proof/review/ (git-ignored); only an image approved after
a look by eye is copied to site/assets/proof/ and listed in site/data/proof.js. OCR can miss text,
and a miss is a leak, so nothing reaches the site without that look.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys

from _azure import ROOT, az_json
from PIL import Image, ImageDraw

RAW = ROOT / "proof" / "raw"
REVIEW = ROOT / "proof" / "review"
OUT = ROOT / "site" / "assets" / "proof"
INDEX = ROOT / "site" / "data" / "proof.js"
APPROVED = RAW / "approved.json"
PATTERNS = [
    r"[0-9a-f]{4,}(?:-[0-9a-f]{2,})+",  # a GUID, or any dashed fragment of one
    r"[0-9a-f]{8,}",  # hex runs: object ids, keys
    r"@",  # email addresses and user principal names
    r"#ext#|onmicrosoft|gmail|outlook\.|hotmail",  # guest markers, directory domains
    r"\d{1,3}(?:\.\d{1,3}){3}",  # IP addresses
]
# OCR reads 0 as O and 1 as l now and then: match hex on the text with those read back.
CONFUSIONS = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1"})
PAD = 4
COVER = (24, 32, 40)


def account_terms() -> list[str]:
    """The signed-in account's names, from the project's CLI: never written into this file."""
    account = az_json("account", "show")
    user = account["user"]["name"].lower()
    terms = {user, *re.split(r"[@._-]", user)}
    if domain := account.get("tenantDefaultDomain"):
        terms |= {domain.lower(), domain.split(".")[0].lower()}
    extra = RAW / "sensitive.txt"
    if extra.exists():
        terms |= {t.strip().lower() for t in extra.read_text().splitlines() if t.strip()}
    common = {"com", "net", "org", "gmail", "outlook", "onmicrosoft", "hotmail"}
    return sorted(t for t in terms if len(t) >= 3 and t not in common)


def lines(image_path) -> list[list[tuple[str, tuple[int, int, int, int]]]]:
    """The words tesseract reads, grouped by screen line, each with its box."""
    tsv = subprocess.run(
        ["tesseract", str(image_path), "-", "--psm", "11", "tsv"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    grouped: dict[tuple[str, ...], list] = {}
    for row in tsv[1:]:
        cols = row.split("\t")
        if len(cols) == 12 and cols[11].strip():
            box = tuple(map(int, cols[6:10]))
            grouped.setdefault(tuple(cols[1:5]), []).append((cols[11].strip(), box))
    return list(grouped.values())


def sensitive_words(words, matchers) -> set[int]:
    """Indexes of the words that any match touches, on the line as read and squeezed together."""
    hits: set[int] = set()
    for joiner in (" ", ""):
        text, spans = "", []
        for word, _ in words:
            spans.append((len(text), len(text) + len(word)))
            text += word + joiner
        for candidate in (text, text.translate(CONFUSIONS)):
            for matcher in matchers:
                for m in matcher.finditer(candidate):
                    hits |= {i for i, (a, b) in enumerate(spans) if a < m.end() and m.start() < b}
    return hits


def redact(path, matchers) -> tuple[Image.Image, int]:
    image = Image.open(path).convert("RGB")
    big = REVIEW / f".{path.stem}.2x.png"  # OCR reads small portal text better at twice the size
    image.resize((image.width * 2, image.height * 2), Image.LANCZOS).save(big)
    boxes = []
    for words in lines(big):
        for i in sensitive_words(words, matchers):
            left, top, width, height = words[i][1]
            boxes.append((left // 2, top // 2, (left + width) // 2, (top + height) // 2))
    big.unlink()
    extra = path.with_suffix(".boxes.json")
    if extra.exists():
        boxes += [(x, y, x + w, y + h) for x, y, w, h in json.loads(extra.read_text())]
    draw = ImageDraw.Draw(image)
    for x0, y0, x1, y1 in boxes:
        draw.rectangle((x0 - PAD, y0 - PAD, x1 + PAD, y1 + PAD), fill=COVER)
    return image, len(boxes)


def publish() -> None:
    approved = json.loads(APPROVED.read_text()) if APPROVED.exists() else {}
    OUT.mkdir(parents=True, exist_ok=True)
    listed = []
    for name, caption in sorted(approved.items()):
        stem = name.rsplit(".", 1)[0]
        shutil.copy(REVIEW / f"{stem}.webp", OUT / f"{stem}.webp")
        listed.append(
            {
                "src": f"assets/proof/{stem}.webp",
                "caption": caption,
                "alt": f"Azure portal screenshot: {caption}, identifiers covered",
            }
        )
    header = "// Written by scripts/redact.py: redacted, reviewed Azure screenshots (#/control).\n"
    INDEX.write_text(f"{header}window.PROOF = {json.dumps(listed, indent=2)};\n")
    print(f"published {len(listed)} reviewed screenshots to {INDEX.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--approve", metavar="NAME", help="publish a reviewed screenshot")
    parser.add_argument("--caption", help="its caption on the site")
    args = parser.parse_args()
    if args.approve:
        stem = args.approve.rsplit(".", 1)[0]
        if not (REVIEW / f"{stem}.webp").exists():
            print(f"redact {args.approve} first: it isn't in {REVIEW.relative_to(ROOT)}/")
            return 1
        approved = json.loads(APPROVED.read_text()) if APPROVED.exists() else {}
        approved[args.approve] = (
            args.caption or stem.split("-", 1)[-1].replace("-", " ").capitalize()
        )
        APPROVED.write_text(json.dumps(approved, indent=2) + "\n")
        publish()
        return 0
    shots = sorted(p for p in RAW.glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
    if not shots:
        print(f"no screenshots in {RAW.relative_to(ROOT)}/: save the portal pages there first")
        return 1
    terms = [re.escape(t) for t in account_terms()]
    matchers = [re.compile(p, re.I) for p in [*PATTERNS, *terms]]
    REVIEW.mkdir(parents=True, exist_ok=True)
    for path in shots:
        image, covered = redact(path, matchers)
        image.save(REVIEW / f"{path.stem}.webp", "WEBP", quality=86)
        print(f"{path.name}: {covered} boxes -> {REVIEW.relative_to(ROOT)}/{path.stem}.webp")
    print("\nLook at each one by eye. Publish only what you've checked: --approve NAME")
    return 0


if __name__ == "__main__":
    sys.exit(main())
