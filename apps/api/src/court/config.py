"""The one place user-visible identity lives.

The product name is undecided (see project-names.md). Every surface reads it from
here, so naming day is a one-line change, never a search-and-replace.
"""

import os

DEFAULT_PRODUCT_NAME = "pl-hackathon"  # placeholder until the name is chosen
ARCHITECTURE_NAME = "Match Intelligence Court"


def product_name() -> str:
    return os.environ.get("PRODUCT_NAME", DEFAULT_PRODUCT_NAME)
