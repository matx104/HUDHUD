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


def test_behind_the_wall_only_what_access_signed_gets_in(monkeypatch):
    import time

    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    from court.server import AccessOnly

    access = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    impostor = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class Keys:  # stands in for the team's published keys: one, "k1"
        def cached(self, kid):
            return access.public_key() if kid == "k1" else None

        get = cached

    def token(key=access, aud="studio-aud", iss="https://team.example", ttl=60, kid="k1"):
        claims = {"aud": aud, "iss": iss, "exp": int(time.time()) + ttl}
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})

    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
    app = create_app()
    app.add_middleware(AccessOnly, team="team.example", audience="studio-aud", keys=Keys())
    client = TestClient(app)

    def status(path, **claims):
        return client.get(path, headers={"Cf-Access-Jwt-Assertion": token(**claims)}).status_code

    assert client.get("/healthz").status_code == 200, "the probes call it directly"
    for path in ("/", "/api/config", "/static/studio.js", "/mcp/"):
        assert client.get(path).status_code == 403, path
    assert status("/api/config") == 200
    assert status("/api/config", key=impostor) == 403, "signed by someone else"
    assert status("/api/config", aud="another-app") == 403, "signed for another app"
    assert status("/api/config", iss="https://other.example") == 403, "another team's"
    assert status("/api/config", ttl=-120) == 403, "expired"
    assert status("/api/config", kid="k2") == 403, "a key Access never published"
    unsigned = jwt.encode({"aud": "studio-aud", "iss": "https://team.example"}, None, "none")
    assert client.get("/", headers={"Cf-Access-Jwt-Assertion": unsigned}).status_code == 403


def test_made_up_key_ids_cant_turn_requests_into_fetches(monkeypatch):
    from court.server import AccessKeys

    keys, fetches = AccessKeys("https://team.example/certs", cooldown_s=300), []
    monkeypatch.setattr(keys, "_fetch", lambda: fetches.append(1) or {"k1": "key"})
    assert keys.get("k1") == "key" and len(fetches) == 1
    assert [keys.get(f"made-up-{i}") for i in range(50)] == [None] * 50
    assert len(fetches) == 1, "one refresh per cooldown, however many unknown ids arrive"
    assert keys.get("k1") == "key"


def test_the_wall_goes_up_only_when_configured(monkeypatch):
    monkeypatch.setenv("ACCESS_TEAM", "team.example")
    monkeypatch.setenv("ACCESS_AUD", "studio-aud")
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
    assert TestClient(create_app()).get("/api/config").status_code == 403
    monkeypatch.delenv("ACCESS_AUD")
    assert TestClient(create_app()).get("/api/config").status_code == 200


def test_personal_modes_ride_in_the_address(client):
    config = client.get("/api/config").json()
    players = config["matches"][0]["players"]
    assert len(players) == 22 and {"id", "name", "number", "position", "team"} <= set(players[0])
    forward = next(p for p in players if p["position"] == "FW" and p["team"] == "home")
    query = f"seed=21&speed=0&stress=0&club=home&player={forward['id']}&focus=player&metric=xg"
    events = _events(client, query)
    hello = events[0][1]
    assert hello["prefs"] == {
        "club": "home",
        "player": forward["id"],
        "focus": "player",
        "metric": "xg",
    }
    personal = [d for k, d in events if k == "personal"]
    assert personal and personal[-1]["card"]["player"]["id"] == forward["id"]
    assert personal[-1]["metric"]["label"] == "Expected goals (xG)"
    cues = [d for k, d in events if k == "output" and d["type"] == "cue"]
    assert all("player" in c["for_you"] and "club" in c["for_you"] for c in cues)
    assert events[-1][1]["hidden_by_focus"] > 0


def test_preferences_that_dont_fit_the_match_are_refused(client):
    assert client.get("/api/stream?seed=21&player=nobody").status_code == 422
    assert client.get("/api/stream?seed=21&focus=player").status_code == 422


def test_full_time_brings_the_recap(client):
    events = _events(client, "seed=21&speed=0&stress=0.25")
    kinds = [k for k, _ in events]
    assert kinds[-2:] == ["recap", "end"], "the recap arrives before the stream closes"
    recap = events[-2][1]
    assert recap["html"].startswith("<!doctype html>") and recap["refused"] == 0
    assert "Checked by the Critic" in recap["html"]


def test_after_full_time_the_match_answers_questions_checked_by_the_critic(client):
    events = _events(client, "seed=21&speed=0&stress=0")
    session = events[0][1]["session"]
    assert client.app.state.sessions == {}, "the stream left, its questions stay"
    reply = client.post(f"/api/sessions/{session}/ask", json={"question": "What's the score?"})
    assert reply.status_code == 200
    answer = reply.json()
    assert answer["status"] == "verified" and answer["text"].startswith("Saltmarsh Rovers 2")
    assert answer["receipt"]["writer"] == "template" and answer["evidence"]
    assert answer["left"] == client.get("/api/config").json()["questions"] - 1
    cannot = client.post(f"/api/sessions/{session}/ask", json={"question": "Who will win?"})
    assert cannot.json()["status"] == "cannot"


def test_questions_are_capped_and_checked_for_size(client, monkeypatch):
    monkeypatch.setattr("court.server.MAX_QUESTIONS", 1)
    session = _events(client, "seed=7&speed=0&stress=0")[0][1]["session"]
    ask = f"/api/sessions/{session}/ask"
    assert client.post(ask, json={"question": "x" * 201}).status_code == 422
    assert client.post(ask, json={"question": "Shots?"}).status_code == 200
    assert client.post(ask, json={"question": "Shots?"}).status_code == 429
    assert client.post("/api/sessions/nope/ask", json={"question": "Shots?"}).status_code == 404


def test_the_ask_page_is_served_and_suggests_from_the_match(client):
    page = client.get("/ask")
    assert page.status_code == 200 and "/static/ask.js" in page.text
    events = _events(client, "seed=21&speed=0&start=89")
    session = events[0][1]["session"]
    questions = client.get(f"/api/sessions/{session}/suggest").json()["questions"]
    assert questions[0] == "Who scored?" and "Who has completed the most passes?" in questions
    assert client.get("/api/sessions/nothing/suggest").status_code == 404


def test_a_follow_up_in_the_studio_reads_the_question_before_it(client):
    session = _events(client, "seed=21&speed=0&start=89")[0][1]["session"]
    first = client.post(
        f"/api/sessions/{session}/ask",
        json={"question": "How many fouls has Brackenfield committed?"},
    ).json()
    follow = client.post(
        f"/api/sessions/{session}/ask", json={"question": "And Saltmarsh Rovers?"}
    ).json()
    assert first["status"] == follow["status"] == "verified"
    assert follow["text"].startswith("Saltmarsh Rovers") and "foul" in follow["text"]
