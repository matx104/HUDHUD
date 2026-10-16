"""JSON Schema export: the cross-language artifact (web studio, overlay renderers)."""

import json
from pathlib import Path

from .models import STREAM_ADAPTER

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schema"
SCHEMA_FILE = "stream-message.schema.json"


def stream_schema() -> dict:
    schema = STREAM_ADAPTER.json_schema()
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "StreamMessage",
        "description": "One message of a synthetic match stream: match_meta first, then events "
        "ordered by seq. Coordinates are in the acting team's attacking frame.",
        **schema,
    }


def render() -> str:
    return json.dumps(stream_schema(), indent=2, sort_keys=True) + "\n"


def write(directory: Path = SCHEMA_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / SCHEMA_FILE
    path.write_text(render(), encoding="utf-8")
    return path
