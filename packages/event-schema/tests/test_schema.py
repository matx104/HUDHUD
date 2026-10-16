from match_events import schema


def test_committed_json_schema_is_current():
    """The JSON Schema is the cross-language contract; regenerate with
    `python -m match_events schema` whenever models.py changes."""
    committed = (schema.SCHEMA_DIR / schema.SCHEMA_FILE).read_text(encoding="utf-8")
    assert committed == schema.render()


def test_schema_covers_every_message_type():
    mapping = schema.stream_schema()["discriminator"]["mapping"]
    assert set(mapping) == {
        "match_meta",
        "pass",
        "shot",
        "tackle",
        "possession_change",
        "pressure",
        "period_start",
        "period_end",
    }
