"""The commentary, spoken: only lines that aired, by their cue's id, in their own language."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from test_server import _events

from court.server import create_app
from court.speech import NothingHeard, SpeechBudgetSpent, SpeechUnavailable, Voice, ssml


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


def _wav(seconds: float, rate: int = 16_000, channels: int = 1) -> bytes:
    import struct

    data = b"\x00\x00" * int(rate * seconds) * channels
    header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt "
    header += struct.pack("<IHHIIHH", 16, 1, channels, rate, rate * 2 * channels, 2 * channels, 16)
    return header + b"data" + struct.pack("<I", len(data)) + data


def test_a_question_said_aloud_comes_back_as_words_in_the_matchs_language():
    sent = []

    async def post(url, headers, body):
        sent.append((url, headers, body))
        return 200, b'{"RecognitionStatus": "Success", "DisplayText": "Who scored?"}'

    voice = Voice(resource_id="r", region="uaenorth", credential=Credential(), post=post)
    assert asyncio.run(voice.listen(_wav(2), "ur")) == "Who scored?"
    url, headers, _ = sent[0]
    assert url.startswith("https://uaenorth.stt.speech.microsoft.com/") and "language=ur-IN" in url
    assert headers["Authorization"] == "Bearer aad#r#t0ken"
    assert headers["Content-Type"].startswith("audio/wav")
    assert voice.listened_s == 2


def test_listening_takes_only_short_16khz_recordings_and_keeps_to_its_budget(monkeypatch):
    async def post(url, headers, body):
        return 200, b'{"RecognitionStatus": "NoMatch"}'

    voice = Voice(resource_id="r", region="uaenorth", credential=Credential(), post=post)
    with pytest.raises(NothingHeard, match="no words"):
        asyncio.run(voice.listen(_wav(1), "en"))
    with pytest.raises(NothingHeard, match="16 kHz"):
        asyncio.run(voice.listen(_wav(1, rate=44_100), "en"))
    with pytest.raises(NothingHeard, match="at most"):
        asyncio.run(voice.listen(_wav(20), "en"))
    with pytest.raises(NothingHeard, match="WAV"):
        asyncio.run(voice.listen(b"OggS" + b"\x00" * 60, "en"))
    monkeypatch.setattr("court.speech.DAILY_LISTEN_S", 2)
    with pytest.raises(SpeechBudgetSpent):
        asyncio.run(voice.listen(_wav(3), "en"))


class FakeEar(FakeVoice):
    async def listen(self, wav, lang):
        if len(wav) < 100:
            raise NothingHeard("no words could be made out")
        return "What's the score?"


def test_the_studio_hears_a_question_for_a_match_it_knows(client):
    test, app = client
    assert test.post("/api/sessions/x/listen", content=_wav(1)).status_code == 404
    app.state.voice = FakeEar()
    session = _events(test, "seed=21&speed=0&stress=0")[0][1]["session"]
    heard = test.post(f"/api/sessions/{session}/listen", content=_wav(1))
    assert heard.status_code == 200 and heard.json() == {"text": "What's the score?", "lang": "en"}
    assert test.post(f"/api/sessions/{session}/listen", content=b"RIFF").status_code == 422
    assert test.post(f"/api/sessions/{session}/listen", content=_wav(16)).status_code == 413
    assert test.post("/api/sessions/nope/listen", content=_wav(1)).status_code == 404
