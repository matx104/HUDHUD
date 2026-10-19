"""The commentary, spoken: only lines that aired, by their cue's id, in their own language."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from test_server import _events

from court.server import create_app
from court.speech import SpeechBudgetSpent, SpeechUnavailable, Voice, ssml


class Credential:
    async def get_token(self, scope):
        return SimpleNamespace(token="t0ken")


def test_the_line_is_text_to_its_languages_voice_never_markup():
    assert "ur-PK-AsadNeural" in ssml("گول", "ur") and "ar-AE-HamdanNeural" in ssml("هدف", "ar")
    spoken = ssml("<break time='9s'/> & more", "en")
    assert "en-GB-RyanNeural" in spoken and "&lt;break" in spoken and "&amp;" in spoken


def test_the_voice_signs_in_with_entra_id_and_keeps_to_its_budget():
    sent = []

    async def post(url, headers, body):
        sent.append((url, headers, body))
        return 200, b"ID3audio"

    voice = Voice(
        resource_id="/subscriptions/s/rg/r", region="uaenorth", credential=Credential(),
        post=post, daily_chars=20,
    )  # fmt: skip
    assert asyncio.run(voice.speak("A goal!", "en")) == b"ID3audio"
    url, headers, body = sent[0]
    assert url == "https://uaenorth.tts.speech.microsoft.com/cognitiveservices/v1"
    assert headers["Authorization"] == "Bearer aad#/subscriptions/s/rg/r#t0ken"
    assert b"A goal!" in body
    with pytest.raises(SpeechBudgetSpent):
        asyncio.run(voice.speak("A much longer line than the budget allows.", "en"))


def test_a_voice_that_doesnt_answer_with_audio_says_so():
    async def post(url, headers, body):
        return 401, b""

    voice = Voice(resource_id="r", region="uaenorth", credential=Credential(), post=post)
    with pytest.raises(SpeechUnavailable, match="401"):
        asyncio.run(voice.speak("A goal!", "en"))


class FakeVoice:
    def __init__(self):
        self.spoken = []

    async def speak(self, text, lang):
        self.spoken.append((text, lang))
        return b"ID3" + text.encode()


@pytest.fixture
def client(monkeypatch):
    for name in ("FOUNDRY_PROJECT_ENDPOINT", "COSMOS_ENDPOINT", "SPEECH_RESOURCE_ID"):
        monkeypatch.delenv(name, raising=False)
    app = create_app()
    return TestClient(app), app


def test_only_a_line_that_aired_can_be_spoken(client):
    test, app = client
    assert test.get("/api/config").json()["voice"] is False
    assert test.get("/api/sessions/x/speak?cue=q-a0001.1").status_code == 404
    app.state.voice = FakeVoice()
    events = _events(test, "seed=21&speed=0&stress=0")
    session = events[0][1]["session"]
    cue = next(d for k, d in events if k == "output" and d["type"] == "cue")
    spoken = test.get(f"/api/sessions/{session}/speak?cue={cue['id']}")
    assert spoken.status_code == 200 and spoken.headers["content-type"] == "audio/mpeg"
    assert app.state.voice.spoken == [(cue["text"], cue["lang"])], "the line as it aired"
    assert test.get(f"/api/sessions/{session}/speak?cue=q-made-up").status_code == 404
    assert test.get(f"/api/sessions/other/speak?cue={cue['id']}").status_code == 404
