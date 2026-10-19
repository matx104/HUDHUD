"""The social card link previews show (site/assets/og.png), printed from kit/social-card.html.

    .venv/bin/python scripts/social_card.py                    # from site/config.js, into the site
    .venv/bin/python scripts/social_card.py --out card.png     # somewhere else, to look first

The card carries the site's address, so rerun it whenever siteUrl changes. Needs Playwright and
Chromium, as scripts/drive_kit.py does.
"""

import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from _azure import ROOT, SITE_URL

TEMPLATE = ROOT / "kit" / "social-card.html"
CARD = ROOT / "site" / "assets" / "og.png"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=CARD, help="where to write the PNG")
    parser.add_argument("--host", help="the address to print (default: siteUrl, bare)")
    args = parser.parse_args()
    config = (ROOT / "site" / "config.js").read_text()
    fields = {
        "name": re.search(r'productName: "([^"]+)"', config)[1],
        "host": args.host or re.sub(r"^https?://|/$", "", SITE_URL),
    }
    from playwright.sync_api import sync_playwright

    chromium = os.environ.get("CHROMIUM") or shutil.which("chromium") or shutil.which("chrome")
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
        page_path = Path(tmp) / TEMPLATE.name
        html = re.sub(r"\{\{(\w+)\}\}", lambda m: fields[m[1]], TEMPLATE.read_text())
        page_path.write_text(html)
        browser = p.chromium.launch(executable_path=chromium)
        page = browser.new_page(viewport={"width": 1200, "height": 630})
        page.goto(page_path.as_uri(), wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        page.locator(".card").screenshot(path=str(args.out))
        browser.close()
    print(f"wrote {args.out}: {fields['host']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
