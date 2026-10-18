"""Does every link on the showcase site and in the README still answer? Read-only.

Some sites refuse automated requests (LinkedIn, X): those are reported as "refuses bots", not as
broken. Run it before sharing the site and before submitting.

    make links
"""

import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from _azure import ROOT

SOURCES = [ROOT / "site" / "index.html", ROOT / "README.md", ROOT / "site" / "config.js"]
LINK = re.compile(r"https?://[^\s\"'<>)\]]+")
BOT_SHY = ("linkedin.com", "x.com", "twitter.com", "topmate.io", "medium.com", "youtube.com/watch")
# The repository is private until the entry is submitted (site/config.js repoPublic).
PRIVATE_FOR_NOW = ("github.com/matx104/HUDHUD",)


def probe(url: str) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (link check)"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return url, f"{response.status}"
    except urllib.error.HTTPError as error:
        return url, f"{error.code}"
    except Exception as error:  # DNS, TLS, timeout: all count as broken
        return url, type(error).__name__


def main() -> int:
    urls = sorted({u.rstrip(".,;") for path in SOURCES for u in LINK.findall(path.read_text())})
    skip = ("fonts.g", "schema.org", "w3.org", "localhost", "127.0.0.1")
    urls = [u for u in urls if not any(part in u for part in skip)]
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(probe, urls))
    broken = 0
    for url, status in results:
        ok = status.startswith(("2", "3"))
        shy = not ok and any(host in url for host in BOT_SHY)
        private = not ok and url.rstrip("/").endswith(PRIVATE_FOR_NOW)
        broken += not ok and not shy and not private
        mark = "✔" if ok else "!" if shy or private else "✘"
        note = " (refuses bots: check by hand)" if shy else ""
        note = " (private until submission)" if private else note
        print(f" {mark} {status:>5}  {url}{note}")
    print(f"\n{len(results)} links, {broken} broken")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
