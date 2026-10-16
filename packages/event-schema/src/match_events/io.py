"""JSONL stream format: one self-describing message per line, `match_meta` first."""

from collections.abc import Iterable
from pathlib import Path

from .models import STREAM_ADAPTER, StreamMessage


def to_jsonl(messages: Iterable[StreamMessage]) -> str:
    return "".join(STREAM_ADAPTER.dump_json(m).decode() + "\n" for m in messages)


def write_jsonl(path: Path, messages: Iterable[StreamMessage]) -> None:
    path.write_text(to_jsonl(messages), encoding="utf-8")


def read_jsonl(path: Path) -> list[StreamMessage]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [STREAM_ADAPTER.validate_json(line) for line in lines if line.strip()]
