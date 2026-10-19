"""The one place user-visible identity lives.

The product name was chosen on 2026-10-17 (see brand.md). Every surface reads it from
here, so a rename is a one-line change, never a search-and-replace.
"""

import os

DEFAULT_PRODUCT_NAME = "HUDHUD"
DEFAULT_PRODUCT_MARK = "HUD²"  # the short form: monogram, app icon, and the heads-up display
ARCHITECTURE_NAME = "Match Intelligence Court"


def product_name() -> str:
    return os.environ.get("PRODUCT_NAME", DEFAULT_PRODUCT_NAME)


def product_mark() -> str:
    return os.environ.get("PRODUCT_MARK", DEFAULT_PRODUCT_MARK)
