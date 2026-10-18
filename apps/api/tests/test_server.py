"""The studio streams a match with every agent's work, and its controls do what they say."""

import json

import pytest
from fastapi.testclient import TestClient

from court.contracts import Cue, Degradation
from court.narrator import TemplateNarrator
from court.orchestrator import run_match
from court.server import ModelBudget, OffAir, Switchable, create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
    return TestClient(create_app())


def _events(client, query: str) -> list[tuple[str, dict]]:
    events, kind = [], None
    with client.stream("GET", f"/api/stream?{query}") as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.startswith("event: "):
                kind = line.removeprefix("event: ")
            elif line.startswith("data: "):
                events.append((kind, json.loads(line.removeprefix("data: "))))
    return events


def test_the_studio_lists_its_matches(client):
    config = client.get("/api/config").json()
    assert [m["seed"] for m in config["matches"]] == [21, 7, 33]
    assert config["models"] is False
    assert client.get("/healthz").json() == {"status": "ok"}


def test_a_match_streams_clock_shots_and_every_output_with_receipts(client):
    events = _events(client, "seed=21&speed=0&stress=0.25")
    kinds = [k for k, _ in events]
    assert kinds[0] == "hello" and kinds[-1] == "end"
    assert "clock" in kinds and "shot" in kinds
    outputs = [d for k, d in events if k == "output"]
    cues = [o for o in outputs if o["type"] == "cue"]
    assert cues and all(c["receipt"]["writer"] == "template" for c in cues)
    assert any(o["type"] == "rejection" for o in outputs), "the stress test makes the Critic work"
    end = events[-1][1]
    assert end["stats"]["aired"] == len(cues)
    last_clock = [d for k, d in events if k == "clock"][-1]
    assert sum(last_clock["score"]) == sum(
        1 for k, d in events if k == "shot" and d["outcome"] == "goal"
    )


def test_asking_for_models_where_there_are_none_says_so(client):
    hello = _events(client, "seed=7&speed=0&narration=foundry")[0][1]
    assert hello["narration"] == "template"
    assert "no models are connected here" in hello["notices"][0]


def test_unknown_matches_and_sessions_are_refused(client):
    assert client.get("/api/stream?seed=999").status_code == 404
    assert client.post("/api/sessions/nope/air?on=false").status_code == 404


async def test_off_air_the_broadcast_degrades_and_says_so(swing_match):
    narrator = Switchable(TemplateNarrator())
    narrator.on_air = False
    with pytest.raises(OffAir):
        await narrator.draft(None, None)
    outputs = []
    await run_match(list(swing_match.stream()), sink=outputs.append, narrator=narrator)
    cues = [o for o in outputs if isinstance(o, Cue)]
    assert cues and all(c.status == "detection_only" for c in cues)
    assert any(isinstance(o, Degradation) for o in outputs)


def test_the_model_budget_resets_daily_and_runs_out():
    budget = ModelBudget(2)
    assert [budget.take() for _ in range(3)] == [True, True, False]
    assert budget.left == 0


def test_joining_late_narrates_only_what_comes_after(client):
    events = _events(client, "seed=21&speed=0&start=54&stress=0")
    cues = [d for k, d in events if k == "output" and d["type"] == "cue"]
    assert cues and all(c["t"] >= 54 * 60 for c in cues)
    assert events[-1][1]["stats"]["alerts_before_joining"] > 0


def test_a_finished_stream_leaves_no_session_behind(client):
    _events(client, "seed=7&speed=0")
    assert client.app.state.sessions == {}


def test_a_server_error_reaches_the_page_without_its_details(client, monkeypatch):
    async def broken(*args, **kwargs):
        raise RuntimeError("internal detail that must stay on the server")

    monkeypatch.setattr("court.server.run_match", broken)
    kind, data = _events(client, "seed=21&speed=0")[-1]
    assert kind == "error" and data["detail"] == "the match stopped on a server error"
    assert "internal detail" not in json.dumps(data) and len(data["ref"]) == 8
    assert client.app.state.sessions == {}


def test_a_full_studio_turns_new_streams_away(client, monkeypatch):
    monkeypatch.setattr("court.server.MAX_STREAMS", 0)
    assert client.get("/api/stream?seed=21&speed=0").status_code == 503
