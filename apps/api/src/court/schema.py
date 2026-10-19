"""The court's output as JSON Schema: the contract a broadcaster's graphics team builds against.

Every message the court puts on its stream (a cue to draw, a claim the Critic refused, a story
spiked, a change of service level) validates against apps/api/schema/output.schema.json, written
from the same Pydantic models the court runs on. CI regenerates it and fails if it drifts.

    python -m court schema
"""

import json
from pathlib import Path

from .contracts import OUTPUT_ADAPTER

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schema"
SCHEMA_FILE = "output.schema.json"


def render() -> str:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Output",
        "description": "One message of the court's output stream, told apart by `type`: a cue "
        "for the overlay (timed, prioritised, with its evidence and receipt), a claim the Critic "
        "refused and why, a story spiked, or a change of service level.",
        **OUTPUT_ADAPTER.json_schema(),
    }
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def write(directory: Path = SCHEMA_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / SCHEMA_FILE
    path.write_text(render(), encoding="utf-8")
    return path
